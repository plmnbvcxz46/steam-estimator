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
    rows = conn.execute(
        "SELECT appid, month, player_hours FROM cleaned_charts_monthly ORDER BY appid, month"
    ).fetchall()
    grouped = {}
    for appid, month, player_hours in rows:
        grouped.setdefault(appid, []).append((month, player_hours))
    return grouped


def month_index(month):
    """把 "2018-06" 换成一个整数，相邻两个月差 1，用来算两个月份差几个月。"""
    year, month_number = month.split("-")
    return int(year) * 12 + int(month_number)


def charts_features(months, release_date, cutoff_date):
    """在线人数这一类特征。

    months 是这款游戏的 [(month, player_hours), ...]，按月份排好；没有记录的游戏给空列表。
    release_date、cutoff_date 是 "YYYY-MM-DD" 文字。
    返回一个 dict：charts_total_hours，共 1 项；算不了时为 None。
    """
    # 1. 没收录的游戏没有记录
    if not months:
        return {"charts_total_hours": None}

    # 2. 记录开始得太晚，漏掉了上架初期玩家最多的几个月，加出来会严重偏小。
    #    第一条记录早于上架月的不拦：说明上架前就有人在玩（抢先体验、测试），照样从第一条加
    first_month = months[0][0]
    release_month = release_date[:7]  # "2015-03-20" -> "2015-03"
    if month_index(first_month) - month_index(release_month) > MAX_LATE_MONTHS:
        return {"charts_total_hours": None}

    # 3. 截止日所在月还没过完，只用它之前的整月。月份是 "YYYY-MM" 文字，按文字比大小就是按时间比
    cutoff_month = cutoff_date[:7]
    before_cutoff = [hours for month, hours in months if month < cutoff_month]
    if not before_cutoff:
        return {"charts_total_hours": None}

    # 4. 每个月都按整月算，直接加
    return {"charts_total_hours": sum(before_cutoff)}
