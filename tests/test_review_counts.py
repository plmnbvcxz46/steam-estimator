import copy
import json
import sqlite3
from pathlib import Path

from crawler import crawl_log
from crawler.http import CrawlError
from crawler.sources import review_counts

FIXTURES = Path(__file__).parent / "fixtures"

# 一个游戏发的请求数：all、steam_purchase，加上每种语言各一次
REQUEST_COUNT = 2 + len(review_counts.LANGUAGES)


def load_summary():
    return json.loads((FIXTURES / "review_summary_220.json").read_text(encoding="utf-8"))


def test_parse_cutoff_pads_month_and_day():
    # 手敲 2018-7-1 也要存成 2018-07-01，否则后面按字符串查不到
    assert review_counts.parse_cutoff("2018-7-1") == "2018-07-01"


def test_cutoff_ts_is_start_of_day_utc():
    # 2018-07-01 零点（UTC）；和早期探索版本的训练集截止时刻一致
    assert review_counts.cutoff_ts("2018-07-01") == 1530403200


def test_build_input_json():
    params = review_counts.build_input_json(220, "2018-07-01", purchase_type=0)
    assert params["appid"] == 220
    assert params["purchase_type"] == 0
    assert params["languages"] == ["all"]  # 不传只统计英文
    assert params["date_range_start"] == 1  # 传 0 会被当成“没传”
    assert params["date_range_end"] == 1530403200


def test_build_input_json_with_language():
    params = review_counts.build_input_json(220, "2018-07-01", languages=("schinese",))
    assert params["languages"] == ["schinese"]


def test_parse_review_summary_real_response():
    # 样本来自 appid 220 在 2018-07-01 零点前的真实返回（评测正文已去掉）
    assert review_counts.parse_review_summary(load_summary()) == (53440, 51896)


# ---- 采集主循环：用假的 get_json 代替联网，数据库用内存临时库 ----

def fake_get_json_factory(failing_purchase_types=()):
    """假的 get_json，按请求参数返回不同的数字，方便检查数字写进了哪一行：
    purchase_type=0 -> 36595 / 35480；languages=["schinese"] -> 1000 / 900；其余 -> 样本原数字。
    calls 记下每次请求的 (purchase_type, languages)。
    """
    calls = []

    def fake_get_json(url, params=None, min_interval=None):
        query = json.loads(params["input_json"])
        purchase_type = query["purchase_type"]
        languages = tuple(query["languages"])
        calls.append((purchase_type, languages))
        if purchase_type in failing_purchase_types:
            raise CrawlError("timeout", "模拟超时")
        response = copy.deepcopy(load_summary())
        summary = response["response"]["query_summary"]
        if purchase_type == 0:
            summary["total_reviews"] = 36595
            summary["total_positive"] = 35480
        if languages == ("schinese",):
            summary["total_reviews"] = 1000
            summary["total_positive"] = 900
        return response

    fake_get_json.calls = calls
    return fake_get_json


def read_counts(conn):
    rows = conn.execute(
        "SELECT query, total, positive FROM raw_review_counts WHERE appid = 220"
    )
    return {query: (total, positive) for query, total, positive in rows}


def test_crawl_writes_one_row_per_request(monkeypatch):
    conn = sqlite3.connect(":memory:")
    monkeypatch.setattr(review_counts, "get_json", fake_get_json_factory())

    review_counts.crawl_review_counts(conn, [220], "2018-07-01")

    # 一次请求一行，总数和好评数存在同一行
    counts = read_counts(conn)
    assert counts["all"] == (53440, 51896)
    assert counts["steam_purchase"] == (36595, 35480)
    assert counts["lang:english"] == (53440, 51896)
    assert counts["lang:schinese"] == (1000, 900)  # 语言请求的数字写进了对应的行
    assert len(counts) == REQUEST_COUNT

    # 每次请求各记一条日志
    keys = crawl_log.done_keys(conn, "review_counts")
    assert len(keys) == REQUEST_COUNT
    assert "220|2018-07-01|all" in keys
    assert "220|2018-07-01|lang:schinese" in keys


def test_crawl_resumes_without_repeating(monkeypatch):
    conn = sqlite3.connect(":memory:")
    fake = fake_get_json_factory()
    monkeypatch.setattr(review_counts, "get_json", fake)

    review_counts.crawl_review_counts(conn, [220], "2018-07-01")
    review_counts.crawl_review_counts(conn, [220], "2018-07-01")  # 重跑：不该再请求

    assert len(fake.calls) == REQUEST_COUNT  # 只在第一次跑时发了请求


def test_crawl_failure_is_retried_next_time(monkeypatch):
    conn = sqlite3.connect(":memory:")
    monkeypatch.setattr(review_counts, "get_json", fake_get_json_factory(failing_purchase_types={0}))
    review_counts.crawl_review_counts(conn, [220], "2018-07-01")

    # 内购买那次失败：all 已写入，steam_purchase 没有
    assert "steam_purchase" not in read_counts(conn)
    assert read_counts(conn)["all"] == (53440, 51896)

    # 下次重跑恢复正常，只补 steam_purchase，不重复请求别的
    fake = fake_get_json_factory()
    monkeypatch.setattr(review_counts, "get_json", fake)
    review_counts.crawl_review_counts(conn, [220], "2018-07-01")
    assert fake.calls == [(0, ("all",))]
    assert read_counts(conn)["steam_purchase"] == (36595, 35480)


def test_crawl_with_several_workers_writes_same_rows(monkeypatch):
    # 4 路并行：请求由几个线程同时发，结果应该和一个一个发完全一样
    conn = sqlite3.connect(":memory:")
    fake = fake_get_json_factory()
    monkeypatch.setattr(review_counts, "get_json", fake)

    review_counts.crawl_review_counts(conn, [220], "2018-07-01", workers=4)

    counts = read_counts(conn)
    assert len(counts) == REQUEST_COUNT
    assert counts["steam_purchase"] == (36595, 35480)
    assert counts["lang:schinese"] == (1000, 900)  # 结果没有和别的请求串行
    assert len(fake.calls) == REQUEST_COUNT


def test_delisted_game_is_recorded_and_not_retried(monkeypatch):
    # 已下架的游戏（如 538510）接口返回 {"response": {}}：不写数据行，记“未收录”，重跑不再请求
    conn = sqlite3.connect(":memory:")
    calls = []

    def fake_get_json(url, params=None, min_interval=None):
        calls.append(params)
        return {"response": {}}

    monkeypatch.setattr(review_counts, "get_json", fake_get_json)

    review_counts.crawl_review_counts(conn, [538510], "2018-07-01")
    review_counts.crawl_review_counts(conn, [538510], "2018-07-01")

    assert conn.execute("SELECT COUNT(*) FROM raw_review_counts").fetchone()[0] == 0
    assert len(crawl_log.done_keys(conn, "review_counts")) == REQUEST_COUNT
    assert len(calls) == REQUEST_COUNT  # 第二次跑没有再发请求
