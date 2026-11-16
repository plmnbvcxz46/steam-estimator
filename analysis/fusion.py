"""信号融合：把信号 A、B 两个估计按评测数分档加权，合成一个。

思路：两路的错基本不相关，合起来能互相抵消一部分。评测数不同的游戏，两路谁更准不一样
（评测少时 A 信息少、B 更准；评测多时 A 更准），所以按评测数分 5 档，每档各定一个 A 的占比：
- 每路的误差 σ 取这一档里它五折预测误差的标准差，权重 w = 1 ÷ σ²，平时错得少的那路分量大；
- A 的占比 = w_A ÷ (w_A + w_B)，B 占剩下的；
- 没有 B 的游戏直接用 A。

设计里占比在校准集上用留一法算，校准集还没做，这里先在训练集五折上算：
预测某一折时，占比只用其余四折的误差，这一折的答案没参与。
公式写成单独的函数，以后换成校准集的数据直接调用。

A、B 的五折预测都读已存的预测表，所以要先跑 analysis.signal_a 和 analysis.signal_b。
都在 ln k 上算：ln 玩家数 = ln k + ln 评测数，两路加的 ln 评测数相同，融合结果一样。

入口：python -m analysis.fusion
"""

import sqlite3

import numpy as np
import pandas as pd

from analysis.evaluation import N_FOLDS, load_train_samples, make_folds, save_experiment, score
from common.paths import DB_PATH

# 每档评测数的起点：10–49、50–199、200–999、1000–4999、5000 以上。
# 试过 2 到 10 档的几种分法，3 档以上成绩都差不多；取整数好记，每档在训练集里至少四百多款
REVIEW_BIN_STARTS = [10, 50, 200, 1000, 5000]


def fusion_cv(true_ln_k, ln_a, ln_b, total_reviews, folds):
    """五折按档加权融合，返回每款游戏的融合 ln k。

    ln_b 是 NaN 的游戏（没有 B）直接取 A。
    """
    true_ln_k = np.asarray(true_ln_k)
    ln_a = np.asarray(ln_a)
    ln_b = np.asarray(ln_b)

    # 1. 每款游戏落在第几档（0 到 4）：数一数它的评测数超过了几个后面档的起点
    bins = np.digitize(total_reviews, REVIEW_BIN_STARTS[1:])
    has_b = ~np.isnan(ln_b)

    # 2. 先全部填成 A：没有 B 的游戏就是这个结果
    fused = ln_a.copy()

    # 3. 每一折、每一档分别定 A 的占比
    for fold in range(N_FOLDS):
        is_test = folds == fold
        for bin_index in range(len(REVIEW_BIN_STARTS)):
            in_bin = bins == bin_index
            # 只用其余四折里这一档、两路都有的游戏算误差，这一折的答案没参与
            fit_rows = ~is_test & in_bin & has_b
            sigma_a = np.std(ln_a[fit_rows] - true_ln_k[fit_rows])
            sigma_b = np.std(ln_b[fit_rows] - true_ln_k[fit_rows])
            # 权重 = 1 ÷ σ²，占比 = 自己的权重 ÷ 两路权重之和
            weight_a = 1 / sigma_a**2
            weight_b = 1 / sigma_b**2
            a_share = weight_a / (weight_a + weight_b)

            # 这一折里这一档、有 B 的游戏按占比合并
            fuse_rows = is_test & in_bin & has_b
            fused[fuse_rows] = a_share * ln_a[fuse_rows] + (1 - a_share) * ln_b[fuse_rows]
    return fused


def main():
    """读两路已存的五折预测，在全部训练游戏上比较只用 A、简单平均、按档加权，
    结果写进五折成绩表（experiment = fusion）。"""
    raise NotImplementedError


if __name__ == "__main__":
    main()
