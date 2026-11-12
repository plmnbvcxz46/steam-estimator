import sqlite3

from crawler.appids import pick_appids


def test_pick_appids_prefix_is_stable_and_none_means_all():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE raw_ars_players_2018 (appid INTEGER PRIMARY KEY)")
    conn.executemany("INSERT INTO raw_ars_players_2018 VALUES (?)", [(i,) for i in range(1, 101)])

    all_ids = pick_appids(conn, None)
    assert sorted(all_ids) == list(range(1, 101))  # None：全部都在

    # 固定种子：取前 10 个就是取前 30 个的前 10 个，扩大规模时已爬的不浪费
    assert pick_appids(conn, 10) == pick_appids(conn, 30)[:10]
