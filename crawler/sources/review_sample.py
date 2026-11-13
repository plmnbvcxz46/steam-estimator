"""采集抽样评测（截止日前按时间分 5 段），写入 raw_review_windows 和 raw_review_sample。

要的是评测者“写评测时玩了多久”（playtime_at_review），供信号 A 的特征和信号 B 的人均时长。
接口做不到随机抽，只取截止日前最新的 100 条又只看得到截止日前不久的评测者，
所以把“上架到截止日”平均切成 5 段，每段请求一次，拿回两样东西：
    这一段的评测总数（存 raw_review_windows，建样本表时当权重）
    这一段最新的至多 100 条评测（存 raw_review_sample）
加权中位数在建样本表时算，这里只存原始数。

和评测计数用同一个接口，地址、限速、截止日换算都从 review_counts 拿。

整体流程（和 review_counts 一样）：
    main -> crawl_review_sample
              |- load_release_ts  查每款游戏的上架时刻，用来切段
              |- pending_jobs     列出还没做的任务（一款 5 段，一段一个任务）
              |    -> make_windows
              |- fetch_job        做一个任务：发一次请求（线程池里做）
              |    -> build_input_json -> get_json -> parse_window
              |- save_result      把一个任务的结果写进数据库（只由主线程做）
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
from crawler.appids import pick_appids
from crawler.http import CrawlError, get_json
from crawler.sources import review_counts

logger = logging.getLogger(__name__)

SOURCE = "review_sample"  # 写进 raw_crawl_log 的数据源名
PROGRESS_EVERY = 300  # 每完成多少次请求打一行进度
WINDOW_COUNT = 5  # 分几段：实测 5 段和 20 段的中位数接近，见 devlog 2026-11-13
PER_PAGE = 100  # 每段取几条，接口一页最多 100 条
# Steam 评测系统 2013 年 11 月上线，之前没有评测；切段的起点不早于这一天
REVIEW_SYSTEM_START = "2013-10-01"

# 一段一行：这一段的起止时刻和评测总数
CREATE_WINDOWS_SQL = """
CREATE TABLE IF NOT EXISTS raw_review_windows (
    appid       INTEGER NOT NULL,
    cutoff_date TEXT NOT NULL,
    window      INTEGER NOT NULL,
    start_ts    INTEGER NOT NULL,
    end_ts      INTEGER NOT NULL,
    total       INTEGER NOT NULL,
    fetched_at  TEXT NOT NULL,
    PRIMARY KEY (appid, cutoff_date, window)
)
"""

INSERT_WINDOW_SQL = """
INSERT INTO raw_review_windows VALUES (
    :appid, :cutoff_date, :window, :start_ts, :end_ts, :total, :fetched_at
)
"""

# 一条评测一行；不存正文
CREATE_SAMPLE_SQL = """
CREATE TABLE IF NOT EXISTS raw_review_sample (
    appid                  INTEGER NOT NULL,
    cutoff_date            TEXT NOT NULL,
    review_id              TEXT NOT NULL,
    window                 INTEGER NOT NULL,
    created_at             TEXT NOT NULL,
    playtime_at_review_min INTEGER,
    playtime_forever_min   INTEGER,
    PRIMARY KEY (appid, cutoff_date, review_id)
)
"""

INSERT_SAMPLE_SQL = """
INSERT INTO raw_review_sample VALUES (
    :appid, :cutoff_date, :review_id, :window, :created_at,
    :playtime_at_review_min, :playtime_forever_min
)
"""


def ensure_tables(conn):
    """建采集日志和两张原始表（已有就跳过）。"""
    crawl_log.ensure_table(conn)
    conn.execute(CREATE_WINDOWS_SQL)
    conn.execute(CREATE_SAMPLE_SQL)


def load_release_ts(conn, appids):
    """查每款游戏的上架时刻，返回 {appid: release_ts}；查不到或为 0 的给 None。

    来自 raw_store_items.release_ts（Unix 秒）。读 raw 表不读清洗表：采集只依赖采集的结果。
    """
    rows = conn.execute("SELECT appid, release_ts FROM raw_store_items")
    known = dict(rows)

    release_of = {}
    for appid in appids:
        release_ts = known.get(appid)
        # 商店没给时间是空，有 16 款给的是 0（没填的占位），都当作没有
        if release_ts == 0:
            release_ts = None
        release_of[appid] = release_ts
    return release_of


def make_windows(release_ts, cutoff_date):
    """把“上架到截止日”平均切成 WINDOW_COUNT 段，返回 [(段号, start_ts, end_ts), ...]。

    起点是上架时刻；上架时刻缺失、早于评测系统上线或晚于截止日时，从 REVIEW_SYSTEM_START 算起。
    第一段的 start_ts 改成 1，早于上架时刻的评测（抢先体验、预购）也算进第一段。
    下一段从上一段的 end_ts + 1 开始，同一条评测不会落进两段。
    """
    # 接口的日期范围两端都含（实测：start 和 end 都等于某条评测的时刻时，能查到这一条）。
    # 最后一段的终点和评测计数一样用截止日零点，5 段的总数加起来应等于计数里的“全部”
    end = review_counts.cutoff_ts(cutoff_date)
    # cutoff_ts 就是“日期 -> 当天零点的时间戳”，这里借来换算评测系统上线日
    review_start = review_counts.cutoff_ts(REVIEW_SYSTEM_START)

    if release_ts is not None and review_start <= release_ts < end:
        start = release_ts
    else:
        start = review_start

    # 段与段的分界点：start、四个中间点、end，一共 6 个
    edges = []
    for i in range(WINDOW_COUNT + 1):
        edges.append(start + (end - start) * i // WINDOW_COUNT)

    windows = []
    for i in range(WINDOW_COUNT):
        if i == 0:
            window_start = 1  # 不能传 0，0 会被当成“没传”
        else:
            window_start = edges[i] + 1
        windows.append((i + 1, window_start, edges[i + 1]))
    return windows


def build_input_json(appid, cutoff_date, start_ts, end_ts):
    """组装一段的请求参数：沿用 review_counts 的，只改每页条数和日期范围。"""
    params = review_counts.build_input_json(appid, cutoff_date)
    params["num_per_page"] = PER_PAGE
    params["date_range_start"] = start_ts
    params["date_range_end"] = end_ts
    return params


def parse_window(response):
    """从接口返回里取出 (这一段评测总数, [抽到的评测, ...])；游戏已下架时返回 None。

    每条评测只留 review_id、created_at、两个时长。
    """
    body = response["response"]
    if body == {}:
        return None  # 已下架的游戏返回 {"response": {}}，和评测计数一样
    total = body["query_summary"]["total_reviews"]

    reviews = []
    # 这一段一条评测都没有时，返回里没有 "reviews" 这个键，不是空列表
    for review in body.get("reviews", []):
        author = review["author"]
        reviews.append(
            {
                "review_id": review["recommendationid"],
                "created_at": ts_to_utc_str(review["timestamp_created"]),
                # 有的评测不带写评测时的时长（实测 2016 年的一段里缺 4 到 25 条），存空
                "playtime_at_review_min": author.get("playtime_at_review"),
                "playtime_forever_min": author["playtime_forever"],
            }
        )
    return total, reviews


def ts_to_utc_str(timestamp):
    """Unix 秒 -> "2018-06-30 23:34:19"（UTC），写法和其他表的时刻一样。"""
    return datetime.fromtimestamp(timestamp, UTC).strftime("%Y-%m-%d %H:%M:%S")


def make_request_key(appid, cutoff_date, window):
    """raw_crawl_log 的 request_key：一款游戏 5 段，要带上段号。"""
    return f"{appid}|{cutoff_date}|{window}"


def pending_jobs(conn, appids, cutoff_date, release_of):
    """列出还没做的任务，一段一个：{"appid", "cutoff_date", "window", "start_ts", "end_ts"}。

    已有定论的段不列进来，中断后重跑从断点继续。
    """
    done = crawl_log.done_keys(conn, SOURCE)
    jobs = []
    for appid in appids:
        for window, start_ts, end_ts in make_windows(release_of[appid], cutoff_date):
            if make_request_key(appid, cutoff_date, window) in done:
                continue
            jobs.append(
                {
                    "appid": appid,
                    "cutoff_date": cutoff_date,
                    "window": window,
                    "start_ts": start_ts,
                    "end_ts": end_ts,
                }
            )
    return jobs


def fetch_job(job):
    """做一个任务：发一次请求，返回结果（dict），失败原因写在 status 里，不抛异常。

    在线程池里运行，只联网、不碰数据库。
    status 是 200、"未收录"（游戏已下架）、get_json 给的失败原因，或 "parse_error"；
    只有 200 时才有 total 和 reviews。
    """
    result = dict(job)  # 带上任务自己的身份和起止时刻，存库时要用
    appid = job["appid"]
    window = job["window"]

    params = build_input_json(appid, job["cutoff_date"], job["start_ts"], job["end_ts"])
    try:
        response = get_json(
            url=review_counts.URL,
            params={"input_json": json.dumps(params)},
            min_interval=review_counts.MIN_INTERVAL,
        )
        parsed = parse_window(response)
    except CrawlError as err:
        logger.warning("appid=%d 第 %d 段请求失败: %s", appid, window, err)
        result["status"] = err.status
        return result
    except (KeyError, TypeError) as err:
        logger.warning("appid=%d 第 %d 段解析失败，缺少或错误的字段: %r", appid, window, err)
        result["status"] = "parse_error"
        return result

    if parsed is None:
        result["status"] = "未收录"
        return result

    result["status"] = 200
    result["total"], result["reviews"] = parsed
    return result


def save_result(conn, result):
    """把一段的结果写进数据库：成功就写一行段、若干行评测；不管成败都在 raw_crawl_log 记结局。"""
    key = make_request_key(result["appid"], result["cutoff_date"], result["window"])
    # 一段一个事务：段、评测、日志要么都写入，要么都不写。
    # 用普通 INSERT：失败的段一行都没写过，重试时不会撞主键；真撞了说明切段有错，让它报出来
    with conn:
        if result["status"] == 200:
            identity = {
                "appid": result["appid"],
                "cutoff_date": result["cutoff_date"],
                "window": result["window"],
            }
            # 评测为 0 的段也写一行：总数 0 本身就是这一段的数据
            conn.execute(
                INSERT_WINDOW_SQL,
                {
                    **identity,
                    "start_ts": result["start_ts"],
                    "end_ts": result["end_ts"],
                    "total": result["total"],
                    "fetched_at": now_utc_str(),
                },
            )
            for review in result["reviews"]:
                conn.execute(INSERT_SAMPLE_SQL, {**identity, **review})
        crawl_log.record(conn, SOURCE, key, result["status"])


def crawl_review_sample(conn, appids, cutoff_date, workers=1):
    """采集 appids 在 cutoff_date 前的抽样评测。只负责调度，和 crawl_review_counts 一样。"""
    ensure_tables(conn)
    release_of = load_release_ts(conn, appids)
    jobs = pending_jobs(conn, appids, cutoff_date, release_of)
    logger.info(
        "共 %d 个游戏，截止日 %s，待发请求 %d 次，%d 路并行",
        len(appids),
        cutoff_date,
        len(jobs),
        workers,
    )

    # 线程池的用法和退出方式见 review_counts.crawl_review_counts
    pool = ThreadPoolExecutor(max_workers=workers)
    try:
        done_count = 0
        for result in pool.map(fetch_job, jobs):
            save_result(conn, result)
            done_count += 1
            if done_count % PROGRESS_EVERY == 0:
                logger.info("进度 %d/%d 次请求", done_count, len(jobs))
    finally:
        pool.shutdown(wait=True, cancel_futures=True)


def main():
    """命令行入口：python -m crawler.sources.review_sample [数量] [--cutoff 日期] [--workers 路数]"""
    parser = argparse.ArgumentParser(description="采集抽样评测")
    parser.add_argument(
        "limit", type=int, nargs="?", default=None, help="从 Ars 表里取多少个 appid；不写则全部"
    )
    parser.add_argument("--cutoff", default=review_counts.DEFAULT_CUTOFF, help="截止日，格式 YYYY-MM-DD")
    parser.add_argument("--workers", type=int, default=1, help="同时发请求的线程数，默认 1")
    args = parser.parse_args()

    setup_logging("review_sample.log")

    conn = sqlite3.connect(DB_PATH)
    try:
        crawl_review_sample(conn, pick_appids(conn, args.limit), args.cutoff, args.workers)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
