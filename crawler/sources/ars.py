"""导入 Ars Technica 2018-07-01 玩家数表，写入 raw_ars_players_2018。"""

import csv
import logging
import sqlite3

from common.clock import now_utc_str
from common.log import setup_logging
from common.paths import DB_PATH, SOURCE_DIR

logger = logging.getLogger(__name__)

# 原件已手工转成 UTF-8（见 devlog），所以直接按 UTF-8 读
SOURCE_ENCODING = "UTF-8"

EXPECTED_HEADER = ["Title", "Players Estimate", "Steam App ID"]


def parse_players(text):
    """把 ' 50,191,347 ' 这样的字符串转成整数 50191347。

    转不了就抛 ValueError，由调用者决定怎么记日志、跳不跳过。
    不在这里返回默认值：悄悄给个 0 会让坏数据混进数据库。
    """
    # 原件里数字两边有空格，中间有千分位逗号，先都去掉
    cleaned = text.strip().replace(",", "")

    # isdigit 只认 0-9，所以空串、字母、负号、小数点都会被挡住
    if not cleaned.isdigit():
        raise ValueError(f"玩家数不是合法的非负整数: {text!r}")

    return int(cleaned)


def read_rows(csv_path):
    """读 Ars 原件，返回 [(appid, title, players), ...]。

    表头不对说明文件换了格式，直接抛 ValueError；
    玩家数解析失败的行写日志后跳过；同一个 appid 只保留第一条。
    """
    rows = []
    seen_appids = set()

    with open(csv_path, newline="", encoding=SOURCE_ENCODING) as f:
        reader = csv.reader(f)

        # 原件的列名两边带空格，比较前先去掉
        header = [name.strip() for name in next(reader)]
        if header != EXPECTED_HEADER:
            raise ValueError(f"表头不符合预期: {header}")

        # 固定是三列、appid 都是数字，格式出错直接报错
        for title, players_text, appid_text in reader:
            appid = int(appid_text)

            try:
                players = parse_players(players_text)
            except ValueError as err:
                logger.warning(
                    "第 %d 行 appid=%d %s，已跳过", reader.line_num, appid, err
                )
                continue

            # appid 是主键，原件里有重复行（内容相同），只保留第一条
            if appid in seen_appids:
                logger.warning("第 %d 行 appid=%d 重复，已跳过", reader.line_num, appid)
                continue

            seen_appids.add(appid)
            rows.append((appid, title.strip(), players))

    return rows


CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS raw_ars_players_2018 (
    appid      INTEGER PRIMARY KEY,
    title      TEXT NOT NULL,
    players    INTEGER NOT NULL,
    fetched_at TEXT NOT NULL
)
"""

# 已有的 appid 直接覆盖，所以重复运行结果不变
INSERT_SQL = """
INSERT OR REPLACE INTO raw_ars_players_2018 (appid, title, players, fetched_at)
VALUES (?, ?, ?, ?)
"""


def import_ars(csv_path, db_path):
    """读 Ars 原件，一次性写进 raw_ars_players_2018，返回写入行数。"""
    rows = read_rows(csv_path)
    fetched_at = now_utc_str()
    records = [(appid, title, players, fetched_at) for appid, title, players in rows]

    conn = sqlite3.connect(db_path)
    try:
        # with conn：块内全部成功才提交，出错自动回滚，库里不会留半截数据
        with conn:
            conn.execute(CREATE_TABLE_SQL)
            conn.executemany(INSERT_SQL, records)
    finally:
        conn.close()

    logger.info("raw_ars_players_2018 写入 %d 行", len(records))
    return len(records)


SOURCE_CSV = SOURCE_DIR / "games_achievements_players_2018-07-01_ars_original.csv"


def main():
    """命令行入口：配置日志，然后导入。"""
    setup_logging("ars_import.log")
    import_ars(SOURCE_CSV, DB_PATH)


if __name__ == "__main__":
    main()
