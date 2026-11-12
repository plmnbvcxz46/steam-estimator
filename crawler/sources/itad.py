"""采集 IsThereAnyDeal（ITAD）的历史价格。

商店接口只能拿到今天的价格，ITAD 记录了每次调价的时刻和价格，用来还原截止日当时的价格。
ITAD 不认 Steam 的 appid，所以分两步：先把 appid 换成 ITAD 的游戏编号（raw_itad_ids），
再按编号逐款查价格历史（raw_price_history）。

接口要 API 密钥，放在项目根目录的 .env 里（ITAD_API_KEY=...），.env 不进仓库。
"""

import argparse
import logging
import sqlite3
from datetime import UTC, datetime

from dotenv import dotenv_values

from common.clock import now_utc_str
from common.log import setup_logging
from common.paths import DB_PATH, PROJECT_ROOT
from crawler import crawl_log
from crawler.appids import pick_appids
from crawler.http import CrawlError, get_json, post_json

logger = logging.getLogger(__name__)

ENV_PATH = PROJECT_ROOT / ".env"

API_BASE = "https://api.isthereanydeal.com"
STEAM_SHOP_ID = 61  # ITAD 给每个商店编了号，Steam 是 61
LOOKUP_URL = f"{API_BASE}/lookup/id/shop/{STEAM_SHOP_ID}/v1"
HISTORY_URL = f"{API_BASE}/games/history/v2"

SOURCE_IDS = "itad_ids"
SOURCE_HISTORY = "itad_history"
COUNTRY = "US"  # 只采美国区，价格是美元
# 接口不给起始时间时只返回最近 3 个月。给一个比 Steam 上线（2003 年）还早的时间，就能拿到全部历史
HISTORY_SINCE = "2000-01-01T00:00:00Z"
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

# 一次价格变动一行，只记变动之后的状态；这个状态一直持续到下一行的 changed_at
CREATE_HISTORY_SQL = """
CREATE TABLE IF NOT EXISTS raw_price_history (
    appid      INTEGER NOT NULL,
    country    TEXT NOT NULL,
    changed_at TEXT NOT NULL,
    currency   TEXT NOT NULL,
    price      REAL NOT NULL,
    regular    REAL NOT NULL,
    cut        INTEGER NOT NULL,
    fetched_at TEXT NOT NULL,
    PRIMARY KEY (appid, country, changed_at)
)
"""

