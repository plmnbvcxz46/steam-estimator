"""采集 Steam 评测计数（截止日前的汇总数），写入 raw_review_counts。

训练集的“评测数 >= 500”门槛、好评率、Steam 内购买占比、各语言占比都从这里来。
只要汇总数，不要评测正文，一次请求就能拿到，不用翻页。

整体流程：
    main -> crawl_review_counts
              |- pending_jobs   列出还没做的任务
              |- fetch_job      做一个任务：发一次请求（线程池里的线程做，可以几路同时）
              |    -> fetch_summary -> build_input_json -> get_json -> parse_review_summary
              |- save_result    把一个任务的结果写进数据库（只由主线程做）
"""

import argparse
import json
import logging
import sqlite3
from concurrent.futures import ThreadPoolExecutor
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
# 相邻两次请求的发出时刻至少隔几秒，所有线程合在一起算：0.1 就是每秒最多 10 次。
# 单线程时碰不到这个上限：一次请求本身要 0.7 到 0.9 秒，约每秒 1 次。
# 实测 8 路并行约每秒 12 次没有被限速，记录见 docs/devlog.md
MIN_INTERVAL = 0.1
PROGRESS_EVERY = 300  # 每完成多少次请求打一行进度
DEFAULT_CUTOFF = "2018-07-01"  # 原型阶段的截止日（Ars 玩家数表的日期）

# query 是请求口径，表示这次请求是怎么筛评测的。每次请求写一行，同时存评测总数和其中的好评数。
# 它是我们自己起的标签，只存进表和日志，不发给 Steam；用英文，方便写 SQL 和以后转成列名。
QUERY_ALL = "all"  # 截止日前所有语言的评测
QUERY_STEAM_PURCHASE = (
    "steam_purchase"  # 只算在 Steam 里买的游戏的评测（purchase_type=0）
)
QUERY_LANGUAGE_PREFIX = (
    "lang:"  # 各语言的标签 = 前缀 + Steam 语言代码，如 "lang:schinese"
)
# 后面再加： "post_policy"（政策日之后的评测），等近年真值表导入后再做

# Steam 的语言代码。接口返回的是所列语言加在一起的数，所以每种语言要单独发一次请求。
# spanish（西班牙西语）和 latam（拉美西语）在这里各存各的，合并留给 pipeline。
LANGUAGES = (
    "english",
    "schinese",
    "tchinese",
    "russian",
    "german",
    "french",
    "polish",
    "japanese",
    "koreana",
    "turkish",
    "brazilian",
    "spanish",
    "latam",
)

# 每个游戏发的请求清单，一项是一次请求的“配方”，字段按名字取，不靠位置。每次请求写一行。
REQUESTS = [
    {"query": QUERY_ALL, "purchase_type": 1, "languages": ("all",)},
    {"query": QUERY_STEAM_PURCHASE, "purchase_type": 0, "languages": ("all",)},
]
for language in LANGUAGES:
    REQUESTS.append(
        {
            "query": QUERY_LANGUAGE_PREFIX + language,
            "purchase_type": 1,
            "languages": (language,),
        }
    )

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


