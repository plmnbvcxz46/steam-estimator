"""采集 Steam 商店信息和标签，写入 raw_store_items、raw_store_tags、raw_tag_names。

用的是批量接口 IStoreBrowseService/GetItems：一次请求可以查很多款游戏，
全部一万三千多款只要几十次请求。
"""

import json
import logging

from common.clock import now_utc_str
from crawler import crawl_log
from crawler.http import CrawlError, get_json

logger = logging.getLogger(__name__)

SOURCE = "store_items"
ITEMS_URL = "https://api.steampowered.com/IStoreBrowseService/GetItems/v1/"
TAGS_URL = "https://api.steampowered.com/IStoreService/GetTagList/v1/"

BATCH_SIZE = 200  # 一次请求查多少款。实测 200 款可以，400 款接口返回 400 拒绝
MIN_INTERVAL = 1.0  # 两次请求之间至少隔几秒。总共只有几十次请求，不需要快
TAG_COUNT = 20  # 每款游戏取权重最高的多少个标签。Steam 自己做推荐也只看前 20 个

# 接口对每款游戏给一个结果代码：1 是查到了，15 是商店里没有这款（已下架等）
RESULT_OK = 1
RESULT_NOT_FOUND = 15

CREATE_ITEMS_SQL = """
CREATE TABLE IF NOT EXISTS raw_store_items (
    appid             INTEGER PRIMARY KEY,
    name              TEXT NOT NULL,
    app_type          INTEGER NOT NULL,
    is_free           INTEGER NOT NULL,
    release_ts        INTEGER,
    is_early_access   INTEGER NOT NULL,
    initial_price_usd REAL,
    fetched_at        TEXT NOT NULL,
    original_release_ts INTEGER
)
"""

CREATE_TAGS_SQL = """
CREATE TABLE IF NOT EXISTS raw_store_tags (
    appid    INTEGER NOT NULL,
    tagid    INTEGER NOT NULL,
    weight   INTEGER NOT NULL,
    position INTEGER NOT NULL,
    PRIMARY KEY (appid, tagid)
)
"""

CREATE_TAG_NAMES_SQL = """
CREATE TABLE IF NOT EXISTS raw_tag_names (
    tagid INTEGER PRIMARY KEY,
    name  TEXT NOT NULL
)
"""

INSERT_ITEM_SQL = """
INSERT OR REPLACE INTO raw_store_items
    (appid, name, app_type, is_free, release_ts, original_release_ts,
     is_early_access, initial_price_usd, fetched_at)
VALUES
    (:appid, :name, :app_type, :is_free, :release_ts, :original_release_ts,
     :is_early_access, :initial_price_usd, :fetched_at)
"""

INSERT_TAG_SQL = """
INSERT INTO raw_store_tags (appid, tagid, weight, position)
VALUES (:appid, :tagid, :weight, :position)
"""


def build_input_json(appids):
    """拼出请求参数：要查哪些游戏、用什么语言和地区、要哪几部分数据。"""
    return {
        "ids": [{"appid": appid} for appid in appids],
        # 地区选美国，价格才是美元
        "context": {"language": "english", "country_code": "US"},
        "data_request": {
            "include_release": True,  # 上架时间
            "include_all_purchase_options": True,  # 全部购买项，用来找游戏自己的价格
            "include_tag_count": TAG_COUNT,
        },
    }


def pick_price_usd(item):
    """从购买项里找出游戏自己的当前原价（美元）；免费或已停售的游戏返回 None。

    一款游戏可能有好几个购买项：单独买这款的“包”，和几款一起卖的“捆绑包”。
    捆绑包的价格不是这款游戏的价格，所以取第一个“包”（有 packageid 的那种）。
    正在打折时 original_price_in_cents 是原价；不打折时没有这一项，final_price_in_cents 就是原价。
    """
    if item.get("is_free"):
        # 免费游戏也可能挂着购买项（比如含它的合集），那不是它的价格
        return None
    for option in item.get("purchase_options", []):
        if "packageid" not in option:
            continue  # 捆绑包，跳过
        cents = option.get("original_price_in_cents") or option["final_price_in_cents"]
        return int(cents) / 100  # 接口给的是字符串形式的美分
    return None


