"""样本表的评测抽样类特征：评测者时长中位数（小时）和有时长的条数。

数据来自 raw_review_windows（每段一共多少条）和 raw_reviews（抽到的每条评测）。
抽样每段最多取 100 条，各段一共有多少条却不一样，所以按段加权，算法见讲解稿 6.5。
"""

MINUTES_PER_HOUR = 60


def weighted_median(values, weights):
    """加权中位数：按值从小到大排，累加权重，第一次达到总权重一半的那个值。

    普通中位数是“人数过半”，这里是“权重过半”。values 和 weights 一一对应，不能为空。
    """
    # 值和权重配成对，按值从小到大排
    pairs = sorted(zip(values, weights))
    half = sum(weights) / 2

    cumulative = 0
    for value, weight in pairs:
        cumulative += weight
        if cumulative >= half:
            return value


def load_playtime_inputs(conn):
    """一次读出全部样本算时长要用的数据，返回两个字典，键都是 (appid, 截止日)：

    - window_totals：{(appid, 截止日): {段号: 这一段的评测总数}}，来自 raw_review_windows
    - playtimes：{(appid, 截止日): [(段号, 写评测时的游玩分钟数), ...]}，来自 raw_reviews，
      只要有时长的评测

    同一款游戏的每个截止日各抽了一组评测，键里带上截止日，训练和校准各取各的那组。
    一次读完再按键查，不用每个样本查一次数据库。
    """
    window_totals = {}
    for appid, cutoff_date, window, total in conn.execute(
        "SELECT appid, cutoff_date, window, total FROM raw_review_windows"
    ):
        # setdefault：这个样本第一次出现时先放一个空字典，再往里填段号
        window_totals.setdefault((appid, cutoff_date), {})[window] = total

    playtimes = {}
    for appid, cutoff_date, window, minutes in conn.execute(
        "SELECT appid, cutoff_date, window, playtime_at_review_min FROM raw_reviews"
        " WHERE playtime_at_review_min IS NOT NULL"
    ):
        playtimes.setdefault((appid, cutoff_date), []).append((window, minutes))

    return window_totals, playtimes


def playtime_features(window_totals, playtimes):
    """一款游戏的评测者时长中位数（小时）和有时长的条数。

    window_totals 是这款的 {段号: 评测总数}，playtimes 是这款的 [(段号, 分钟数), ...]。
    每条的权重 = 这一段的评测总数 ÷ 这一段有时长的条数，这样一段的权重加起来
    正好是这一段的评测总数。整段都没有时长的段自然没有评测进来，等于跳过。
    一条有时长的评测都没有时，中位数为空（None），sample_n 为 0。
    """
    if not playtimes:
        return {"playtime_median_hrs": None, "sample_n": 0}

    # 先数每段有几条有时长的评测，算权重要用
    count_by_window = {}
    for window, _ in playtimes:
        count_by_window[window] = count_by_window.get(window, 0) + 1

    hours = []
    weights = []
    for window, minutes in playtimes:
        hours.append(minutes / MINUTES_PER_HOUR)
        # 这一条代表这一段里的多少条评测
        weights.append(window_totals[window] / count_by_window[window])

    return {"playtime_median_hrs": weighted_median(hours, weights), "sample_n": len(playtimes)}
