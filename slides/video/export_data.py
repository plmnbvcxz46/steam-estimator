"""讲解视频的取数：把动画要画的真实数字导成一个 JSON，动画页只读这个文件。

用法（在仓库根目录）：.venv/bin/python -m slides.video.export_data <输出 json>

数据库只读打开。能复用 viz/ 里的算法就直接导入，保证视频里的数和 figures/ 里的图一致。
"""

import json
import sqlite3
import sys

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

from analysis.calibration import MIN_AGE_YEARS
from analysis.evaluation import HIT_HIGH, HIT_LOW, N_FOLDS, load_train_samples, make_folds, score
from analysis.fusion import REVIEW_BIN_STARTS
from analysis.model_inputs import build_inputs, choose_tags
from analysis.signal_a import TREE_PARAMS
from analysis.signal_b import fit_line
from common.paths import DB_PATH, FROZEN_MODEL_PATH, PROJECT_ROOT
from query.__main__ import confidence_label, estimate
from viz.calibration_age import load_points as load_age_points
from viz.feature_importance import load_fixed_multiplier, load_importance, mean
from viz.fusion_by_reviews import scores_by_bin
from viz.fusion_comparison import load_predictions
from viz.k_by_reviews import summarize_bins
from viz.reviews_vs_players import fit_fixed_multiplier, load_points


def band_edges(points, summaries):
    """镜 3 的上下两条虚线：每档 k 的第 5 和第 95 百分位，换成玩家数，放在这一档评测数的中间。

    用百分位而不用最大最小值，是为了让虚线描的是“大多数点”的边，不被一两个极端点拉走。
    """
    edges = []
    for s in summaries:
        start, end = s["start"], s["end"]
        ks = [players / reviews for _, reviews, players in points if start <= reviews < end]
        low, high = np.percentile(ks, [5, 95])
        # 档的中间取几何平均：坐标是对数的，几何平均就是这一段的正中
        reviews_hi = min(end, max(r for _, r, _ in points) + 1)
        middle = float(np.sqrt(start * reviews_hi))
        edges.append({"reviews": middle, "low": float(low) * middle, "high": float(high) * middle})
    return edges


# 镜 7–9 的三种方法，顺序就是视频里出场的顺序
METHODS = ["fixed", "linear", "tree"]
# k 线的滑动窗口：每次取评测数相邻的这么多款游戏，取估出 k 的中位数。
# 窗口按款数取、不按评测数范围取，右边游戏稀的地方也不会只剩几款、线抖起来
WINDOW = 600
LINE_POINTS = 60


def method_results(conn, points):
    """三种方法的五折预测：每款游戏估没估对，以及“k 线”（估出的 k 随评测数的走势）。

    返回 hits（{appid: [三种方法各估对没有]}）和 methods（每种方法的估对比例和 k 线）。
    """
    reviews_of = {appid: reviews for appid, reviews, _ in points}
    rates = dict(conn.execute(
        "SELECT variant, hit_rate FROM result_cv_scores WHERE experiment = 'methods'"
    ).fetchall())
    hits = {}
    methods = {}
    for index, variant in enumerate(METHODS):
        rows = conn.execute(
            "SELECT sample_id, true_ln_k, predicted_ln_k FROM result_cv_predictions"
            " WHERE experiment = 'methods' AND variant = ?",
            (variant,),
        ).fetchall()
        games = []
        for sample_id, true_ln_k, predicted_ln_k in rows:
            appid = int(sample_id.split(":")[1])  # sample_id 形如 train:appid:日期
            # 估计 ÷ 真值落在 0.7 到 1.3 之间算估对，和 analysis/evaluation.py 同一个口径
            ratio = np.exp(predicted_ln_k - true_ln_k)
            hits.setdefault(appid, [0, 0, 0])[index] = int(HIT_LOW <= ratio <= HIT_HIGH)
            games.append((reviews_of[appid], predicted_ln_k))
        games.sort()
        reviews = np.array([r for r, _ in games])
        predicted = np.array([k for _, k in games])
        line = []
        for start in np.linspace(0, len(games) - WINDOW, LINE_POINTS).astype(int):
            window = slice(start, start + WINDOW)
            middle = float(np.exp(np.median(np.log(reviews[window]))))
            k = float(np.exp(np.median(predicted[window])))
            line.append([middle, k * middle])
        methods[variant] = {"hit_rate": rates[variant], "line": line}
    return hits, methods


