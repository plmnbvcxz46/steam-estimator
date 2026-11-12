"""清洗评测计数：raw_review_counts -> cleaned_review_counts。

raw 表里一款游戏的一个截止日有 15 行，每个查询口径一行（全部、Steam 内购买、13 种语言）。
这里把它们合成一行，后面建样本、画图都直接读这一行，不用每次自己拼。

只存条数不存占比：占比是“谁除以谁”的选择，留到建样本表时再算。
只排除评测数为 0 的游戏；“评测太少”的门槛会随交叉验证调整，放在建样本表时做。

cleaned 表是派生数据：每次运行都整张表重建，结果只取决于 raw 表。
"""

import logging
import sqlite3

from common.log import setup_logging
from common.paths import DB_PATH

logger = logging.getLogger(__name__)

# 采集时请求的 13 种语言，写法是 Steam 的语言代码（koreana、latam 都是 Steam 自己的叫法）
LANGUAGES = [
    "brazilian",
    "english",
    "french",
    "german",
    "japanese",
    "koreana",
    "latam",
    "polish",
    "russian",
    "schinese",
    "spanish",
    "tchinese",
    "turkish",
]

# 每款游戏应有的全部口径：全部、Steam 内购买，加上每种语言一个
EXPECTED_QUERIES = {"all", "steam_purchase"}
for language in LANGUAGES:
    EXPECTED_QUERIES.add("lang:" + language)

CREATE_TABLE_SQL = """
CREATE TABLE cleaned_review_counts (
    appid                  INTEGER NOT NULL,
    cutoff_date            TEXT NOT NULL,
    total_reviews          INTEGER NOT NULL,
    positive_reviews       INTEGER NOT NULL,
    steam_purchase_reviews INTEGER NOT NULL,
    reviews_brazilian      INTEGER NOT NULL,
    reviews_english        INTEGER NOT NULL,
    reviews_french         INTEGER NOT NULL,
    reviews_german         INTEGER NOT NULL,
    reviews_japanese       INTEGER NOT NULL,
    reviews_koreana        INTEGER NOT NULL,
    reviews_latam          INTEGER NOT NULL,
    reviews_polish         INTEGER NOT NULL,
    reviews_russian        INTEGER NOT NULL,
    reviews_schinese       INTEGER NOT NULL,
    reviews_spanish        INTEGER NOT NULL,
    reviews_tchinese       INTEGER NOT NULL,
    reviews_turkish        INTEGER NOT NULL,
    PRIMARY KEY (appid, cutoff_date)
)
"""

INSERT_SQL = """
INSERT INTO cleaned_review_counts VALUES (
    :appid, :cutoff_date, :total_reviews, :positive_reviews, :steam_purchase_reviews,
    :reviews_brazilian, :reviews_english, :reviews_french, :reviews_german,
    :reviews_japanese, :reviews_koreana, :reviews_latam, :reviews_polish,
    :reviews_russian, :reviews_schinese, :reviews_spanish, :reviews_tchinese,
    :reviews_turkish
)
"""


def group_by_game(raw_rows):
    """把 raw 的多行按 (appid, cutoff_date) 归到一起。

    返回 {(appid, cutoff_date): {口径: (total, positive)}}。
    """
    grouped = {}
    for appid, cutoff_date, query, total, positive in raw_rows:
        key = (appid, cutoff_date)
        # setdefault：这款第一次出现时先放一个空字典，再往里填口径
        grouped.setdefault(key, {})[query] = (total, positive)
    return grouped


def merge_queries(appid, cutoff_date, counts):
    """把一款游戏 15 个口径的计数合成 cleaned 表的一行（dict）。

    counts 是 {口径: (total, positive)}。口径不齐说明采集没跑完，直接报错，
    不悄悄跳过：跳过会让这款游戏从此在后面所有分析里消失，却没人知道。
    """
    if set(counts) != EXPECTED_QUERIES:
        missing = sorted(EXPECTED_QUERIES - set(counts))
        raise ValueError(f"appid={appid} cutoff_date={cutoff_date} 口径不齐，缺 {missing}，先把采集跑完")

    total, positive = counts["all"]
    # 好评数只取“全部”口径：分口径的好评率大多只有几条评测撑着，用不上
    row = {
        "appid": appid,
        "cutoff_date": cutoff_date,
        "total_reviews": total,
        "positive_reviews": positive,
        "steam_purchase_reviews": counts["steam_purchase"][0],
    }
    for language in LANGUAGES:
        row["reviews_" + language] = counts["lang:" + language][0]
    return row


def build_cleaned_review_counts(conn):
    """读 raw_review_counts，重建 cleaned_review_counts。

    评测数为 0 的不写入，最后在汇总日志里记个数。
    """
    raw_rows = conn.execute(
        "SELECT appid, cutoff_date, query, total, positive FROM raw_review_counts"
        " ORDER BY appid, cutoff_date"
    ).fetchall()
    grouped = group_by_game(raw_rows)

    cleaned_rows = []
    zero_review_count = 0
    for (appid, cutoff_date), counts in grouped.items():
        row = merge_queries(appid, cutoff_date, counts)
        # 截止日前一条评测都没有，k = 玩家数 ÷ 评测数 无从算起
        if row["total_reviews"] == 0:
            zero_review_count += 1
            continue
        cleaned_rows.append(row)

    # 删旧表、建新表、写入放在同一个事务里：中途出错就整体撤销，旧表原样还在。
    # 要手动写 BEGIN，因为 sqlite3 模块只在 INSERT 这类语句前才自动开事务
    with conn:
        conn.execute("BEGIN")
        conn.execute("DROP TABLE IF EXISTS cleaned_review_counts")
        conn.execute(CREATE_TABLE_SQL)
        conn.executemany(INSERT_SQL, cleaned_rows)

    logger.info(
        "raw_review_counts 共 %d 款（游戏 × 截止日）：写入 %d，评测数为 0 的 %d",
        len(grouped),
        len(cleaned_rows),
        zero_review_count,
    )


def main():
    """命令行入口：python -m pipeline.review_counts"""
    setup_logging("cleaned_review_counts.log")

    conn = sqlite3.connect(DB_PATH)
    try:
        build_cleaned_review_counts(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
