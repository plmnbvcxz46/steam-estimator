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

import html
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
    multiplier = 1
    if text.endswith("K"):
        multiplier = 1_000
        text = text[:-1]
    elif text.endswith("M"):
        multiplier = 1_000_000
        text = text[:-1]
    # float 认不出的（空串、字母）会抛 ValueError。
    # 12.4 × 1000000 算出来是 12400000.000000002，所以四舍五入再转整数
    return round(float(text) * multiplier)


def cell_text(cell):
    """一格的文字：去掉标签和前后空白，再把 &amp; 这类转义换回原字符。"""
    return html.unescape(re.sub(r"<[^>]+>", "", cell)).strip()


def parse_page(page):
    """从网页文字里找出销量表，返回 raw_truth_gamalytic 的若干行（还没有 fetched_at）。

    外部网页要严格校验：找不到表、表头不对、某一行看不懂，都抛 ValueError。
    """
    # 1. 页面上有 7 张表，前 6 张是小的成绩汇总；表头对得上的必须正好一张
    tables = []
    for table in re.findall(r"<table.*?</table>", page, re.S):
        header = [cell_text(th) for th in re.findall(r"<th.*?</th>", table, re.S)]
        if header == EXPECTED_HEADER:
            tables.append(table)
    if len(tables) != 1:
        raise ValueError(f"表头是 {EXPECTED_HEADER} 的表有 {len(tables)} 张，应为 1 张")

    rows = []
    # 2. 逐行取格子。表头那行只有 <th> 没有 <td>，找不到格子，跳过
    for tr in re.findall(r"<tr.*?</tr>", tables[0], re.S):
        cells = re.findall(r"<td.*?</td>", tr, re.S)
        if not cells:
            continue
        if len(cells) != 5:
            raise ValueError(f"有一行是 {len(cells)} 格，应为 5 格: {cell_text(tr)}")
        game_cell, date_cell, units_cell = cells[0], cells[1], cells[2]

        # 3. appid 取自游戏名的链接 /game/<appid>，找不到说明这一行和预期不一样
        appid_match = re.search(r'href="/game/(\d+)"', game_cell)
        if appid_match is None:
            raise ValueError(f"游戏格里没有 /game/<appid> 链接: {cell_text(game_cell)}")

        # 出处是公布销量那一格的链接，少数几行没有，存 None。
        # 网页里有一条链接末尾多了个空格，strip 去掉
        url_match = re.search(r'href="([^"]+)"', units_cell)
        source_url = html.unescape(url_match.group(1)).strip() if url_match else None

        rows.append(
            {
                "appid": int(appid_match.group(1)),
                # 'Jul 10, 2022' -> '2022-07-10'；格式不对 strptime 会抛 ValueError
                "report_date": datetime.strptime(cell_text(date_cell), "%b %d, %Y").strftime("%Y-%m-%d"),
                "title": cell_text(game_cell),
                "units_sold": parse_units(cell_text(units_cell)),
                "source_url": source_url,
            }
        )
    return rows


def main():
    """命令行入口：请求网页、解析，整表替换写进 raw_truth_gamalytic。"""
    setup_logging("gamalytic.log")
    # 1. 取网页。get_html 自带限速和重试，最终失败会抛 CrawlError：只有一页，失败了就直接报错
    page = get_html(PAGE_URL)

    # 2. 解析，每行补上采集时间
    rows = parse_page(page)
    fetched_at = now_utc_str()
    for row in rows:
        row["fetched_at"] = fetched_at

    conn = sqlite3.connect(DB_PATH)
    try:
        # 3. 整表替换：先删旧的再写新的。with conn 里全部成功才提交，
        #    出错（如同一款同一天出现两次，主键冲突）就整个回滚，库里留着旧表，不会只剩半张
        with conn:
            conn.execute(CREATE_TABLE_SQL)
            conn.execute("DELETE FROM raw_truth_gamalytic")
            conn.executemany(INSERT_SQL, rows)
    finally:
        conn.close()
    logger.info("raw_truth_gamalytic 写入 %d 行，%d 款游戏", len(rows), len({row["appid"] for row in rows}))


if __name__ == "__main__":
    main()
