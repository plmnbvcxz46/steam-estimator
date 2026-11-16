"""校准：用近年的真值把两路估计再对一遍，并用留一法测出估得有多准。

模型是在训练集（2018 年）上学的；校准集是近年公布了真实销量的一百多款游戏。做三件事：
1. 用训练集得到两路“校准前”的估计：树模型给每款出 ln k（信号 A），
   在线人数那一路用训练集拟合的 a、b 出 ln k（信号 B，只有能算总小时的游戏有）；
2. 在校准集上对正：A 拟合 真值 = γ0 + β × 树的估计 + c × ln 游戏年龄；B 只整体平移（加上平均偏差）；
3. 融合：有 B 的游戏按评测数分档加权，各档 A 的占比沿用训练集五折的误差；没有 B 的取 A。

第 2 步用留一法评估：每次拿出一款，用其余游戏定 γ0、β、c 和 B 的平移量，再估这一款，
这一款的答案没参与。

校准里为什么还要一项年龄：树模型的输入里已经有游戏年龄，但它学的是 2018 年的规律（越老倍数越高，
那时的老游戏都是评测系统上线前上架的，早期玩家没留下评测）。近年游戏没有这个效应，树照旧规律
会把老游戏估高、刚上架的估低；树看不到近年的真值，只能在校准这一步纠正。
校准公式还试过加“政策后评测占比”和“评测数”两项，留一法下误差都不降，没有加。

训练时不读校准集里也有的游戏。结果写进五折成绩表（experiment = calibration、calibration_with_b），
要先跑 analysis.signal_a、analysis.signal_b（各档占比读它们存的五折预测）。

入口：python -m analysis.calibration
"""

import sqlite3

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

from analysis.evaluation import (
    DEFAULT_MIN_REVIEWS,
    load_train_samples,
    save_experiment,
    score,
)
from analysis.fusion import REVIEW_BIN_STARTS
from analysis.model_inputs import build_inputs, choose_tags
from analysis.signal_a import TREE_PARAMS
from analysis.signal_b import fit_line
from common.paths import DB_PATH

# 校准里游戏年龄取对数前的下限：30 天。上架 1 天和上架 30 天取对数后差得很远，
# 而校准集里刚上架几天的游戏只有几款，不设下限的话年龄这一项的系数会被它们带着走
MIN_AGE_YEARS = 30 / 365


def load_calib_samples(conn, min_reviews=DEFAULT_MIN_REVIEWS):
    """从 cleaned_samples 读校准样本，每款游戏只留一条，算出 ln k。

    和训练集用同一个评测数门槛。同一款有几条真值时留公布日期最晚的：
    留一法按游戏留出，一款只能占一行；越晚评测越多，k 越稳。
    """
    # 按 appid、截止日排序：行的顺序固定，同一款里最晚的排在最后
    samples = pd.read_sql_query(
        "SELECT * FROM cleaned_samples WHERE split = 'calib' AND total_reviews >= ?"
        " ORDER BY appid, cutoff_date",
        conn,
        params=(min_reviews,),
    )
    # keep="last"：同一个 appid 出现几次时只留最后一行，也就是最晚的那条
    samples = samples.drop_duplicates("appid", keep="last").reset_index(drop=True)
    samples["ln_k"] = np.log(samples["truth_value"] / samples["total_reviews"])
    return samples


def raw_estimates(train, calib):
    """用训练集得到校准集每款游戏“校准前”的两路估计，返回 (树的 ln k, B 的 ln k)。

    B 只有能算总小时的游戏有，其余是 NaN。
    """
    # 信号 A：标签清单只从训练集选，训练和校准按同一份清单展开，两边的列才对得上
    tag_list = choose_tags(train["tags"])
    model = HistGradientBoostingRegressor(**TREE_PARAMS)
    model.fit(build_inputs(train, tag_list), train["ln_k"])
    ln_tree = model.predict(build_inputs(calib, tag_list))

    # 信号 B：a、b 用训练集里能算总小时的游戏拟合（和 analysis.signal_b 同一个算法，这里用全部训练游戏）
    with_hours = train[train["charts_total_hours"].notna()]
    a, b = fit_line(
        np.log(with_hours["playtime_median_hrs"]),
        np.log(with_hours["charts_total_hours"] / with_hours["truth_value"]),
    )
    # 玩家数 = 总小时 ÷ 人均小时，再除以评测数得到 k；没有总小时的游戏算出来是 NaN
    ln_hours_per_player = a + b * np.log(calib["playtime_median_hrs"])
    ln_b = (
        np.log(calib["charts_total_hours"])
        - ln_hours_per_player
        - np.log(calib["total_reviews"])
    )
    return ln_tree, ln_b.to_numpy()


def train_a_shares(conn, train):
    """各评测数档里 A 的占比，按训练集五折的误差算（和 analysis.fusion 同一个公式）。

    校准集里两路都有的游戏只有几十款，分 5 档每档十来款，自己算占比不稳，所以沿用训练集的。
    """
    predictions = pd.read_sql_query(
        "SELECT sample_id, variant, predicted_ln_k - true_ln_k AS error FROM result_cv_predictions"
        " WHERE experiment = 'signal_b'",
        conn,
    ).merge(train[["sample_id", "total_reviews"]], on="sample_id")
    predictions["bin"] = np.digitize(
        predictions["total_reviews"], REVIEW_BIN_STARTS[1:]
    )
    # 每档、每路的误差标准差 σ；权重 = 1 ÷ σ²，A 的占比 = A 的权重 ÷ 两路权重之和
    sigma = predictions.groupby(["bin", "variant"])["error"].std().unstack()
    weight_a = 1 / sigma["signal_a"] ** 2
    weight_b = 1 / sigma["signal_b"] ** 2
    return (weight_a / (weight_a + weight_b)).to_numpy()


