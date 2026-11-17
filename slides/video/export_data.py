"""讲解视频的取数：把动画要画的真实数字导成一个 JSON，动画页只读这个文件。

用法（在仓库根目录）：.venv/bin/python -m slides.video.export_data <输出 json>

数据库只读打开。能复用 viz/ 里的算法就直接导入，保证视频里的数和 figures/ 里的图一致。
"""

import json
import sqlite3
import sys

import joblib
import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor

from analysis.evaluation import HIT_HIGH, HIT_LOW, N_FOLDS, load_train_samples, make_folds
from analysis.model_inputs import build_inputs, choose_tags
from analysis.signal_a import TREE_PARAMS
from common.paths import DB_PATH, PROJECT_ROOT
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
    for variant in METHODS:
        counted = sum(h[METHODS.index(variant)] for h in hits.values()) / len(hits)
        print(variant, "估对比例", f"{methods[variant]['hit_rate']:.1%}", "逐款数出来", f"{counted:.1%}")


if __name__ == "__main__":
    main()
