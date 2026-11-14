"""两个对照方法：固定倍数、线性回归（以后加）。

它们是用来比的“笨办法”：树模型要明显好过它们，才说明真的从特征里学到了东西。
分折和打分都用 analysis.evaluation 里的，三种方法比的是同一批游戏、同一套折。

入口：python -m analysis.baselines
"""

import sqlite3

import numpy as np

from analysis.evaluation import N_FOLDS, load_train_samples, make_folds, score
from common.paths import DB_PATH


def fixed_multiplier_cv(ln_k, folds):
    """固定倍数的五折交叉验证：不看任何特征，所有游戏用同一个 ln k。

    每一折用其余 4 折的 ln k 平均值去猜这一折。平均值不用全部游戏一次算好，
    否则被猜的游戏自己也参与了平均，等于偷看答案。

    返回每款游戏的预测 ln k，顺序和输入相同。
    """
    ln_k = np.asarray(ln_k)
    predicted = np.empty(len(ln_k))
    for fold in range(N_FOLDS):
        is_test = folds == fold
        # 教材：不在这一折的游戏；考题：在这一折的游戏
        train_mean = ln_k[~is_test].mean()
        predicted[is_test] = train_mean
    return predicted


def main():
    """读训练样本，跑固定倍数的五折交叉验证，打印成绩。"""
    conn = sqlite3.connect(DB_PATH)
    try:
        samples = load_train_samples(conn)
    finally:
        conn.close()

    folds = make_folds(len(samples))
    predicted = fixed_multiplier_cv(samples["ln_k"], folds)
    result = score(samples["ln_k"], predicted)

    print(f"训练样本 {len(samples)} 款")
    print(f"固定倍数：均方根误差 {result['rmse']:.3f}，±30% 命中率 {result['hit_rate']:.1%}")


if __name__ == "__main__":
    main()
