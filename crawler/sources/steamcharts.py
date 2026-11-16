"""采集 SteamCharts 的月度在线人数，写入 raw_charts_monthly。供信号 B 算总游玩小时。

SteamCharts 没有接口，只有网页：https://steamcharts.com/app/<appid>
页面里有一张按月的表，每行 5 格：月份、平均在线人数、比上月增减、增减百分比、峰值。
我们存月份、平均在线人数、峰值；增减是相邻两月算出来的，不存。
第一行 “Last 30 Days” 是最近 30 天，不是整月，也不存。

没收录的游戏回 500 和网站的通用页，交给 get_html 认出来记“未收录”，不重试。
"""

import logging
import re
import sqlite3
from concurrent.futures import ThreadPoolExecutor

from common.clock import now_utc_str
from crawler import crawl_log
from crawler.http import CrawlError, get_html

logger = logging.getLogger(__name__)

SOURCE = "steamcharts"
PAGE_URL = "https://steamcharts.com/app/{appid}"
# 没收录的游戏，页面是网站通用页，标题里有这一段；收录了的游戏标题是“游戏名 - Steam Charts”
NOT_TRACKED_MARKER = "Steam Charts - Tracking What's Played"
# 第三方小网站，没有公布限额。实测连续 2 分钟每秒约 5 次、短时间约 7 次都没被限流（devlog 2026-11-16）；
# 留出余量取每秒 4 次，所有线程合计。一次请求本身约 0.5 秒，要 --workers 4 左右才跑得满
MIN_INTERVAL = 0.25

