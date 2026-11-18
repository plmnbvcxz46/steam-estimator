"""树模型的参数比较：叶子数、棵数、每片叶子至少多少款，另加学习率对照和分折方式检验。

比法和选择规则见 DEVELOPMENT 4.1 节。只写成绩表（result_cv_scores），不存每款预测，
viz.tree_params 读表画“棵数 → 误差”曲线。

入口：python -m analysis.tree_params
"""

import sqlite3

import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor

from analysis.evaluation import N_FOLDS, load_train_samples, make_folds, save_experiment
from analysis.model_inputs import build_inputs, choose_tags
from analysis.signal_a import TREE_PARAMS, tree_cv
from common.paths import DB_PATH

# 在这些棵数上打分；最后一个就是每折要种到的棵数
ITERATION_CHECKPOINTS = [50, 100, 200, 300, 500, 700, 1000]

# 每棵树最多几片叶子：31 是默认值，另取小一半和大一倍
LEAF_OPTIONS = [15, 31, 63]

# 每片叶子至少多少款：20 是默认值
MIN_LEAF_OPTIONS = [20, 50, 100]

# 比较每片最少款数时用的叶子数：看完叶子数比较的曲线后改成选定的值，先放默认值 31
CHOSEN_MAX_LEAF_NODES = 31

# 学习率对照：0.05 每步只走一半，棵数检查点跟着翻倍
DEFAULT_LEARNING_RATE = 0.1
SLOW_LEARNING_RATE = 0.05
SLOW_CHECKPOINTS = [100, 200, 400, 600, 1000, 1400, 2000]

# 分折方式检验：同一组参数只换分折的随机种子，看差距稳不稳。0 就是平时用的那套
FOLD_SEEDS = [0, 1, 2, 3, 4]

# 参加检验的三组参数：默认值、两条曲线里最低点比默认低的两组（各取它的最低点棵数）。
# 是按修正 SpeedRunners 上架日之前的曲线挑的，重跑后最低点有移动，没有换（见 DEVELOPMENT 4.1 节）
SEED_CHECK_PARAMS = {
    "default": {"max_iter": 100, "early_stopping": False},
    "lr_0.05": TREE_PARAMS,
    "min_100": {"max_iter": 200, "min_samples_leaf": 100, "early_stopping": False},
}


def tree_cv_curve(inputs, ln_k, folds, max_leaf_nodes, min_samples_leaf,
                  learning_rate=DEFAULT_LEARNING_RATE, checkpoints=ITERATION_CHECKPOINTS):
    """一组参数的五折交叉验证，一次训练拿到各个棵数的预测。

    返回 {棵数: 每款游戏的预测 ln k}，棵数取 checkpoints，最后一个就是每折种到的棵数。
    """
    ln_k = np.asarray(ln_k)
    curve = {iterations: np.empty(len(ln_k)) for iterations in checkpoints}
    max_iter = checkpoints[-1]

    for fold in range(N_FOLDS):
        is_test = folds == fold
        # 和 signal_a.tree_cv 一样关掉提前停止
        model = HistGradientBoostingRegressor(
            max_iter=max_iter,
            learning_rate=learning_rate,
            max_leaf_nodes=max_leaf_nodes,
            min_samples_leaf=min_samples_leaf,
            early_stopping=False,
        )
        model.fit(inputs[~is_test], ln_k[~is_test])

        # staged_predict 每种完一棵就给出一次预测：第 1 次是 1 棵树的，第 2 次是 2 棵的……
        # 这和只种 n 棵的模型预测完全一样，所以种一次就能取出所有棵数的成绩
        for iterations, predicted in enumerate(model.staged_predict(inputs[is_test]), start=1):
            if iterations in curve:
                curve[iterations][is_test] = predicted
    return curve


def compare_tree_size(conn, inputs, ln_k, sample_ids, folds):
    """每种叶子数一条棵数曲线，写进 experiment = tree_size。"""
    predictions = {}
    for leaves in LEAF_OPTIONS:
        # 每片叶子至少多少款先用默认值 20，下一个比较再动它
        curve = tree_cv_curve(inputs, ln_k, folds, leaves, 20)
        for iterations, predicted in curve.items():
            predictions[f"leaves_{leaves}_iter_{iterations}"] = predicted
    save_experiment(conn, "tree_size", sample_ids, ln_k, predictions, save_predictions=False)


def compare_learning_rate(conn, inputs, ln_k, sample_ids, folds):
    """31 片叶子下，学习率 0.1 和 0.05 各一条曲线，写进 experiment = learning_rate。"""
    predictions = {}
    for learning_rate, checkpoints in [
        (DEFAULT_LEARNING_RATE, ITERATION_CHECKPOINTS),
        (SLOW_LEARNING_RATE, SLOW_CHECKPOINTS),
    ]:
        curve = tree_cv_curve(inputs, ln_k, folds, 31, 20, learning_rate, checkpoints)
        for iterations, predicted in curve.items():
            predictions[f"lr_{learning_rate}_iter_{iterations}"] = predicted
    save_experiment(conn, "learning_rate", sample_ids, ln_k, predictions, save_predictions=False)


def compare_min_leaf(conn, inputs, ln_k, sample_ids, folds, max_leaf_nodes):
    """选定叶子数下，每片叶子至少多少款，写进 experiment = min_leaf。"""
    predictions = {}
    for min_samples_leaf in MIN_LEAF_OPTIONS:
        curve = tree_cv_curve(inputs, ln_k, folds, max_leaf_nodes, min_samples_leaf)
        for iterations, predicted in curve.items():
            predictions[f"min_{min_samples_leaf}_iter_{iterations}"] = predicted
    save_experiment(conn, "min_leaf", sample_ids, ln_k, predictions, save_predictions=False)


def compare_fold_seeds(conn, inputs, ln_k, sample_ids):
    """每组参数在 5 种分折方式下各跑一遍五折，写进 experiment = fold_seeds。

    一组参数要在每种分折下都比默认好才算真的更好：只换分折，默认参数的误差自己就会浮动。
    """
    predictions = {}
    for seed in FOLD_SEEDS:
        folds = make_folds(len(ln_k), seed)
        for name, params in SEED_CHECK_PARAMS.items():
            predictions[f"seed_{seed}_{name}"] = tree_cv(inputs, ln_k, folds, params)
    save_experiment(conn, "fold_seeds", sample_ids, ln_k, predictions, save_predictions=False)


def main():
    """读训练样本，跑三组参数比较和分折方式检验，写进成绩表。"""
    conn = sqlite3.connect(DB_PATH)
    try:
        samples = load_train_samples(conn)
        folds = make_folds(len(samples))
        ln_k = samples["ln_k"]
        sample_ids = samples["sample_id"]
        inputs = build_inputs(samples, choose_tags(samples["tags"]))

        compare_tree_size(conn, inputs, ln_k, sample_ids, folds)
        compare_learning_rate(conn, inputs, ln_k, sample_ids, folds)
        compare_min_leaf(conn, inputs, ln_k, sample_ids, folds, CHOSEN_MAX_LEAF_NODES)
        compare_fold_seeds(conn, inputs, ln_k, sample_ids)
    finally:
        conn.close()
    print("参数比较已写入 result_cv_scores（experiment = tree_size、learning_rate、min_leaf、fold_seeds）")


if __name__ == "__main__":
    main()
