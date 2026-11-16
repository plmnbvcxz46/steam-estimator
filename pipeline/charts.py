"""清洗月度在线人数：raw_charts_monthly -> cleaned_charts_monthly。

raw 表一行是一款游戏一个月的“平均同时在线人数”。信号 B 要的是“一共玩了多少小时”，
所以这里给每个月算出当月的玩家小时：平均人数 × 当月天数 × 24。
比如 6 月平均 100 人在线，6 月有 30 天，这个月一共玩了 100 × 30 × 24 = 72000 小时。

只换算，不做取舍：不按截止日截取，不管上架当月只上架了几天，
也不判断记录是不是从上架初期开始的，这些放在建样本表时。
所以 raw 表有多少行，cleaned 表就有多少行。

cleaned 表是派生数据：每次运行都整张表重建，结果只取决于 raw 表。
"""

import calendar
import logging
import sqlite3

from common.log import setup_logging
from common.paths import DB_PATH

logger = logging.getLogger(__name__)

HOURS_PER_DAY = 24

CREATE_TABLE_SQL = """
CREATE TABLE cleaned_charts_monthly (
    appid        INTEGER NOT NULL,
    month        TEXT NOT NULL,
    avg_players  REAL NOT NULL,
    days         INTEGER NOT NULL,
    player_hours REAL NOT NULL,
    PRIMARY KEY (appid, month)
)
"""

INSERT_SQL = """
INSERT INTO cleaned_charts_monthly VALUES (
    :appid, :month, :avg_players, :days, :player_hours
)
"""


def days_in_month(month):
    """"2018-02" 这个月有几天（闰年 2 月是 29 天）。"""
    year, month_number = month.split("-")
    # monthrange 返回（这个月 1 号是星期几，这个月有几天），只要后一个
    return calendar.monthrange(int(year), int(month_number))[1]


def to_cleaned_row(appid, month, avg_players):
    """raw 表的一行 -> cleaned 表的一行（dict），加上当月天数和玩家小时。"""
    days = days_in_month(month)
    return {
        "appid": appid,
        "month": month,
        "avg_players": avg_players,
        "days": days,
        "player_hours": avg_players * days * HOURS_PER_DAY,
    }


def build_cleaned_charts(conn):
    """读 raw_charts_monthly，重建 cleaned_charts_monthly。"""
    raw_rows = conn.execute(
        "SELECT appid, month, avg_players FROM raw_charts_monthly ORDER BY appid, month"
    ).fetchall()
    cleaned_rows = [to_cleaned_row(appid, month, avg) for appid, month, avg in raw_rows]

    # 删旧表、建新表、写入放在同一个事务里：中途出错就整体撤销，旧表原样还在。
    # 要手动写 BEGIN，因为 sqlite3 模块只在 INSERT 这类语句前才自动开事务
    with conn:
        conn.execute("BEGIN")
        conn.execute("DROP TABLE IF EXISTS cleaned_charts_monthly")
        conn.execute(CREATE_TABLE_SQL)
        conn.executemany(INSERT_SQL, cleaned_rows)

    # 只换算不删行，两个数应该相等；不相等说明代码有错，日志里一眼能看出来
    game_count = len({row["appid"] for row in cleaned_rows})
    logger.info(
        "raw_charts_monthly 共 %d 款 %d 行：写入 %d 行", game_count, len(raw_rows), len(cleaned_rows)
    )


def main():
    """命令行入口：python -m pipeline.charts"""
    setup_logging("cleaned_charts.log")

    conn = sqlite3.connect(DB_PATH)
    try:
        build_cleaned_charts(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
