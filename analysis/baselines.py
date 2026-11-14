"""两个对照方法：固定倍数、线性回归。

它们是用来比的“笨办法”：树模型要明显好过它们，才说明真的从特征里学到了东西。
分折和打分都用 analysis.evaluation 里的，三种方法比的是同一批游戏、同一套折。

入口：python -m analysis.baselines
"""

import sqlite3

import numpy as np
from sklearn.linear_model import LinearRegression

from analysis.evaluation import N_FOLDS, load_train_samples, make_folds, score
from analysis.model_inputs import build_inputs, choose_tags
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


# 线性回归里取对数的列：它们横跨好几个数量级，和 ln k 的关系按“翻几倍”算才接近直线
LOG_COLUMNS = ["total_reviews", "game_age_years", "playtime_median_hrs"]


def linear_inputs(inputs):
    """线性回归专用的输入：几列取对数，去掉英语一列。

    英语要去掉：9 组语言占比加起来恒等于 1，留着全部 9 列，
    系数可以任意互相挪而预测不变，算不出唯一的解。
    """
    # copy 一份再改，不动传进来的表（树模型还要用原值）
    linear = inputs.copy()
    for column in LOG_COLUMNS:
        # 三列在训练样本里都大于 0（时长最小 5 分钟，年龄最小 2 天），可以直接取对数；
        # 时长缺的仍是空，取对数后还是空
        linear[column] = np.log(linear[column])
    return linear.drop(columns=["lang_english"])


def linear_regression_cv(inputs, ln_k, folds):
    """线性回归的五折交叉验证，返回每款游戏的预测 ln k。

    每一折：用其余 4 折的中位数填缺失、拟合系数，再去猜这一折。
    中位数也只用其余 4 折算，和固定倍数的平均值一样，不偷看考题。
    """
    ln_k = np.asarray(ln_k)
    predicted = np.empty(len(ln_k))
    for fold in range(N_FOLDS):
        is_test = folds == fold
        train_inputs = inputs[~is_test]
        test_inputs = inputs[is_test]

        # 线性回归不认空值，缺的用教材部分每列的中位数补；考题也用教材的中位数补
        medians = train_inputs.median()
        train_inputs = train_inputs.fillna(medians)
        test_inputs = test_inputs.fillna(medians)

        # fit 就是最小二乘法：找出让教材部分误差平方和最小的常数和系数
        model = LinearRegression()
        model.fit(train_inputs, ln_k[~is_test])
        predicted[is_test] = model.predict(test_inputs)
    return predicted


def main():
    """读训练样本，跑固定倍数和线性回归的五折交叉验证，打印成绩。"""
    conn = sqlite3.connect(DB_PATH)
    try:
        samples = load_train_samples(conn)
    finally:
        conn.close()

    folds = make_folds(len(samples))
    print(f"训练样本 {len(samples)} 款")

    predicted = fixed_multiplier_cv(samples["ln_k"], folds)
    result = score(samples["ln_k"], predicted)
    print(f"固定倍数：均方根误差 {result['rmse']:.3f}，±30% 命中率 {result['hit_rate']:.1%}")

    tag_list = choose_tags(samples["tags"])
    inputs = linear_inputs(build_inputs(samples, tag_list))
    predicted = linear_regression_cv(inputs, samples["ln_k"], folds)
    result = score(samples["ln_k"], predicted)
    print(f"线性回归（{inputs.shape[1]} 列）：均方根误差 {result['rmse']:.3f}，±30% 命中率 {result['hit_rate']:.1%}")


if __name__ == "__main__":
    main()