# 树模型的冻结文件：镜 10 画的那棵树就是它的第 1 棵
FROZEN_PATH = PROJECT_ROOT / "data" / "models" / "frozen.joblib"
# 镜 10 的曲线：每加几棵树记一次估对比例
CURVE_STEP = 5


def first_tree():
    """冻结模型第 1 棵树的根和下一层：每个分叉按哪一列、在哪里切、有多少款游戏。"""
    model = joblib.load(FROZEN_PATH)["tree"]
    nodes = model._predictors[0][0].nodes  # sklearn 没有公开取树结构的接口，只能读这个内部属性
    names = model.feature_names_in_

    def split(index):
        node = nodes[index]
        return {"feature": str(names[node["feature_idx"]]), "threshold": float(node["num_threshold"]),
                "count": int(node["count"]), "left": int(node["left"]), "right": int(node["right"])}

    root = split(0)
    return {"root": root, "left": split(root["left"]), "right": split(root["right"])}


def staged_hit_rate(conn):
    """镜 10 的曲线：五折交叉验证里，树一棵棵加上去，估对比例怎么涨。返回曲线和模型的输入列数（镜 11 要用）。

    和 analysis.signal_a 同样的样本、分折和参数，只是每加一棵树就记一次预测。
    0 棵树时每款都估成训练集的平均 ln k，也就是固定 k。
    """
    samples = load_train_samples(conn)
    folds = make_folds(len(samples))
    ln_k = samples["ln_k"].to_numpy()
    inputs = build_inputs(samples, choose_tags(samples["tags"]))
    staged = np.zeros((TREE_PARAMS["max_iter"] + 1, len(ln_k)))
    for fold in range(N_FOLDS):
        is_test = folds == fold
        model = HistGradientBoostingRegressor(**TREE_PARAMS).fit(inputs[~is_test], ln_k[~is_test])
        staged[0, is_test] = ln_k[~is_test].mean()
        for n_trees, predicted in enumerate(model.staged_predict(inputs[is_test]), start=1):
            staged[n_trees, is_test] = predicted
    ratio = np.exp(staged - ln_k)
    hit = ((ratio >= HIT_LOW) & (ratio <= HIT_HIGH)).mean(axis=1)
    curve = [[n, float(hit[n])] for n in range(0, len(hit), CURVE_STEP)]
    return curve, inputs.shape[1]


def off_by_three(conn):
    """树模型五折预测里，估计和真值差 3 倍以上的游戏有多少款。"""
    rows = conn.execute(
        "SELECT predicted_ln_k - true_ln_k FROM result_cv_predictions"
        " WHERE experiment = 'methods' AND variant = 'tree'"
    ).fetchall()
    return sum(1 for (error,) in rows if abs(error) > np.log(3))


def source_counts(conn):
    """镜 11：每个来源有多少进了这 9623 款的样本表（训练集、评测 10 条以上）。
    只数用到的：评测计数、评测抽样只取截止日 2018-07-01 的；价格历史只数截止日之前的调价，特征只用这些。"""
    train = "(SELECT appid FROM cleaned_samples WHERE split = 'train' AND total_reviews >= 10)"
    count = lambda sql: conn.execute(sql).fetchone()[0]
    n_games = count("SELECT COUNT(*) FROM cleaned_samples WHERE split = 'train' AND total_reviews >= 10")
    return {
        "players": n_games,  # 每款一个玩家数
        "store": count(f"SELECT COUNT(*) FROM raw_store_items WHERE appid IN {train}"),
        "review_queries": count(f"SELECT COUNT(*) FROM raw_review_counts WHERE cutoff_date = '2018-07-01' AND appid IN {train}"),
        "reviews": count(f"SELECT COUNT(*) FROM raw_reviews WHERE cutoff_date = '2018-07-01' AND appid IN {train}"),
        "price_changes": count(f"SELECT COUNT(*) FROM raw_price_history WHERE changed_at < '2018-07-01' AND appid IN {train}"),
    }