INSERT_HISTORY_SQL = """
INSERT INTO raw_price_history
    (appid, country, changed_at, currency, price, regular, cut, fetched_at)
VALUES
    (:appid, :country, :changed_at, :currency, :price, :regular, :cut, :fetched_at)
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
    conn.execute(CREATE_HISTORY_SQL)


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


def to_utc_str(timestamp):
    """把 ITAD 的时间（如 "2018-06-21T23:04:55+02:00"）换成 UTC，写法和 fetched_at 一样。

    ITAD 给的是带时差的本地时间，冬夏令时的时差还不一样（+01:00 / +02:00），
    不统一换算的话，按时间先后排序和与截止日比较都会出错。
    """
    moment = datetime.fromisoformat(timestamp)
    return moment.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S")


def parse_history(appid, entries):
    """把接口返回的一款游戏的价格历史变成 raw_price_history 的若干行。

    只认 Steam 商店的记录：请求时已经只要 Steam，这里再核对一遍，混进别的商店就报错。
    """
    rows = []
    for entry in entries:
        if entry["shop"]["id"] != STEAM_SHOP_ID:
            raise ValueError(f"appid={appid} 的历史里混进了别的商店 {entry['shop']}")
        deal = entry["deal"]
        rows.append(
            {
                "appid": appid,
                "country": COUNTRY,
                "changed_at": to_utc_str(entry["timestamp"]),
                "currency": deal["price"]["currency"],
                "price": deal["price"]["amount"],  # 实付价
                "regular": deal["regular"]["amount"],  # 当时的标价
                "cut": deal["cut"],  # 折扣百分比
            }
        )
    return rows


def save_history(conn, appid, rows):
    """把一款游戏的价格历史写进 raw_price_history，日志一起记，放在同一个事务里。

    重采同一款时整段历史换成新的：先删旧的再写，免得新旧混在一起。
    用普通 INSERT 而不是 INSERT OR REPLACE：同一时刻要是有两条记录，
    会因主键冲突报错，而不是悄悄只留下一条。
    """
    fetched_at = now_utc_str()
    for row in rows:
        row["fetched_at"] = fetched_at
    with conn:
        conn.execute(
            "DELETE FROM raw_price_history WHERE appid = ? AND country = ?", (appid, COUNTRY)
        )
        conn.executemany(INSERT_HISTORY_SQL, rows)
        # ITAD 收录了这款，但 Steam 美国区一条价格记录都没有，也是一种定论
        crawl_log.record(conn, SOURCE_HISTORY, appid, 200 if rows else "空结果")


def load_itad_ids(conn, appids):
    """查出 appids 里 ITAD 收录了的那些，返回 [(appid, itad_id)]，顺序和 appids 一样。"""
    known = dict(conn.execute("SELECT appid, itad_id FROM raw_itad_ids WHERE itad_id IS NOT NULL"))
    return [(appid, known[appid]) for appid in appids if appid in known]


def crawl_price_history(conn, appids, api_key):
    """逐款查价格历史，写入 raw_price_history。要先跑过换编号。

    没换到编号的游戏（未收录或换编号失败）这里不查；已有定论的跳过，可断点续跑。
    """
    ensure_tables(conn)

    games = load_itad_ids(conn, appids)
    done = crawl_log.done_keys(conn, SOURCE_HISTORY)
    todo = [(appid, itad_id) for appid, itad_id in games if str(appid) not in done]
    logger.info(
        "价格历史：%d 款里有编号的 %d 款，已完成 %d 款，本次要查 %d 款",
        len(appids), len(games), len(games) - len(todo), len(todo),
    )

    for index, (appid, itad_id) in enumerate(todo, start=1):
        params = {
            "key": api_key,
            "id": itad_id,
            "country": COUNTRY,
            "shops": STEAM_SHOP_ID,
            "since": HISTORY_SINCE,
        }
        try:
            entries = get_json(HISTORY_URL, params=params, min_interval=MIN_INTERVAL)
            rows = parse_history(appid, entries)
            save_history(conn, appid, rows)
        except CrawlError as err:
            logger.warning("appid=%d 请求失败: %s", appid, err)
            with conn:
                crawl_log.record(conn, SOURCE_HISTORY, appid, err.status)
            continue
        except (KeyError, TypeError, ValueError, sqlite3.IntegrityError) as err:
            # 缺字段、结构变了、同一时刻两条记录：记下原因，跳过这款，不让整次采集崩掉
            logger.warning("appid=%d 解析失败: %r", appid, err)
            with conn:
                crawl_log.record(conn, SOURCE_HISTORY, appid, "parse_error")
            continue

        if index % 100 == 0 or index == len(todo):
            logger.info("价格历史进度 %d/%d", index, len(todo))


def main():
    """命令行入口：python -m crawler.sources.itad [数量]，不写数量就采全部"""
    parser = argparse.ArgumentParser(description="采集 ITAD 历史价格")
    parser.add_argument(
        "limit", type=int, nargs="?", default=None,
        help="从 Ars 表里取多少个 appid 来采；不写则采全部",
    )
    args = parser.parse_args()

    setup_logging("itad.log")
    api_key = load_api_key()

    conn = sqlite3.connect(DB_PATH)
    try:
        appids = pick_appids(conn, args.limit)
        crawl_itad_ids(conn, appids, api_key)
        crawl_price_history(conn, appids, api_key)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
