from pytest import approx

from pipeline.samples.price_features import EMPTY_FEATURES, pick_one_per_time, price_features

CUTOFF = "2018-07-01"


def test_same_time_keeps_the_one_matching_previous_regular():
    # ITAD 同时跟踪两个购买项：第 2 个时刻有原价 10 和 30 两条，前一段原价是 10
    segments = [
        ("2018-01-01 00:00:00", "2018-02-01 00:00:00", 10, 10, 0),
        ("2018-02-01 00:00:00", "2018-03-01 00:00:00", 10, 5, 50),
        ("2018-02-01 00:00:00", "2018-03-01 00:00:00", 30, 15, 50),
    ]

    kept, unmatched = pick_one_per_time(segments)

    assert kept == segments[:2]
    assert unmatched == 0


def test_long_discount_is_cut_and_last_segment_ends_at_cutoff():
    # 先打 75% 折 40 天（只算 30 天，多出 10 天按原价），再原价到 12 月，截止日切在 7 月 1 日
    segments = [
        ("2018-04-02 00:00:00", "2018-05-12 00:00:00", 10, 2.5, 75),
        ("2018-05-12 00:00:00", "2018-12-01 00:00:00", 10, 10, 0),
    ]

    features = price_features(segments, CUTOFF)

    # 截止日前共 40 + 50 = 90 天；付的钱 30×2.5 + 10×10 + 50×10 = 675
    assert features["price_at_cutoff_usd"] == 10
    assert features["avg_price_usd"] == approx(7.5)
    assert features["frac_time_cut25"] == approx(30 / 90)
    assert features["frac_time_cut75"] == approx(30 / 90)


def test_history_starting_after_cutoff_gives_empty():
    # 训练集里约 51 款：价格记录从截止日之后才有，之前的价格不知道
    segments = [("2019-01-01 00:00:00", "2019-02-01 00:00:00", 10, 10, 0)]

    assert price_features(segments, CUTOFF) == EMPTY_FEATURES