def fit_a_calibration(ln_tree, ln_age, true_ln_k):
    """最小二乘拟合信号 A 的校准公式 真值 = γ0 + β × 树的估计 + c × ln 游戏年龄，返回 (γ0, β, c)。"""
    # 三列：全是 1 的一列对应截距 γ0，后两列对应 β 和 c
    columns = np.column_stack([np.ones(len(ln_tree)), ln_tree, ln_age])
    coefficients, *_ = np.linalg.lstsq(columns, true_ln_k, rcond=None)
    return coefficients


def calibrate_loo(true_ln_k, ln_tree, ln_age, ln_b, a_share):
    """留一法校准并融合，返回三组预测：(校准后的 A, 校准后的 B, 融合)。

    a_share 是每款游戏所在档的 A 占比。没有 B 的游戏，B 是 NaN，融合取 A。
    """
    n = len(true_ln_k)
    has_b = ~np.isnan(ln_b)
    signal_a = np.empty(n)
    signal_b = np.full(n, np.nan)

    for i in range(n):
        others = np.arange(n) != i

        # A：用其余游戏拟合 γ0、β、c，再套到这一款上
        gamma0, beta, c = fit_a_calibration(ln_tree[others], ln_age[others], true_ln_k[others])
        signal_a[i] = gamma0 + beta * ln_tree[i] + c * ln_age[i]

        # B：加上其余游戏里 B 的平均偏差（真值 − B）
        if has_b[i]:
            fit_rows = others & has_b
            signal_b[i] = ln_b[i] + np.mean(true_ln_k[fit_rows] - ln_b[fit_rows])

    fused = np.where(has_b, a_share * signal_a + (1 - a_share) * signal_b, signal_a)
    return signal_a, signal_b, fused


def main():
    """读样本、校准、留一法评估，结果写进五折成绩表。"""
    conn = sqlite3.connect(DB_PATH)
    try:
        train = load_train_samples(conn)
        calib = load_calib_samples(conn)
        a_share_by_bin = train_a_shares(conn, train)

        # 训练时不读校准集里也有的游戏：模型要是见过这款，再估它就像提前看过答案
        seen = train["appid"].isin(calib["appid"])
        train = train[~seen]

        true_ln_k = calib["ln_k"].to_numpy()
        ln_tree, ln_b = raw_estimates(train, calib)
        # 校准用的 ln 游戏年龄，不足 30 天的按 30 天算
        ln_age = np.log(calib["game_age_years"].clip(lower=MIN_AGE_YEARS).to_numpy())
        bins = np.digitize(calib["total_reviews"], REVIEW_BIN_STARTS[1:])
        signal_a, signal_b, fused = calibrate_loo(
            true_ln_k, ln_tree, ln_age, ln_b, a_share_by_bin[bins]
        )

        # 对照：固定倍数，每款都猜其余游戏 ln k 的平均
        n = len(calib)
        fixed = np.array([true_ln_k[np.arange(n) != i].mean() for i in range(n)])

        # 全部校准游戏：对照、校准前、校准后的 A、融合
        all_predictions = {
            "fixed": fixed,
            "tree_raw": ln_tree,
            "signal_a": signal_a,
            "fused": fused,
        }
        save_experiment(
            conn,
            "calibration",
            calib["sample_id"],
            true_ln_k,
            all_predictions,
            save_predictions=True,
        )

        # 两路都有的游戏：A、校准前后的 B、融合
        has_b = ~np.isnan(ln_b)
        with_b_predictions = {
            "signal_a": signal_a[has_b],
            "signal_b_raw": ln_b[has_b],
            "signal_b": signal_b[has_b],
            "fused": fused[has_b],
        }
        save_experiment(
            conn,
            "calibration_with_b",
            calib["sample_id"][has_b],
            true_ln_k[has_b],
            with_b_predictions,
            save_predictions=True,
        )
    finally:
        conn.close()

    # 最终用的系数：用全部校准游戏拟合（留一法只用来评估）
    gamma0, beta, c = fit_a_calibration(ln_tree, ln_age, true_ln_k)
    print(
        f"训练集去掉校准集里也有的 {seen.sum()} 款，剩 {len(train)} 款；校准集 {n} 款，其中有 B 的 {has_b.sum()} 款"
    )
    print(
        f"A 的校准：γ0 = {gamma0:.3f}，β = {beta:.3f}，c = {c:.3f}；B 的平移量 {np.mean(true_ln_k[has_b] - ln_b[has_b]):+.3f}"
    )
    print("全部校准游戏：")
    for variant, predicted in all_predictions.items():
        result = score(true_ln_k, predicted)
        print(
            f"  {variant}：均方根误差 {result['rmse']:.3f}，±30% 命中率 {result['hit_rate']:.1%}"
        )
    print("两路都有的游戏：")
    for variant, predicted in with_b_predictions.items():
        result = score(true_ln_k[has_b], predicted)
        print(
            f"  {variant}：均方根误差 {result['rmse']:.3f}，±30% 命中率 {result['hit_rate']:.1%}"
        )
    print(
        "成绩已写入 result_cv_scores、result_cv_predictions（experiment = calibration、calibration_with_b）"
    )


if __name__ == "__main__":
    main()
