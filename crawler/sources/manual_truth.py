"""导入手填的销量真值表 data/source/sales_truth_manual.csv，写入 raw_truth_manual。校准集的真值来源之一。

零散来源（开发者帖子、推特、采访、新闻稿）每处只有一两个数，不值得各写一个爬虫，
人工读原话核对后填进这张 CSV，一行一个公布的销量：
- appid、title：游戏编号和名字；
- report_date：公布日期，写成 YYYY-MM-DD；
- units_sold：公布的 Steam 销量，整数，不写千分位逗号；
- source_url、quote：出处链接和原话，必填，答辩被问“这个数哪来的”时能指给人看；
- note：备注，可空（如“首月”“只算 Steam”）。

新增真值只要在 CSV 里加一行再重跑本脚本，代码不用改。重跑整表替换，结果和 CSV 一致。
同一款可以有多行（不同日期公布的数），主键 (appid, report_date)，选哪条交给 pipeline。

入口：python -m crawler.sources.manual_truth
"""

import csv
import logging
import sqlite3
from datetime import datetime

from common.clock import now_utc_str
from common.log import setup_logging
from common.paths import DB_PATH, SOURCE_DIR

logger = logging.getLogger(__name__)

SOURCE_CSV = SOURCE_DIR / "sales_truth_manual.csv"

EXPECTED_HEADER = ["appid", "title", "report_date", "units_sold", "source_url", "quote", "note"]

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS raw_truth_manual (
    appid       INTEGER NOT NULL,
    report_date TEXT NOT NULL,
    title       TEXT NOT NULL,
    units_sold  INTEGER NOT NULL,
    source_url  TEXT NOT NULL,
    quote       TEXT NOT NULL,
    note        TEXT,
    fetched_at  TEXT NOT NULL,
    PRIMARY KEY (appid, report_date)
)
"""

INSERT_SQL = """
INSERT INTO raw_truth_manual (appid, report_date, title, units_sold, source_url, quote, note, fetched_at)
VALUES (:appid, :report_date, :title, :units_sold, :source_url, :quote, :note, :fetched_at)
"""


def read_rows(csv_path):
    """读手填表，返回 raw_truth_manual 的若干行（还没有 fetched_at）。

    手填容易出错，填错了直接报错并指出第几行，改好 CSV 再跑，不悄悄跳过。
    """
    rows = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != EXPECTED_HEADER:
            raise ValueError(f"表头不符合预期: {reader.fieldnames}，应为 {EXPECTED_HEADER}")

        for record in reader:
            where = f"{csv_path.name} 第 {reader.line_num} 行"
            if not record["source_url"].strip() or not record["quote"].strip():
                raise ValueError(f"{where}：出处链接和原话必填")

            # 日期按原样存进表里，后面都按 '2023-08-29' 这种写法查。
            # 写成 '2023-8-29' strptime 也认，所以换算回去比一比，不一样就报错
            report_date = record["report_date"].strip()
            if datetime.strptime(report_date, "%Y-%m-%d").strftime("%Y-%m-%d") != report_date:
                raise ValueError(f"{where}：日期要写成 YYYY-MM-DD，实际是 {report_date!r}")

            rows.append(
                {
                    # int() 认不出（空、带逗号、带小数点）会抛 ValueError，报错信息里有原值
                    "appid": int(record["appid"]),
                    "report_date": report_date,
                    "title": record["title"].strip(),
                    "units_sold": int(record["units_sold"]),
                    "source_url": record["source_url"].strip(),
                    "quote": record["quote"].strip(),
                    # 备注空着就存 NULL，不存空串
                    "note": record["note"].strip() or None,
                }
            )
    return rows


def main():
    """命令行入口：读手填表，整表替换写进 raw_truth_manual。"""
    setup_logging("manual_truth_import.log")

    rows = read_rows(SOURCE_CSV)
    fetched_at = now_utc_str()
    for row in rows:
        row["fetched_at"] = fetched_at

    conn = sqlite3.connect(DB_PATH)
    try:
        # 整表替换：CSV 里删掉的行，表里也跟着没了。
        # 同一款同一天填了两行会主键冲突，整个回滚，库里留着上一次的表
        with conn:
            conn.execute(CREATE_TABLE_SQL)
            conn.execute("DELETE FROM raw_truth_manual")
            conn.executemany(INSERT_SQL, rows)
    finally:
        conn.close()
    logger.info("raw_truth_manual 写入 %d 行，%d 款游戏", len(rows), len({row["appid"] for row in rows}))


if __name__ == "__main__":
    main()
