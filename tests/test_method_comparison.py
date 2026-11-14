"""对比图取数：从两张五折结果表读出的成绩和“估计 ÷ 真值”是对的。"""

import math
import sqlite3

import numpy as np

from analysis.evaluation import save_experiment
from viz.method_comparison import load_ratios, load_scores


def test_load_ratios_groups_by_method_and_converts_to_ratio():
    # 真 ln k 都是 0（k = 1）：猜 ln 2 就是猜成 2 倍，猜 ln 0.5 就是一半
    conn = sqlite3.connect(":memory:")
    sample_ids = ["train:1:2018-07-01", "train:2:2018-07-01"]
    predictions = {
        "fixed": np.array([math.log(2), math.log(0.5)]),
        "tree": np.array([0.0, 0.0]),
    }
    save_experiment(conn, "methods", sample_ids, [0.0, 0.0], predictions, save_predictions=True)
    # 别的比较的行不该被读进来
    save_experiment(conn, "tree_size", sample_ids, [0.0, 0.0], {"leaves_15": np.array([5.0, 5.0])}, True)

    ratios = load_ratios(conn)
    scores = load_scores(conn)

    assert set(ratios) == {"fixed", "tree"}
    assert np.allclose(sorted(ratios["fixed"]), [0.5, 2.0])
    assert np.allclose(ratios["tree"], [1.0, 1.0])
    assert scores["tree"]["hit_rate"] == 1.0
    assert scores["fixed"]["hit_rate"] == 0.0
