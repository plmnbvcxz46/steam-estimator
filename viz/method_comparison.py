"""三种方法的对比图：固定倍数、线性回归、树模型的五折交叉验证成绩。

上半张是每种方法“估计 ÷ 真值”的分布，灰带是 ±30% 命中范围；
下半张是命中率和均方根误差两组柱子。

只读 result_cv_scores、result_cv_predictions 里 experiment = 'methods' 的行，
先运行 python -m analysis.signal_a 写入。
"""

import logging
import sqlite3

import matplotlib
import matplotlib.ticker

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from analysis.evaluation import HIT_HIGH, HIT_LOW
from common.log import setup_logging
from common.paths import DB_PATH, FIGURES_DIR
from viz.reviews_vs_players import CHINESE_FONTS

logger = logging.getLogger(__name__)

OUTPUT_NAME = "method_comparison.png"
EXPERIMENT = "methods"

# 表里的英文代号 -> 图上的名字和颜色。顺序就是图上的顺序，颜色固定跟着方法走
VARIANTS = {
    "fixed": ("固定倍数", "#2a78d6"),
    "linear": ("线性回归", "#eb6834"),
    "tree": ("树模型", "#1baf7a"),
}


# 分布曲线的横轴范围（估计 ÷ 真值）和分格数。超出范围的极少数游戏不画，只影响尾巴
RATIO_MIN = 0.05
RATIO_MAX = 20
N_BINS = 60

INK = "#0b0b0b"
MUTED = "#52514e"
GRID = "#e4e3df"
BAND = "#d9d8d3"


def load_scores(conn, experiment=EXPERIMENT):
    """读一次比较里各种做法的成绩，返回 {variant: {"rmse": ..., "hit_rate": ...}}。

    默认读三种方法的比较；信号 B 的对比图传 experiment = 'signal_b'。
    """
    rows = conn.execute(
        "SELECT variant, rmse, hit_rate FROM result_cv_scores WHERE experiment = ?",
        (experiment,),
    ).fetchall()
    return {variant: {"rmse": rmse, "hit_rate": hit_rate} for variant, rmse, hit_rate in rows}


def load_ratios(conn, experiment=EXPERIMENT):
    """读每款游戏的预测，返回 {variant: 每款的 估计 ÷ 真值}。"""
    rows = conn.execute(
        "SELECT variant, predicted_ln_k - true_ln_k FROM result_cv_predictions WHERE experiment = ?",
        (experiment,),
    ).fetchall()
    errors = {}
    for variant, error in rows:
        errors.setdefault(variant, []).append(error)
    # e 的（猜的 ln k − 真的 ln k）次方 = 猜的 k ÷ 真的 k = 估计 ÷ 真值
    return {variant: np.exp(values) for variant, values in errors.items()}


def style_axes(ax):
    """去掉上、右边框，网格和刻度用浅色，不和数据抢眼。"""
    for side in ["top", "right"]:
        ax.spines[side].set_visible(False)
    for side in ["left", "bottom"]:
        ax.spines[side].set_color(MUTED)
    ax.tick_params(colors=MUTED)
    ax.grid(True, axis="y", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)


def draw_distribution(ax, ratios, variants=VARIANTS):
    """每种方法一条曲线：横轴是估计 ÷ 真值，纵轴是落在这一小格里的游戏占比。"""
    # 在对数坐标上等宽分格，“猜成一半”和“猜成两倍”的格子一样宽
    edges = np.geomspace(RATIO_MIN, RATIO_MAX, N_BINS + 1)
    centers = np.sqrt(edges[:-1] * edges[1:])

    ax.axvspan(HIT_LOW, HIT_HIGH, color=BAND, alpha=0.6, linewidth=0, label="±30% 命中区间")
    for variant, (name, color) in variants.items():
        counts, _ = np.histogram(ratios[variant], bins=edges)
        ax.plot(centers, counts / len(ratios[variant]), color=color, linewidth=2, label=name)

    ax.set_xscale("log")
    ticks = [0.1, 0.3, HIT_LOW, 1, HIT_HIGH, 3, 10]
    ax.set_xticks(ticks, [f"{t:g}" for t in ticks])
    ax.minorticks_off()
    ax.set_xlabel("估计值与真值之比", color=MUTED)
    ax.set_ylabel("游戏占比", color=MUTED)
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))
    ax.set_title("估计值与真值之比的分布", color=INK, fontsize=11)
    ax.legend(frameon=False)
    style_axes(ax)


def draw_bars(ax, scores, key, title, label_format, variants=VARIANTS):
    """一组柱子，一种方法一根，柱顶写数值。"""
    names = [name for name, _ in variants.values()]
    colors = [color for _, color in variants.values()]
    values = [scores[variant][key] for variant in variants]
    bars = ax.bar(names, values, color=colors, width=0.6)
    ax.bar_label(bars, [label_format(v) for v in values], padding=3, color=INK, fontsize=10)
    ax.set_title(title, color=INK, fontsize=11)
    ax.margins(y=0.15)
    style_axes(ax)


def draw(scores, ratios, output_path, variants=VARIANTS, title="三种方法的五折交叉验证成绩"):
    """上：比值的分布曲线；下左：命中率；下右：均方根误差。

    variants、title 默认是三种方法的；信号 B 的对比图换成 A、B 两种。
    """
    plt.rcParams["font.sans-serif"] = CHINESE_FONTS
    # 负号用普通减号，中文字体里没有数学负号
    plt.rcParams["axes.unicode_minus"] = False

    fig = plt.figure(figsize=(9, 7.5))
    grid = fig.add_gridspec(2, 2, height_ratios=[1.6, 1])
    draw_distribution(fig.add_subplot(grid[0, :]), ratios, variants)

    ax_hit = fig.add_subplot(grid[1, 0])
    draw_bars(ax_hit, scores, "hit_rate", "±30% 命中率", lambda v: f"{v:.1%}", variants)
    ax_hit.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))
    draw_bars(fig.add_subplot(grid[1, 1]), scores, "rmse", "ln k 均方根误差", lambda v: f"{v:.3f}", variants)

    fig.suptitle(title, color=INK, fontsize=13)
    fig.tight_layout()
    output_path.parent.mkdir(exist_ok=True)
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


def main():
    """命令行入口：python -m viz.method_comparison"""
    setup_logging("viz.log")

    conn = sqlite3.connect(DB_PATH)
    try:
        scores = load_scores(conn)
        ratios = load_ratios(conn)
    finally:
        conn.close()

    for variant, result in scores.items():
        logger.info("%s：均方根误差 %.3f，±30%% 命中率 %.1f%%", variant, result["rmse"], result["hit_rate"] * 100)

    output_path = FIGURES_DIR / OUTPUT_NAME
    draw(scores, ratios, output_path)
    logger.info("图存在 %s", output_path)


if __name__ == "__main__":
    main()