def parse_item(item):
    """把接口返回的一款游戏变成两样东西：raw_store_items 的一行，raw_store_tags 的若干行。"""
    appid = item["id"]
    row = {
        "appid": appid,
        "name": item["name"],
        "app_type": item["type"],
        # 不是免费、不在抢先体验时，接口干脆不给这两个字段，所以用 get 取，没有就是 False
        "is_free": int(item.get("is_free", False)),
        "is_early_access": int(item.get("is_early_access", False)),
        # 未定档的游戏没有上架时间
        "release_ts": item["release"].get("steam_release_date"),
        # 抢先体验转正式版等情况下，商店会把 steam_release_date 改成后来的日期，
        # 这个字段留着最早上架的那一刻。只有部分游戏有，没有就是 None
        "original_release_ts": item["release"].get("original_steam_release_date"),
        "initial_price_usd": pick_price_usd(item),
    }

    tag_rows = []
    # 接口返回的标签已经按权重从高到低排好，position 就是它在这个顺序里排第几
    for position, tag in enumerate(item.get("tags", []), start=1):
        tag_rows.append(
            {
                "appid": appid,
                "tagid": tag["tagid"],
                "weight": tag["weight"],
                "position": position,
            }
        )
    return row, tag_rows


def save_batch(conn, appids, items):
    """把一批游戏的结果写进数据库，返回（写入的款数，未收录的款数）。

    appids 是这一批请求的游戏，items 是接口返回的结果，两者一一对应、顺序相同。
    整批放在一个事务里：数据行和日志要么都写入，要么都不写。
    """
    if [item.get("id") for item in items] != list(appids):
        # 返回的游戏和请求的对不上，说明接口的行为和我们以为的不一样，这一批不能用
        raise ValueError("返回的游戏和请求的游戏对不上")

    fetched_at = now_utc_str()
    saved_count = 0
    not_found_count = 0
    with conn:
        for appid, item in zip(appids, items):
            result = item["success"]
            if result == RESULT_NOT_FOUND:
                crawl_log.record(conn, SOURCE, appid, crawl_log.NOT_FOUND)
                not_found_count += 1
                continue
            if result != RESULT_OK:
                # 没见过的结果代码：记下来，不当成有定论，下次重跑还会再试
                logger.warning("appid=%d 返回了没见过的结果代码 %r", appid, result)
                crawl_log.record(conn, SOURCE, appid, f"result_{result}")
                continue

            row, tag_rows = parse_item(item)
            row["fetched_at"] = fetched_at
            conn.execute(INSERT_ITEM_SQL, row)
            # 重爬同一款游戏时标签可能变了，先删旧的再写新的
            conn.execute("DELETE FROM raw_store_tags WHERE appid = ?", (appid,))
            conn.executemany(INSERT_TAG_SQL, tag_rows)
            crawl_log.record(conn, SOURCE, appid, 200)
            saved_count += 1
    return saved_count, not_found_count


def ensure_tables(conn):
    crawl_log.ensure_table(conn)
    conn.execute(CREATE_ITEMS_SQL)
    # original_release_ts 是全量采完后才加的列。CREATE TABLE IF NOT EXISTS 碰到已有的表
    # 什么都不做，所以老库里的表要单独补上这一列；新加的列排在最后，
    # 建表语句里也把它写在最后，新库和老库的列顺序才一样
    columns = [row[1] for row in conn.execute("PRAGMA table_info(raw_store_items)")]
    if "original_release_ts" not in columns:
        conn.execute("ALTER TABLE raw_store_items ADD COLUMN original_release_ts INTEGER")
    conn.execute(CREATE_TAGS_SQL)
    conn.execute(CREATE_TAG_NAMES_SQL)


