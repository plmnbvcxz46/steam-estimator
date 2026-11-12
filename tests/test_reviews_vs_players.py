"""探查图的取数：评测数读清洗表，查不到评测数的游戏不出现。"""

import sqlite3

from viz.reviews_vs_players import load_points


def test_load_points_reads_cleaned_table_and_skips_games_without_counts():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE raw_ars_players_2018 (appid INTEGER PRIMARY KEY, players INTEGER)")
    conn.execute(
        "CREATE TABLE cleaned_review_counts (appid INTEGER, cutoff_date TEXT, total_reviews INTEGER)"
    )
    # 20 号游戏已下架或评测数为 0，清洗表里没有它
    conn.execute("INSERT INTO raw_ars_players_2018 VALUES (10, 5000), (20, 300)")
    conn.execute("INSERT INTO cleaned_review_counts VALUES (10, '2018-07-01', 120)")

    assert load_points(conn) == [(10, 120, 5000)]
