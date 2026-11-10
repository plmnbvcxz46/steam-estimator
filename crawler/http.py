"""所有采集模块共用的请求函数：限速、超时、重试与退避。"""

import logging
import time
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)

TIMEOUT = 15  # 单次请求最多等多少秒
MAX_RETRIES = 4  # 第一次失败后最多再试几次
BACKOFF_BASE = 2  # 退避：第 n 次重试前等 2**n 秒（2、4、8、16）

_last_request_time = {}  # 主机名 -> 上次请求的时刻

# 整个程序共用一个会话：它会把到同一个网站的连接留着复用，省掉每次请求前的握手。
# 实测评测接口：每次新建连接约 3.4 秒一次，复用后约 1 秒一次。
_session = requests.Session()


class CrawlError(Exception):
    """请求最终失败。status 是 HTTP 状态码，或 'timeout' / 'network' / 'bad_json'，
    调用者把它记进 raw_crawl_log。"""

    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


def _wait_for_turn(url, min_interval):
    """同一个网站的两次请求之间至少隔 min_interval 秒。按照网站划分，不强睡:)"""
    host = urlparse(url).netloc
    last = _last_request_time.get(host)
    if last is not None:
        wait = min_interval - (time.monotonic() - last)
        if wait > 0:
            time.sleep(wait)
    _last_request_time[host] = time.monotonic()


def get_json(url, params=None, min_interval=1.5):
    """GET 一个返回 JSON 的接口，成功返回解析后的数据，最终失败抛 CrawlError。"""
    for attempt in range(MAX_RETRIES + 1):
        _wait_for_turn(url, min_interval)

        try:
            resp = _session.get(url, params=params, timeout=TIMEOUT)
        except requests.Timeout:
            status = "timeout"
        except requests.ConnectionError:
            status = "network"
        else:
            if resp.status_code == 200:
                try:
                    return resp.json()
                except ValueError:
                    status = "bad_json"
            elif resp.status_code == 429 or resp.status_code >= 500:
                status = resp.status_code
            else:
                # 404 等 4xx：请求本身有问题，重试没用
                raise CrawlError(
                    resp.status_code, f"请求被拒绝 {resp.status_code}: {url}"
                )

        # 走到这里说明这次失败了，而且值得重试
        if attempt == MAX_RETRIES:
            raise CrawlError(status, f"重试 {MAX_RETRIES} 次仍失败 ({status}): {url}")
        delay = BACKOFF_BASE ** (attempt + 1)
        logger.warning("请求失败 (%s)，%d 秒后重试: %s", status, delay, url)
        time.sleep(delay)