def build_input_json(appid, cutoff_date, purchase_type=1, languages=("all",)):
    """组装接口的 input_json 参数（返回 dict，调用处再 json.dumps）。

    关键参数：
        appid                       游戏编号
        num_per_page: 0             只要汇总数，不要评测正文
        languages                   Steam 语言代码的列表；["all"] 是所有语言，不传只统计英文评测
        purchase_type               0=只算在 Steam 买的，1=全部，2=非 Steam 购买
        filter: 1                   按时间排序；默认“最有帮助”会自动放宽日期范围
        filter_offtopic_activity: False   不过滤“刷差评”期间的评测
        date_range_start: 1         不能传 0，0 会被当成“没传”
        date_range_end              用 cutoff_ts(cutoff_date)
    """
    return {
        "appid": appid,
        "num_per_page": 0,
        "languages": list(languages),  # JSON 里的数组对应列表，元组要先转一下
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


def fetch_summary(appid, cutoff_date, purchase_type=1, languages=("all",)):
    """请求一次，返回 (评测总数, 好评数)。请求最终失败时 get_json 会抛 CrawlError，这里不拦。"""
    params: dict = build_input_json(
        appid=appid,
        cutoff_date=cutoff_date,
        purchase_type=purchase_type,
        languages=languages,
    )
    res = get_json(
        url=URL, params={"input_json": json.dumps(params)}, min_interval=MIN_INTERVAL
    )
    summary = parse_review_summary(res)
    return summary


def make_request_key(appid, cutoff_date, query):
    """raw_crawl_log 的 request_key。一个游戏要发好几次请求，key 要带上截止日和口径。"""
    return f"{appid}|{cutoff_date}|{query}"


def pending_jobs(conn, appids, cutoff_date):
    """列出还没做的任务，返回一个列表。每一项是一个任务，也就是一次请求要用的全部参数：
        {"appid": 220, "cutoff_date": "2018-07-01",
         "query": "lang:schinese", "purchase_type": 1, "languages": ("schinese",)}
    一个游戏有 15 种口径，所以会列出 15 个任务。

    已有定论的请求不列进来，所以中断后重跑会从断点继续。
    """
    done = crawl_log.done_keys(conn, SOURCE)
    jobs = []
    for appid in appids:
        for request in REQUESTS:
            key = make_request_key(appid, cutoff_date, request["query"])
            if key not in done:
                jobs.append(
                    {
                        "appid": appid,
                        "cutoff_date": cutoff_date,
                        "query": request["query"],
                        "purchase_type": request["purchase_type"],
                        "languages": request["languages"],
                    }
                )
    return jobs


def fetch_job(job):
    """做一个任务：发一次请求，返回结果（dict）。失败不抛异常，原因写在 status 里。

    结果里带着任务自己的身份（appid、cutoff_date、query），拿到结果就知道它是谁的。
    status 是 200、get_json 给的失败原因（如 "timeout"、429），或 "parse_error"；
    只有 200 时才有 total 和 positive。

    这个函数会在线程池的线程里运行，所以只联网、不碰数据库：
    sqlite3 的连接只能在创建它的线程里用，写库统一留给主线程。
    """
    appid = job["appid"]
    cutoff_date = job["cutoff_date"]
    query = job["query"]
    result = {"appid": appid, "cutoff_date": cutoff_date, "query": query}

    try:
        total, positive = fetch_summary(
            appid, cutoff_date, job["purchase_type"], job["languages"]
        )
    except CrawlError as err:
        logger.warning("appid=%d 口径=%s 请求失败: %s", appid, query, err)
        result["status"] = err.status
        return result
    except (KeyError, TypeError) as err:
        # 接口返回缺字段或结构变了：记下原因，跳过这一次，不让整批崩掉
        logger.warning(
            "appid=%d 口径=%s 解析失败，缺少或错误的字段: %r", appid, query, err
        )
        result["status"] = "parse_error"
        return result

    result["status"] = 200
    result["total"] = total
    result["positive"] = positive
    return result


def save_result(conn, result):
    """把一个任务的结果写进数据库：成功就写数据行，不管成败都在 raw_crawl_log 记结局。"""
    key = make_request_key(result["appid"], result["cutoff_date"], result["query"])
    # 一个请求一个事务：数据行和日志要么都写入，要么都不写
    with conn:
        if result["status"] == 200:
            row = {
                "appid": result["appid"],
                "cutoff_date": result["cutoff_date"],
                "query": result["query"],
                "total": result["total"],
                "positive": result["positive"],
                "fetched_at": now_utc_str(),
            }
            conn.execute(INSERT_SQL, row)
        crawl_log.record(conn, SOURCE, key, result["status"])


def crawl_review_counts(conn, appids, cutoff_date=DEFAULT_CUTOFF, workers=1):
    """采集 appids 在 cutoff_date 的评测计数，写入 raw_review_counts，并在 raw_crawl_log 记结局。

    workers 是同时发请求的线程数；1 就是一个一个来。
    这里只负责调度：列任务、交给线程池、把结果一个个存下来。
    """
    crawl_log.ensure_table(conn)
    conn.execute(CREATE_TABLE_SQL)

    jobs = pending_jobs(conn, appids, cutoff_date)
    logger.info(
        "共 %d 个游戏，截止日 %s，待发请求 %d 次，%d 路并行",
        len(appids),
        cutoff_date,
        len(jobs),
        workers,
    )

    # 线程池：里面有 workers 个线程，各自从 jobs 里领任务去做 fetch_job。
    # 等网络回信的时间占了一次请求的绝大部分，几个线程同时等，总时间就省下来了
    pool = ThreadPoolExecutor(max_workers=workers)
    try:
        # pool.map(fetch_job, jobs) 的意思是“对 jobs 里的每一项调用 fetch_job”，
        # 只不过是由池里的线程去调。结果按 jobs 的顺序一个个交回来，
        # 哪个还没做完，主线程就在这一行等它
        done_count = 0
        for result in pool.map(fetch_job, jobs):
            save_result(conn, result)
            done_count += 1
            if done_count % PROGRESS_EVERY == 0:
                logger.info("进度 %d/%d 次请求", done_count, len(jobs))
    finally:
        # 正常结束或按 Ctrl+C 都会走到这里。cancel_futures=True 把还没开始的任务全部取消，
        # 否则线程池会坚持把剩下的十几万次请求发完才肯退出
        pool.shutdown(wait=True, cancel_futures=True)


def main():
    """命令行入口：python -m crawler.sources.review_counts [数量] [--cutoff 日期] [--workers 路数]"""
    parser = argparse.ArgumentParser(description="采集 Steam 评测计数")
    parser.add_argument(
        "limit",
        type=int,
        nargs="?",
        default=None,
        help="从 Ars 表里取多少个 appid 来爬；不写则爬全部",
    )
    parser.add_argument(
        "--cutoff", default=DEFAULT_CUTOFF, help="截止日，格式 YYYY-MM-DD"
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="同时发请求的线程数，默认 1；速度上限由 MIN_INTERVAL 决定，超过 10 没有意义",
    )
    args = parser.parse_args()

    setup_logging("review_counts.log")

    # 取哪些 appid：沿用 appdetails.pick_appids（从 Ars 表按固定种子打乱取前 N）；
    # 以后“评测数 >= 500”的筛选属于 pipeline，不在这里做。
    conn = sqlite3.connect(DB_PATH)
    try:
        crawl_review_counts(
            conn, pick_appids(conn, args.limit), args.cutoff, args.workers
        )
    finally:
        conn.close()


if __name__ == "__main__":
    main()
