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
    # 1. 每款游戏落在第几档（0 到 4）
    # 2. 先全部填成 A：没有 B 的游戏就是这个结果
    # 3. 对每一折、每一档：
    #    用其余四折里这一档、两路都有的游戏，算 A、B 的误差 σ，
    #    A 的占比 = (1/σ_A²) ÷ (1/σ_A² + 1/σ_B²)，
    #    这一折里这一档、有 B 的游戏：融合 = 占比 × A + (1 − 占比) × B
    raise NotImplementedError


def main():
    """读两路已存的五折预测，在全部训练游戏上比较只用 A、简单平均、按档加权，
    结果写进五折成绩表（experiment = fusion）。"""
    raise NotImplementedError


if __name__ == "__main__":
    main()
