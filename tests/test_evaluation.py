import math

import numpy as np

from analysis.evaluation import N_FOLDS, make_folds, score


def test_folds_are_balanced_and_repeatable():
    # 9623 款分 5 折：各折人数最多差 1，两次分得一模一样
    folds = make_folds(9623)
    counts = np.bincount(folds)
    assert len(counts) == N_FOLDS
    assert counts.max() - counts.min() <= 1
    assert (make_folds(9623) == folds).all()


def test_score_hit_window_is_relative_30_percent():
    # 真值 k = 1：猜 1.29 倍、0.71 倍算命中，1.31 倍、0.69 倍不算
    true_ln_k = [0.0, 0.0, 0.0, 0.0]
    predicted_ln_k = [math.log(1.29), math.log(0.71), math.log(1.31), math.log(0.69)]
    assert score(true_ln_k, predicted_ln_k)["hit_rate"] == 0.5


def test_score_rmse():
    # 差 +1 和 −1：平方都是 1，平均 1，开方还是 1
    assert score([0.0, 0.0], [1.0, -1.0])["rmse"] == 1.0
