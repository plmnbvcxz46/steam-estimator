"""重要性图取数：组名带下划线也能拆对，每组按分折种子顺序收齐 5 个原值。"""

import sqlite3

import numpy as np

from analysis.evaluation import save_experiment
from viz.feature_importance import load_importance


def test_load_importance_groups_scores_by_name():
    conn = sqlite3.connect(":memory:")
    sample_ids = ["train:1:2018-07-01", "train:2:2018-07-01"]
    # 真值都是 0。原样全猜中：误差 0、命中率 1；
    # 打乱 steam_purchase 后种子 0 误差 1、种子 1 误差 2，都在 ±30% 以外，命中率 0
    predictions = {
        "seed_0_baseline": np.array([0.0, 0.0]),
        "seed_1_baseline": np.array([0.0, 0.0]),
        "seed_0_steam_purchase": np.array([1.0, 1.0]),
        "seed_1_steam_purchase": np.array([2.0, 2.0]),
    }
    save_experiment(conn, "feature_importance", sample_ids, [0.0, 0.0], predictions,
                    save_predictions=False)

    scores = load_importance(conn)

    assert scores["baseline"] == {"rmse": [0.0, 0.0], "hit": [1.0, 1.0]}
    assert scores["steam_purchase"] == {"rmse": [1.0, 2.0], "hit": [0.0, 0.0]}
