import sqlite3

from crawler import crawl_log, multi_machine
from crawler.sources import review_counts
from crawler.sources.appdetails import pick_appids

ARS_SQL = """
CREATE TABLE raw_ars_players_2018 (
    appid      INTEGER PRIMARY KEY,
    title      TEXT NOT NULL,
    players    INTEGER NOT NULL,
    fetched_at TEXT NOT NULL
)
"""


def make_main_conn(appids):
    """内存里的主库：Ars 表里放这些 appid，再建好评测计数表和采集日志表。"""
    conn = sqlite3.connect(":memory:")
    conn.execute(ARS_SQL)
    for appid in appids:
        conn.execute(
            "INSERT INTO raw_ars_players_2018 VALUES (?, ?, 1000, '2026-11-01 00:00:00')",
            (appid, f"game{appid}"),
        )
    conn.execute(review_counts.CREATE_TABLE_SQL)
    crawl_log.ensure_table(conn)
    conn.commit()
    return conn


def add_count(conn, appid, query, total, status=200):
    """模拟采集器做完了一次请求：成功就写数据行，并记日志。"""
    key = review_counts.make_request_key(appid, "2018-07-01", query)
    with conn:
        if status == 200:
            conn.execute(
                "INSERT INTO raw_review_counts VALUES (?, '2018-07-01', ?, ?, 0, '2026-11-01 00:00:00')",
                (appid, query, total),
            )
        crawl_log.record(conn, review_counts.SOURCE, key, status)


def part_appids(path):
    part = sqlite3.connect(path)
    appids = [appid for (appid,) in part.execute("SELECT appid FROM raw_ars_players_2018")]
    part.close()
    return appids


def test_split_into_parts_sizes():
    assert multi_machine.split_into_parts(list(range(10)), 3) == [[0, 1, 2, 3], [4, 5, 6], [7, 8, 9]]


def test_split_covers_every_unfinished_game_once(tmp_path):
    conn = make_main_conn(range(1, 11))
    # 采集顺序里的第一个游戏已经全部爬完，不该再分给任何人
    order = pick_appids(conn, None)
    finished = order[0]
    for request in review_counts.REQUESTS:
        add_count(conn, finished, request["query"], 5)

    sizes = multi_machine.split(conn, 3, out_dir=tmp_path)

    assert sizes == [3, 3, 3]
    part2 = part_appids(tmp_path / "part2.db")
    part3 = part_appids(tmp_path / "part3.db")
    # 本机留前 3 个，两台服务器各拿后面的 3 个，互不重复
    assert sorted(part2) == sorted(order[4:7])
    assert sorted(part3) == sorted(order[7:10])


def test_merge_adds_rows_and_success_wins(tmp_path):
    main = make_main_conn([1, 2])
    add_count(main, 1, "all", 100)
    add_count(main, 2, "all", None, status="timeout")  # 本机这次失败了

    # 另一台机器的库：appid 2 成功了；appid 1 也有一行（数字故意不同，看会不会覆盖本机的）
    other_path = tmp_path / "other.db"
    other = sqlite3.connect(other_path)
    other.execute(review_counts.CREATE_TABLE_SQL)
    crawl_log.ensure_table(other)
    add_count(other, 2, "all", 200)
    add_count(other, 1, "all", 999)
    other.close()

    added = multi_machine.merge(main, other_path)

    assert added == 1
    rows = main.execute("SELECT appid, total FROM raw_review_counts ORDER BY appid").fetchall()
    assert rows == [(1, 100), (2, 200)]  # 本机已有的行不被覆盖，缺的补上
    # appid 2 在本机记的是失败，合并后变成完成，重跑时不会再请求
    assert "2|2018-07-01|all" in crawl_log.done_keys(main, review_counts.SOURCE)
