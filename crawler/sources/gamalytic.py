"""采集 Gamalytic 博客里的公开销量对照表，写入 raw_truth_gamalytic。校准集的真值来源之一。

网页：https://gamalytic.com/blog/how-to-accurately-estimate-steam-sales
文章末尾有一张表，每行 5 格：游戏、日期、公布销量、Gamalytic 估计、差多少。
- 游戏那一格是链接 /game/<appid>，appid 从这里取；
- 公布销量那一格的链接是这个数字的原始出处（reddit、新闻等），少数几行没有链接；
- 销量写成 14K、12.4M 这种缩写，换算成整数；
- Gamalytic 自己的估计和“差多少”两格校准用不到，不存。

整张表在一个网页上，一次请求就够，不用 raw_crawl_log 记进度：重跑就整表重采、整表替换。
同一款游戏可能有两行（不同日期公布的两个数），所以主键是 (appid, report_date)，选哪条交给 pipeline。

入口：python -m crawler.sources.gamalytic
"""

import logging
import re
import sqlite3
from datetime import datetime

from common.clock import now_utc_str
from common.log import setup_logging
from common.paths import DB_PATH
from crawler.http import get_html

logger = logging.getLogger(__name__)

PAGE_URL = "https://gamalytic.com/blog/how-to-accurately-estimate-steam-sales"

# 表头不对说明网站改了版，直接报错，不往下猜
EXPECTED_HEADER = ["Game", "Date", "Reported units sold", "Estimate", "% difference"]

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS raw_truth_gamalytic (
    appid       INTEGER NOT NULL,
    report_date TEXT NOT NULL,
    title       TEXT NOT NULL,
    units_sold  INTEGER NOT NULL,
    source_url  TEXT,
    fetched_at  TEXT NOT NULL,
    PRIMARY KEY (appid, report_date)
)
"""

INSERT_SQL = """
INSERT INTO raw_truth_gamalytic (appid, report_date, title, units_sold, source_url, fetched_at)
VALUES (:appid, :report_date, :title, :units_sold, :source_url, :fetched_at)
"""


def parse_units(text):
    """把 '14K'、'12.4M'、'750' 换算成整数 14000、12400000、750。看不懂就抛 ValueError。"""
    # TODO：去掉末尾的 K / M，乘 1000 / 1000000，四舍五入成整数


def parse_page(page):
    """从网页文字里找出销量表，返回 raw_truth_gamalytic 的若干行（还没有 fetched_at）。

    外部网页要严格校验：找不到表、表头不对、某一行看不懂，都抛 ValueError。
    """
    # TODO 1：找到表头是 EXPECTED_HEADER 的那张表（页面上还有 6 张小的成绩表）
    # TODO 2：逐行取 5 格的文字和行里的链接
    # TODO 3：appid 取自 /game/<appid>，日期 'Jul 10, 2022' 换成 '2022-07-10'，
    #         销量用 parse_units，出处取公布销量那一格的链接，没有就是 None


def main():
    """命令行入口：请求网页、解析，整表替换写进 raw_truth_gamalytic。"""
    setup_logging("gamalytic.log")
    # TODO 1：get_html 取网页（自带限速和重试，最终失败会抛 CrawlError，直接让它报错）
    # TODO 2：parse_page 解析，每行补上 fetched_at
    # TODO 3：一个事务里先删旧表内容再写新的，出错整个回滚，库里不留半张表


if __name__ == "__main__":
    main()
