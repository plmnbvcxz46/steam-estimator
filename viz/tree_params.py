"""树模型参数比较的曲线图：棵数 → 五折均方根误差。

上排三张曲线：叶子数（tree_size）、学习率（learning_rate）、每片叶子至少多少款（min_leaf）。
每种设置一条线，默认参数的线是蓝色，灰带是默认值上下 0.005，星号是选定的参数。
下排两张（fold_seeds）：换 5 个分折的随机种子，两组候选参数比默认好多少，
一张看均方根误差，一张看命中率；在零线以上就是比默认好。

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

# 选定的参数在学习率那张图上的位置：0.05 那条线的第 400 棵
CHOSEN_LINE = "lr_0.05"
CHOSEN_ITERATIONS = 400

# 分折种子检验的两组候选：名字、图例、颜色（和上排对应的线同色）
SEED_CANDIDATES = [
    ("lr_0.05", "选定参数：学习率 0.05，树的数量 400", "#eb6834"),
    ("min_100", "候选参数：叶子最小样本数 100，树的数量 200", "#1baf7a"),
]

# 每张小图：experiment、标题、默认那条线的名字、{线的名字: 图例}
PANELS = [
    ("tree_size", "最大叶子数", "leaves_31",
     {"leaves_15": "15", "leaves_31": "31 默认值", "leaves_63": "63"}),
    ("learning_rate", "学习率", "lr_0.1",
     {"lr_0.1": "0.1 默认值", "lr_0.05": "0.05"}),
    ("min_leaf", "叶子最小样本数", "min_20",
     {"min_20": "20 默认值", "min_50": "50", "min_100": "100"}),
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


def load_seed_gains(conn):
    """读分折种子检验，返回 {候选名: [(种子, 误差低了多少, 命中率高了多少), ...]}。

    都是和同一种分折下的默认参数比，正数就是比默认好。
    """
    rows = conn.execute(
        "SELECT variant, rmse, hit_rate FROM result_cv_scores WHERE experiment = 'fold_seeds'"
    ).fetchall()
    scores = {}
    for variant, rmse, hit_rate in rows:
        # "seed_3_lr_0.05" -> 种子 3、参数组 "lr_0.05"
        _, seed, name = variant.split("_", 2)
        scores[(int(seed), name)] = (rmse, hit_rate)

    seeds = sorted({seed for seed, _ in scores})
    gains = {}
    for name, _, _ in SEED_CANDIDATES:
        gains[name] = []
        for seed in seeds:
            default_rmse, default_hit = scores[(seed, "default")]
            rmse, hit = scores[(seed, name)]
            gains[name].append((seed, default_rmse - rmse, hit - default_hit))
    return gains


def draw_panel(ax, curves, title, default_name, labels):
    """一张小图：每种设置一条线，标出默认参数那个点和它上下 0.005 的灰带。"""
    default_rmse = dict(curves[default_name])[DEFAULT_ITERATIONS]
    ax.axhspan(default_rmse - BAND_WIDTH, default_rmse + BAND_WIDTH,
               color=BAND, alpha=0.6, linewidth=0, label=f"默认值 ±{BAND_WIDTH}")

    other_colors = iter(OTHER_COLORS)
    for name, label in labels.items():
        iterations, rmse = zip(*curves[name])
        color = DEFAULT_COLOR if name == default_name else next(other_colors)
        ax.plot(iterations, rmse, "-o", color=color, linewidth=2, markersize=4, label=label)
    ax.plot(DEFAULT_ITERATIONS, default_rmse, "o", color=DEFAULT_COLOR, markersize=10,
            markerfacecolor="none", markeredgewidth=2)
    if CHOSEN_LINE in curves:
        chosen_rmse = dict(curves[CHOSEN_LINE])[CHOSEN_ITERATIONS]
        ax.plot(CHOSEN_ITERATIONS, chosen_rmse, "*", color=INK, markersize=14, label="选定参数")

    ticks = [50, 100, 200, 500, 1000, 2000]
    ax.set_xscale("log")
    ax.set_xticks(ticks, [str(t) for t in ticks])
    ax.minorticks_off()
    ax.set_title(title, color=INK, fontsize=11)
    ax.set_xlabel("树的数量", color=MUTED)
    for side in ["top", "right"]:
        ax.spines[side].set_visible(False)
    ax.tick_params(colors=MUTED)
    ax.grid(True, axis="y", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, fontsize=9)


def draw_seed_panel(ax, gains, index, title, ylabel, scale):
    """下排一张：横轴是分折的随机种子，每组候选一条线，纵轴是比默认好多少，零线以上是更好。"""
    ax.axhline(0, color=DEFAULT_COLOR, linewidth=1.5, label="默认参数")
    for name, label, color in SEED_CANDIDATES:
        seeds = [point[0] for point in gains[name]]
        values = [point[index] * scale for point in gains[name]]
        ax.plot(seeds, values, "-o", color=color, linewidth=2, markersize=6, label=label)
    ax.set_xticks(seeds, [str(seed) for seed in seeds])
    ax.set_xlabel("分折随机种子", color=MUTED)
    ax.set_ylabel(ylabel, color=MUTED)
    ax.set_title(title, color=INK, fontsize=11)
    for side in ["top", "right"]:
        ax.spines[side].set_visible(False)
    ax.tick_params(colors=MUTED)
    ax.grid(True, axis="y", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)


def draw(curves_by_experiment, seed_gains, output_path):
    """上排三张曲线共用纵轴；下排两张是分折种子检验。"""
    plt.rcParams["font.sans-serif"] = CHINESE_FONTS
    plt.rcParams["axes.unicode_minus"] = False
    fig = plt.figure(figsize=(12, 8.4))
    grid = fig.add_gridspec(2, 6)

    top_axes = []
    for column, (experiment, title, default_name, labels) in enumerate(PANELS):
        share = top_axes[0] if top_axes else None
        ax = fig.add_subplot(grid[0, column * 2:column * 2 + 2], sharey=share)
        draw_panel(ax, curves_by_experiment[experiment], title, default_name, labels)
        top_axes.append(ax)
    top_axes[0].set_ylabel("均方根误差", color=MUTED)

    ax_rmse = fig.add_subplot(grid[1, 0:3])
    draw_seed_panel(ax_rmse, seed_gains, 1, "不同分折下均方根误差的降低量", "降低量", 1)
    draw_seed_panel(fig.add_subplot(grid[1, 3:6]), seed_gains, 2,
                    "不同分折下 ±30% 命中率的提升", "提升百分点", 100)
    # 下排两张的线相同，图例只放一份，摆在图的最下方，不压住数据
    handles, labels = ax_rmse.get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=len(labels), frameon=False, fontsize=9)
    fig.suptitle("树模型超参数比较", color=INK, fontsize=13)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    output_path.parent.mkdir(exist_ok=True)
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


def main():
    """命令行入口：python -m viz.tree_params"""
    setup_logging("viz.log")

    conn = sqlite3.connect(DB_PATH)
    try:
        curves_by_experiment = {experiment: load_curves(conn, experiment) for experiment, *_ in PANELS}
        seed_gains = load_seed_gains(conn)
    finally:
        conn.close()

    output_path = FIGURES_DIR / OUTPUT_NAME
    draw(curves_by_experiment, seed_gains, output_path)
    logger.info("图存在 %s", output_path)


if __name__ == "__main__":
    main()
