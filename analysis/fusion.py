"""信号融合：把信号 A、B 两个估计按固定权重合成一个。

做法见 DEVELOPMENT 4.3：
- 每路的误差 σ 取它五折预测误差的标准差，权重 w = 1 ÷ σ²，平时错得少的那路说话分量大；
- B 先加上纠偏项 μ_B（B 平均比真值低多少），再参与加权；
- 没有 B 的游戏直接用 A。

设计里 σ、μ_B 在校准集上用留一法算，校准集还没做，这里先在训练集五折上算：
预测某一折时，σ、μ_B 只用其余四折的误差，这一折的答案没参与。
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


def fit_fusion_params(true_ln_k, ln_a, ln_b):
    """用一批两路都有的游戏，算出融合要用的三个数：σ_A、σ_B、μ_B。

    只用两路都有的游戏：权重只在两路都有时起作用，σ 要反映的是这批游戏上谁更准。
    返回 (sigma_a, sigma_b, mu_b)。
    """
    raise NotImplementedError
【+

def fuse(ln_a, ln_b, sigma_a, sigma_b, mu_b):
    """按固定权重合并两路的 ln k 估计；ln_b 是 NaN（没有 B）的游戏直接取 A。"""
    raise NotImplementedError


def fusion_cv(true_ln_k, ln_a, ln_b, folds):
    """五折：每一折用其余四折算 σ、μ_B，再融合这一折，返回每款游戏的融合 ln k。"""
    raise NotImplementedError


def main():
    """读两路已存的五折预测，在全部训练游戏上比较只用 A、简单平均、加权融合，
    结果写进五折成绩表（experiment = fusion）。"""
    raise NotImplementedError


if __name__ == "__main__":
    main()
