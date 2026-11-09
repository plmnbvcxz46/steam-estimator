import pytest

from crawler.ars import parse_players


def test_parse_players_normal():
    # 原件里的真实写法：两边有空格，中间有千分位逗号
    assert parse_players(" 50,191,347 ") == 50191347


def test_parse_players_plain_number():
    assert parse_players("46305966") == 46305966


def test_parse_players_rejects_bad_input():
    # 这些都应该报错，而不是返回某个默认值
    bad_inputs = ["", "   ", "abc", "-5", "1.5", "1,2x"]
    for bad in bad_inputs:
        with pytest.raises(ValueError):
            parse_players(bad)
