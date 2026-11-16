import numpy as np
import pandas as pd

from analysis.signal_b import signal_b_cv


def test_games_on_the_line_are_predicted_exactly():
    # 造 10 款游戏，人均小时正好落在直线 ln h = 0.2 + 0.9 × ln t 上。
    # 拟合应当找回这条线，再一路换算回去：推 h → 玩家数 = H ÷ h → k = 玩家数 ÷ 评测数，
    # 估出来的 ln k 应当等于真值。任何一步写反（比如乘成了除），这里都对不上
    playtime = np.array([1.0, 2.0, 3.0, 5.0, 8.0, 12.0, 20.0, 30.0, 50.0, 80.0])
    players = np.array([5e3, 2e4, 8e3, 1e5, 3e4, 6e4, 2e5, 1.5e4, 4e4, 9e4])
    reviews = np.array([50, 300, 120, 900, 400, 500, 2000, 100, 600, 700])
    hours_per_player = np.exp(0.2 + 0.9 * np.log(playtime))
    samples = pd.DataFrame({
        "charts_total_hours": players * hours_per_player,
        "playtime_median_hrs": playtime,
        "truth_value": players,
        "total_reviews": reviews,
    })
    folds = np.arange(10) % 5  # 每折 2 款

    predicted = signal_b_cv(samples, folds)

    true_ln_k = np.log(players / reviews)
    assert np.allclose(predicted, true_ln_k)
