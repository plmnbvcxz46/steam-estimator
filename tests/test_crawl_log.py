import sqlite3

from crawler import crawl_log


def make_conn():
    # ":memory:" 是只存在于内存里的临时数据库，测试完自动消失
    conn = sqlite3.connect(":memory:")
    crawl_log.ensure_table(conn)
    return conn


def test_done_keys_skips_failures():
    conn = make_conn()
    crawl_log.record(conn, "store_items", 440, 200)
    crawl_log.record(conn, "store_items", 999, "未收录")
    crawl_log.record(conn, "store_items", 123, "timeout")  # 失败，不算完成
    crawl_log.record(conn, "store_items", 456, 500)

    # request_key 统一按文本存，所以返回的是字符串
    assert crawl_log.done_keys(conn, "store_items") == {"440", "999"}


def test_retry_success_overwrites_failure():
    conn = make_conn()
    crawl_log.record(conn, "store_items", 123, "timeout")
    assert crawl_log.done_keys(conn, "store_items") == set()

    crawl_log.record(conn, "store_items", 123, 200)  # 重试成功
    assert crawl_log.done_keys(conn, "store_items") == {"123"}


def test_done_keys_are_per_source():
    conn = make_conn()
    crawl_log.record(conn, "store_items", 440, 200)
    assert crawl_log.done_keys(conn, "reviews") == set()
