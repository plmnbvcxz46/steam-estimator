from pipeline.samples.store_features import store_features


def test_game_age_is_years_between_release_and_cutoff():
    # Half-Life 2：2004-11-16 上架，到 2018-07-01 相差 4975 天
    features = store_features("2018-07-01", "2004-11-16", "FPS|Action")

    assert round(features["game_age_years"], 2) == 13.62
    assert features["tags"] == "FPS|Action"


def test_empty_tags_are_copied_as_is():
    # 真实数据里有 2 款 cleaned_games 的标签就是空串，样本表照抄，不在这里取舍
    assert store_features("2018-07-01", "2018-06-30", "")["tags"] == ""
