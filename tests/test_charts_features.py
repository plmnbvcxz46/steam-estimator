from pipeline.samples.charts_features import charts_features

CUTOFF = "2018-07-01"

# 一款游戏的每月玩家小时；2018-07 是截止日所在月，不该加进去
MONTHS = [
    ("2015-04", 100.0),
    ("2015-05", 50.0),
    ("2018-06", 10.0),
    ("2018-07", 999.0),
]


def total_hours(months, release_date):
    return charts_features(months, release_date, CUTOFF)["charts_total_hours"]


def test_sums_months_before_cutoff_month():
    # 记录就在上架月开始：加到 2018-06 为止
    assert total_hours(MONTHS, "2015-04-20") == 160.0


def test_record_one_month_late_is_kept():
    # 月底上架，SteamCharts 下个月才开始记：真实数据里有 112 款，照样算
    assert total_hours(MONTHS, "2015-03-28") == 160.0


def test_record_two_months_late_is_empty():
    # 漏掉了上架初期玩家最多的几个月，加出来会偏小，不算。2012 年 7 月前上架的游戏都属于这种
    assert total_hours(MONTHS, "2015-02-20") is None


def test_record_before_release_month_starts_from_first_record():
    # 上架前就有人在玩（抢先体验、测试），后来商店改了上架日：真实数据里有 869 款，从第一条加
    assert total_hours(MONTHS, "2015-06-01") == 160.0


def test_not_tracked_or_nothing_before_cutoff_is_empty():
    # SteamCharts 没收录
    assert total_hours([], "2015-04-20") is None
    # 截止日所在月才开始有记录，之前一个整月都没有
    assert total_hours([("2018-07", 5.0)], "2018-07-01") is None