# 镜 13–16 左边考题表的 9 列：组名和 part3.js 的 GROUPS3 同一个顺序，最后一列是答案
TABLE_GROUPS = ["game_age", "tags", "total_reviews", "positive_rate", "steam_purchase",
                "languages", "playtime", "price"]
TABLE_ROWS = 20


def importance(conn):
    """镜 13–16：8 组特征打乱后的误差和估对比例（5 种分折平均），按误差从大到小排。

    和 figures/feature_importance.png 读的是同一张表、同样取平均。"""
    scores = load_importance(conn)
    groups = [{"key": key, "rmse": mean(v["rmse"]), "hit": mean(v["hit"])}
              for key, v in scores.items() if key != "baseline"]
    groups.sort(key=lambda g: -g["rmse"])
    fixed_rmse, fixed_hit = load_fixed_multiplier(conn)
    base = scores["baseline"]
    return {
        "baseline": {"rmse": mean(base["rmse"]), "hit": mean(base["hit"])},
        "fixed": {"rmse": fixed_rmse, "hit": fixed_hit},
        "groups": groups,
    }


def table_cells(conn):
    """镜 13–16 考题表里画的 20 款真实游戏：每组取一列代表，值换成在 9623 款里的百分位（0–1），画成格子里的小条。

    最后一列是答案（玩家数）。"""
    samples = load_train_samples(conn)
    inputs = build_inputs(samples, choose_tags(samples["tags"]))
    tags = [c for c in inputs.columns if c.startswith("tag_")]
    columns = [
        inputs["game_age_years"],
        inputs[tags].sum(axis=1),       # 标签：这款打了几个选中的标签
        inputs["total_reviews"],
        inputs["positive_rate"],
        inputs["steam_purchase_ratio"],
        inputs["lang_english"],         # 语言：英语评测占比
        inputs["playtime_median_hrs"],
        inputs["price_at_cutoff_usd"],
        samples["truth_value"],
    ]
    ranks = np.column_stack([c.rank(pct=True).to_numpy() for c in columns])
    rows = np.random.default_rng(0).choice(len(samples), TABLE_ROWS, replace=False)
    return [[round(float(v), 3) for v in ranks[r]] for r in rows]


# 镜 14：上架年份太少的几年（2004–2007 每年不到 10 款）不画
MIN_YEAR = 2008
CUTOFF_YEAR = 2018 + 181 / 365  # 截止日 2018-07-01 折成年份


def k_by_year(conn):
    """镜 14：按上架年份分组，每年 k 的中位数和款数。上架年份 = 截止日减去游戏年龄。"""
    samples = load_train_samples(conn)
    years = np.floor(CUTOFF_YEAR - samples["game_age_years"].to_numpy()).astype(int)
    k = np.exp(samples["ln_k"].to_numpy())
    out = []
    for year in range(MIN_YEAR, int(years.max()) + 1):
        chosen = k[years == year]
        out.append([year, float(np.median(chosen)), int(len(chosen))])
    return out


# 镜 17 拿来画在线人数曲线的那款游戏：Stardew Valley，上架后一个月冲到最高，之后稳在七八千人
EXAMPLE_APPID = 413150
# 镜 18–21 的四条线，顺序就是出场顺序
FUSION_LINES = ["signal_a", "signal_b", "simple_mean", "binned_weighted"]


