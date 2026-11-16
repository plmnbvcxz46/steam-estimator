"""采集 SteamCharts 的月度在线人数，写入 raw_charts_monthly。供信号 B 算总游玩小时。

SteamCharts 没有接口，只有网页：https://steamcharts.com/app/<appid>
页面里有一张按月的表，每行 5 格：月份、平均在线人数、比上月增减、增减百分比、峰值。
我们存月份、平均在线人数、峰值；增减是相邻两月算出来的，不存。
第一行 “Last 30 Days” 是最近 30 天，不是整月，也不存。

没收录的游戏回 500 和网站的通用页，交给 get_html 认出来记“未收录”，不重试。
"""

import argparse
import logging
import re
import sqlite3

from common.clock import now_utc_str
from common.log import setup_logging
from common.paths import DB_PATH
from crawler import crawl_log
from crawler.appids import pick_appids
from crawler.http import CrawlError, get_html

logger = logging.getLogger(__name__)

SOURCE = "steamcharts"
PAGE_URL = "https://steamcharts.com/app/{appid}"
# 没收录的游戏，页面是网站通用页，标题里有这一段；收录了的游戏标题是“游戏名 - Steam Charts”
NOT_TRACKED_MARKER = "Steam Charts - Tracking What's Played"
# 第三方小网站，没有公布限额，按早期探索版本的 1.5 秒一次，单线程慢慢采
MIN_INTERVAL = 1.5

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
    # TODO 填实现：补 fetched_at，删旧、写新、记日志
    raise NotImplementedError


def crawl_steamcharts(conn, appids):
    """逐款取网页、解析、入库。已有定论的跳过，中断后重跑同一条命令即可续上。"""
    # TODO 填实现：算出待采列表，逐款 get_html → parse_months → save_months，失败记日志
    raise NotImplementedError


def main():
    """命令行入口：python -m crawler.sources.steamcharts [数量]，不写数量就采全部"""
    parser = argparse.ArgumentParser(description="采集 SteamCharts 月度在线人数")
    parser.add_argument(
        "limit", type=int, nargs="?", default=None,
        help="从 Ars 表里取多少个 appid 来采；不写则采全部",
    )
    args = parser.parse_args()

    setup_logging("steamcharts.log")

    conn = sqlite3.connect(DB_PATH)
    try:
        appids = pick_appids(conn, args.limit)
        crawl_steamcharts(conn, appids)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
