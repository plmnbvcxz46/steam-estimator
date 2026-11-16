"""信号 B：从在线人数估玩家数。

思路：玩家数 = 总游玩小时 H ÷ 人均游玩小时 h。
H 由 SteamCharts 的在线人数算出（样本表 charts_total_hours）；h 不知道，
用评测者游玩时长的中位数 t 来推：取对数后拟合一条直线 ln h = a + b × ln t。

和信号 A 用同一批训练样本、同一套五折、同一种打分，只比能算出 H 的那部分游戏。
A 的预测直接读五折预测表里树模型那一份，所以要先跑 python -m analysis.signal_a。

入口：python -m analysis.signal_b
"""

import numpy as np


def fit_line(x, y):
    """最小二乘拟合一条直线 y = a + b × x，返回 (a, b)。

    最小二乘：让每个点到直线的竖直距离平方后加起来最小。
    成绩也按误差的平方算（均方根误差），两边是同一个标准。
    """
    # 直线是一次多项式，polyfit 的第三个参数 1 就是“一次”。
    # 它按次数从高到低返回系数：先斜率 b，再截距 a
    b, a = np.polyfit(x, y, 1)
    return a, b


def signal_b_cv(samples, folds):
    """信号 B 的五折交叉验证，返回每款游戏的预测 ln k，顺序和输入相同。

    samples 只含能算出 H 的游戏；folds 是这些游戏各自的折号。
    每折用另外四折拟合 a、b，再给这一折估玩家数，换成 ln k。
    """
    raise NotImplementedError


def main():
    """读训练样本，比较 A、B 和两者平均，结果写进五折成绩表（experiment = signal_b）。"""
    raise NotImplementedError


if __name__ == "__main__":
    main()
