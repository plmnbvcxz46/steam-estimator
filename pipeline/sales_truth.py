"""合并各来源的销量真值：raw_truth_gamalytic、raw_truth_manual -> cleaned_sales_truth。

每个真值来源一张 raw 表，列名各不相同；这里把它们对到同一套列上，下游（校准样本、
按新截止日补爬评测）只读这一张表，以后加来源，下游一行都不用改。

只合并，不做取舍：同一款的多条记录、不同来源的重复都留着，每款选哪一条放在建样本表时。
所以各 raw 表加起来多少行，cleaned 表就有多少行。

cleaned 表是派生数据：每次运行都整张表重建，结果只取决于 raw 表。
要先跑 crawler.sources.gamalytic 和 crawler.sources.manual_truth。

入口：python -m pipeline.sales_truth
"""

import logging
import sqlite3

from common.log import setup_logging
from common.paths import DB_PATH

logger = logging.getLogger(__name__)

# 每个来源一条查询，把它的列改名成统一的列。新增来源：先写爬虫或导入脚本，再在这里加一项
SOURCE_QUERIES = {
    "gamalytic": "SELECT appid, report_date, title, units_sold, source_url FROM raw_truth_gamalytic",
    "manual": "SELECT appid, report_date, title, units_sold, source_url FROM raw_truth_manual",
}

CREATE_TABLE_SQL = """
CREATE TABLE cleaned_sales_truth (
    source      TEXT NOT NULL,
    appid       INTEGER NOT NULL,
    report_date TEXT NOT NULL,
    title       TEXT NOT NULL,
    units_sold  INTEGER NOT NULL,
    source_url  TEXT,
    PRIMARY KEY (source, appid, report_date)
)
"""

INSERT_SQL = """
INSERT INTO cleaned_sales_truth (source, appid, report_date, title, units_sold, source_url)
VALUES (?, ?, ?, ?, ?, ?)
"""


def main():
    """命令行入口：读各来源的 raw 表，重建 cleaned_sales_truth。"""
    setup_logging("cleaned_sales_truth.log")

    conn = sqlite3.connect(DB_PATH)
    try:
        # 1. 逐个来源读出来，每行前面加上来源名
        rows = []
        for source, query in SOURCE_QUERIES.items():
            source_rows = conn.execute(query).fetchall()
            logger.info("%s：%d 行", source, len(source_rows))
            for row in source_rows:
                rows.append((source, *row))

        # 2. 删旧表、建新表、写入放在同一个事务里，中途出错旧表原样还在。
        #    要手动写 BEGIN，因为 sqlite3 模块只在 INSERT 这类语句前才自动开事务
        with conn:
            conn.execute("BEGIN")
            conn.execute("DROP TABLE IF EXISTS cleaned_sales_truth")
            conn.execute(CREATE_TABLE_SQL)
            conn.executemany(INSERT_SQL, rows)
    finally:
        conn.close()

    logger.info("cleaned_sales_truth 写入 %d 行，%d 款游戏", len(rows), len({row[1] for row in rows}))


if __name__ == "__main__":
    main()