def fusion(conn):
    """镜 17–22：信号 B 的例子和拟合、按评测数分档的四条线、两张总成绩。

    分档成绩用 viz/fusion_by_reviews.py 的同一段计算，和 figures/fusion_by_reviews_with_b.png 一致。"""
    samples = load_train_samples(conn)
    table = load_predictions(conn)
    table["total_reviews"] = samples.set_index("sample_id")["total_reviews"]
    with_b = table[table["has_b"]]

    by_bin, counts = scores_by_bin(with_b, FUSION_LINES)
    lines = {v: {"rmse": [float(x) for x in by_bin[v]["rmse"]], "hit": [float(x) for x in by_bin[v]["hit_rate"]]}
             for v in FUSION_LINES}

    def totals(subset, variants):
        out = {}
        for v in variants:
            result = score(subset["true_ln_k"], subset[v])
            out[v] = {"rmse": float(result["rmse"]), "hit": float(result["hit_rate"])}
        return out

    # 两路误差的相关系数：越接近 0，两路越少往同一边错
    error_a = with_b["signal_a"] - with_b["true_ln_k"]
    error_b = with_b["signal_b"] - with_b["true_ln_k"]
    corr = float(np.corrcoef(error_a, error_b)[0, 1])

    # 每档 A 的占比：公式和 analysis.fusion 一样（1 ÷ σ² 归一）。
    # 融合时每一折用其余四折各算一次，这里用全部有 B 的游戏算一次，只为画出大小，数差不多
    bins = np.digitize(with_b["total_reviews"], REVIEW_BIN_STARTS[1:])
    shares = []
    for b in range(len(REVIEW_BIN_STARTS)):
        in_bin = bins == b
        weight_a = 1 / np.std(error_a[in_bin]) ** 2
        weight_b = 1 / np.std(error_b[in_bin]) ** 2
        shares.append(float(weight_a / (weight_a + weight_b)))

    # 换算框里的点：评测者时长中位数 t 和人均小时 h = H ÷ 真实玩家数，和 viz/signal_b_fit.py 同一批游戏
    has_hours = samples[samples["charts_total_hours"].notna()]
    ln_t = np.log(has_hours["playtime_median_hrs"].to_numpy())
    ln_h = np.log(has_hours["charts_total_hours"].to_numpy() / has_hours["truth_value"].to_numpy())
    a, b = fit_line(ln_t, ln_h)

    # 例子游戏：截止月以前的每月平均在线人数，加起来要等于样本表里它的总小时
    row = samples[samples["appid"] == EXAMPLE_APPID].iloc[0]
    cutoff_month = row["cutoff_date"][:7]
    months = conn.execute(
        "SELECT month, avg_players, player_hours FROM cleaned_charts_monthly"
        " WHERE appid = ? AND month < ? ORDER BY month",
        (EXAMPLE_APPID, cutoff_month),
    ).fetchall()
    assert abs(sum(m[2] for m in months) - row["charts_total_hours"]) < 1, "例子游戏的总小时和样本表对不上"
    name = conn.execute("SELECT name FROM cleaned_games WHERE appid = ?", (EXAMPLE_APPID,)).fetchone()[0]

    return {
        "bin_starts": REVIEW_BIN_STARTS,
        "counts": counts,
        "lines": lines,
        "with_b": totals(with_b, FUSION_LINES),
        "all": totals(table, ["signal_a", "simple_mean", "binned_weighted"]),
        "n_with_b": int(len(with_b)),
        "n_all": int(len(table)),
        "corr": corr,
        "shares": shares,
        "fit": {"a": float(a), "b": float(b), "points": [[round(float(x), 3), round(float(y), 3)] for x, y in zip(ln_t, ln_h)]},
        "example": {"name": name, "months": [[m[0], float(m[1])] for m in months]},
    }


# 镜 25 的单款查询：Vampire Survivors，2026-11-16 查过一次，样本表里有它的 query 行
QUERY_SAMPLE = "query:1794680:2026-11-16"


