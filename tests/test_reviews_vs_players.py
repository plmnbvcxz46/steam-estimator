"""探查图的取数：每款游戏只取“全部评测”那一行，查不到评测数的游戏不出现。"""

import sqlite3

from viz.reviews_vs_players import load_points


def test_load_points_takes_all_row_and_skips_games_without_counts():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE raw_ars_players_2018 (appid INTEGER PRIMARY KEY, players INTEGER)")
    conn.execute(
        "CREATE TABLE raw_review_counts (appid INTEGER, cutoff_date TEXT, query TEXT, total INTEGER)"
    )
    # 10 号游戏有两种数法的评测数；20 号游戏已下架，评测表里没有它
    conn.execute("INSERT INTO raw_ars_players_2018 VALUES (10, 5000), (20, 300)")
    conn.execute(
        "INSERT INTO raw_review_counts VALUES"
        " (10, '2018-07-01', 'all', 120), (10, '2018-07-01', 'lang:english', 80)"
    )

    assert load_points(conn) == [(10, 120, 5000)]
