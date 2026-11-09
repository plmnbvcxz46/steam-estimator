import json
from pathlib import Path

from crawler.appdetails import parse_appdetails

FIXTURES = Path(__file__).parent / "fixtures"


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_parse_paid_game():
    row = parse_appdetails(413150, load("appdetails_413150.json"))
    assert row == {
        "appid": 413150,
        "name": "Stardew Valley",
        "app_type": "game",
        "is_free": 0,
        "release_date": "Feb 26, 2016",
        "initial_price_usd": 14.99,  # 接口给的是美分 1499
        "genres": "Indie|RPG|Simulation",
    }


def test_parse_free_game_has_no_price():
    row = parse_appdetails(440, load("appdetails_440.json"))
    assert row["is_free"] == 1
    assert row["initial_price_usd"] is None


def test_parse_missing_app_returns_none():
    assert parse_appdetails(1, load("appdetails_1.json")) is None