# 网页上的月份是英文全称，如 "June 2018"，换成 "2018-06"
MONTHS = {
    "January": 1, "February": 2, "March": 3, "April": 4, "May": 5, "June": 6,
    "July": 7, "August": 8, "September": 9, "October": 10, "November": 11, "December": 12,
}

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS raw_charts_monthly (
    appid        INTEGER NOT NULL,
    month        TEXT NOT NULL,
    avg_players  REAL NOT NULL,
    peak_players INTEGER NOT NULL,
    fetched_at   TEXT NOT NULL,
    PRIMARY KEY (appid, month)
)
"""

INSERT_SQL = """
INSERT INTO raw_charts_monthly (appid, month, avg_players, peak_players, fetched_at)
VALUES (:appid, :month, :avg_players, :peak_players, :fetched_at)
"""


def ensure_tables(conn):
    crawl_log.ensure_table(conn)
    conn.execute(CREATE_TABLE_SQL)


def parse_months(appid, page):
    """从网页文字里找出月份表，返回 raw_charts_monthly 的若干行（还没有 fetched_at）。

    外部网页要严格校验：找不到表、某一行看不懂，都抛 ValueError，由调用者记 parse_error，
    不悄悄跳过，免得网站改版后存进一半数据。
    """
    # 页面里只有月份表有 <tbody>。不是正好一个，说明页面变了样，不往下猜
    bodies = re.findall(r"<tbody>(.*?)</tbody>", page, re.S)
    if len(bodies) != 1:
        raise ValueError(f"appid={appid} 页面里有 {len(bodies)} 个表体，应为 1 个")

    rows = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", bodies[0], re.S):
        # 取出每一格的文字：去掉格子里的标签，再去掉前后的空白和换行
        cells = [
            re.sub(r"<[^>]+>", "", td).strip()
            for td in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        ]
        if len(cells) != 5:
            raise ValueError(f"appid={appid} 有一行是 {len(cells)} 格，应为 5 格: {cells}")
        if cells[0] == "Last 30 Days":
            continue  # 最近 30 天，不是整月

        # "June 2018" -> "2018-06"；月份名不认识会抛 KeyError，同样记 parse_error
        month_name, year = cells[0].split()
        month = f"{int(year)}-{MONTHS[month_name]:02d}"
        rows.append(
            {
                "appid": appid,
                "month": month,
                "avg_players": float(cells[1]),
                "peak_players": int(cells[4]),
            }
        )
    return rows


def save_months(conn, appid, rows):
    """把一款游戏的月份行写进 raw_charts_monthly，日志一起记，放在同一个事务里。

    重采同一款时整段换成新的：先删旧的再写。表里一个整月都没有，记“空结果”。
    """
    fetched_at = now_utc_str()
    for row in rows:
        row["fetched_at"] = fetched_at
    # with conn：里面几句要么全部生效，要么一句都不生效。
    # 删了旧的还没写完新的就断电，旧数据也会回来，不会只剩半款
    with conn:
        conn.execute("DELETE FROM raw_charts_monthly WHERE appid = ?", (appid,))
        # 普通 INSERT：同一个月出现两次会因主键冲突报错，不会悄悄只留一条
        conn.executemany(INSERT_SQL, rows)
        crawl_log.record(conn, SOURCE, appid, 200 if rows else crawl_log.EMPTY)


def fetch_one(appid):
    """取一款的网页并解析，返回 {"appid", "status", "rows"}，失败原因写在 status 里，不抛异常。

    在线程池里运行，只联网、不碰数据库；只有 status 为 200 时 rows 才有内容。
    """
    result = {"appid": appid, "status": 200, "rows": []}
    try:
        page = get_html(
            PAGE_URL.format(appid=appid),
            min_interval=MIN_INTERVAL,
            not_found_marker=NOT_TRACKED_MARKER,
        )
        result["rows"] = parse_months(appid, page)
    except CrawlError as err:
        if err.status in (crawl_log.NOT_FOUND, 404):
            # 没收录有两种回法：500 加通用页（get_html 已认出），或 404（连这个 appid 都不认识，
            # 实测重试仍是 404）。约七成游戏都没收录，是正常结局，不写警告，只在进度里计数
            result["status"] = crawl_log.NOT_FOUND
        else:
            logger.warning("appid=%d 请求失败: %s", appid, err)
            result["status"] = err.status
    except (KeyError, ValueError) as err:
        # 页面看不懂（找不到表、格数不对、月份认不出）
        logger.warning("appid=%d 解析失败: %r", appid, err)
        result["status"] = crawl_log.PARSE_ERROR
    return result


def crawl_steamcharts(conn, appids, workers=1):
    """逐款取网页、解析、入库。已有定论的跳过，中断后重跑同一条命令即可续上。

    几个线程同时发请求（fetch_one），写库只由主线程做：SQLite 的连接不能在线程之间共用。
    """
    ensure_tables(conn)

    done = crawl_log.done_keys(conn, SOURCE)
    todo = [appid for appid in appids if str(appid) not in done]
    logger.info(
        "SteamCharts：共 %d 款，已完成 %d 款，本次要采 %d 款，%d 路并行",
        len(appids), len(appids) - len(todo), len(todo), workers,
    )

    # 每种结局各有几款，进度里一起报：未收录不再逐条写日志，靠这里看个总数
    counts = {"收录": 0, "未收录": 0, "失败": 0}
    pool = ThreadPoolExecutor(max_workers=workers)
    try:
        # 对 todo 里每一款调用 fetch_one，由池里的线程去做；结果按 todo 的顺序交回来
        for index, result in enumerate(pool.map(fetch_one, todo), start=1):
            appid = result["appid"]
            if result["status"] == crawl_log.NOT_FOUND:
                counts["未收录"] += 1
                with conn:
                    crawl_log.record(conn, SOURCE, appid, crawl_log.NOT_FOUND)
            elif result["status"] != 200:
                counts["失败"] += 1
                with conn:
                    crawl_log.record(conn, SOURCE, appid, result["status"])
            else:
                try:
                    save_months(conn, appid, result["rows"])
                    counts["收录"] += 1
                except sqlite3.IntegrityError as err:
                    # 同一个月出现两次：整款没有写入（事务回滚），记下原因，下次重试
                    logger.warning("appid=%d 写入失败: %r", appid, err)
                    counts["失败"] += 1
                    with conn:
                        crawl_log.record(conn, SOURCE, appid, crawl_log.PARSE_ERROR)

            if index % 100 == 0 or index == len(todo):
                logger.info(
                    "SteamCharts 进度 %d/%d：收录 %d，未收录 %d，失败 %d",
                    index, len(todo), counts["收录"], counts["未收录"], counts["失败"],
                )
    finally:
        # 正常结束或按 Ctrl+C 都会走到这里。cancel_futures=True 把还没开始的任务全部取消，
        # 否则线程池会坚持把剩下的请求发完才肯退出
        pool.shutdown(wait=True, cancel_futures=True)
