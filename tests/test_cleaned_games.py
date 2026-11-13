import sqlite3

from crawler.sources import store_items
from pipeline.games import build_cleaned_games, clean_tags, release_ts_to_date

# 测试用的标签表，名字和 tagid 取自真实的 raw_tag_names
TAG_NAMES = [(113, "Free to Play"), (493, "Early Access"), (492, "Indie"), (597, "Casual"), (9, "Strategy")]


def make_conn(items, tags):
    """建一个内存数据库并放进测试行。

    items 每行是 (appid, app_type, release_ts)；tags 每行是 (appid, tagid, weight, position)。
    """
    conn = sqlite3.connect(":memory:")
    store_items.ensure_tables(conn)
    conn.executemany("INSERT INTO raw_tag_names VALUES (?, ?)", TAG_NAMES)
    for appid, app_type, release_ts in items:
        conn.execute(
            "INSERT INTO raw_store_items (appid, name, app_type, is_free, release_ts,"
            " is_early_access, initial_price_usd, fetched_at)"
            " VALUES (?, ?, ?, 0, ?, 0, 9.99, '2026-11-01 00:00:00')",
            (appid, f"name{appid}", app_type, release_ts),
        )
    conn.executemany("INSERT INTO raw_store_tags VALUES (?, ?, ?, ?)", tags)
    conn.commit()
    return conn


def cleaned_rows(conn):
    return conn.execute("SELECT * FROM cleaned_games ORDER BY appid").fetchall()


def test_clean_tags_drops_status_words():
    assert clean_tags(["Casual", "Indie", "Early Access"]) == "Casual|Indie"
    assert clean_tags(["Free to Play", "Indie", "Strategy"]) == "Indie|Strategy"


def test_release_ts_to_date_uses_pacific_time():
    # 取自真实数据 44100：商店页写 Feb 18, 2010。
    # 这个时间戳是 UTC 2 月 19 日 00:20，按 UTC 转会晚一天
    assert release_ts_to_date(1266538800) == "2010-02-18"
    # 取自真实数据 413150（Stardew Valley）：商店页写 Feb 26, 2016
    assert release_ts_to_date(1456509578) == "2016-02-26"


def test_build_sorts_tags_by_weight_and_drops_status_words():
    # 取自真实数据 791390 的形状：Strategy 和 Indie 权重相同，按 position 排
    conn = make_conn(
        [(10, 0, 1456509578)],
        [(10, 493, 294, 4), (10, 492, 1917, 3), (10, 9, 1917, 2), (10, 597, 1961, 1)],
    )
    build_cleaned_games(conn)
    assert cleaned_rows(conn) == [(10, "name10", "2016-02-26", "store", "Casual|Strategy|Indie")]


def test_build_writes_empty_tags_when_game_has_none():
    # 真实库里有 2 款游戏一个标签都没有
    conn = make_conn([(10, 0, 1456509578)], [])
    build_cleaned_games(conn)
    assert cleaned_rows(conn) == [(10, "name10", "2016-02-26", "store", "")]


def test_build_skips_non_games_and_missing_release_dates():
    conn = make_conn(
        [
            (10, 0, 1456509578),
            (20, 1, 1456509578),  # 不是游戏
            (30, 0, None),  # 接口没给发行日
            (40, 0, 0),  # 商店没填发行日的占位
        ],
        [],
    )
    build_cleaned_games(conn)
    assert [row[0] for row in cleaned_rows(conn)] == [10]


def test_build_twice_rebuilds_from_scratch():
    # 重跑时整张表重建：raw 里已经没有的游戏不会留在 cleaned 里，也不会出现重复行
    conn = make_conn([(10, 0, 1456509578), (11, 0, 1456509578)], [])
    build_cleaned_games(conn)
    with conn:
        conn.execute("DELETE FROM raw_store_items WHERE appid = 11")
    build_cleaned_games(conn)
    assert [row[0] for row in cleaned_rows(conn)] == [10]
