"""采集 Steam 评测计数（截止日前的汇总数），写入 raw_review_counts。

训练集的“评测数 >= 500”门槛、好评率、Steam 内购买占比、各语言占比都从这里来。
只要汇总数，不要评测正文，一次请求就能拿到，不用翻页。

整体流程（照 appdetails.py 的样子）：
    main -> crawl_review_counts -> fetch_summary -> build_input_json -> get_json -> parse_review_summary
"""

import argparse
import json
import logging
import sqlite3
from datetime import UTC, datetime

from common.clock import now_utc_str
from common.log import setup_logging
from common.paths import DB_PATH
from crawler import crawl_log
from crawler.http import CrawlError, get_json
from crawler.sources.appdetails import pick_appids

logger = logging.getLogger(__name__)

SOURCE = "review_counts"  # 写进 raw_crawl_log 的数据源名
URL = "https://api.steampowered.com/IUserReviewsService/GetAppReviews/v1/"
MIN_INTERVAL = 1.5  # 暂定值，小批量实测后再定
DEFAULT_CUTOFF = "2018-07-01"  # 原型阶段的截止日（Ars 玩家数表的日期）

# query 是请求口径，表示这次请求是怎么筛评测的。每次请求写一行，同时存评测总数和其中的好评数。
# 先做前两种，政策后和各语言放后面。
QUERY_ALL = "全部"  # 截止日前所有语言的评测
QUERY_STEAM_PURCHASE = "Steam内购买"  # 只算在 Steam 里买的游戏的评测（purchase_type=0）
# 第二步再加： "政策后"（date_range_start 设为 2019-11 的政策日）、"语言:<名字>"（languages=[名字]）

# 每个游戏发的请求：(口径, purchase_type)。每次请求写一行
REQUESTS = ((QUERY_ALL, 1), (QUERY_STEAM_PURCHASE, 0))

