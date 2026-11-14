import numpy as np
import pandas as pd

from analysis.signal_a import tree_cv


def test_tree_learns_a_step_and_routes_missing_values():
    # 答案是一道台阶：x < 0 的 ln k 是 0，x > 0 的是 5。
    # 每 10 款里有 1 款缺 x（真实数据里 51 款缺价格），它们的 ln k 都是 5。
    # 树模型不填缺失，应该自己学会把空值分到 5 那一边
    x = np.linspace(-1, 1, 200)
    ln_k = np.where(x < 0, 0.0, 5.0)
    is_missing = np.arange(200) % 10 == 0
    x[is_missing] = np.nan
    ln_k[is_missing] = 5.0
    inputs = pd.DataFrame({"x": x})
    folds = np.arange(200) % 5

    predicted = tree_cv(inputs, ln_k, folds)

    # 预测按输入的顺序排：每一款都猜在自己那级台阶附近
    assert np.allclose(predicted, ln_k, atol=0.5)
