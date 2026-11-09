"""时间戳：统一用 UTC，写进 raw 表的 fetched_at 等字段。"""

from datetime import UTC, datetime


def now_utc_str():
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