# 主键 (appid, cutoff_date, query)：同一个游戏、同一个截止日、同一种口径只有一行
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS raw_review_counts (
    appid       INTEGER NOT NULL,
    cutoff_date TEXT NOT NULL,
    query       TEXT NOT NULL,
    total       INTEGER NOT NULL,
    positive    INTEGER NOT NULL,
    fetched_at  TEXT NOT NULL,
    PRIMARY KEY (appid, cutoff_date, query)
)
"""

INSERT_SQL = """
INSERT OR REPLACE INTO raw_review_counts (appid, cutoff_date, query, total, positive, fetched_at)
VALUES (:appid, :cutoff_date, :query, :total, :positive, :fetched_at)
"""


def cutoff_ts(cutoff_date):
    """'2018-07-01' -> 当天零点（UTC）的 Unix 时间戳（整数）。

    文档规定“一切输入只取截止日之前的数据”，所以截止日当天的评测不算，
    取当天零点作为 date_range_end。2018-07-01 对应 1530403200，和早期探索版本一致。
    """
    day = datetime.strptime(cutoff_date, "%Y-%m-%d").replace(tzinfo=UTC)
    return int(day.timestamp())


def build_input_json(appid, cutoff_date, purchase_type=1):
    """组装接口的 input_json 参数（返回 dict，调用处再 json.dumps）。

    关键参数（旧版踩过的坑）：
        appid                       游戏编号
        num_per_page: 0             只要汇总数，不要评测正文（实测接口仍会附带 20 条，不影响汇总）
        languages: ["all"]          不传只统计英文评测
        purchase_type               0=只算在 Steam 买的，1=全部，2=非 Steam 购买
        filter: 1                   按时间排序；默认“最有帮助”会自动放宽日期范围
        filter_offtopic_activity: False   不过滤“刷差评”期间的评测
        date_range_start: 1         不能传 0，0 会被当成“没传”
        date_range_end              用 cutoff_ts(cutoff_date)
    """
    return {
        "appid": appid,
        "num_per_page": 0,
        "languages": ["all"],
        "purchase_type": purchase_type,
        "filter": 1,
        "filter_offtopic_activity": False,
        "date_range_start": 1,
        "date_range_end": cutoff_ts(cutoff_date),
    }


def parse_review_summary(response):
    """从接口返回里取出 (评测总数, 好评数)。

    返回里的位置： response["response"]["query_summary"]["total_reviews"] 和 ["total_positive"]
    接口没给汇总时，让它直接报错（KeyError），由主循环记 parse_error 并跳过。
    """
    summary = response["response"]["query_summary"]
    return summary["total_reviews"], summary["total_positive"]


def fetch_summary(appid, cutoff_date, purchase_type=1):
    """请求一次，返回 (评测总数, 好评数)。请求最终失败时 get_json 会抛 CrawlError，这里不拦。"""
    params: dict = build_input_json(
        appid=appid, cutoff_date=cutoff_date, purchase_type=purchase_type
    )
    res = get_json(
        url=URL, params={"input_json": json.dumps(params)}, min_interval=MIN_INTERVAL
    )
    summary = parse_review_summary(res)
    return summary


def make_request_key(appid, cutoff_date, query):
    """raw_crawl_log 的 request_key。一个游戏要发好几次请求，key 要带上截止日和口径。"""
    return f"{appid}|{cutoff_date}|{query}"


def crawl_review_counts(conn, appids, cutoff_date=DEFAULT_CUTOFF):
    """逐个采集 appids 在 cutoff_date 的评测计数，写入 raw_review_counts，并在 raw_crawl_log 记结局。

    已有定论的请求会跳过，所以中断后重跑同一条命令即可从断点继续。
    """
    crawl_log.ensure_table(conn)
    conn.execute(CREATE_TABLE_SQL)

    done = crawl_log.done_keys(conn, SOURCE)
    logger.info("共 %d 个游戏，截止日 %s", len(appids), cutoff_date)

    for i, appid in enumerate(appids, start=1):
        for query, purchase_type in REQUESTS:
            key = make_request_key(appid, cutoff_date, query)
            if key in done:
                continue

            try:
                total, positive = fetch_summary(appid, cutoff_date, purchase_type)
            except CrawlError as err:
                logger.warning("appid=%d 口径=%s 请求失败: %s", appid, query, err)
                with conn:
                    crawl_log.record(conn, SOURCE, key, err.status)
                continue
            except (KeyError, TypeError) as err:
                # 接口返回缺字段或结构变了：记下原因，跳过这一次，不让整批崩掉
                logger.warning("appid=%d 口径=%s 解析失败，缺少或错误的字段: %r", appid, query, err)
                with conn:
                    crawl_log.record(conn, SOURCE, key, "parse_error")
                continue

            row = {
                "appid": appid,
                "cutoff_date": cutoff_date,
                "query": query,
                "total": total,
                "positive": positive,
                "fetched_at": now_utc_str(),
            }
            # 一个请求一个事务：数据行和日志要么都写入，要么都不写
            with conn:
                conn.execute(INSERT_SQL, row)
                crawl_log.record(conn, SOURCE, key, 200)

        if i % 20 == 0:
            logger.info("进度 %d/%d", i, len(appids))


def main():
    """命令行入口：python -m crawler.sources.review_counts [数量] [--cutoff 日期]"""
    parser = argparse.ArgumentParser(description="采集 Steam 评测计数")
    parser.add_argument(
        "limit", type=int, nargs="?", default=None,
        help="从 Ars 表里取多少个 appid 来爬；不写则爬全部",
    )
    parser.add_argument("--cutoff", default=DEFAULT_CUTOFF, help="截止日，格式 YYYY-MM-DD")
    args = parser.parse_args()

    setup_logging("review_counts.log")

    # 取哪些 appid：沿用 appdetails.pick_appids（从 Ars 表按固定种子打乱取前 N）；
    # 以后“评测数 >= 500”的筛选属于 pipeline，不在这里做。
    conn = sqlite3.connect(DB_PATH)
    try:
        crawl_review_counts(conn, pick_appids(conn, args.limit), args.cutoff)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
