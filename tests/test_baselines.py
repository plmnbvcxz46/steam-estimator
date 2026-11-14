import numpy as np

from analysis.baselines import fixed_multiplier_cv


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
