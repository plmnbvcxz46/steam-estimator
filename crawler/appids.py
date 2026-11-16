"""决定采集哪些（游戏, 截止日），各采集器共用。

名单由两部分连起来：
- 训练集：Ars 表的游戏，截止日都是 2018-07-01，按固定种子打乱后取前 N 款；
- 校准集：各真值表的每一行，截止日是它自己的公布日期，每次全取。
截止日和游戏从同一行一起读出来，不会配错；同一款游戏两边都有，就有两个截止日，两份都要采。
"""

import random

SHUFFLE_SEED = 42  # 固定随机种子：每次打乱出的顺序一样，扩大 N 时已爬的不浪费

TRAIN_CUTOFF = "2018-07-01"  # 训练集的截止日（Ars 玩家数表的日期）

# 各真值来源的 raw 表，列名都一样（appid、report_date、title、units_sold、source_url）。
# 新增来源：先写爬虫或导入脚本，再在这里加一项；采集名单和 pipeline.sales_truth 都读这一份
TRUTH_TABLES = {
    "gamalytic": "raw_truth_gamalytic",
    "manual": "raw_truth_manual",
}


def pick_appids(conn, limit):
    """返回要采集的 [(appid, cutoff_date), ...]：训练集在前，校准集在后。

    limit 只管训练集：从 Ars 表取 limit 款（先排序再用固定种子打乱，取前 limit 个），
    为 None 时取全部（列表切片 [:None] 就是整个列表）。校准集只有一百多条，每次全取。
    """
    rows = conn.execute("SELECT appid FROM raw_ars_players_2018 ORDER BY appid")
    appids = [appid for (appid,) in rows]
    random.Random(SHUFFLE_SEED).shuffle(appids)
    targets = [(appid, TRAIN_CUTOFF) for appid in appids[:limit]]

    # 校准集：每张真值表的每一行，截止日就是公布日期。
    # 同一款同一天可能在两个来源里都有，重复的只留一个
    for table in TRUTH_TABLES.values():
        rows = conn.execute(f"SELECT appid, report_date FROM {table} ORDER BY appid, report_date")
        for appid, report_date in rows:
            if (appid, report_date) not in targets:
                targets.append((appid, report_date))
    return targets
