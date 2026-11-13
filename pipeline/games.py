"""清洗商店信息：raw_store_items + raw_store_tags + raw_tag_names + raw_reviews -> cleaned_games。

把 raw 表合成后面能直接用的一张表：
- 只留游戏，去掉 DLC、原声带等
- 上架日取三个时刻里最早的（商店上架时刻、最早上架时刻、抽到的最早评测），
  从时间戳换成 "2013-09-26" 这样的日期
- 标签按权重排好，去掉不是分类的状态词，用 | 连成一串

cleaned 表是派生数据：每次运行都整张表重建，结果只取决于 raw 表。

进了这张表的行保证有发行日：没有发行日的游戏不写入，记到日志里。
"""

import logging
import sqlite3
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from common.log import setup_logging
from common.paths import DB_PATH

logger = logging.getLogger(__name__)

# raw_store_items.app_type 里 0 表示游戏，其他数字是 DLC、原声带、软件等
APP_TYPE_GAME = 0

# Steam 的时间戳记的是按美国太平洋时间定的发行时刻（多是当地白天）。
# 按 UTC 转，这一刻常常已经是第二天：实测 1221 款里有 173 款会晚一天
STORE_TIMEZONE = ZoneInfo("America/Los_Angeles")

# 上架日的出处，存进 release_date_source，以后能区分哪些是准的、哪些是近似的
RELEASE_DATE_SOURCE_STORE = "store"  # 商店现在写的上架时刻
RELEASE_DATE_SOURCE_ORIGINAL = "store_original"  # 商店留着的最早上架时刻（抢先体验开卖等）
RELEASE_DATE_SOURCE_REVIEW = "first_review"  # 抽到的最早评测，可能比真正的第一条晚

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


def load_first_review_ts(conn):
    """每款游戏抽到的最早一条评测的时刻，返回 {appid: Unix 秒}。

    created_at 是 UTC 的 "2014-05-29 07:34:46"，格式固定，按字符串比大小就是按时间比，
    所以直接在 SQL 里取 MIN，再换成时间戳，好和商店的两个时刻比较。
    """
    rows = conn.execute("SELECT appid, MIN(created_at) FROM raw_reviews GROUP BY appid")
    first_review_ts = {}
    for appid, created_at in rows:
        moment = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)
        first_review_ts[appid] = int(moment.timestamp())
    return first_review_ts


def pick_release(release_ts, original_release_ts, first_review_ts):
    """三个时刻里取最早的，返回（时刻, 出处）；一个都没有时返回 (None, None)。

    抢先体验转正式版、老游戏重新上架时，商店会把上架时刻改成后来的日期；
    最早上架时刻只有部分游戏有；评测早于这两个，说明那时已经能买了。
    """
    candidates = []
    # 商店上架时刻为 0 是没填时的占位，按时间戳转会变成 1970 年，当作没有
    if release_ts:
        candidates.append((release_ts, RELEASE_DATE_SOURCE_STORE))
    if original_release_ts is not None:
        candidates.append((original_release_ts, RELEASE_DATE_SOURCE_ORIGINAL))
    if first_review_ts is not None:
        candidates.append((first_review_ts, RELEASE_DATE_SOURCE_REVIEW))
    if not candidates:
        return None, None
    # 按时刻比；万一时刻相同，取排在前面的
    return min(candidates, key=lambda candidate: candidate[0])


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
    """读四张 raw 表，重建 cleaned_games。

    不是游戏的、三个时刻都没有的不写入；后者每款记一行 warning，最后打印汇总。
    """
    raw_rows = conn.execute(
        "SELECT appid, name, app_type, release_ts, original_release_ts"
        " FROM raw_store_items ORDER BY appid"
    ).fetchall()
    tags_by_appid = load_tag_names(conn)
    first_review_by_appid = load_first_review_ts(conn)

    cleaned_rows = []
    not_game_count = 0
    no_release_count = 0
    # 每种出处各用了多少款，最后写进日志
    source_counts = {
        RELEASE_DATE_SOURCE_STORE: 0,
        RELEASE_DATE_SOURCE_ORIGINAL: 0,
        RELEASE_DATE_SOURCE_REVIEW: 0,
    }

    for appid, name, app_type, release_ts, original_release_ts in raw_rows:
        if app_type != APP_TYPE_GAME:
            logger.info("appid=%d 不是游戏（app_type=%d），不写入", appid, app_type)
            not_game_count += 1
            continue

        # 没抽到评测的游戏不在字典里，get 取不到就是 None
        first_review_ts = first_review_by_appid.get(appid)
        chosen_ts, source = pick_release(release_ts, original_release_ts, first_review_ts)
        if chosen_ts is None:
            logger.warning("appid=%d 没有上架时刻也没有评测，不写入", appid)
            no_release_count += 1
            continue
        source_counts[source] += 1

        # 少数游戏一个标签都没有，get 取不到时给空列表，tags 就是空字符串
        tag_names = tags_by_appid.get(appid, [])

        cleaned_rows.append(
            {
                "appid": appid,
                "name": name,
                "release_date": release_ts_to_date(chosen_ts),
                "release_date_source": source,
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
        "raw_store_items 共 %d 行：写入 %d，不是游戏 %d，没有上架日 %d",
        len(raw_rows),
        len(cleaned_rows),
        not_game_count,
        no_release_count,
    )
    logger.info("上架日的出处：%s", source_counts)


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
