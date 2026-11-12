"""决定采集哪些游戏：从 Ars 表按固定种子打乱取前 N 款，各采集器共用。"""

import random

SHUFFLE_SEED = 42  # 固定随机种子：每次打乱出的顺序一样，扩大 N 时已爬的不浪费


def pick_appids(conn, limit):
    """从 Ars 表里取 limit 个 appid：先排序再用固定种子打乱，取前 limit 个。

    limit 为 None 时取全部（列表切片 [:None] 就是整个列表）。
    """
    rows = conn.execute("SELECT appid FROM raw_ars_players_2018 ORDER BY appid")
    appids = [appid for (appid,) in rows]
    random.Random(SHUFFLE_SEED).shuffle(appids)
    return appids[:limit]
