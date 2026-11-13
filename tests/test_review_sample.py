from crawler.sources.review_sample import make_windows, parse_window

CUTOFF = "2018-07-01"
CUTOFF_TS = 1530403200  # 2018-07-01 零点（UTC）
REVIEW_START_TS = 1380585600  # 2013-10-01 零点（UTC）


# ---- 切段 ----


def test_windows_cover_release_to_cutoff_without_overlap():
    # 2015-01-01 上架的游戏
    windows = make_windows(1420070400, CUTOFF)

    assert [w[0] for w in windows] == [1, 2, 3, 4, 5]
    assert windows[0][1] == 1  # 第一段从 1 开始，早于上架的评测也算进来
    assert windows[-1][2] == CUTOFF_TS  # 最后一段到截止日零点，和评测计数一样
    for before, after in zip(windows, windows[1:]):
        assert after[1] == before[2] + 1  # 首尾相接、不重叠


def test_windows_without_release_start_from_review_system():
    # 真实情况：104 款游戏商店没给上架时刻（为空或为 0）
    windows = make_windows(None, CUTOFF)
    # 第二段的起点离 2013-10-01 正好五分之一的区间
    assert windows[1][1] == REVIEW_START_TS + (CUTOFF_TS - REVIEW_START_TS) // 5 + 1


# ---- 解析：返回的样子取自真实请求 ----


def review(review_id, created, at_review, forever):
    """拼一条接口格式的评测（只留我们用到的字段）；at_review 为 None 表示接口没给这个字段。"""
    author = {"steamid": "1", "playtime_forever": forever}
    if at_review is not None:
        author["playtime_at_review"] = at_review
    return {"recommendationid": review_id, "timestamp_created": created, "author": author}


def test_parse_keeps_total_and_reviews():
    # 220 截止日前最新的一条：写评测时 422 分钟，采集时 744 分钟
    response = {
        "response": {
            "query_summary": {"num_reviews": 1, "total_reviews": 53436},
            "reviews": [review("43200691", 1530401659, 422, 744)],
        }
    }
    total, reviews = parse_window(response)

    assert total == 53436
    assert reviews == [
        {
            "review_id": "43200691",
            "created_at": "2018-06-30 23:34:19",
            "playtime_at_review_min": 422,
            "playtime_forever_min": 744,
        }
    ]


def test_parse_review_without_playtime_at_review_stores_none():
    # 真实情况：2016 年的一段里有 4 到 25 条评测不带 playtime_at_review
    response = {
        "response": {
            "query_summary": {"total_reviews": 1},
            "reviews": [review("1", 1470000000, None, 300)],
        }
    }
    _, reviews = parse_window(response)
    assert reviews[0]["playtime_at_review_min"] is None


def test_parse_empty_window_has_no_reviews_key():
    # 真实情况：这一段没有评测时，返回里根本没有 "reviews"
    response = {"response": {"query_summary": {"total_reviews": 0}, "cursor": "*"}}
    assert parse_window(response) == (0, [])


def test_parse_delisted_game_returns_none():
    assert parse_window({"response": {}}) is None

