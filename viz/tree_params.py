"""树模型参数比较的曲线图：棵数 → 五折均方根误差。

三张小图并排：叶子数（tree_size）、学习率（learning_rate）、每片叶子至少多少款（min_leaf）。
每种设置一条线，默认参数的线是蓝色，灰带是默认值上下 0.005。

只读 result_cv_scores，先运行 python -m analysis.tree_params 写入。
"""

import logging
import sqlite3

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from common.log import setup_logging
from common.paths import DB_PATH, FIGURES_DIR
from viz.reviews_vs_players import CHINESE_FONTS

logger = logging.getLogger(__name__)

OUTPUT_NAME = "tree_params.png"


# 默认参数的线统一用蓝色，其余设置依次用橙、绿
DEFAULT_COLOR = "#2a78d6"
OTHER_COLORS = ["#eb6834", "#1baf7a"]
INK = "#0b0b0b"
MUTED = "#52514e"
GRID = "#e4e3df"
BAND = "#d9d8d3"

# 默认参数那个点在第几棵；灰带的半宽
DEFAULT_ITERATIONS = 100
BAND_WIDTH = 0.005

# 每张小图：experiment、标题、默认那条线的名字、{线的名字: 图例}
PANELS = [
    ("tree_size", "每棵树最多几片叶子", "leaves_31",
     {"leaves_15": "15 片", "leaves_31": "31 片（默认）", "leaves_63": "63 片"}),
    ("learning_rate", "学习率", "lr_0.1",
     {"lr_0.1": "0.1（默认）", "lr_0.05": "0.05"}),
    ("min_leaf", "每片叶子至少多少款", "min_20",
     {"min_20": "20 款（默认）", "min_50": "50 款", "min_100": "100 款"}),
]


def load_curves(conn, experiment):
    """读一次比较的成绩，返回 {线的名字: [(棵数, 均方根误差), ...]}，按棵数排好。

    variant 形如 "leaves_31_iter_300"：最后一段是棵数，前面是线的名字。
    """
    rows = conn.execute(
        "SELECT variant, rmse FROM result_cv_scores WHERE experiment = ?", (experiment,)
    ).fetchall()
    curves = {}
    for variant, rmse in rows:
        # rsplit 从右边切一刀："leaves_31_iter_300" -> "leaves_31" 和 "300"
        name, iterations = variant.rsplit("_iter_", 1)
        curves.setdefault(name, []).append((int(iterations), rmse))
    return {name: sorted(points) for name, points in curves.items()}


def draw_panel(ax, curves, title, default_name, labels):
    """一张小图：每种设置一条线，标出默认参数那个点和它上下 0.005 的灰带。"""
    default_rmse = dict(curves[default_name])[DEFAULT_ITERATIONS]
    ax.axhspan(default_rmse - BAND_WIDTH, default_rmse + BAND_WIDTH,
               color=BAND, alpha=0.6, linewidth=0, label=f"默认 ±{BAND_WIDTH}")

    other_colors = iter(OTHER_COLORS)
    for name, label in labels.items():
        iterations, rmse = zip(*curves[name])
        color = DEFAULT_COLOR if name == default_name else next(other_colors)
        ax.plot(iterations, rmse, "-o", color=color, linewidth=2, markersize=4, label=label)
    ax.plot(DEFAULT_ITERATIONS, default_rmse, "o", color=DEFAULT_COLOR, markersize=10,
            markerfacecolor="none", markeredgewidth=2)

    ticks = [50, 100, 200, 500, 1000, 2000]
    ax.set_xscale("log")
    ax.set_xticks(ticks, [str(t) for t in ticks])
    ax.minorticks_off()
    ax.set_title(title, color=INK, fontsize=11)
    ax.set_xlabel("树的棵数（对数坐标）", color=MUTED)
    for side in ["top", "right"]:
        ax.spines[side].set_visible(False)
    ax.tick_params(colors=MUTED)
    ax.grid(True, axis="y", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, fontsize=9)


def draw(curves_by_experiment, output_path):
    """三张小图并排，共用纵轴。"""
    plt.rcParams["font.sans-serif"] = CHINESE_FONTS
    fig, axes = plt.subplots(1, len(PANELS), figsize=(12, 4.2), sharey=True)
    for ax, (experiment, title, default_name, labels) in zip(axes, PANELS):
        draw_panel(ax, curves_by_experiment[experiment], title, default_name, labels)
    axes[0].set_ylabel("五折均方根误差", color=MUTED)
    fig.suptitle("树模型参数比较", color=INK, fontsize=13)
    fig.tight_layout()
    output_path.parent.mkdir(exist_ok=True)
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


def main():
    """命令行入口：python -m viz.tree_params"""
    setup_logging("viz.log")

    conn = sqlite3.connect(DB_PATH)
    try:
        curves_by_experiment = {experiment: load_curves(conn, experiment) for experiment, *_ in PANELS}
    finally:
        conn.close()

    output_path = FIGURES_DIR / OUTPUT_NAME
    draw(curves_by_experiment, output_path)
    logger.info("图存在 %s", output_path)


if __name__ == "__main__":
    main()
