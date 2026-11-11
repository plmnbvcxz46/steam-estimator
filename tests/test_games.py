import sqlite3

from crawler.sources import appdetails
from pipeline.games import build_cleaned_games, clean_genres, date_shape, parse_release_date


def test_clean_genres_drops_status_words():
    # 取自真实数据：791390 带 Early Access，488910 带 Free To Play
    assert clean_genres("Casual|Indie|RPG|Early Access") == "Casual|Indie|RPG"
    assert clean_genres("Free To Play|Indie|Strategy") == "Indie|Strategy"


def test_clean_genres_keeps_real_genres_unchanged():
    assert clean_genres("Action|Adventure|Indie") == "Action|Adventure|Indie"


def test_parse_release_date():
    assert parse_release_date("Sep 26, 2013") == "2013-09-26"


def test_parse_release_date_pads_single_digit_day():
    # 商店写 "Sep 8"，日只有一位；输出要补成两位，否则按字符串比较日期会出错
    assert parse_release_date("Sep 8, 2016") == "2016-09-08"


def test_parse_release_date_returns_none_when_not_a_date():
    assert parse_release_date("Coming soon") is None


def test_date_shape_groups_same_pattern():
    assert date_shape("Mar 2017") == date_shape("Apr 2018") == "aaa 9999"
    assert date_shape("Coming soon") == "aaaaaa aaaa"


def make_conn(raw_rows):
    """建一个内存数据库，放进几行 raw_appdetails。每行是 (appid, app_type, release_date, genres)。"""
    conn = sqlite3.connect(":memory:")
    conn.execute(appdetails.CREATE_TABLE_SQL)
    for appid, app_type, release_date, genres in raw_rows:
        conn.execute(
            "INSERT INTO raw_appdetails VALUES (?, ?, ?, 0, ?, NULL, ?, '2026-11-01 00:00:00')",
            (appid, f"name{appid}", app_type, release_date, genres),
        )
    conn.commit()
    return conn


def cleaned_rows(conn):
    return conn.execute("SELECT * FROM cleaned_games ORDER BY appid").fetchall()


def test_build_cleans_date_and_genres():
    conn = make_conn([(10, "game", "Sep 8, 2016", "Indie|Early Access")])
    build_cleaned_games(conn)
    assert cleaned_rows(conn) == [(10, "name10", "2016-09-08", "store", "Indie")]


def test_build_skips_non_games_and_unparsed_dates():
    conn = make_conn([
        (10, "game", "Sep 8, 2016", "Indie"),
        (20, "dlc", "Sep 8, 2016", "Indie"),
        (30, "game", "Coming soon", "Indie"),
    ])
    build_cleaned_games(conn)
    assert [row[0] for row in cleaned_rows(conn)] == [10]


def test_build_twice_rebuilds_from_scratch():
    # 重跑时整张表重建：raw 里已经没有的游戏不会留在 cleaned 里，也不会出现重复行
    conn = make_conn([(10, "game", "Sep 8, 2016", "Indie"), (11, "game", "Sep 9, 2016", "Indie")])
    build_cleaned_games(conn)
    with conn:
        conn.execute("DELETE FROM raw_appdetails WHERE appid = 11")
    build_cleaned_games(conn)
    assert [row[0] for row in cleaned_rows(conn)] == [10]
