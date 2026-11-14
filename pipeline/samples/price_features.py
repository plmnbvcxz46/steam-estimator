"""样本表的历史价格类特征：截止日原价、平均实付价格、三档折扣时间占比。

数据来自 cleaned_prices 的时间段。清洗表只切段、不做取舍，
这里做三个取舍：同一时刻两条记录只留一条、只用截止日前的部分、过长的折扣截断。
"""

import logging

from pipeline.prices import days_between

logger = logging.getLogger(__name__)

# 一段折扣最多算多少天，超出的部分按原价算：多半是 ITAD 漏记了“恢复原价”。
# 实测 99% 的折扣不超过 28 天
MAX_DISCOUNT_DAYS = 30

# 三档折扣：折扣不低于这个百分比的时间占比各算一列
CUT_LEVELS = [25, 50, 75]

# 没有价格记录，或第一条记录在截止日之后，五列都给空
EMPTY_FEATURES = {
    "price_at_cutoff_usd": None,
    "avg_price_usd": None,
    "frac_time_cut25": None,
    "frac_time_cut50": None,
    "frac_time_cut75": None,
}


def load_price_segments(conn):
    """读出全部价格段，同一时刻的两条记录已只留一条。

    返回 {appid: [(started_at, ended_at, regular, price, cut), ...]}，每款按开始时刻排好序。
    去重和截止日无关，所以读的时候就做掉，接不上的总数在这里记日志。
    """
    # 同一时刻的几条按原价、实付价排，“取第一条”每次都取到同一条
    rows = conn.execute(
        "SELECT appid, started_at, ended_at, regular, price, cut FROM cleaned_prices"
        " ORDER BY appid, started_at, regular, price"
    ).fetchall()

    grouped = {}
    for appid, started_at, ended_at, regular, price, cut in rows:
        grouped.setdefault(appid, []).append((started_at, ended_at, regular, price, cut))

    segments_by_game = {}
    unmatched_total = 0
    for appid, segments in grouped.items():
        kept, unmatched = pick_one_per_time(segments)
        segments_by_game[appid] = kept
        unmatched_total += unmatched

    logger.info("同一时刻有多条价格记录、前后都接不上原价的 %d 处，取了原价最低的那条", unmatched_total)
    return segments_by_game


def first_with_regular(candidates, regulars):
    """在候选段里找原价属于 regulars 的第一条，找不到返回 None。"""
    for segment in candidates:
        if segment[2] in regulars:
            return segment
    return None


def pick_one_per_time(segments):
    """同一开始时刻有两条记录时只留一条，返回 (去重后的段列表, 接不上的处数)。

    取原价和前一段相同的那条；接不上（或者是第一段，没有前一段）时看后一时刻。
    都接不上的取第一条，也就是原价最低的那条。
    """
    # 按开始时刻分组；segments 已排好序，组的顺序就是时间顺序
    times = []
    by_time = {}
    for segment in segments:
        started_at = segment[0]
        if started_at not in by_time:
            times.append(started_at)
            by_time[started_at] = []
        by_time[started_at].append(segment)

    kept = []
    unmatched = 0
    for i, started_at in enumerate(times):
        candidates = by_time[started_at]
        if len(candidates) == 1:
            kept.append(candidates[0])
            continue

        chosen = None
        if kept:
            previous_regular = kept[-1][2]
            chosen = first_with_regular(candidates, {previous_regular})
        if chosen is None and i + 1 < len(times):
            # 后一时刻也可能有两条，它们的原价都算“接得上”
            next_regulars = {segment[2] for segment in by_time[times[i + 1]]}
            chosen = first_with_regular(candidates, next_regulars)
        if chosen is None:
            chosen = candidates[0]
            unmatched += 1
        kept.append(chosen)
    return kept, unmatched


def segments_before_cutoff(segments, cutoff_moment):
    """只留截止时刻前的部分，返回 [(regular, price, cut, days), ...]。

    跨过截止时刻的那一段切掉后半截，days 按切完的长度重算。
    时刻都写成 "YYYY-MM-DD HH:MM:SS"，同样的写法下文字的大小就是时间先后，可以直接比。
    """
    clipped = []
    for started_at, ended_at, regular, price, cut in segments:
        if started_at >= cutoff_moment:
            break
        end = min(ended_at, cutoff_moment)
        clipped.append((regular, price, cut, days_between(started_at, end)))
    return clipped


def price_features(segments, cutoff_date):
    """历史价格这一类特征，返回 5 项的 dict。

    segments 是 load_price_segments 给出的一款游戏的段列表（没有记录时给空列表）。
    """
    # 和评测计数一样，截止日当天不算：截止时刻是截止日的零点（UTC）
    cutoff_moment = cutoff_date + " 00:00:00"

    # 第一条记录之前的价格不知道，不假设为原价，所以第一段在截止日之后就全给空
    if not segments or segments[0][0] >= cutoff_moment:
        return dict(EMPTY_FEATURES)

    # 截止日原价：截止时刻落在哪一段，取那段的原价。段首尾相接一直到采集时刻，一定找得到
    for started_at, ended_at, regular, price, cut in segments:
        if started_at <= cutoff_moment < ended_at:
            price_at_cutoff = regular
            break

    total_days = 0
    paid = 0
    cut_days = {level: 0 for level in CUT_LEVELS}
    for regular, price, cut, days in segments_before_cutoff(segments, cutoff_moment):
        # 折扣最多算 MAX_DISCOUNT_DAYS 天，超出的天数按原价、不打折算
        if cut > 0 and days > MAX_DISCOUNT_DAYS:
            discount_days = MAX_DISCOUNT_DAYS
        else:
            discount_days = days
        full_price_days = days - discount_days

        paid += price * discount_days + regular * full_price_days
        for level in CUT_LEVELS:
            if cut >= level:
                cut_days[level] += discount_days
        total_days += days

    features = {
        "price_at_cutoff_usd": price_at_cutoff,
        # 按天数加权：每天的实付价加起来再除以天数，免费的天是 0
        "avg_price_usd": paid / total_days,
    }
    for level in CUT_LEVELS:
        features[f"frac_time_cut{level}"] = cut_days[level] / total_days
    return features
