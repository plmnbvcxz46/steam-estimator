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