def calibration(conn):
    """镜 23–25：近年 116 款的成绩、k 随年龄的变化、留一法的“真值 ÷ 估计”、区间倍数、单款查询。

    成绩读 result_cv_scores（experiment = calibration）；年龄分档用 viz/calibration_age.py 的同一段取数；
    查询用 query 的 estimate 和冻结文件，样本行是当时现场采的，这里不联网。"""
    scores = {v: {"rmse": r, "hit": h} for v, r, h in conn.execute(
        "SELECT variant, rmse, hit_rate FROM result_cv_scores WHERE experiment = 'calibration'")}

    ages, counts = load_age_points(conn)

    # 留一法里每款的“真值 ÷ 融合估计”，有 B、没 B 分开
    loo = pd.read_sql_query(
        "SELECT sample_id, true_ln_k - predicted_ln_k AS err FROM result_cv_predictions"
        " WHERE experiment = 'calibration' AND variant = 'fused'", conn)
    with_b = {r[0] for r in conn.execute(
        "SELECT sample_id FROM result_cv_predictions WHERE experiment = 'calibration_with_b' AND variant = 'fused'")}
    has_b = loo["sample_id"].isin(with_b)
    frozen = joblib.load(FROZEN_MODEL_PATH)

    # 单款查询：估计、区间、标签都由 query 的 estimate 算；两路各自的 k 另算一次，画对比尺用
    sample = pd.read_sql_query("SELECT * FROM cleaned_samples WHERE sample_id = ?", conn, params=(QUERY_SAMPLE,))
    units, low, high, divergence = estimate(sample, frozen)
    reviews = int(sample["total_reviews"].iloc[0])
    ln_tree = frozen["tree"].predict(build_inputs(sample, frozen["tag_list"]))[0]
    gamma0, beta, c = frozen["a_calibration"]
    ln_a = gamma0 + beta * ln_tree + c * np.log(max(sample["game_age_years"].iloc[0], MIN_AGE_YEARS))
    line_a, line_b = frozen["b_line"]
    ln_b = (np.log(sample["charts_total_hours"].iloc[0]) - (line_a + line_b * np.log(sample["playtime_median_hrs"].iloc[0]))
            - np.log(reviews) + frozen["b_shift"])
    assert abs(abs(ln_a - ln_b) - divergence) < 1e-9, "两路的 k 和 estimate 对不上"
    name = conn.execute("SELECT name FROM raw_store_items WHERE appid = ?", (int(sample["appid"].iloc[0]),)).fetchone()[0]

    return {
        "n": int(len(loo)),
        "n_with_b": int(has_b.sum()),
        "scores": scores,
        "age_train": [float(np.exp(x)) for x in ages["train_truth"]],
        "age_calib": [float(np.exp(x)) for x in ages["calib_truth"]],
        "age_counts": [int(x) for x in counts],
        "ratios_b": [round(float(np.exp(x)), 4) for x in loo["err"][has_b]],
        "ratios_no_b": [round(float(np.exp(x)), 4) for x in loo["err"][~has_b]],
        "interval": {"b": [float(x) for x in frozen["interval_ratios"][True]],
                     "no_b": [float(x) for x in frozen["interval_ratios"][False]]},
        "query": {"name": name, "reviews": reviews, "units": float(units), "low": float(low), "high": float(high),
                  "k_a": float(np.exp(ln_a)), "k_b": float(np.exp(ln_b)), "label": confidence_label(reviews, divergence)},
    }


