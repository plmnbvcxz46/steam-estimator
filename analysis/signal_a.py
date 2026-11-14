"""信号 A 的树模型：用梯度提升树学 ln k。

和两个对照（analysis.baselines）用同一批训练样本、同一套五折、同一种打分，
成绩才能直接比。树模型要明显好过线性回归，才说明从特征里学到了线性回归学不到的东西。

这一步只做五折评估；参数比较、全量拟合和保存模型在后面几步加。

入口：python -m analysis.signal_a
"""

import sqlite3

import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor

from analysis.evaluation import N_FOLDS, load_train_samples, make_folds, score
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
    """读训练样本，跑树模型的五折交叉验证，打印成绩。"""
    conn = sqlite3.connect(DB_PATH)
    try:
        samples = load_train_samples(conn)
    finally:
        conn.close()

    folds = make_folds(len(samples))
    print(f"训练样本 {len(samples)} 款")

    tag_list = choose_tags(samples["tags"])
    inputs = build_inputs(samples, tag_list)
    predicted = tree_cv(inputs, samples["ln_k"], folds)
    result = score(samples["ln_k"], predicted)
    print(f"树模型（{inputs.shape[1]} 列）：均方根误差 {result['rmse']:.3f}，±30% 命中率 {result['hit_rate']:.1%}")


if __name__ == "__main__":
    main()
