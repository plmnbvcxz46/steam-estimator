import numpy as np
import pandas as pd

from analysis.baselines import fixed_multiplier_cv, linear_regression_cv


def test_fixed_multiplier_does_not_use_own_fold():
    # 第 0 折的游戏 ln k 都是 100，别的折都是 0。
    # 不偷看的话，第 0 折被猜成 0（其余折的平均）；偷看了就会大于 0
    ln_k = np.array([100.0, 100.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
    folds = np.array([0, 0, 1, 1, 2, 2, 3, 3, 4, 4])

    predicted = fixed_multiplier_cv(ln_k, folds)

    assert predicted[0] == 0.0
    assert predicted[1] == 0.0
    # 别的折的教材里有那两个 100：8 款里 2 款是 100，平均 25
    assert predicted[2] == 25.0


def test_linear_regression_learns_a_straight_line():
    # 答案正好是 2x + 1，线性回归在没见过的折上也应该猜中
    x = np.arange(20, dtype=float)
    inputs = pd.DataFrame({"x": x})
    ln_k = 2 * x + 1
    folds = np.arange(20) % 5

    predicted = linear_regression_cv(inputs, ln_k, folds)

    assert np.allclose(predicted, ln_k)


def test_linear_regression_fills_missing_with_training_median():
    # 第 0 款缺 x（真实数据里 51 款缺价格）。它在第 0 折，其余折的 x 中位数是 10，
    # 答案是 2x + 1，所以补完后猜 21
    x = np.array([np.nan, 6, 7, 8, 9, 0, 11, 12, 13, 14], dtype=float)
    inputs = pd.DataFrame({"x": x})
    ln_k = np.where(np.isnan(x), 0, 2 * x + 1)
    folds = np.array([0, 1, 1, 2, 2, 0, 3, 3, 4, 4])

    predicted = linear_regression_cv(inputs, ln_k, folds)

    assert np.isclose(predicted[0], 21)
