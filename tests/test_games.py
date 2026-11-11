from pipeline.games import parse_release_date


def test_parse_release_date():
    assert parse_release_date("Sep 26, 2013") == "2013-09-26"


def test_parse_release_date_pads_single_digit_day():
    # 商店写 "Sep 8"，日只有一位；输出要补成两位，否则按字符串比较日期会出错
    assert parse_release_date("Sep 8, 2016") == "2016-09-08"


def test_parse_release_date_returns_none_when_not_a_date():
    assert parse_release_date("Coming soon") is None
