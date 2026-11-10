import copy
import json
import sqlite3
from pathlib import Path

from crawler import crawl_log
from crawler.http import CrawlError
from crawler.sources import review_counts

FIXTURES = Path(__file__).parent / "fixtures"


def load_summary():
    return json.loads((FIXTURES / "review_summary_220.json").read_text(encoding="utf-8"))


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
    """假的 get_json：purchase_type=1 返回样本；purchase_type=0 返回改过数字的样本。"""
    calls = []

    def fake_get_json(url, params=None, min_interval=None):
        query = json.loads(params["input_json"])
        purchase_type = query["purchase_type"]
        calls.append(purchase_type)
        if purchase_type in failing_purchase_types:
            raise CrawlError("timeout", "模拟超时")
        response = copy.deepcopy(load_summary())
        if purchase_type == 0:
            response["response"]["query_summary"]["total_reviews"] = 36595
            response["response"]["query_summary"]["total_positive"] = 35480
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
    assert read_counts(conn) == {"全部": (53440, 51896), "Steam内购买": (36595, 35480)}
    # 两次请求各记一条日志
    assert crawl_log.done_keys(conn, "review_counts") == {
        "220|2018-07-01|全部",
        "220|2018-07-01|Steam内购买",
    }


def test_crawl_resumes_without_repeating(monkeypatch):
    conn = sqlite3.connect(":memory:")
    fake = fake_get_json_factory()
    monkeypatch.setattr(review_counts, "get_json", fake)

    review_counts.crawl_review_counts(conn, [220], "2018-07-01")
    review_counts.crawl_review_counts(conn, [220], "2018-07-01")  # 重跑：不该再请求

    assert fake.calls == [1, 0]  # 只在第一次跑时请求了两次


def test_crawl_failure_is_retried_next_time(monkeypatch):
    conn = sqlite3.connect(":memory:")
    monkeypatch.setattr(review_counts, "get_json", fake_get_json_factory(failing_purchase_types={0}))
    review_counts.crawl_review_counts(conn, [220], "2018-07-01")

    # 内购买那次失败：“全部”已写入，内购买没有
    assert read_counts(conn) == {"全部": (53440, 51896)}

    # 下次重跑恢复正常，只补内购买，不重复请求“全部”
    fake = fake_get_json_factory()
    monkeypatch.setattr(review_counts, "get_json", fake)
    review_counts.crawl_review_counts(conn, [220], "2018-07-01")
    assert fake.calls == [0]
    assert read_counts(conn) == {"全部": (53440, 51896), "Steam内购买": (36595, 35480)}
