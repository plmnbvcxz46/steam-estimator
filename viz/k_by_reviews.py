"""探查图：评测数不同的游戏，k 的波动有多大。

k = 玩家数 ÷ 评测数。把游戏按评测数分成几档，每一档看 k 的中位数和波动范围，
用来判断评测数少到什么程度时 k 就不可用了，以及提高门槛要损失多少游戏。

和散点图共用取数：读样本表的训练行，非游戏和评测数为 0 的已经去掉。
"""

import logging
import sqlite3

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from common.log import setup_logging
from common.paths import DB_PATH, FIGURES_DIR
from viz.reviews_vs_players import CHINESE_FONTS, CUTOFF_DATE, load_points

logger = logging.getLogger(__name__)

OUTPUT_NAME = "k_by_reviews.png"

# 每一档的起点。一档是“从这个数到下一个数之前”，最后一档没有上限。
# 评测少的地方分得细，因为 k 在那里变化最快
BIN_STARTS = [1, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 20000]


def bin_label(index):
    """第 index 档的名字，如 "10–19"、"20000+"。"""
    start = BIN_STARTS[index]
    if index == len(BIN_STARTS) - 1:
        return f"{start}+"
    return f"{start}–{BIN_STARTS[index + 1] - 1}"


def summarize_bins(points):
    """把游戏按评测数分档，返回每一档的统计，一档一个字典。

    low、median、high 是这一档 k 的第 10、50、90 百分位：把这一档的 k 从小到大排，
    排在 10%、50%、90% 位置上的值。用百分位而不用最大最小值，
    是因为最大最小值由一两款极端的游戏决定，百分位看的是大多数游戏。
    """
    # 先给每一档准备一个空列表，再把每款游戏的 k 放进它所在的档
    k_by_bin = [[] for _ in BIN_STARTS]
    for _, reviews, players in points:
        index = 0
        # 往后找，直到下一档的起点比评测数大
        while index + 1 < len(BIN_STARTS) and reviews >= BIN_STARTS[index + 1]:
            index += 1
        k_by_bin[index].append(players / reviews)

    summaries = []
    for index, k_values in enumerate(k_by_bin):
        low, median, high = np.percentile(k_values, [10, 50, 90])
        summaries.append(
            {
                "label": bin_label(index),
                "count": len(k_values),
                "low": float(low),
                "median": float(median),
                "high": float(high),
            }
        )
    return summaries


def draw(summaries, output_path):
    """上图：每档 k 的中位数和波动范围。下图：每档有多少款游戏。"""
    labels = [s["label"] for s in summaries]
    positions = range(len(summaries))

    plt.rcParams["font.sans-serif"] = CHINESE_FONTS
    # 两张图上下排，共用横轴。不把两种量画在同一张图的左右两个纵轴上，那样容易读错
    fig, (ax_k, ax_count) = plt.subplots(
        2, 1, figsize=(9, 7), sharex=True, height_ratios=[3, 1]
    )

    color = "#2a6fb0"
    for x, s in zip(positions, summaries):
        # 竖线从第 10 百分位画到第 90 百分位，圆点是中位数
        ax_k.plot([x, x], [s["low"], s["high"]], color=color, linewidth=3, alpha=0.45)
        ax_k.plot(x, s["median"], "o", color=color, markersize=7)
        # 竖线顶上写波动倍数：第 90 百分位是第 10 百分位的多少倍
        ax_k.annotate(
            f"{s['high'] / s['low']:.0f} 倍",
            (x, s["high"]),
            textcoords="offset points",
            xytext=(0, 5),
            ha="center",
            fontsize=9,
            color="#333333",
        )

    # k 的差别是按倍数算的，纵轴取对数后“差几倍”就是“差多长”
    ax_k.set_yscale("log")
    # 刻度直接写成 20、50、100 这样的数，比 2×10¹ 好读；上面留出空位写倍数
    ax_k.set_yticks(
        [10, 20, 50, 100, 200, 500, 1000],
        ["10", "20", "50", "100", "200", "500", "1000"],
    )
    ax_k.minorticks_off()
    ax_k.set_ylim(10, 1000)
    ax_k.set_ylabel("k = 玩家数 ÷ 评测数（对数坐标，底数 10）")
    ax_k.set_title("评测数越少，k 越不稳定")
    ax_k.grid(True, axis="y", color="#dddddd", linewidth=0.5)
    ax_k.set_axisbelow(True)

    bars = ax_count.bar(
        positions, [s["count"] for s in summaries], color="#9aa5b1", width=0.7
    )
    ax_count.bar_label(bars, fontsize=8, color="#333333")
    ax_count.set_ylabel("游戏款数")
    ax_count.set_xlabel(f"截至 {CUTOFF_DATE} 的评测数")
    ax_count.set_xticks(list(positions), labels, fontsize=7.5)
    ax_count.margins(y=0.2)

    total = sum(s["count"] for s in summaries)
    note = (
        f"圆点是每档 k 的中位数，竖线从第 10 百分位到第 90 百分位，线上的数字是两者之比。样本量 {total} 款。\n"
        "数据来源：玩家数为 Ars Technica 整理的 2018-07-01 玩家数表，评测数为 Steam 评测接口。"
    )
    fig.text(0.01, 0.01, note, fontsize=8, color="#555555")
    fig.subplots_adjust(bottom=0.14, hspace=0.08)

    output_path.parent.mkdir(exist_ok=True)
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


def main():
    """命令行入口：python -m viz.k_by_reviews"""
    setup_logging("viz.log")

    conn = sqlite3.connect(DB_PATH)
    try:
        points = load_points(conn)
    finally:
        conn.close()

    logger.info("参与分档的游戏 %d 款", len(points))

    summaries = summarize_bins(points)
    for s in summaries:
        logger.info(
            "评测数 %s：%d 款，k 中位数 %.1f，第 10 百分位 %.1f，第 90 百分位 %.1f",
            s["label"],
            s["count"],
            s["median"],
            s["low"],
            s["high"],
        )

    output_path = FIGURES_DIR / OUTPUT_NAME
    draw(summaries, output_path)
    logger.info("图存在 %s", output_path)


if __name__ == "__main__":
    main()