def main():
    output_path = sys.argv[1]

    # mode=ro：只读打开，动画取数绝不改库
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        points = load_points(conn)
        hits, methods = method_results(conn, points)
        curve, n_features = staged_hit_rate(conn)
        n_off3 = off_by_three(conn)
        sources = source_counts(conn)
        imp = importance(conn)
        cells = table_cells(conn)
        ages = k_by_year(conn)
        fus = fusion(conn)
        cal = calibration(conn)
    finally:
        conn.close()

    summaries = summarize_bins(points)
    # summarize_bins 只给了档名，这里补上每档的起止，画分隔线要用
    starts = [1, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 20000]
    for index, s in enumerate(summaries):
        s["start"] = starts[index]
        s["end"] = starts[index + 1] if index + 1 < len(starts) else float("inf")
        # 这一档游戏评测数的中位数：视频里这一档的矩形就画在这里，也就是这一档的游戏扎堆的地方。
        # 不用这一档横轴范围的正中间：最后一档一直跨到 232 万条，正中间那里几乎没有游戏
        reviews = [r for _, r, _ in points if s["start"] <= r < s["end"]]
        s["center"] = float(np.median(reviews))

    multiplier, _ = fit_fixed_multiplier(points)
    edges = band_edges(points, summaries)
    for s in summaries:
        if s["end"] == float("inf"):
            s["end"] = None  # JSON 没有无穷大

    data = {
        # 每个点：评测数、玩家数，后面三个是固定 k、线性回归、树模型估对没有（评测 1–9 条的没参加，是 null）
        "points": [[reviews, players, *hits.get(appid, [None] * 3)] for appid, reviews, players in points],
        "fixed_k": float(multiplier),
        "bins": summaries,
        "band": edges,
        "methods": methods,
        "tree": first_tree(),
        "curve": curve,
        "features": n_features,
        # 镜 12：最好的树模型仍估错 3 倍以上的游戏（估计 ÷ 真值大于 3 或小于 1/3）
        "off3": n_off3,
        "sources": sources,
        # 镜 13–16
        "importance": imp,
        "table_groups": TABLE_GROUPS,
        "cells": cells,
        "k_by_year": ages,
        # 镜 17–22
        "fusion": fus,
        # 镜 23–25
        "calibration": cal,
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)

    # 打出要和分镜核对的数
    n_small = sum(1 for _, r, _ in points if r < 10)
    print("点数", len(points), "评测 1–9 条", n_small, "保留", len(points) - n_small)
    print("固定 k", round(multiplier, 1))
    for s in summaries:
        print(s["label"], s["count"], "倍数", round(s["high"] / s["low"], 1),
              "中位数", round(s["median"], 1), "p10", round(s["low"], 1), "p90", round(s["high"], 1))
    print("曲线：0 棵树", f"{curve[0][1]:.1%}", "400 棵", f"{curve[-1][1]:.1%}",
          "（重新训练的，表里存的是", f"{methods['tree']['hit_rate']:.1%}）")
    print("估错 3 倍以上", data["off3"], "款；各来源", data["sources"])
    print("第 1 棵树", data["tree"])
    print("不打乱", imp["baseline"], "固定 k", imp["fixed"])
    for g in imp["groups"]:
        print("  打乱", g["key"], f"{g['rmse']:.3f}", f"{g['hit']:.1%}")
    print("按上架年份的 k 中位数", [(y, round(m), n) for y, m, n in ages])
    print("融合：每档", fus["counts"], "有 B", fus["n_with_b"], "全部", fus["n_all"], "误差相关", round(fus["corr"], 3))
    for v, line in fus["lines"].items():
        print("  ", v, [round(x, 3) for x in line["rmse"]], [f"{x:.1%}" for x in line["hit"]])
    print("  A 占比", [round(x, 3) for x in fus["shares"]], "拟合 a b", round(fus["fit"]["a"], 2), round(fus["fit"]["b"], 2))
    print("  有 B", {v: (round(r["rmse"], 3), f"{r['hit']:.1%}") for v, r in fus["with_b"].items()})
    print("  全部", {v: (round(r["rmse"], 3), f"{r['hit']:.1%}") for v, r in fus["all"].items()})
    print("  例子", fus["example"]["name"], len(fus["example"]["months"]), "个月")
    print("校准：", cal["n"], "款，有 B", cal["n_with_b"], {v: f"{r['hit']:.1%}" for v, r in cal["scores"].items()})
    print("  k 随年龄：训练集", [round(x) for x in cal["age_train"]], "近年", [round(x) for x in cal["age_calib"]], cal["age_counts"])
    print("  区间倍数", {g: [round(x, 2) for x in v] for g, v in cal["interval"].items()})
    q = cal["query"]
    print("  查询", q["name"], q["reviews"], f"{q['units'] / 1e4:.0f} 万", f"{q['low'] / 1e4:.0f}–{q['high'] / 1e4:.0f} 万",
          "A", round(q["k_a"], 1), "B", round(q["k_b"], 1), q["label"])
    for variant in METHODS:
        counted = sum(h[METHODS.index(variant)] for h in hits.values()) / len(hits)
        print(variant, "估对比例", f"{methods[variant]['hit_rate']:.1%}", "逐款数出来", f"{counted:.1%}")


if __name__ == "__main__":
    main()
