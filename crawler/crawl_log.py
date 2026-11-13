"""raw_crawl_log：记录每个请求的结局，重跑时靠它判断哪些不用再请求。

这里的函数只执行 SQL、不提交事务：采集时“写数据”和“记日志”要放在同一个
事务里，由调用者统一提交。
"""

from common.clock import now_utc_str

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS raw_crawl_log (
    source      TEXT NOT NULL,
    request_key TEXT NOT NULL,
    status      TEXT NOT NULL,
    fetched_at  TEXT NOT NULL,
    PRIMARY KEY (source, request_key)
)
"""

# 除了 HTTP 状态码，采集器自己会记下面三种结局。写成常量是为了防止手敲错字：
# “未收录”错一个字就不在 DONE_STATUSES 里，会每次重跑都重新请求，而且没有任何提示。
NOT_FOUND = "未收录"  # 接口明确说没有这款游戏（如已下架）
EMPTY = "空结果"  # 请求成功，但一条数据都没有
PARSE_ERROR = "parse_error"  # 返回的内容和预期对不上，下次重试

# 已有定论的结局，重跑时跳过；其余（超时、断线、429、5xx、parse_error 等）都要重试
DONE_STATUSES = ("200", NOT_FOUND, EMPTY)


def ensure_table(conn):
    conn.execute(CREATE_TABLE_SQL)


def record(conn, source, request_key, status):
    """记一条结局；同一个请求以后再记会覆盖旧的（失败后重试成功就变成成功）。"""
    conn.execute(
        "INSERT OR REPLACE INTO raw_crawl_log (source, request_key, status, fetched_at)"
        " VALUES (?, ?, ?, ?)",
        (source, str(request_key), str(status), now_utc_str()),
    )


def done_keys(conn, source):
    """返回这个数据源里已有定论的 request_key 集合。"""
    rows = conn.execute(
        "SELECT request_key, status FROM raw_crawl_log WHERE source = ?", (source,)
    )
    return {key for key, status in rows if status in DONE_STATUSES}
