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


# ---- 价格历史 ----


def entry(timestamp, price, regular, cut):
    """拼一条接口格式的价格记录，字段和真实返回一样（只留我们用到的）。"""
    return {
        "timestamp": timestamp,
        "shop": {"id": 61, "name": "Steam"},
        "deal": {
            "price": {"amount": price, "currency": "USD"},
            "regular": {"amount": regular, "currency": "USD"},
            "cut": cut,
        },
    }


# 220 的两条真实记录，夏令时 +02:00、冬令时 +01:00 各一条
HISTORY_220 = [
    entry("2018-06-21T23:04:55+02:00", 0.99, 9.99, 90),
    entry("2018-02-19T23:20:18+01:00", 9.99, 9.99, 0),
]


def test_to_utc_handles_both_offsets():
    # 夏令时减 2 小时，冬令时减 1 小时；夏令时这条跨过了零点
    assert itad.to_utc_str("2018-06-21T23:04:55+02:00") == "2018-06-21 21:04:55"
    assert itad.to_utc_str("2018-02-20T00:20:18+01:00") == "2018-02-19 23:20:18"


def fake_get_json_factory(histories):
    """返回一个假的 get_json：按请求的 ITAD 编号从 histories 里取历史，记下问了哪些编号。"""
    calls = []

    def fake_get_json(url, params=None, min_interval=None):
        calls.append(params["id"])
        return histories[params["id"]]

    fake_get_json.calls = calls
    return fake_get_json


def history_conn():
    """一个已换好编号的库：220、440 有编号，999999 未收录。"""
    conn = sqlite3.connect(":memory:")
    itad.ensure_tables(conn)
    with conn:
        conn.executemany(
            "INSERT INTO raw_itad_ids VALUES (?, ?, '2026-11-12 00:00:00')",
            [(220, KNOWN_IDS[220]), (440, KNOWN_IDS[440]), (999999, None)],
        )
    return conn


def history_statuses(conn):
    rows = conn.execute("SELECT request_key, status FROM raw_crawl_log WHERE source = 'itad_history'")
    return dict(rows)


def test_history_writes_rows_and_skips_games_without_id(monkeypatch):
    conn = history_conn()
    # 440 在 ITAD 有编号，但 Steam 美国区一条记录都没有
    fake = fake_get_json_factory({KNOWN_IDS[220]: HISTORY_220, KNOWN_IDS[440]: []})
    monkeypatch.setattr(itad, "get_json", fake)

    itad.crawl_price_history(conn, [220, 440, 999999], "测试密钥")

    assert fake.calls == [KNOWN_IDS[220], KNOWN_IDS[440]]  # 999999 没编号，不请求
    rows = conn.execute(
        "SELECT appid, country, changed_at, price, regular, cut FROM raw_price_history ORDER BY changed_at"
    ).fetchall()
    assert rows == [
        (220, "US", "2018-02-19 22:20:18", 9.99, 9.99, 0),
        (220, "US", "2018-06-21 21:04:55", 0.99, 9.99, 90),
    ]
    assert history_statuses(conn) == {"220": "200", "440": "空结果"}


def test_history_resumes_without_repeating(monkeypatch):
    conn = history_conn()
    fake = fake_get_json_factory({KNOWN_IDS[220]: HISTORY_220, KNOWN_IDS[440]: []})
    monkeypatch.setattr(itad, "get_json", fake)

    itad.crawl_price_history(conn, [220], "测试密钥")
    itad.crawl_price_history(conn, [220, 440], "测试密钥")  # 重跑：220 已有定论，只该问 440

    assert fake.calls == [KNOWN_IDS[220], KNOWN_IDS[440]]


def test_history_keeps_two_purchase_options_at_same_moment(monkeypatch):
    # 真实情况（appid 40700）：同一时刻两个购买项一起打折，原价 14.99 和 4.99，两条都要留下
    conn = history_conn()
    two_options = [
        entry("2021-02-11T21:56:18+01:00", 5.99, 14.99, 60),
        entry("2021-02-11T21:56:18+01:00", 1.99, 4.99, 60),
    ]
    monkeypatch.setattr(itad, "get_json", fake_get_json_factory({KNOWN_IDS[220]: two_options}))

    itad.crawl_price_history(conn, [220], "测试密钥")

    rows = conn.execute("SELECT price, regular FROM raw_price_history ORDER BY regular").fetchall()
    assert rows == [(1.99, 4.99), (5.99, 14.99)]
    assert history_statuses(conn) == {"220": "200"}