def crawl_store_items(conn, appids):
    """分批采集 appids 的商店信息和标签，并在 raw_crawl_log 记录每款的结局。

    已有定论的 appid 会跳过，所以中断后重跑同一条命令即可从断点继续。
    """
    ensure_tables(conn)

    done = crawl_log.done_keys(conn, SOURCE)
    todo = [appid for appid in appids if str(appid) not in done]
    logger.info("共 %d 个，已完成 %d 个，本次要爬 %d 个", len(appids), len(appids) - len(todo), len(todo))

    for start in range(0, len(todo), BATCH_SIZE):
        batch = todo[start : start + BATCH_SIZE]
        params = {"input_json": json.dumps(build_input_json(batch))}
        try:
            response = get_json(ITEMS_URL, params=params, min_interval=MIN_INTERVAL)
            items = response["response"]["store_items"]
            saved_count, not_found_count = save_batch(conn, batch, items)
        except CrawlError as err:
            logger.warning("第 %d 到 %d 个请求失败: %s", start + 1, start + len(batch), err)
            with conn:
                for appid in batch:
                    crawl_log.record(conn, SOURCE, appid, err.status)
            continue
        except (KeyError, TypeError, ValueError) as err:
            # 接口返回缺字段或结构变了：记下原因，跳过这一批，不让整次采集崩掉
            logger.warning("第 %d 到 %d 个解析失败: %r", start + 1, start + len(batch), err)
            with conn:
                for appid in batch:
                    crawl_log.record(conn, SOURCE, appid, crawl_log.PARSE_ERROR)
            continue

        logger.info(
            "进度 %d/%d：这一批写入 %d 款，未收录 %d 款",
            start + len(batch), len(todo), saved_count, not_found_count,
        )


def backfill_original_release(conn):
    """给已经采过的游戏补上 original_release_ts 这一列，别的列一律不动。

    已采的游戏在采集日志里都有定论，正常重跑会跳过它们，所以单独写这个函数：
    把表里已有的游戏重新请求一遍，只更新这一列，fetched_at 也不改。
    一共只有几十次请求，所以不记采集日志、不做续传：中途失败就整个重跑，
    UPDATE 重复执行结果一样。
    """
    ensure_tables(conn)
    appids = [appid for (appid,) in conn.execute("SELECT appid FROM raw_store_items ORDER BY appid")]
    filled_count = 0
    for start in range(0, len(appids), BATCH_SIZE):
        batch = appids[start : start + BATCH_SIZE]
        params = {"input_json": json.dumps(build_input_json(batch))}
        response = get_json(ITEMS_URL, params=params, min_interval=MIN_INTERVAL)
        items = response["response"]["store_items"]
        if [item.get("id") for item in items] != batch:
            raise ValueError("返回的游戏和请求的游戏对不上")

        with conn:
            for appid, item in zip(batch, items):
                if item["success"] != RESULT_OK:
                    # 采完之后才下架的游戏查不到了，这一列留空
                    logger.info("appid=%d 现在查不到了，最早上架时刻留空", appid)
                    continue
                original = item["release"].get("original_steam_release_date")
                conn.execute(
                    "UPDATE raw_store_items SET original_release_ts = ? WHERE appid = ?",
                    (original, appid),
                )
                if original is not None:
                    filled_count += 1
        logger.info("补最早上架时刻 %d/%d", start + len(batch), len(appids))

    logger.info("补完：%d 款里 %d 款有最早上架时刻", len(appids), filled_count)


def save_tag_names(conn, tags):
    """把标签名单写进 raw_tag_names。tags 是接口返回的列表，每项有 tagid 和 name。"""
    rows = [(tag["tagid"], tag["name"]) for tag in tags]
    with conn:
        # 名单很小，每次整张表换成最新的
        conn.execute("DELETE FROM raw_tag_names")
        conn.executemany("INSERT INTO raw_tag_names (tagid, name) VALUES (?, ?)", rows)
    return len(rows)


def crawl_tag_names(conn):
    """采集全部标签的编号和英文名。标签表里存的是编号，要靠这张名单才知道是哪个标签。"""
    ensure_tables(conn)
    response = get_json(TAGS_URL, params={"language": "english"}, min_interval=MIN_INTERVAL)
    count = save_tag_names(conn, response["response"]["tags"])
    logger.info("标签名单 %d 个", count)
