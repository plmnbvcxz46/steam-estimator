"""raw_crawl_log：记录每个请求的结局，重跑时靠它判断哪些不用再请求。

这里的函数只执行 SQL、不提交事务：采集时“写数据”和“记日志”要放在同一个
事务里，由调用者统一提交。
"""

from datetime import UTC, datetime

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS raw_crawl_log (
    source      TEXT NOT NULL,
    request_key TEXT NOT NULL,
    status      TEXT NOT NULL,
    fetched_at  TEXT NOT NULL,
    PRIMARY KEY (source, request_key)
)
"""

# 已有定论的结局，重跑时跳过；其余（超时、断线、429、5xx 等）都要重试
DONE_STATUSES = ("200", "未收录", "空结果")


def ensure_table(conn):
    conn.execute(CREATE_TABLE_SQL)


def record(conn, source, request_key, status):
    """记一条结局；同一个请求以后再记会覆盖旧的（失败后重试成功就变成成功）。"""
    fetched_at = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        "INSERT OR REPLACE INTO raw_crawl_log (source, request_key, status, fetched_at)"
        " VALUES (?, ?, ?, ?)",
        (source, str(request_key), str(status), fetched_at),
    )


def done_keys(conn, source):
    """返回这个数据源里已有定论的 request_key 集合。"""
    rows = conn.execute(
        "SELECT request_key, status FROM raw_crawl_log WHERE source = ?", (source,)
    )
    return {key for key, status in rows if status in DONE_STATUSES}
