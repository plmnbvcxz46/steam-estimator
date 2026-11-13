"""清洗价格历史：raw_price_history -> cleaned_prices。

raw 表一行是一个“价格变动点”：从这一刻起卖多少钱。这里把变动点变成“时间段”：
每个变动点开一段，到这款游戏的下一个变动时刻结束；最后一段到采集时刻结束。
有了结束时刻，后面查“截止日那天卖多少钱”只要找截止日落在哪一段，不用再去找下一行。

只切段，不做取舍：同一时刻的两条记录都留，过长的折扣也不截断，这些放在建样本表时。
所以 raw 表有多少行，cleaned 表就有多少行。

cleaned 表是派生数据：每次运行都整张表重建，结果只取决于 raw 表。
"""

import logging
import sqlite3
from datetime import datetime

from common.log import setup_logging
from common.paths import DB_PATH

logger = logging.getLogger(__name__)

SECONDS_PER_DAY = 24 * 60 * 60

CREATE_TABLE_SQL = """
CREATE TABLE cleaned_prices (
    appid      INTEGER NOT NULL,
    started_at TEXT NOT NULL,
    ended_at   TEXT NOT NULL,
    regular    REAL NOT NULL,
    price      REAL NOT NULL,
    cut        INTEGER NOT NULL,
    days       REAL NOT NULL,
    PRIMARY KEY (appid, started_at, regular, price)
)
"""

INSERT_SQL = """
INSERT INTO cleaned_prices VALUES (
    :appid, :started_at, :ended_at, :regular, :price, :cut, :days
)
"""


def group_by_game(raw_rows):
    """把 raw 的多行按 appid 归到一起，返回 {appid: [该游戏的行, ...]}。"""
    grouped = {}
    for row in raw_rows:
        appid = row[0]
        grouped.setdefault(appid, []).append(row)
    return grouped


def days_between(start, end):
    """两个时刻相差几天，带小数。时刻的写法是 "2018-06-21 21:04:55"，都是 UTC。"""
    seconds = (
        datetime.fromisoformat(end) - datetime.fromisoformat(start)
    ).total_seconds()
    return round(seconds / SECONDS_PER_DAY, 4)


def make_segments(appid, rows):
    """把一款游戏的变动点变成时间段，返回 cleaned 表的若干行（dict）。

    rows 是这款游戏在 raw 表里的行：(appid, changed_at, regular, price, cut, fetched_at)。
    """
    # 一款游戏的历史是一次请求取回、一次写入的，所以采集时刻都一样
    fetched_at = rows[0][5]

    # 结束时刻是“下一个不同的时刻”，不是“下一行”：同一时刻有两条记录时，
    # 按下一行算会让其中一条只持续 0 秒。所以先把时刻去重、排好序，再给每个时刻配它的下一个
    times = sorted({row[1] for row in rows})
    end_of = {}
    for i, time in enumerate(times):
        if i + 1 < len(times):
            end_of[time] = times[i + 1]
        else:
            # 最后一个时刻后面没有变动了，这个价格一直持续到我们去采的那一刻
            end_of[time] = fetched_at

    segments = []
    for _, changed_at, regular, price, cut, _ in rows:
        ended_at = end_of[changed_at]
        segments.append(
            {
                "appid": appid,
                "started_at": changed_at,
                "ended_at": ended_at,
                "regular": regular,
                "price": price,
                "cut": cut,
                "days": days_between(changed_at, ended_at),
            }
        )
    return segments


def build_cleaned_prices(conn):
    """读 raw_price_history，重建 cleaned_prices。"""
    raw_rows = conn.execute(
        "SELECT appid, changed_at, regular, price, cut, fetched_at FROM raw_price_history"
        " ORDER BY appid, changed_at"
    ).fetchall()
    grouped = group_by_game(raw_rows)

    cleaned_rows = []
    for appid, rows in grouped.items():
        cleaned_rows.extend(make_segments(appid, rows))

    # 删旧表、建新表、写入放在同一个事务里：中途出错就整体撤销，旧表原样还在。
    # 要手动写 BEGIN，因为 sqlite3 模块只在 INSERT 这类语句前才自动开事务
    with conn:
        conn.execute("BEGIN")
        conn.execute("DROP TABLE IF EXISTS cleaned_prices")
        conn.execute(CREATE_TABLE_SQL)
        conn.executemany(INSERT_SQL, cleaned_rows)

    # 只切段不删行，两个数应该相等；不相等说明代码有错，日志里一眼能看出来
    logger.info(
        "raw_price_history 共 %d 款 %d 行：写入 %d 段",
        len(grouped),
        len(raw_rows),
        len(cleaned_rows),
    )


def main():
    """命令行入口：python -m pipeline.prices"""
    setup_logging("cleaned_prices.log")

    conn = sqlite3.connect(DB_PATH)
    try:
        build_cleaned_prices(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
