import json
import sqlite3
from pathlib import Path

from crawler import crawl_log
from crawler.http import CrawlError
from crawler.sources import store_items
from crawler.sources.store_items import parse_item

FIXTURES = Path(__file__).parent / "fixtures"

# 样本文件是一次真实请求的返回，里面依次是这 5 款：
# 付费游戏、免费游戏、捆绑包排在前面的、正在打折的、商店里查不到的
BATCH_APPIDS = [413150, 440, 639840, 1200, 852]


def load_items():
    text = (FIXTURES / "store_items_batch.json").read_text(encoding="utf-8")
    return json.loads(text)["response"]["store_items"]


def item_of(appid):
    return load_items()[BATCH_APPIDS.index(appid)]


def test_parse_paid_game():
    row, tag_rows = parse_item(item_of(413150))
    assert row == {
        "appid": 413150,
        "name": "Stardew Valley",
        "app_type": 0,
        "is_free": 0,
        "is_early_access": 0,
        "release_ts": 1456509578,
        "initial_price_usd": 14.99,  # 接口给的是美分 "1499"
    }
    assert len(tag_rows) == 20
    # 第一个标签权重最高，排第 1
    assert tag_rows[0] == {"appid": 413150, "tagid": 87918, "weight": 859, "position": 1}


def test_free_game_has_no_price_even_with_purchase_options():
    # Team Fortress 2 免费，但挂着一个含它的合集（The Orange Box），那不是它的价格
    row, _ = parse_item(item_of(440))
    assert row["is_free"] == 1
    assert row["initial_price_usd"] is None


def test_price_skips_bundle_and_takes_the_games_own_package():
    # 第一个购买项是 2.60 美元的捆绑包，游戏自己卖 3.99
    row, _ = parse_item(item_of(639840))
    assert row["initial_price_usd"] == 3.99


def test_price_is_the_original_price_when_on_sale():
    # 采集时正在打折：现价 1.99，原价 4.99
    row, _ = parse_item(item_of(1200))
    assert row["initial_price_usd"] == 4.99


# ---- 采集主循环：用假的 get_json 代替联网，数据库用内存临时库 ----


def fake_get_json_factory(fail=False):
    """返回一个假的 get_json：记下每次请求查了哪些游戏，返回样本文件里对应的那几款。"""
    calls = []

    def fake_get_json(url, params=None, min_interval=None):
        asked = [entry["appid"] for entry in json.loads(params["input_json"])["ids"]]
        calls.append(asked)
        if fail:
            raise CrawlError("timeout", "模拟超时")
        return {"response": {"store_items": [item_of(appid) for appid in asked]}}

    fake_get_json.calls = calls
    return fake_get_json


def log_statuses(conn):
    rows = conn.execute("SELECT request_key, status FROM raw_crawl_log WHERE source = 'store_items'")
    return dict(rows)


def test_crawl_writes_items_tags_and_log(monkeypatch):
    conn = sqlite3.connect(":memory:")
    monkeypatch.setattr(store_items, "get_json", fake_get_json_factory())

    store_items.crawl_store_items(conn, BATCH_APPIDS)

    appids = [a for (a,) in conn.execute("SELECT appid FROM raw_store_items ORDER BY appid")]
    assert appids == [440, 1200, 413150, 639840]  # 852 查不到，不写数据行
    assert log_statuses(conn)["852"] == "未收录"
    assert log_statuses(conn)["440"] == "200"
    tag_count = conn.execute("SELECT COUNT(*) FROM raw_store_tags WHERE appid = 639840").fetchone()[0]
    assert tag_count == 9  # 这款游戏只有 9 个标签


def test_crawl_resumes_without_repeating(monkeypatch):
    conn = sqlite3.connect(":memory:")
    fake = fake_get_json_factory()
    monkeypatch.setattr(store_items, "get_json", fake)

    store_items.crawl_store_items(conn, [440, 852])
    store_items.crawl_store_items(conn, [440, 852, 413150])  # 重跑：前两款已有定论，只该请求 413150

    assert fake.calls == [[440, 852], [413150]]


def test_crawl_failure_is_logged_and_retried_next_time(monkeypatch):
    conn = sqlite3.connect(":memory:")
    monkeypatch.setattr(store_items, "get_json", fake_get_json_factory(fail=True))
    store_items.crawl_store_items(conn, [440, 413150])
    assert log_statuses(conn) == {"440": "timeout", "413150": "timeout"}

    fake = fake_get_json_factory()
    monkeypatch.setattr(store_items, "get_json", fake)
    store_items.crawl_store_items(conn, [440, 413150])
    assert fake.calls == [[440, 413150]]  # 上次失败的不算有定论，重跑时再请求
    assert log_statuses(conn) == {"440": "200", "413150": "200"}


def test_recrawl_replaces_old_tags():
    conn = sqlite3.connect(":memory:")
    store_items.ensure_tables(conn)
    item = item_of(639840)
    store_items.save_batch(conn, [639840], [item])
    item["tags"] = item["tags"][:3]  # 假设重爬时这款游戏只剩 3 个标签
    store_items.save_batch(conn, [639840], [item])

    tag_count = conn.execute("SELECT COUNT(*) FROM raw_store_tags").fetchone()[0]
    assert tag_count == 3
