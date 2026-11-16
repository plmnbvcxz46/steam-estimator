"""采集的总入口：python -m crawler [--workers 路数]

爬什么由 crawler.appids.pick_appids 的名单决定，每一项是（游戏, 截止日）；
这里只管按固定顺序把各个数据源跑一遍。各数据源的文件里只有干活的函数，没有自己的入口。

顺序有讲究：
1. 真值先进库：名单要读真值表；
2. 商店信息排在评测抽样前面：抽样要用上架时刻来切段；
3. ITAD 先换编号再查价格历史。

已经采过的请求在 raw_crawl_log 里有记录，会自动跳过：
中断了重跑同一条命令即可续上；以后新增了真值，重跑只会采新出现的游戏和截止日。
"""

import argparse
import logging
import sqlite3

from common.log import setup_logging
from common.paths import DB_PATH
from crawler.appids import pick_appids
from crawler.sources import gamalytic, manual_truth
from crawler.sources.itad import crawl_itad_ids, crawl_price_history, load_api_key
from crawler.sources.review_counts import crawl_review_counts
from crawler.sources.reviews import crawl_reviews
from crawler.sources.steamcharts import crawl_steamcharts
from crawler.sources.store_items import crawl_store_items, crawl_tag_names

logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="按名单采集全部数据源")
    parser.add_argument("--workers", type=int, default=4, help="评测和在线人数同时发请求的线程数，默认 4")
    args = parser.parse_args()

    # 日志只在这里配置一次，所有数据源都写进同一个文件
    setup_logging("crawler.log")
    # 密钥没填就在最开头报错，不要等爬了一半才发现
    api_key = load_api_key()

    # 1. 真值：两个来源都是整表替换，每次都重做
    gamalytic.main()
    manual_truth.main()

    conn = sqlite3.connect(DB_PATH)
    try:
        # 2. 名单：[(appid, 截止日), ...]。按游戏采的数据源只要不重复的 appid
        targets = pick_appids(conn, None)
        appids = sorted({appid for appid, _ in targets})
        logger.info("名单共 %d 项，%d 款游戏", len(targets), len(appids))

        # 3. 按游戏采的：一款游戏采一次，存的是整段历史或采集当天的样子，不分截止日
        crawl_store_items(conn, appids)
        crawl_tag_names(conn)
        crawl_itad_ids(conn, appids, api_key)
        crawl_price_history(conn, appids, api_key)
        crawl_steamcharts(conn, appids, args.workers)

        # 4. 按截止日采的：同一个截止日的游戏放一组，每组采一次。
        #    截止日只从名单里来，和游戏是配好的一对，别处不再指定
        appids_by_cutoff = {}
        for appid, cutoff_date in targets:
            appids_by_cutoff.setdefault(cutoff_date, []).append(appid)
        for cutoff_date, group in appids_by_cutoff.items():
            crawl_review_counts(conn, group, cutoff_date, args.workers)
            crawl_reviews(conn, group, cutoff_date, args.workers)
    finally:
        conn.close()


main()
