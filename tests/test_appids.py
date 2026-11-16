import sqlite3

from crawler.appids import TRAIN_CUTOFF, TRUTH_TABLES, pick_appids


def make_conn():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE raw_ars_players_2018 (appid INTEGER PRIMARY KEY)")
    conn.executemany("INSERT INTO raw_ars_players_2018 VALUES (?)", [(i,) for i in range(1, 101)])
    for table in TRUTH_TABLES.values():
        conn.execute(f"CREATE TABLE {table} (appid INTEGER, report_date TEXT)")
    return conn


def test_pick_appids_prefix_is_stable_and_none_means_all():
    conn = make_conn()

    all_targets = pick_appids(conn, None)
    assert sorted(all_targets) == [(i, TRAIN_CUTOFF) for i in range(1, 101)]  # None：全部都在

    # 固定种子：取前 10 个就是取前 30 个的前 10 个，扩大规模时已爬的不浪费
    assert pick_appids(conn, 10) == pick_appids(conn, 30)[:10]


def test_truth_rows_keep_their_own_date_and_duplicates_once():
    # 真实数据里有：游戏 5 也在 Ars 表里（两个截止日都要），两个来源公布同一款同一天
    conn = make_conn()
    gamalytic, manual = TRUTH_TABLES["gamalytic"], TRUTH_TABLES["manual"]
    conn.execute(f"INSERT INTO {gamalytic} VALUES (5, '2022-07-10')")
    conn.execute(f"INSERT INTO {gamalytic} VALUES (500, '2023-02-16')")
    conn.execute(f"INSERT INTO {manual} VALUES (500, '2023-02-16')")

    targets = pick_appids(conn, None)
    assert (5, TRAIN_CUTOFF) in targets
    assert targets[-2:] == [(5, "2022-07-10"), (500, "2023-02-16")]
    assert len(targets) == 102
