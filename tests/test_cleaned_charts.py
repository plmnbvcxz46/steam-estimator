import sqlite3

from crawler.sources import steamcharts
from pipeline.charts import build_cleaned_charts

FETCHED_AT = "2026-11-16 03:00:00"


def make_conn(rows):
    """建一个只有 raw_charts_monthly 的内存库，rows 是 (appid, month, avg_players, peak_players)。"""
    conn = sqlite3.connect(":memory:")
    conn.execute(steamcharts.CREATE_TABLE_SQL)
    # with conn 把写入提交掉：清洗函数自己要开事务，留着没提交的写入会冲突
    with conn:
        for appid, month, avg_players, peak_players in rows:
            conn.execute(
                "INSERT INTO raw_charts_monthly VALUES (?, ?, ?, ?, ?)",
                (appid, month, avg_players, peak_players, FETCHED_AT),
            )
    return conn


def test_each_month_becomes_player_hours():
    # 平均人数取自 Half-Life 2（220）的真实数据，峰值随便填（清洗用不到）。
    # 2016 年是闰年，2 月有 29 天
    conn = make_conn([
        (220, "2016-02", 895.41, 1500),
        (220, "2018-06", 813.75, 1400),
    ])
    build_cleaned_charts(conn)

    rows = conn.execute(
        "SELECT appid, month, avg_players, days, player_hours FROM cleaned_charts_monthly ORDER BY month"
    ).fetchall()
    # 只换算不删行：raw 两行，cleaned 也是两行
    assert rows == [
        (220, "2016-02", 895.41, 29, 895.41 * 29 * 24),
        (220, "2018-06", 813.75, 30, 813.75 * 30 * 24),
    ]
