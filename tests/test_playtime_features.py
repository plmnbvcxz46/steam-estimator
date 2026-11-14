from pipeline.samples.playtime_features import playtime_features, weighted_median


def test_weighted_median_follows_weight_not_count():
    # 讲解稿 6.5 的例子：B 段 3 条各权重 10，A 段 3 条各权重 100。
    # 总权重 330，一半 165，累加到 20 时第一次达到
    values = [1, 2, 3, 10, 20, 30]
    weights = [10, 10, 10, 100, 100, 100]
    assert weighted_median(values, weights) == 20


def test_playtime_features_weights_each_window_by_its_total():
    # 第 1 段一共 300 条，抽到 3 条；第 2 段一共 30 条，抽到 3 条。时长按分钟给
    window_totals = {1: 300, 2: 30}
    playtimes = [(1, 600), (1, 1200), (1, 1800), (2, 60), (2, 120), (2, 180)]

    features = playtime_features(window_totals, playtimes)

    assert features == {"playtime_median_hrs": 20, "sample_n": 6}


def test_playtime_features_without_any_playtime():
    # 真实数据里有 1 款一条带时长的评测都没抽到
    assert playtime_features({1: 5}, []) == {"playtime_median_hrs": None, "sample_n": 0}
