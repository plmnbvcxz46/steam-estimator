"""几台机器分头采集评测计数：拆名单、合并结果。采集器本身不用改。

SQLite 的数据库只是一个本地文件，别的机器连不上，所以每台机器写自己的库，跑完再合并：

    1. 本机：python -m crawler.multi_machine split 3
           把还没爬完的游戏按采集顺序切成 3 段。第 1 段留给本机，
           第 2、3 段各生成一个小数据库（data/split/part2.db、part3.db），里面只有那一段的游戏名单
    2. 把小数据库拷到服务器的 data/steam.db，在服务器上照常运行采集器。
       采集器从库里的 Ars 表读名单，表里只有那一段，它就只爬那一段
    3. 服务器跑完后把它的 data/steam.db 拷回本机
    4. 本机：python -m crawler.multi_machine merge 拷回来的文件
    5. 本机重跑采集器：服务器爬过的会跳过，只补剩下的
"""

import argparse
import logging
import sqlite3

from common.log import setup_logging
from common.paths import DATA_DIR, DB_PATH
from crawler import crawl_log
from crawler.sources import review_counts
from crawler.sources.appdetails import pick_appids

logger = logging.getLogger(__name__)

SPLIT_DIR = DATA_DIR / "split"
ARS_TABLE = "raw_ars_players_2018"


def unfinished_appids(conn, cutoff_date):
    """还有请求没做完的游戏，按采集器的顺序排列。"""
    jobs = review_counts.pending_jobs(conn, pick_appids(conn, None), cutoff_date)
    appids = []
    seen = set()
    for job in jobs:
        # 一个游戏有好几个任务，只记第一次出现；任务本来就是按采集顺序排的
        if job["appid"] not in seen:
            seen.add(job["appid"])
            appids.append(job["appid"])
    return appids


def split_into_parts(items, parts):
    """把列表按顺序切成 parts 段，尽量一样长；除不尽时前面几段各多一个。

    例如 10 个切 3 段是 4、3、3。
    """
    base = len(items) // parts
    extra = len(items) % parts
    result = []
    start = 0
    for i in range(parts):
        size = base + 1 if i < extra else base
        result.append(items[start : start + size])
        start += size
    return result


def write_part_db(conn, appids, path):
    """新建一个小数据库，里面只有 Ars 表，且只含 appids 这些游戏。"""
    if path.exists():
        path.unlink()  # 重新拆分时覆盖旧文件

    # 建表语句直接从主库里取，保证两边的表结构一样
    create_sql = conn.execute(
        "SELECT sql FROM sqlite_master WHERE name = ?", (ARS_TABLE,)
    ).fetchone()[0]

    wanted = set(appids)
    rows = []
    for row in conn.execute(f"SELECT * FROM {ARS_TABLE} ORDER BY appid"):
        if row[0] in wanted:  # 第一列是 appid
            rows.append(row)

    part = sqlite3.connect(path)
    try:
        with part:
            part.execute(create_sql)
            part.executemany(f"INSERT INTO {ARS_TABLE} VALUES (?, ?, ?, ?)", rows)
    finally:
        part.close()


def split(conn, parts, cutoff_date=review_counts.DEFAULT_CUTOFF, out_dir=SPLIT_DIR):
    """把没爬完的游戏切成 parts 段：第 1 段留给本机，其余各写一个小数据库。返回每段的游戏数。"""
    appids = unfinished_appids(conn, cutoff_date)
    chunks = split_into_parts(appids, parts)

    out_dir.mkdir(parents=True, exist_ok=True)
    logger.info("没爬完的游戏共 %d 个，切成 %d 段", len(appids), parts)
    logger.info("第 1 段 %d 个：留给本机，本机照常运行采集器即可", len(chunks[0]))
    for number, chunk in enumerate(chunks[1:], start=2):
        path = out_dir / f"part{number}.db"
        write_part_db(conn, chunk, path)
        logger.info("第 %d 段 %d 个：%s", number, len(chunk), path)
    return [len(chunk) for chunk in chunks]


def merge(conn, other_path):
    """把另一台机器的库并进来：评测计数表和采集日志表。"""
    # 采集器正常都会建这两张表；这里再保证一次，主库是新的也能合并
    conn.execute(review_counts.CREATE_TABLE_SQL)
    crawl_log.ensure_table(conn)

    # ATTACH 把另一个数据库文件挂进来，起名 other，之后就能用 other.表名 读它
    conn.execute("ATTACH DATABASE ? AS other", (str(other_path),))
    try:
        before = conn.execute("SELECT COUNT(*) FROM raw_review_counts").fetchone()[0]
        # 三条写入放在一个事务里：要么都并进来，要么都不并
        with conn:
            # 数据行：主键相同的行本机已经有了就跳过（OR IGNORE）
            conn.execute(
                "INSERT OR IGNORE INTO raw_review_counts SELECT * FROM other.raw_review_counts"
            )
            # 日志分两步，让“成功”优先：
            # 先把对方已有定论的记录写进来，覆盖本机的失败记录
            marks = ",".join("?" * len(crawl_log.DONE_STATUSES))
            conn.execute(
                "INSERT OR REPLACE INTO raw_crawl_log"
                f" SELECT * FROM other.raw_crawl_log WHERE status IN ({marks})",
                crawl_log.DONE_STATUSES,
            )
            # 再把对方的失败记录补进来，但只补本机完全没有记录的
            conn.execute("INSERT OR IGNORE INTO raw_crawl_log SELECT * FROM other.raw_crawl_log")
        after = conn.execute("SELECT COUNT(*) FROM raw_review_counts").fetchone()[0]
    finally:
        conn.execute("DETACH DATABASE other")

    logger.info("合并 %s：评测计数新增 %d 行，现有 %d 行", other_path, after - before, after)
    return after - before


def main():
    """命令行入口：python -m crawler.multi_machine split 段数 | merge 文件"""
    parser = argparse.ArgumentParser(description="几台机器分头采集：拆名单、合并结果")
    commands = parser.add_subparsers(dest="command", required=True)
    split_parser = commands.add_parser("split", help="把没爬完的游戏切成几段")
    split_parser.add_argument("parts", type=int, help="切成几段（含本机）")
    merge_parser = commands.add_parser("merge", help="把另一台机器的库并进来")
    merge_parser.add_argument("path", help="另一台机器拷回来的数据库文件")
    args = parser.parse_args()

    setup_logging("multi_machine.log")

    conn = sqlite3.connect(DB_PATH)
    try:
        if args.command == "split":
            split(conn, args.parts)
        else:
            merge(conn, args.path)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
