"""讲解视频的取数：把动画要画的真实数字导成一个 JSON，动画页只读这个文件。

用法（在仓库根目录）：.venv/bin/python -m slides.video.export_data <输出 json>

数据库只读打开。能复用 viz/ 里的算法就直接导入，保证视频里的数和 figures/ 里的图一致。
"""

import json
import sqlite3
import sys

import numpy as np

from analysis.evaluation import HIT_HIGH, HIT_LOW
from common.paths import DB_PATH
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


def main():
    output_path = sys.argv[1]

    # mode=ro：只读打开，动画取数绝不改库
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        points = load_points(conn)
        hits, methods = method_results(conn, points)
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
    for variant in METHODS:
        counted = sum(h[METHODS.index(variant)] for h in hits.values()) / len(hits)
        print(variant, "估对比例", f"{methods[variant]['hit_rate']:.1%}", "逐款数出来", f"{counted:.1%}")


if __name__ == "__main__":
    main()
