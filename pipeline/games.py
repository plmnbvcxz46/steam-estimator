"""清洗商店信息：raw_store_items + raw_store_tags + raw_tag_names -> cleaned_games。

三张 raw 表是批量接口的原样结果，这里把它们合成后面能直接用的一张表：
- 只留游戏，去掉 DLC、原声带等
- 发行日从时间戳换成 "2013-09-26" 这样的日期
- 标签按权重排好，去掉不是分类的状态词，用 | 连成一串

cleaned 表是派生数据：每次运行都整张表重建，结果只取决于 raw 表。

进了这张表的行保证有发行日：没有发行日的游戏不写入，记到日志里。
"""

import logging
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

from common.log import setup_logging
from common.paths import DB_PATH

logger = logging.getLogger(__name__)

# raw_store_items.app_type 里 0 表示游戏，其他数字是 DLC、原声带、软件等
APP_TYPE_GAME = 0

# Steam 的时间戳记的是按美国太平洋时间定的发行时刻（多是当地白天）。
# 按 UTC 转，这一刻常常已经是第二天：实测 1221 款里有 173 款会晚一天
STORE_TIMEZONE = ZoneInfo("America/Los_Angeles")

# 发行日的出处。现在只有商店一种；以后抢先体验的游戏会改用第一条评测的日期，
# 那时这一列会多出一个取值
RELEASE_DATE_SOURCE_STORE = "store"

# 这两个标签说的是游戏“现在”的状态，不是分类。
# 训练样例的截止日是 2018 年，留着它们等于用了未来的信息
NOT_TAGS = {"Early Access", "Free to Play"}

CREATE_TABLE_SQL = """
CREATE TABLE cleaned_games (
    appid               INTEGER PRIMARY KEY,
    name                TEXT NOT NULL,
    release_date        TEXT NOT NULL,
    release_date_source TEXT NOT NULL,
    tags                TEXT NOT NULL
)
"""

INSERT_SQL = """
INSERT INTO cleaned_games (appid, name, release_date, release_date_source, tags)
VALUES (:appid, :name, :release_date, :release_date_source, :tags)
"""


def release_ts_to_date(release_ts):
    """把商店的发行时间戳（秒）换成太平洋时间的 YYYY-MM-DD。"""
    return datetime.fromtimestamp(release_ts, STORE_TIMEZONE).strftime("%Y-%m-%d")


def clean_tags(tag_names):
    """去掉状态标签，把剩下的用 | 连起来。tag_names 要已经按权重排好。"""
    kept = []
    for name in tag_names:
        if name not in NOT_TAGS:
            kept.append(name)
    return "|".join(kept)


def load_tag_names(conn):
    """读出每款游戏的标签名，返回 {appid: [标签名, ...]}，每款内部按权重从高到低。"""
    # 权重相同时按 position 排，position 是接口返回时的先后，保证每次结果一样
    rows = conn.execute(
        """
        SELECT t.appid, n.name
        FROM raw_store_tags AS t
        JOIN raw_tag_names AS n ON n.tagid = t.tagid
        ORDER BY t.appid, t.weight DESC, t.position ASC
        """
    )
    tags_by_appid = {}
    for appid, name in rows:
        # setdefault：这款第一次出现时先放一个空列表，再往里追加
        tags_by_appid.setdefault(appid, []).append(name)
    return tags_by_appid


def build_cleaned_games(conn):
    """读三张 raw 表，重建 cleaned_games。

    不是游戏的、没有发行日的不写入；没有发行日的每款记一行 warning，最后打印汇总。
    """
    raw_rows = conn.execute(
        "SELECT appid, name, app_type, release_ts FROM raw_store_items ORDER BY appid"
    ).fetchall()
    tags_by_appid = load_tag_names(conn)

    cleaned_rows = []
    not_game_count = 0
    no_release_count = 0

    for appid, name, app_type, release_ts in raw_rows:
        if app_type != APP_TYPE_GAME:
            logger.info("appid=%d 不是游戏（app_type=%d），不写入", appid, app_type)
            not_game_count += 1
            continue

        # NULL 是接口没给；0 是商店没填时的占位，按时间戳转会变成 1970 年，同样当作没有
        if release_ts is None or release_ts == 0:
            logger.warning("appid=%d 没有发行日，不写入: release_ts=%r", appid, release_ts)
            no_release_count += 1
            continue

        # 少数游戏一个标签都没有，get 取不到时给空列表，tags 就是空字符串
        tag_names = tags_by_appid.get(appid, [])

        cleaned_rows.append(
            {
                "appid": appid,
                "name": name,
                "release_date": release_ts_to_date(release_ts),
                "release_date_source": RELEASE_DATE_SOURCE_STORE,
                "tags": clean_tags(tag_names),
            }
        )

    # 删旧表、建新表、写入放在同一个事务里：中途出错就整体撤销，旧表原样还在。
    # 要手动写 BEGIN，因为 sqlite3 模块只在 INSERT 这类语句前才自动开事务，
    # DROP 和 CREATE 不在其列
    with conn:
        conn.execute("BEGIN")
        conn.execute("DROP TABLE IF EXISTS cleaned_games")
        conn.execute(CREATE_TABLE_SQL)
        conn.executemany(INSERT_SQL, cleaned_rows)

    logger.info(
        "raw_store_items 共 %d 行：写入 %d，不是游戏 %d，没有发行日 %d",
        len(raw_rows),
        len(cleaned_rows),
        not_game_count,
        no_release_count,
    )


def main():
    """命令行入口：python -m pipeline.games"""
    setup_logging("games.log")

    conn = sqlite3.connect(DB_PATH)
    try:
        build_cleaned_games(conn)
    finally:
        # 不管中途有没有出错，都把数据库连接关掉
        conn.close()


if __name__ == "__main__":
    main()
