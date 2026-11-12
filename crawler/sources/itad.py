"""采集 IsThereAnyDeal（ITAD）的历史价格。

商店接口只能拿到今天的价格，ITAD 记录了每次调价的时刻和价格，用来还原截止日当时的价格。
ITAD 不认 Steam 的 appid，所以分两步：先把 appid 换成 ITAD 的游戏编号（raw_itad_ids），
再按编号逐款查价格历史（raw_price_history）。

接口要 API 密钥，放在项目根目录的 .env 里（ITAD_API_KEY=...），.env 不进仓库。
"""

import logging

from dotenv import dotenv_values

from common.clock import now_utc_str
from common.paths import PROJECT_ROOT
from crawler import crawl_log
from crawler.http import CrawlError, post_json

logger = logging.getLogger(__name__)

ENV_PATH = PROJECT_ROOT / ".env"

API_BASE = "https://api.isthereanydeal.com"
STEAM_SHOP_ID = 61  # ITAD 给每个商店编了号，Steam 是 61
LOOKUP_URL = f"{API_BASE}/lookup/id/shop/{STEAM_SHOP_ID}/v1"

SOURCE_IDS = "itad_ids"
LOOKUP_BATCH_SIZE = 200  # 一次换多少款。旧探索版本用的就是 200
# 限额是 5 分钟 1000 次，平均 0.3 秒一次；留点余量取 0.4
MIN_INTERVAL = 0.4

CREATE_IDS_SQL = """
CREATE TABLE IF NOT EXISTS raw_itad_ids (
    appid      INTEGER PRIMARY KEY,
    itad_id    TEXT,
    fetched_at TEXT NOT NULL
)
"""


def load_api_key():
    """从 .env 读 ITAD 密钥。没填就直接报错，并说清楚怎么填。"""
    # dotenv_values 只把文件读成字典，不改系统环境变量，密钥从哪来一目了然
    key = dotenv_values(ENV_PATH).get("ITAD_API_KEY")
    if not key:
        raise RuntimeError(f"缺少 ITAD_API_KEY：照 .env.example 在 {ENV_PATH} 里写一行 ITAD_API_KEY=你的密钥")
    return key


def ensure_tables(conn):
    crawl_log.ensure_table(conn)
    conn.execute(CREATE_IDS_SQL)


def shop_key(appid):
    """ITAD 里 Steam 游戏的写法是 "app/730"；"sub/..." 是礼包，我们用不到。"""
    return f"app/{appid}"


def save_ids(conn, appids, response):
    """把一批换编号的结果写进 raw_itad_ids，返回（收录的款数，未收录的款数）。

    response 形如 {"app/730": "编号", "app/12345": None}，None 表示 ITAD 没收录这款。
    未收录的也写一行、编号留空，这样“查过但没有”和“还没查”分得开。
    整批放在一个事务里：数据行和日志要么都写入，要么都不写。
    """
    expected = {shop_key(appid) for appid in appids}
    if set(response) != expected:
        # 返回的游戏和请求的对不上，说明接口的行为和我们以为的不一样，这一批不能用
        raise ValueError("返回的游戏和请求的游戏对不上")

    fetched_at = now_utc_str()
    found_count = 0
    not_found_count = 0
    with conn:
        for appid in appids:
            itad_id = response[shop_key(appid)]
            conn.execute(
                "INSERT OR REPLACE INTO raw_itad_ids (appid, itad_id, fetched_at) VALUES (?, ?, ?)",
                (appid, itad_id, fetched_at),
            )
            if itad_id is None:
                crawl_log.record(conn, SOURCE_IDS, appid, "未收录")
                not_found_count += 1
            else:
                crawl_log.record(conn, SOURCE_IDS, appid, 200)
                found_count += 1
    return found_count, not_found_count


def crawl_itad_ids(conn, appids, api_key):
    """分批把 appids 换成 ITAD 编号，写入 raw_itad_ids。

    已有定论的 appid 会跳过，所以中断后重跑同一条命令即可从断点继续。
    """
    ensure_tables(conn)

    done = crawl_log.done_keys(conn, SOURCE_IDS)
    todo = [appid for appid in appids if str(appid) not in done]
    logger.info("换编号：共 %d 个，已完成 %d 个，本次要换 %d 个", len(appids), len(appids) - len(todo), len(todo))

    for start in range(0, len(todo), LOOKUP_BATCH_SIZE):
        batch = todo[start : start + LOOKUP_BATCH_SIZE]
        body = [shop_key(appid) for appid in batch]
        try:
            # 密钥放在网址参数里，这是 ITAD 规定的传法；出错信息只写网址本身，不会把密钥写进日志
            response = post_json(LOOKUP_URL, body, params={"key": api_key}, min_interval=MIN_INTERVAL)
            found_count, not_found_count = save_ids(conn, batch, response)
        except CrawlError as err:
            logger.warning("换编号第 %d 到 %d 个请求失败: %s", start + 1, start + len(batch), err)
            with conn:
                for appid in batch:
                    crawl_log.record(conn, SOURCE_IDS, appid, err.status)
            continue
        except (TypeError, ValueError) as err:
            # 返回的不是预期的字典，或游戏对不上：记下原因，跳过这一批
            logger.warning("换编号第 %d 到 %d 个解析失败: %r", start + 1, start + len(batch), err)
            with conn:
                for appid in batch:
                    crawl_log.record(conn, SOURCE_IDS, appid, "parse_error")
            continue

        logger.info(
            "换编号进度 %d/%d：这一批收录 %d 款，未收录 %d 款",
            start + len(batch), len(todo), found_count, not_found_count,
        )
