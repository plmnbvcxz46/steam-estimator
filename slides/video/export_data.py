"""讲解视频的取数：把动画要画的真实数字导成一个 JSON，动画页只读这个文件。

用法（在仓库根目录）：.venv/bin/python -m slides.video.export_data <输出 json>

数据库只读打开。能复用 viz/ 里的算法就直接导入，保证视频里的数和 figures/ 里的图一致。
"""

import json
import sqlite3
import sys

import numpy as np

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


def main():
    output_path = sys.argv[1]

    # mode=ro：只读打开，动画取数绝不改库
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        points = load_points(conn)
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
        "points": [[reviews, players] for _, reviews, players in points],
        "fixed_k": float(multiplier),
        "bins": summaries,
        "band": edges,
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


if __name__ == "__main__":
    main()
