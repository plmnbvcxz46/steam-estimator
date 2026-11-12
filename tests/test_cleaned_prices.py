import sqlite3

from crawler.sources import itad
from pipeline.prices import build_cleaned_prices

FETCHED_AT = "2026-11-12 11:00:00"


def make_conn(rows):
    """建一个只有 raw_price_history 的内存库，rows 是 (appid, changed_at, regular, price, cut)。"""
    conn = sqlite3.connect(":memory:")
    conn.execute(itad.CREATE_HISTORY_SQL)
    with conn:
        for appid, changed_at, regular, price, cut in rows:
            conn.execute(
                "INSERT INTO raw_price_history VALUES (?, 'US', ?, 'USD', ?, ?, ?, ?)",
                (appid, changed_at, price, regular, cut, FETCHED_AT),
            )
    return conn


def segments(conn):
    return conn.execute(
        "SELECT appid, started_at, ended_at, price, days FROM cleaned_prices ORDER BY appid, started_at, price"
    ).fetchall()


def test_each_point_becomes_a_segment_and_last_ends_at_fetch_time():
    # 220 的真实片段：6-21 打 1 折，7-05 恢复原价，之后一直到采集时刻
    conn = make_conn([
        (220, "2018-06-21 21:04:55", 9.99, 0.99, 90),
        (220, "2018-07-05 20:59:36", 9.99, 9.99, 0),
    ])
    build_cleaned_prices(conn)

    rows = segments(conn)
    assert rows[0][:4] == (220, "2018-06-21 21:04:55", "2018-07-05 20:59:36", 0.99)
    assert rows[1][:4] == (220, "2018-07-05 20:59:36", FETCHED_AT, 9.99)
    assert rows[0][4] == 13.9963  # 14 天少 5 分 19 秒


def test_two_records_at_same_moment_share_one_segment():
    # Left 4 Dead 2 的真实片段：9-24 同一时刻插进一条 0 元的记录，两条都要留，结束时刻都是 9-28
    conn = make_conn([
        (550, "2020-09-24 17:42:56", 0.0, 0.0, 0),
        (550, "2020-09-24 17:42:56", 9.99, 1.99, 80),
        (550, "2020-09-28 17:22:33", 9.99, 9.99, 0),
    ])
    build_cleaned_prices(conn)

    ended = [row[2] for row in segments(conn)]
    assert ended == ["2020-09-28 17:22:33", "2020-09-28 17:22:33", FETCHED_AT]


def test_build_twice_rebuilds_from_scratch():
    conn = make_conn([
        (220, "2018-06-21 21:04:55", 9.99, 0.99, 90),
        (440, "2013-08-04 13:58:49", 9.99, 9.99, 0),
    ])
    build_cleaned_prices(conn)
    with conn:
        conn.execute("DELETE FROM raw_price_history WHERE appid = 440")
    build_cleaned_prices(conn)

    assert [row[0] for row in segments(conn)] == [220]
