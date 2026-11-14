"""参数曲线图取数：variant 拆成线的名字和棵数，按棵数排好。"""

import sqlite3

import numpy as np

from analysis.evaluation import save_experiment
from viz.tree_params import load_curves


def test_load_curves_splits_variant_and_sorts_by_iterations():
    conn = sqlite3.connect(":memory:")
    sample_ids = ["train:1:2018-07-01", "train:2:2018-07-01"]
    # 预测和真值都是 0，误差是 0；故意按 300、100 的顺序写入
    predictions = {
        "leaves_31_iter_300": np.array([0.0, 0.0]),
        "leaves_31_iter_100": np.array([0.0, 0.0]),
        "leaves_15_iter_100": np.array([0.0, 0.0]),
    }
    save_experiment(conn, "tree_size", sample_ids, [0.0, 0.0], predictions, save_predictions=False)

    curves = load_curves(conn, "tree_size")

    assert set(curves) == {"leaves_31", "leaves_15"}
    assert [iterations for iterations, _ in curves["leaves_31"]] == [100, 300]


def test_load_seed_gains_compares_with_default_on_same_folds():
    # 种子 0 下：默认误差 1、两组候选都猜中（误差 0），所以误差都比默认低 1
    from viz.tree_params import load_seed_gains

    conn = sqlite3.connect(":memory:")
    sample_ids = ["train:1:2018-07-01", "train:2:2018-07-01"]
    predictions = {
        "seed_0_default": np.array([1.0, 1.0]),
        "seed_0_lr_0.05": np.array([0.0, 0.0]),
        "seed_0_min_100": np.array([0.0, 0.0]),
    }
    save_experiment(conn, "fold_seeds", sample_ids, [0.0, 0.0], predictions, save_predictions=False)

    gains = load_seed_gains(conn)

    seed, rmse_gain, hit_gain = gains["lr_0.05"][0]
    assert (seed, rmse_gain, hit_gain) == (0, 1.0, 1.0)
