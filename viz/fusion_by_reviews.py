"""按评测数分档的融合成绩：每一档里各种做法的均方根误差和 ±30% 命中率。

横轴是融合用的 5 档评测数（analysis.fusion.REVIEW_BIN_STARTS），左图误差、右图命中率。
画两张：
- 有信号 B 的游戏：A、B、简单平均、按档加权四条线，看两路在哪一档谁更准、融合在哪一档帮得多；
- 全部训练游戏：没有 B 的游戏画不了 B，只画 A、简单平均、按档加权三条线。

读 result_cv_predictions 里 experiment = 'fusion' 和 'signal_b' 的行，
先运行 python -m analysis.fusion 写入；评测数从样本表读。
"""

import logging
import sqlite3

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker
import numpy as np

from analysis.evaluation import load_train_samples, score
from analysis.fusion import REVIEW_BIN_STARTS
from common.log import setup_logging
from common.paths import DB_PATH, FIGURES_DIR
from viz.fusion_comparison import VARIANTS, load_predictions
from viz.method_comparison import INK, MUTED, style_axes
from viz.reviews_vs_players import CHINESE_FONTS

logger = logging.getLogger(__name__)

# 信号 B 用 A、B 对比图里的颜色；只在有 B 的那张图里画
SIGNAL_B = ("信号 B", "#2a78d6")


def bin_labels():
    """每档的名字，如 10–49、5000 以上。"""
    labels = []
    for index, start in enumerate(REVIEW_BIN_STARTS):
        if index == len(REVIEW_BIN_STARTS) - 1:
            labels.append(f"{start} 以上")
        else:
            labels.append(f"{start}–{REVIEW_BIN_STARTS[index + 1] - 1}")
    return labels


def scores_by_bin(table, lines):
    """每种做法在每一档的成绩，返回 {variant: {"rmse": [...], "hit_rate": [...]}} 和每档游戏数。"""
    bins = np.digitize(table["total_reviews"], REVIEW_BIN_STARTS[1:])
    results = {variant: {"rmse": [], "hit_rate": []} for variant in lines}
    counts = []
    for bin_index in range(len(REVIEW_BIN_STARTS)):
        in_bin = bins == bin_index
        counts.append(int(in_bin.sum()))
        for variant in lines:
            result = score(table["true_ln_k"][in_bin], table[variant][in_bin])
            results[variant]["rmse"].append(result["rmse"])
            results[variant]["hit_rate"].append(result["hit_rate"])
    return results, counts


def draw(results, counts, lines, title, output_path):
    """左：均方根误差；右：±30% 命中率。每种做法一条折线。"""
    plt.rcParams["font.sans-serif"] = CHINESE_FONTS
    plt.rcParams["axes.unicode_minus"] = False
    fig, (ax_rmse, ax_hit) = plt.subplots(1, 2, figsize=(12, 5))

    positions = np.arange(len(REVIEW_BIN_STARTS))
    # 横轴标签下面写每档游戏数，档里游戏少的点更不稳
    tick_labels = [f"{label}\n{count} 款" for label, count in zip(bin_labels(), counts)]
    panels = [
        (ax_rmse, "rmse", "ln k 均方根误差"),
        (ax_hit, "hit_rate", "±30% 命中率"),
    ]
    for ax, key, panel_title in panels:
        for variant, (name, color) in lines.items():
            ax.plot(positions, results[variant][key], marker="o", color=color, linewidth=2, label=name)
        ax.set_xticks(positions, tick_labels)
        ax.set_xlabel("评测数", color=MUTED)
        ax.set_title(panel_title, color=INK, fontsize=11)
        style_axes(ax)
    ax_hit.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))
    ax_rmse.legend(frameon=False)

    fig.suptitle(title, color=INK, fontsize=13)
    fig.tight_layout()
    output_path.parent.mkdir(exist_ok=True)
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


def main():
    """命令行入口：python -m viz.fusion_by_reviews"""
    setup_logging("viz.log")

    conn = sqlite3.connect(DB_PATH)
    try:
        table = load_predictions(conn)
        samples = load_train_samples(conn)
    finally:
        conn.close()
    # 评测数从样本表按编号对上
    table["total_reviews"] = samples.set_index("sample_id")["total_reviews"]

    with_b_lines = {"signal_a": VARIANTS["signal_a"], "signal_b": SIGNAL_B}
    with_b_lines.update({variant: VARIANTS[variant] for variant in ["simple_mean", "binned_weighted"]})
    figures = [
        ("fusion_by_reviews_with_b.png", table[table["has_b"]], with_b_lines, "有信号 B 的"),
        ("fusion_by_reviews_all.png", table, VARIANTS, "全部"),
    ]
    for output_name, subset, lines, label in figures:
        results, counts = scores_by_bin(subset, lines)
        logger.info("%s：每档 %s 款", label, counts)
        title = f"按评测数分档的五折交叉验证成绩（{label} {len(subset)} 款游戏）"
        output_path = FIGURES_DIR / output_name
        draw(results, counts, lines, title, output_path)
        logger.info("图存在 %s", output_path)


if __name__ == "__main__":
    main()
