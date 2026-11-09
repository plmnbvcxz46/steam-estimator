"""采集 Steam appdetails（商店信息），写入 raw_appdetails。"""

import argparse
import logging
import random
import sqlite3

from common.clock import now_utc_str
from common.log import setup_logging
from common.paths import DB_PATH
from crawler import crawl_log
from crawler.http import CrawlError, get_json

logger = logging.getLogger(__name__)

SOURCE = "appdetails"
URL = "https://store.steampowered.com/api/appdetails"
MIN_INTERVAL = 1.5  # 两次请求之间至少隔几秒；暂定值，等小批量实测后再定
SHUFFLE_SEED = 42  # 固定随机种子：每次打乱出的顺序一样，扩大 N 时已爬的不浪费

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS raw_appdetails (
    appid             INTEGER PRIMARY KEY,
    name              TEXT NOT NULL,
    app_type          TEXT NOT NULL,
    is_free           INTEGER NOT NULL,
    release_date      TEXT,
    initial_price_usd REAL,
    genres            TEXT NOT NULL,
    fetched_at        TEXT NOT NULL
)
"""

# :appid 这种写法是“具名占位符”，执行时用同名的字典键填进去
INSERT_SQL = """
INSERT OR REPLACE INTO raw_appdetails
    (appid, name, app_type, is_free, release_date, initial_price_usd, genres, fetched_at)
VALUES
    (:appid, :name, :app_type, :is_free, :release_date, :initial_price_usd, :genres, :fetched_at)
"""


def parse_appdetails(appid, response):
    """把接口返回的 JSON 变成 raw_appdetails 的一行（dict）。

    response 是接口返回的整个 JSON，形如 {"413150": {"success": true, "data": {...}}}。
    接口说“没有这款游戏”（success 为 false）时返回 None，由调用者记为“未收录”。
    """
    entry = response[str(appid)]
    if not entry["success"]:
        return None

    data = entry["data"]

    # 免费游戏没有 price_overview；价格单位是美分，除以 100 换成美元
    price = data.get("price_overview")
    initial_price_usd = price["initial"] / 100 if price else None

    # genres 是 [{"id": ..., "description": "RPG"}, ...]，只取名字，用 | 连起来
    genres = "|".join(g["description"] for g in data.get("genres", []))

    return {
        "appid": appid,
        "name": data["name"],
        "app_type": data["type"],
        "is_free": int(data["is_free"]),
        # raw 层原样保存：日期格式五花八门，怎么解析留给 pipeline 清洗时决定
        "release_date": data["release_date"]["date"],
        "initial_price_usd": initial_price_usd,
        "genres": genres,
    }


def crawl_appdetails(conn, appids):
    """逐个采集 appids，写入 raw_appdetails，并在 raw_crawl_log 记录每个的结局。

    已有定论的 appid 会跳过，所以中断后重跑同一条命令即可从断点继续。
    """
    crawl_log.ensure_table(conn)
    conn.execute(CREATE_TABLE_SQL)

    done = crawl_log.done_keys(conn, SOURCE)
    todo = [appid for appid in appids if str(appid) not in done]
    logger.info("共 %d 个，已完成 %d 个，本次要爬 %d 个", len(appids), len(appids) - len(todo), len(todo))

    for i, appid in enumerate(todo, start=1):
        params = {"appids": appid, "cc": "us", "l": "english"}
        try:
            response = get_json(URL, params=params, min_interval=MIN_INTERVAL)
        except CrawlError as err:
            logger.warning("appid=%d 请求失败: %s", appid, err)
            with conn:
                crawl_log.record(conn, SOURCE, appid, err.status)
            continue

        try:
            row = parse_appdetails(appid, response)
        except (KeyError, TypeError) as err:
            # 接口返回缺字段或结构变了：记下原因，跳过这一款，不让整批崩掉
            logger.warning("appid=%d 解析失败，缺少或错误的字段: %r", appid, err)
            with conn:
                crawl_log.record(conn, SOURCE, appid, "parse_error")
            continue

        # 一个 appid 一个事务：数据行和日志要么都写入，要么都不写
        with conn:
            if row is None:
                crawl_log.record(conn, SOURCE, appid, "未收录")
            else:
                row["fetched_at"] = now_utc_str()
                conn.execute(INSERT_SQL, row)
                crawl_log.record(conn, SOURCE, appid, 200)

        if i % 20 == 0:
            logger.info("进度 %d/%d", i, len(todo))


def pick_appids(conn, limit):
    """从 Ars 表里取 limit 个 appid：先排序再用固定种子打乱，取前 limit 个。

    limit 为 None 时取全部（列表切片 [:None] 就是整个列表）。
    """
    rows = conn.execute("SELECT appid FROM raw_ars_players_2018 ORDER BY appid")
    appids = [appid for (appid,) in rows]
    random.Random(SHUFFLE_SEED).shuffle(appids)
    return appids[:limit]


def main():
    """命令行入口：python -m crawler.appdetails [数量]，不写数量就爬全部"""
    parser = argparse.ArgumentParser(description="采集 Steam appdetails")
    # nargs="?" 表示这个参数可以不写；不写时取默认值 None，也就是全部
    parser.add_argument(
        "limit", type=int, nargs="?", default=None,
        help="从 Ars 表里取多少个 appid 来爬；不写则爬全部",
    )
    args = parser.parse_args()

    setup_logging("appdetails.log")

    conn = sqlite3.connect(DB_PATH)
    try:
        crawl_appdetails(conn, pick_appids(conn, args.limit))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
