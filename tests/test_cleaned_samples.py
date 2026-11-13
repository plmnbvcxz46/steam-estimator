import sqlite3

from crawler.sources import ars
from pipeline import games, review_counts
from pipeline.samples import build_samples, review_count_features

CUTOFF = "2018-07-01"


def make_conn():
    """建好样本表要读的三张上游表，空的。"""
    conn = sqlite3.connect(":memory:")
    conn.execute(ars.CREATE_TABLE_SQL)
    conn.execute(games.CREATE_TABLE_SQL)
    conn.execute(review_counts.CREATE_TABLE_SQL)
    return conn


def add_ars(conn, appid, players):
    conn.execute(
        "INSERT INTO raw_ars_players_2018 (appid, title, players, fetched_at)"
        " VALUES (?, 'x', ?, '2026-11-10 00:00:00')",
        (appid, players),
    )


def add_game(conn, appid):
    conn.execute(
        "INSERT INTO cleaned_games (appid, name, release_date, release_date_source, tags)"
        " VALUES (?, 'x', '2015-01-01', 'store', 'Action')",
        (appid,),
    )


def add_reviews(conn, appid, total):
    # 只关心评测数，其他计数都填 0
    columns = ["appid", "cutoff_date", "total_reviews", "positive_reviews", "steam_purchase_reviews"]
    values = [appid, CUTOFF, total, 0, 0]
    for language in review_counts.LANGUAGES:
        columns.append("reviews_" + language)
        values.append(0)
    placeholders = ", ".join("?" * len(values))
    conn.execute(
        f"INSERT INTO cleaned_review_counts ({', '.join(columns)}) VALUES ({placeholders})", values
    )


def sample_rows(conn):
    return conn.execute(
        "SELECT sample_id, appid, cutoff_date, split, truth_value, total_reviews"
        " FROM cleaned_samples ORDER BY appid"
    ).fetchall()


def test_keeps_only_games_in_all_three_tables():
    conn = make_conn()
    # 1：三张表都有，留下
    add_ars(conn, 1, 5000)
    add_game(conn, 1)
    add_reviews(conn, 1, 40)
    # 2：Ars 里有、有评测，但不是游戏（真实数据里有 52 款这样的）
    add_ars(conn, 2, 3000)
    add_reviews(conn, 2, 30)
    # 3：是游戏、有评测，但 Ars 里没有，没有答案
    add_game(conn, 3)
    add_reviews(conn, 3, 20)
    conn.commit()

    build_samples(conn)

    assert sample_rows(conn) == [("train:1:2018-07-01", 1, CUTOFF, "train", 5000, 40)]


def test_keeps_games_with_few_reviews():
    # 评测数门槛留给训练时设，样本表里 1 条评测的也要有
    conn = make_conn()
    add_ars(conn, 1, 800)
    add_game(conn, 1)
    add_reviews(conn, 1, 1)
    conn.commit()

    build_samples(conn)

    assert [row[5] for row in sample_rows(conn)] == [1]


def test_rebuild_replaces_old_rows():
    # 重跑是整张表重建，不会把同一批样本写两遍
    conn = make_conn()
    add_ars(conn, 1, 5000)
    add_game(conn, 1)
    add_reviews(conn, 1, 40)
    conn.commit()

    build_samples(conn)
    build_samples(conn)

    assert len(sample_rows(conn)) == 1


def test_review_count_features_are_shares_of_total():
    # 100 条评测：80 条好评、60 条 Steam 内购买；英语 50、简中 30，其余 12 种语言 0
    language_reviews = {language: 0 for language in review_counts.LANGUAGES}
    language_reviews["english"] = 50
    language_reviews["schinese"] = 30

    features = review_count_features(100, 80, 60, language_reviews)

    assert features["positive_rate"] == 0.8
    assert features["steam_purchase_ratio"] == 0.6
    assert features["share_english"] == 0.5
    assert features["share_schinese"] == 0.3
    # 13 种之外的语言占剩下的 20 条
    assert features["share_other"] == 0.2
    assert len(features) == 16
