import json
import sqlite3

from crawler.http import CrawlError
from crawler.sources import reviews, store_items
from crawler.sources.reviews import make_windows, parse_window

CUTOFF = "2018-07-01"
CUTOFF_TS = 1530403200  # 2018-07-01 零点（UTC）
REVIEW_START_TS = 1380585600  # 2013-10-01 零点（UTC）


# ---- 切段 ----


def test_windows_cover_release_to_cutoff_without_overlap():
    # 2015-01-01 上架的游戏
    windows = make_windows(1420070400, CUTOFF)

    assert [w[0] for w in windows] == [1, 2, 3, 4, 5]
    assert windows[0][1] == 1  # 第一段从 1 开始，早于上架的评测也算进来
    assert windows[-1][2] == CUTOFF_TS  # 最后一段到截止日零点，和评测计数一样
    for before, after in zip(windows, windows[1:]):
        assert after[1] == before[2] + 1  # 首尾相接、不重叠


def test_windows_without_release_start_from_review_system():
    # 真实情况：104 款游戏商店没给上架时刻（为空或为 0）
    windows = make_windows(None, CUTOFF)
    # 第二段的起点离 2013-10-01 正好五分之一的区间
    assert windows[1][1] == REVIEW_START_TS + (CUTOFF_TS - REVIEW_START_TS) // 5 + 1


# ---- 解析：返回的样子取自真实请求 ----


def review(review_id, created, at_review, forever):
    """拼一条接口格式的评测（只留我们用到的字段）；at_review 为 None 表示接口没给这个字段。"""
    author = {"steamid": "1", "playtime_forever": forever}
    if at_review is not None:
        author["playtime_at_review"] = at_review
    return {"recommendationid": review_id, "timestamp_created": created, "author": author}


def test_parse_keeps_total_and_reviews():
    # 220 截止日前最新的一条：写评测时 422 分钟，采集时 744 分钟
    response = {
        "response": {
            "query_summary": {"num_reviews": 1, "total_reviews": 53436},
            "reviews": [review("43200691", 1530401659, 422, 744)],
        }
    }
    total, reviews = parse_window(response)

    assert total == 53436
    assert reviews == [
        {
            "review_id": "43200691",
            "created_at": "2018-06-30 23:34:19",
            "playtime_at_review_min": 422,
            "playtime_forever_min": 744,
        }
    ]


def test_parse_review_without_playtime_at_review_stores_none():
    # 真实情况：2016 年的一段里有 4 到 25 条评测不带 playtime_at_review
    response = {
        "response": {
            "query_summary": {"total_reviews": 1},
            "reviews": [review("1", 1470000000, None, 300)],
        }
    }
    _, reviews = parse_window(response)
    assert reviews[0]["playtime_at_review_min"] is None


def test_parse_empty_window_has_no_reviews_key():
    # 真实情况：这一段没有评测时，返回里根本没有 "reviews"
    response = {"response": {"query_summary": {"total_reviews": 0}, "cursor": "*"}}
    assert parse_window(response) == (0, [])


def test_parse_delisted_game_returns_none():
    assert parse_window({"response": {}}) is None



# ---- 采集主循环：用假的 get_json 代替联网，数据库用内存临时库 ----


def fake_get_json_factory(fail_windows=()):
    """假的 get_json：每段回一条评测，总数按段号给（第 1 段 10 条、第 2 段 20 条……）。

    靠请求里的 date_range_start 认出是第几段；calls 记下每次请求的 (appid, 段起点)。
    fail_windows 里的段模拟超时。
    """
    calls = []

    def fake_get_json(url, params=None, min_interval=None):
        query = json.loads(params["input_json"])
        appid = query["appid"]
        start = query["date_range_start"]
        calls.append((appid, start))
        windows = make_windows(None, CUTOFF)
        window = [w for w, s, _ in windows if s == start][0]
        if window in fail_windows:
            raise CrawlError("timeout", "模拟超时")
        return {
            "response": {
                "query_summary": {"total_reviews": window * 10},
                "reviews": [review(f"{appid}-{window}", query["date_range_end"], 60, 120)],
            }
        }

    fake_get_json.calls = calls
    return fake_get_json


def crawl_conn():
    """一个有商店表的内存库；220 没给上架时刻（为 0），按评测系统上线日切段，好让假接口认段。"""
    conn = sqlite3.connect(":memory:")
    conn.execute(store_items.CREATE_ITEMS_SQL)
    with conn:
        conn.execute("INSERT INTO raw_store_items VALUES (220, 'Half-Life 2', 0, 0, 0, 0, 9.99, 'x')")
    return conn


def test_crawl_writes_windows_and_reviews(monkeypatch):
    conn = crawl_conn()
    monkeypatch.setattr(reviews, "get_json", fake_get_json_factory())

    reviews.crawl_reviews(conn, [220], CUTOFF)

    windows = conn.execute("SELECT window, total FROM raw_review_windows ORDER BY window").fetchall()
    assert windows == [(1, 10), (2, 20), (3, 30), (4, 40), (5, 50)]
    sampled = conn.execute("SELECT review_id, window FROM raw_reviews ORDER BY window").fetchall()
    assert sampled == [("220-1", 1), ("220-2", 2), ("220-3", 3), ("220-4", 4), ("220-5", 5)]


def test_crawl_retries_only_failed_windows(monkeypatch):
    conn = crawl_conn()
    monkeypatch.setattr(reviews, "get_json", fake_get_json_factory(fail_windows=(3,)))
    reviews.crawl_reviews(conn, [220], CUTOFF)
    assert conn.execute("SELECT COUNT(*) FROM raw_review_windows").fetchone()[0] == 4

    # 重跑：成功的 4 段已有定论，只该再请求第 3 段
    fake = fake_get_json_factory()
    monkeypatch.setattr(reviews, "get_json", fake)
    reviews.crawl_reviews(conn, [220], CUTOFF)

    third_start = make_windows(None, CUTOFF)[2][1]
    assert fake.calls == [(220, third_start)]
    assert conn.execute("SELECT COUNT(*) FROM raw_review_windows").fetchone()[0] == 5
