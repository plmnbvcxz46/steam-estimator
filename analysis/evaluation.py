"""三种方法共用的评估工具：读训练样本、分五折、打分。

固定倍数、线性回归、树模型都从这里读同一批样本、用同一套分折、同一种打分，
比出来的差别才只来自方法本身。

目标是 ln k = ln(玩家数 ÷ 评测数)，不是玩家数本身，理由见 DEVELOPMENT.md 信号 A 一节。
"""

import numpy as np
import pandas as pd

# 训练集默认的评测数门槛：1 到 9 条的 k 主要是噪声。
# 门槛要用交叉验证比较几个值，所以写成参数，这里只是默认
DEFAULT_MIN_REVIEWS = 10

# 五折交叉验证：分 5 份，轮流拿 1 份当考题、4 份当教材
N_FOLDS = 5

# 分折的随机种子固定，每次跑分到的折都一样，结果能复现
FOLD_SEED = 0

# 命中：估计值在真值的 ±30% 以内，即 0.7 ≤ 估计 ÷ 真值 ≤ 1.3
HIT_LOW = 0.7
HIT_HIGH = 1.3


def load_train_samples(conn, min_reviews=DEFAULT_MIN_REVIEWS):
    """从 cleaned_samples 读训练样本，按评测数门槛筛，算出 ln k。

    返回一个 pandas 表，每行一款游戏，带 ln_k 列（训练的答案）。
    """
    # 按 appid 排序：行的顺序固定，分折才固定
    samples = pd.read_sql_query(
        "SELECT * FROM cleaned_samples WHERE split = 'train' AND total_reviews >= ?"
        " ORDER BY appid",
        conn,
        params=(min_reviews,),
    )
    samples["ln_k"] = np.log(samples["truth_value"] / samples["total_reviews"])
    return samples


def make_folds(n_samples):
    """把 n_samples 款游戏随机分进 5 折，返回每款所在的折号（0 到 4）。"""
    # 先把 0 到 n-1 随机打乱，再按“打乱后排第几”轮流发折号：
    # 排第 0、5、10…… 的进第 0 折，排第 1、6、11…… 的进第 1 折，各折人数最多差 1
    rng = np.random.default_rng(FOLD_SEED)
    shuffled = rng.permutation(n_samples)
    folds = np.empty(n_samples, dtype=int)
    folds[shuffled] = np.arange(n_samples) % N_FOLDS
    return folds


def score(true_ln_k, predicted_ln_k):
    """给一组预测打分，返回均方根误差和 ±30% 命中率。

    两个分都在 ln k 上算，和换回玩家数再算是一回事：
    评测数 R 是已知的，玩家数 = R × k，乘的 R 两边相同，比值只差在 k 上。
    """
    errors = np.asarray(predicted_ln_k) - np.asarray(true_ln_k)
    rmse = np.sqrt(np.mean(errors**2))

    # e 的（猜的 ln k − 真的 ln k）次方 = 猜的 k ÷ 真的 k = 估计 ÷ 真值
    ratio = np.exp(errors)
    hits = (ratio >= HIT_LOW) & (ratio <= HIT_HIGH)
    return {"rmse": rmse, "hit_rate": hits.mean()}
