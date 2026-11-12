import sqlite3

from crawler.http import CrawlError
from crawler.sources import itad

# 假的换编号结果：ITAD 收录了 220 和 440，没收录 999999
KNOWN_IDS = {
    220: "018d937f-012f-73b8-ab2c-898516969e6a",
    440: "018d937f-0000-0000-0000-000000000440",
}


# ---- 换编号：用假的 post_json 代替联网，数据库用内存临时库 ----


def fake_post_json_factory(fail=False):
    """返回一个假的 post_json：记下每次请求问了哪些游戏，按 KNOWN_IDS 回答，查不到的给 None。"""
    calls = []

    def fake_post_json(url, body, params=None, min_interval=None):
        calls.append(body)
        if fail:
            raise CrawlError("timeout", "模拟超时")
        answer = {}
        for key in body:
            appid = int(key.removeprefix("app/"))
            answer[key] = KNOWN_IDS.get(appid)
        return answer

    fake_post_json.calls = calls
    return fake_post_json


def log_statuses(conn):
    rows = conn.execute("SELECT request_key, status FROM raw_crawl_log WHERE source = 'itad_ids'")
    return dict(rows)


def test_lookup_writes_found_and_not_found(monkeypatch):
    conn = sqlite3.connect(":memory:")
    monkeypatch.setattr(itad, "post_json", fake_post_json_factory())

    itad.crawl_itad_ids(conn, [220, 440, 999999], "测试密钥")

    rows = conn.execute("SELECT appid, itad_id FROM raw_itad_ids ORDER BY appid").fetchall()
    # 没收录的也有一行，编号为空
    assert rows == [(220, KNOWN_IDS[220]), (440, KNOWN_IDS[440]), (999999, None)]
    assert log_statuses(conn) == {"220": "200", "440": "200", "999999": "未收录"}


def test_lookup_resumes_without_repeating(monkeypatch):
    conn = sqlite3.connect(":memory:")
    fake = fake_post_json_factory()
    monkeypatch.setattr(itad, "post_json", fake)

    itad.crawl_itad_ids(conn, [220, 999999], "测试密钥")
    itad.crawl_itad_ids(conn, [220, 999999, 440], "测试密钥")  # 重跑：前两款已有定论，只该问 440

    assert fake.calls == [["app/220", "app/999999"], ["app/440"]]


def test_lookup_failure_is_logged_and_retried_next_time(monkeypatch):
    conn = sqlite3.connect(":memory:")
    monkeypatch.setattr(itad, "post_json", fake_post_json_factory(fail=True))
    itad.crawl_itad_ids(conn, [220, 440], "测试密钥")
    assert log_statuses(conn) == {"220": "timeout", "440": "timeout"}

    fake = fake_post_json_factory()
    monkeypatch.setattr(itad, "post_json", fake)
    itad.crawl_itad_ids(conn, [220, 440], "测试密钥")
    assert fake.calls == [["app/220", "app/440"]]  # 上次失败的不算有定论，重跑时再请求
    assert log_statuses(conn) == {"220": "200", "440": "200"}
