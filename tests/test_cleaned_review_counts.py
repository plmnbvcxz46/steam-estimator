import sqlite3

import pytest

from crawler.sources import review_counts as raw_review_counts
from pipeline.review_counts import EXPECTED_QUERIES, LANGUAGES, build_cleaned_review_counts

CUTOFF = "2018-07-01"


def insert_game(conn, appid, total, skip_query=None):
    """给一款游戏插满 15 个口径。

    为了好核对，每个口径用不同的数：全部 = total，Steam 内购买 = total - 1，
    第 i 种语言 = i。skip_query 用来模拟采集没跑完、少了一个口径。
    """
    rows = [(appid, CUTOFF, "all", total, total // 2)]
    rows.append((appid, CUTOFF, "steam_purchase", max(total - 1, 0), 0))
    for i, language in enumerate(LANGUAGES):
        rows.append((appid, CUTOFF, "lang:" + language, min(i, total), 0))
    for row in rows:
        if row[2] == skip_query:
            continue
        conn.execute(
            "INSERT INTO raw_review_counts VALUES (?, ?, ?, ?, ?, '2026-11-10 00:00:00')", row
        )
    conn.commit()


def make_conn():
    conn = sqlite3.connect(":memory:")
    conn.execute(raw_review_counts.CREATE_TABLE_SQL)
    return conn


def cleaned_appids(conn):
    return [appid for (appid,) in conn.execute("SELECT appid FROM cleaned_review_counts ORDER BY appid")]


def test_expected_queries_are_fifteen():
    # 采集时就是 15 个口径；这个数变了说明语言表改了，清洗表的列也要跟着改
    assert len(EXPECTED_QUERIES) == 15


def test_merges_fifteen_rows_into_one():
    conn = make_conn()
    insert_game(conn, 10, total=20)
    build_cleaned_review_counts(conn)

    conn.row_factory = sqlite3.Row  # 让查询结果能按列名取值
    row = conn.execute("SELECT * FROM cleaned_review_counts").fetchone()
    assert row["appid"] == 10
    assert row["cutoff_date"] == CUTOFF
    assert row["total_reviews"] == 20
    assert row["positive_reviews"] == 10
    assert row["steam_purchase_reviews"] == 19
    assert row["reviews_brazilian"] == 0  # 第 0 种语言
    assert row["reviews_turkish"] == 12  # 第 12 种语言


def test_skips_games_with_zero_reviews():
    conn = make_conn()
    insert_game(conn, 10, total=20)
    insert_game(conn, 20, total=0)
    build_cleaned_review_counts(conn)
    assert cleaned_appids(conn) == [10]


def test_missing_query_raises():
    # 采集中断时会出现口径不齐，这时要报错让人去补采，而不是悄悄少一款
    conn = make_conn()
    insert_game(conn, 10, total=20, skip_query="lang:schinese")
    with pytest.raises(ValueError, match="lang:schinese"):
        build_cleaned_review_counts(conn)


def test_build_twice_rebuilds_from_scratch():
    conn = make_conn()
    insert_game(conn, 10, total=20)
    insert_game(conn, 11, total=30)
    build_cleaned_review_counts(conn)
    with conn:
        conn.execute("DELETE FROM raw_review_counts WHERE appid = 11")
    build_cleaned_review_counts(conn)
    assert cleaned_appids(conn) == [10]
