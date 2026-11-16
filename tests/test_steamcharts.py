import sqlite3
from pathlib import Path

from crawler.http import CrawlError
from crawler.sources import steamcharts

# 从 Half-Life 2（220）的真网页截的片段：Last 30 Days、最近两个整月、最早的 2012 年 7 月
PAGE_220 = (Path(__file__).parent / "fixtures" / "steamcharts_220.html").read_text()


def test_parse_skips_last_30_days():
    rows = steamcharts.parse_months(220, PAGE_220)

    # Last 30 Days 不是整月，不要；最早一个月的增减是 "-"，不影响解析
    assert rows == [
        {"appid": 220, "month": "2026-10", "avg_players": 1513.57, "peak_players": 2686},
        {"appid": 220, "month": "2026-09", "avg_players": 1321.33, "peak_players": 2327},
        {"appid": 220, "month": "2012-07", "avg_players": 1144.80, "peak_players": 1895},
    ]


# ---- 逐款采集：用假的 get_html 代替联网，数据库用内存临时库 ----


def fake_get_html_factory(pages):
    """返回一个假的 get_html：pages 里有的 appid 返回那张网页，没有的当作没收录。
    calls 记下依次请求了哪些 appid。"""
    calls = []

    def fake_get_html(url, min_interval=None, not_found_marker=None):
        appid = int(url.rsplit("/", 1)[1])
        calls.append(appid)
        if appid not in pages:
            raise CrawlError("未收录", f"未收录: {url}")
        return pages[appid]

    fake_get_html.calls = calls
    return fake_get_html


def log_statuses(conn):
    return dict(conn.execute("SELECT request_key, status FROM raw_crawl_log WHERE source = 'steamcharts'"))


def test_crawl_writes_rows_and_resumes(monkeypatch):
    conn = sqlite3.connect(":memory:")
    fake = fake_get_html_factory({220: PAGE_220})
    monkeypatch.setattr(steamcharts, "get_html", fake)

    steamcharts.crawl_steamcharts(conn, [220, 999999])
    steamcharts.crawl_steamcharts(conn, [220, 999999, 440])  # 重跑：前两款已有定论，只该请求 440

    assert fake.calls == [220, 999999, 440]
    assert log_statuses(conn) == {"220": "200", "999999": "未收录", "440": "未收录"}
    count = conn.execute("SELECT COUNT(*) FROM raw_charts_monthly WHERE appid = 220").fetchone()[0]
    assert count == 3


def test_unreadable_page_is_logged_and_retried_next_time(monkeypatch):
    # 网站改版、页面里找不到月份表：记 parse_error，不存数据，下次重跑再请求
    conn = sqlite3.connect(":memory:")
    fake = fake_get_html_factory({220: "<html><title>Half-Life 2 - Steam Charts</title></html>"})
    monkeypatch.setattr(steamcharts, "get_html", fake)

    steamcharts.crawl_steamcharts(conn, [220])
    steamcharts.crawl_steamcharts(conn, [220])

    assert fake.calls == [220, 220]
    assert log_statuses(conn) == {"220": "parse_error"}
    assert conn.execute("SELECT COUNT(*) FROM raw_charts_monthly").fetchone()[0] == 0
