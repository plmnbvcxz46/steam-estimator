"""所有采集模块共用的请求函数：限速、超时、重试与退避。"""

import logging
import threading
import time
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter

logger = logging.getLogger(__name__)

TIMEOUT = 15  # 单次请求最多等多少秒
MAX_RETRIES = 4  # 第一次失败后最多再试几次
BACKOFF_BASE = 2  # 退避：第 n 次重试前等 2**n 秒（2、4、8、16）
POOL_SIZE = 32  # 会话最多留着多少条连接复用；要不小于并行的线程数

_next_slot = {}  # 主机名 -> 最近一次领出去的“发出时刻”
# 多个线程会同时来领发出时刻。锁保证一次只有一个线程在领，
# 否则两个线程可能读到同一个旧时刻，领到同一个号，间隔就不准了
_slot_lock = threading.Lock()

# 整个程序共用一个会话：它会把到同一个网站的连接留着复用，省掉每次请求前的握手。
# 实测评测接口：每次新建连接约 3.4 秒一次，复用后约 1 秒一次。
_session = requests.Session()
# 会话默认只留 10 条连接。线程数超过 10 时，多出来的连接用完就被丢掉，
# 下次又得重新握手（本机一次握手要 3 秒左右），并行就白开了。所以把上限调大
_session.mount("https://", HTTPAdapter(pool_maxsize=POOL_SIZE))


class CrawlError(Exception):
    """请求最终失败。status 是 HTTP 状态码，或 'timeout' / 'network' / 'bad_json'，
    调用者把它记进 raw_crawl_log。"""

    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


def _wait_for_turn(url, min_interval):
    """同一个网站相邻两次请求的发出时刻至少隔 min_interval 秒。按网站分别计算。

    做法像排队领号：每次请求先领一个发出时刻，比上一个号晚 min_interval；
    领完号再等到那个时刻。几个线程同时来，也是一个接一个往后排，
    所以 min_interval 管的是所有线程加起来的速度（0.1 就是每秒最多 10 次）。
    """
    host = urlparse(url).netloc
    with _slot_lock:
        now = time.monotonic()
        last_slot = _next_slot.get(host)
        if last_slot is None:
            my_slot = now  # 这个网站的第一次请求，不用等
        else:
            # 上一个号已经过去很久就立刻发，否则排在它后面
            my_slot = max(now, last_slot + min_interval)
        _next_slot[host] = my_slot

    # 等待放在锁外面：自己睡觉时，别的线程还能继续领号
    wait = my_slot - now
    if wait > 0:
        time.sleep(wait)


def get_json(url, params=None, min_interval=1.5):
    """GET 一个返回 JSON 的接口，成功返回解析后的数据，最终失败抛 CrawlError。"""
    return _request_json("GET", url, params, None, min_interval)


def post_json(url, body, params=None, min_interval=1.5):
    """POST 一个返回 JSON 的接口，body 会编码成 JSON 放进请求体。
    限速、重试和 get_json 完全一样。"""
    return _request_json("POST", url, params, body, min_interval)


def _request_json(method, url, params, body, min_interval):
    """GET 和 POST 共用的部分：排队限速、发请求、判断要不要重试。"""
    for attempt in range(MAX_RETRIES + 1):
        _wait_for_turn(url, min_interval)

        try:
            # body 为 None 时 requests 不发请求体，所以 GET 也能走这一行
            resp = _session.request(method, url, params=params, json=body, timeout=TIMEOUT)
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
