import json
import sqlite3
from pathlib import Path

from crawler import appdetails, crawl_log
from crawler.appdetails import parse_appdetails
from crawler.http import CrawlError

FIXTURES = Path(__file__).parent / "fixtures"


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_parse_paid_game():
    row = parse_appdetails(413150, load("appdetails_413150.json"))
    assert row == {
        "appid": 413150,
        "name": "Stardew Valley",
        "app_type": "game",
        "is_free": 0,
        "release_date": "Feb 26, 2016",
        "initial_price_usd": 14.99,  # 接口给的是美分 1499
        "genres": "Indie|RPG|Simulation",
    }


def test_parse_free_game_has_no_price():
    row = parse_appdetails(440, load("appdetails_440.json"))
    assert row["is_free"] == 1
    assert row["initial_price_usd"] is None


def test_parse_missing_app_returns_none():
    assert parse_appdetails(1, load("appdetails_1.json")) is None


# ---- 采集主循环：用假的 get_json 代替联网，数据库用内存临时库 ----

def make_conn():
    return sqlite3.connect(":memory:")


def fake_get_json_factory(failing=()):
    """返回一个假的 get_json：从样本文件里取数据；failing 里的 appid 模拟请求失败。"""
    calls = []

    def fake_get_json(url, params=None, min_interval=None):
        appid = params["appids"]
        calls.append(appid)
        if appid in failing:
            raise CrawlError("timeout", "模拟超时")
        return load(f"appdetails_{appid}.json")

    fake_get_json.calls = calls
    return fake_get_json


def test_crawl_writes_rows_and_log(monkeypatch):
    conn = make_conn()
    monkeypatch.setattr(appdetails, "get_json", fake_get_json_factory())

    appdetails.crawl_appdetails(conn, [413150, 440, 1])

    rows = conn.execute("SELECT appid, name FROM raw_appdetails ORDER BY appid").fetchall()
    assert rows == [(440, "Team Fortress 2"), (413150, "Stardew Valley")]  # 1 未收录，无数据行
    assert crawl_log.done_keys(conn, "appdetails") == {"413150", "440", "1"}


def test_crawl_resumes_without_repeating(monkeypatch):
    conn = make_conn()
    fake = fake_get_json_factory()
    monkeypatch.setattr(appdetails, "get_json", fake)

    appdetails.crawl_appdetails(conn, [440])
    appdetails.crawl_appdetails(conn, [440, 413150])  # 重跑：440 已完成，只该请求 413150

    assert fake.calls == [440, 413150]


def test_crawl_failure_is_logged_and_retried_next_time(monkeypatch):
    conn = make_conn()
    monkeypatch.setattr(appdetails, "get_json", fake_get_json_factory(failing={440}))
    appdetails.crawl_appdetails(conn, [440, 413150])

    # 440 失败：没有数据行，也不算完成；413150 不受影响
    assert crawl_log.done_keys(conn, "appdetails") == {"413150"}
    assert conn.execute("SELECT COUNT(*) FROM raw_appdetails").fetchone()[0] == 1

    # 下次重跑，440 恢复正常，应该被补上
    monkeypatch.setattr(appdetails, "get_json", fake_get_json_factory())
    appdetails.crawl_appdetails(conn, [440, 413150])
    assert crawl_log.done_keys(conn, "appdetails") == {"413150", "440"}


def test_pick_appids_prefix_is_stable_and_none_means_all():
    conn = make_conn()
    conn.execute("CREATE TABLE raw_ars_players_2018 (appid INTEGER PRIMARY KEY)")
    conn.executemany("INSERT INTO raw_ars_players_2018 VALUES (?)", [(i,) for i in range(1, 101)])

    all_ids = appdetails.pick_appids(conn, None)
    assert sorted(all_ids) == list(range(1, 101))  # None：全部都在

    # 固定种子：取前 10 个就是取前 30 个的前 10 个，扩大规模时已爬的不浪费
    assert appdetails.pick_appids(conn, 10) == appdetails.pick_appids(conn, 30)[:10]
