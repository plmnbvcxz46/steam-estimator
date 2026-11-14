"""信号 A 的树模型：用梯度提升树学 ln k。

和两个对照（analysis.baselines）用同一批训练样本、同一套五折、同一种打分，
成绩才能直接比。树模型要明显好过线性回归，才说明从特征里学到了线性回归学不到的东西。

这一步只做五折评估；参数比较、全量拟合和保存模型在后面几步加。

入口：python -m analysis.signal_a
"""

import sqlite3

import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor

from analysis.baselines import fixed_multiplier_cv, linear_inputs, linear_regression_cv
from analysis.evaluation import N_FOLDS, load_train_samples, make_folds, save_experiment, score
from analysis.model_inputs import build_inputs, choose_tags
from common.paths import DB_PATH


def tree_cv(inputs, ln_k, folds):
    """树模型的五折交叉验证，返回每款游戏的预测 ln k，顺序和输入相同。

    inputs 直接用 build_inputs 的输出：不取对数、不填缺失、不去英语，
    这三件事只有线性回归需要。
    """
    ln_k = np.asarray(ln_k)
    predicted = np.empty(len(ln_k))
    for fold in range(N_FOLDS):
        is_test = folds == fold
        # 参数先全用默认，只关掉提前停止：默认在样本超过 1 万款时自动打开，
        # 会随机留一部分教材当验证，开不开取决于样本多少，结果不好比
        model = HistGradientBoostingRegressor(early_stopping=False)
        # 空值原样交给模型，它自己决定空值走哪一边
        model.fit(inputs[~is_test], ln_k[~is_test])
        predicted[is_test] = model.predict(inputs[is_test])
    return predicted


def main():
    """读训练样本，跑三种方法的五折交叉验证，结果写进五折成绩表（experiment = methods）。"""
    conn = sqlite3.connect(DB_PATH)
    try:
        samples = load_train_samples(conn)
        folds = make_folds(len(samples))
        ln_k = samples["ln_k"]
        tag_list = choose_tags(samples["tags"])
        inputs = build_inputs(samples, tag_list)

        # 三种方法用同一批游戏、同一套折；线性回归要先取对数、去英语，另两种不用
        predictions = {
            "fixed": fixed_multiplier_cv(ln_k, folds),
            "linear": linear_regression_cv(linear_inputs(inputs), ln_k, folds),
            "tree": tree_cv(inputs, ln_k, folds),
        }
        # 对比图要画每款的误差分布，所以连预测一起存
        save_experiment(conn, "methods", samples["sample_id"], ln_k, predictions, save_predictions=True)
    finally:
        conn.close()

    result = score(ln_k, predictions["tree"])
    print(f"训练样本 {len(samples)} 款")
    print(f"树模型（{inputs.shape[1]} 列）：均方根误差 {result['rmse']:.3f}，±30% 命中率 {result['hit_rate']:.1%}")
    print("三种方法的成绩已写入 result_cv_scores、result_cv_predictions（experiment = methods）")


if __name__ == "__main__":
    main()
