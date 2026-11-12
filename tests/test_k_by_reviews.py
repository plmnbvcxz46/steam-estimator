"""分档统计：游戏按评测数落进正确的档，每档的 k 算对。"""

from viz.k_by_reviews import BIN_STARTS, summarize_bins


def test_summarize_bins_puts_games_in_right_bin():
    # 每档放一款 k = 10 的游戏垫底，否则空档算不了百分位
    points = [(index, start, start * 10) for index, start in enumerate(BIN_STARTS)]
    # 再加两款：评测数 9 落在第一档（1–9），评测数 10 落在第二档（10–19）
    points.append((900, 9, 9 * 30))
    points.append((901, 10, 10 * 50))

    summaries = summarize_bins(points)

    assert [s["count"] for s in summaries[:3]] == [2, 2, 1]
    assert summaries[0]["label"] == "1–9"
    assert summaries[0]["median"] == 20  # k 为 10 和 30，中位数是 20
    assert summaries[1]["median"] == 30  # k 为 10 和 50
    assert summaries[-1]["label"] == "20000+"
