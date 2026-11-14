import math
import sqlite3

import numpy as np

from analysis.evaluation import N_FOLDS, make_folds, save_experiment, score


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


def test_save_experiment_replaces_only_its_own_rows():
    # 重跑一个 experiment 会把它原来的行整个换掉（第二次没有 fixed，fixed 就不该还在），
    # 别的 experiment 不受影响；只存成绩时不写预测
    conn = sqlite3.connect(":memory:")
    sample_ids = ["train:1:2018-07-01", "train:2:2018-07-01"]
    true_ln_k = [1.0, 2.0]

    save_experiment(conn, "methods", sample_ids, true_ln_k,
                    {"fixed": np.array([1.5, 1.5]), "tree": np.array([1.0, 2.1])}, True)
    save_experiment(conn, "tree_size", sample_ids, true_ln_k,
                    {"leaves_15": np.array([1.0, 2.0])}, False)
    save_experiment(conn, "methods", sample_ids, true_ln_k,
                    {"tree": np.array([1.0, 2.0])}, True)

    scores = conn.execute(
        "SELECT experiment, variant, n_samples, rmse FROM result_cv_scores ORDER BY experiment"
    ).fetchall()
    assert scores == [("methods", "tree", 2, 0.0), ("tree_size", "leaves_15", 2, 0.0)]

    predictions = conn.execute(
        "SELECT variant, sample_id, predicted_ln_k FROM result_cv_predictions ORDER BY sample_id"
    ).fetchall()
    assert predictions == [("tree", "train:1:2018-07-01", 1.0), ("tree", "train:2:2018-07-01", 2.0)]
