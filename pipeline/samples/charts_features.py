"""样本表的在线人数类特征：总游玩小时 charts_total_hours（信号 B 的 H）。

数据来自 cleaned_charts_monthly 的每月玩家小时。清洗表只换算、不做取舍，
这里做两个取舍（规则由早期数据试算定下，见 DEVELOPMENT“信号 B”一节）：
- 记录是不是从上架初期开始的：第一条记录最多比上架月晚 1 个月，更晚的算不了，给空；
- 加哪些月：从第一条记录加到截止日所在月的前一个月，每个月都按整月算。
"""

# 第一条记录最多比上架月晚几个月。试算里晚 1 个月的 112 款不比别的差，晚 2 个月以上的只有 2 款
MAX_LATE_MONTHS = 1


def load_monthly_hours(conn):
    """读出全部游戏的每月玩家小时。

    返回 {appid: [(month, player_hours), ...]}，每款按月份从早到晚排好。
    """
    # TODO 填实现
    raise NotImplementedError


def month_index(month):
    """把 "2018-06" 换成一个整数，相邻两个月差 1，用来算两个月份差几个月。"""
    # TODO 填实现：年 × 12 + 月
    raise NotImplementedError


def charts_features(months, release_date, cutoff_date):
    """在线人数这一类特征。

    months 是这款游戏的 [(month, player_hours), ...]，按月份排好；没有记录的游戏给空列表。
    release_date、cutoff_date 是 "YYYY-MM-DD" 文字。
    返回一个 dict：charts_total_hours，共 1 项；算不了时为 None。
    """
    # TODO 填实现：
    # 1. 没有记录，给空
    # 2. 第一条记录比上架月晚超过 MAX_LATE_MONTHS 个月，给空
    # 3. 只留截止日所在月之前的月份；一个都不剩，给空
    # 4. 把剩下各月的玩家小时加起来
    raise NotImplementedError
