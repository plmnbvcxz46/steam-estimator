"""特征按组重要性的条形图：每组打乱后，五折成绩变成多少。

左图是均方根误差，右图是 ±30% 命中率，都画打乱后的原值，不画差值，
这样一眼能看出“从多少变成多少”。两条竖线作参照：
实线是全部特征原样的成绩，虚线是完全不用特征的固定倍数方法。
每组一条线段从实线画到打乱后的成绩：越长这组越重要，越靠近虚线说明模型丢掉的本事越多。
圆点是 5 种分折下的平均，黑线标出 5 种分折里的最小到最大。

只读 result_cv_scores，先运行 python -m analysis.feature_importance 和 python -m analysis.signal_a 写入。
"""

import logging
import sqlite3

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter

from common.log import setup_logging
from common.paths import DB_PATH, FIGURES_DIR
from viz.reviews_vs_players import CHINESE_FONTS

logger = logging.getLogger(__name__)

OUTPUT_NAME = "feature_importance.png"

BAR_COLOR = "#2a78d6"
INK = "#0b0b0b"
MUTED = "#52514e"
GRID = "#e4e3df"
# 两条参照线：原样成绩用深灰实线，固定倍数用橙色虚线
BASELINE_COLOR = "#52514e"
FIXED_COLOR = "#eb6834"

# 组名 -> 图上的名称
GROUP_LABELS = {
    "game_age": "游戏年龄",
    "steam_purchase": "Steam 购买比例",
    "price": "价格",
    "languages": "评测语言占比",
    "tags": "标签",
    "playtime": "评测时游玩时长",
    "total_reviews": "评测数",
    "positive_rate": "好评率",
}


def load_importance(conn):
    """读重要性成绩，返回 {名字: {"rmse": [...], "hit": [...]}}，每个列表是 5 种分折各一个值。

    名字是组名，外加 "baseline"（原样不打乱）。都是原值：均方根误差，命中率（0 到 1）。
    variant 形如 "seed_3_price"：种子 3 下把价格组打乱。
    """
    rows = conn.execute(
        "SELECT variant, rmse, hit_rate FROM result_cv_scores WHERE experiment = 'feature_importance'"
        " ORDER BY variant"
    ).fetchall()
    scores = {}
    for variant, rmse, hit_rate in rows:
        # "seed_3_steam_purchase" -> 组名 "steam_purchase"（组名里可能带下划线，只切两刀）
        _, _, name = variant.split("_", 2)
        scores.setdefault(name, {"rmse": [], "hit": []})
        scores[name]["rmse"].append(rmse)
        scores[name]["hit"].append(hit_rate)
    return scores


def load_fixed_multiplier(conn):
    """读固定倍数方法的成绩（experiment = methods），返回 (均方根误差, 命中率)。"""
    return conn.execute(
        "SELECT rmse, hit_rate FROM result_cv_scores WHERE experiment = 'methods' AND variant = 'fixed'"
    ).fetchone()


def mean(values):
    return sum(values) / len(values)


def draw_panel(ax, scores, names, key, fixed_value, title, value_format, label_gap, xlim):
    """一张图：每组一条线段，从原样成绩画到打乱后的成绩，端点的圆点是 5 种分折的平均。

    线段越长，这组越重要。黑线是 5 种分折的范围，两条竖线作参照。
    label_gap 为正时数值写在圆点右边，为负时写在左边：都写在远离原样的那一侧，不压住线。
    """
    positions = list(range(len(names)))
    baseline = mean(scores["baseline"][key])
    means = [mean(scores[name][key]) for name in names]
    lows = [min(scores[name][key]) for name in names]
    highs = [max(scores[name][key]) for name in names]

    ax.axvline(baseline, color=BASELINE_COLOR, linewidth=2, label="全部特征原样")
    ax.axvline(fixed_value, color=FIXED_COLOR, linewidth=2, linestyle="--", label="固定倍数方法")
    # 两条竖线的数值写在线的顶端，原来是多少一眼可见
    top = len(names) - 0.45
    for value, color in [(baseline, BASELINE_COLOR), (fixed_value, FIXED_COLOR)]:
        ax.text(value, top, value_format.format(value), ha="center", va="bottom",
                color=color, fontsize=9)
    ax.hlines(positions, baseline, means, color=BAR_COLOR, linewidth=6, alpha=0.35)
    ax.hlines(positions, lows, highs, color=INK, linewidth=2, label="5 种分折的最小值到最大值")
    ax.plot(means, positions, "o", color=BAR_COLOR, markersize=9, label="打乱该组后：5 种分折的平均值")

    for position, value, low, high in zip(positions, means, lows, highs):
        if label_gap > 0:
            ax.text(high + label_gap, position, value_format.format(value),
                    va="center", ha="left", color=MUTED, fontsize=9)
        else:
            ax.text(low + label_gap, position, value_format.format(value),
                    va="center", ha="right", color=MUTED, fontsize=9)

    ax.set_xlim(xlim)
    ax.set_title(title, color=INK, fontsize=11)
    for side in ["top", "right"]:
        ax.spines[side].set_visible(False)
    ax.tick_params(colors=MUTED)
    ax.grid(True, axis="x", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)


def draw(scores, fixed, output_path):
    """左右两张共用纵轴：左边均方根误差，右边命中率。最重要的组在最上面。"""
    plt.rcParams["font.sans-serif"] = CHINESE_FONTS
    plt.rcParams["axes.unicode_minus"] = False

    # 按打乱后的平均误差从小到大排：纵轴从下往上数，误差最大（最重要）的落在最上面
    names = sorted(GROUP_LABELS, key=lambda name: mean(scores[name]["rmse"]))
    fixed_rmse, fixed_hit = fixed

    fig, (ax_rmse, ax_hit) = plt.subplots(1, 2, figsize=(11, 4.8), sharey=True)
    # 误差越大越差，往右画；命中率越低越差，往左画
    draw_panel(ax_rmse, scores, names, "rmse", fixed_rmse, "均方根误差",
               "{:.3f}", 0.008, (0.65, 1.06))
    draw_panel(ax_hit, scores, names, "hit", fixed_hit, "±30% 命中率",
               "{:.1%}", -0.004, (0.22, 0.48))
    ax_hit.xaxis.set_major_formatter(PercentFormatter(xmax=1, decimals=0))
    ax_rmse.set_yticks(list(range(len(names))), [GROUP_LABELS[name] for name in names])

    # 两张的图例相同，只放一份，摆在图的最下方
    handles, labels = ax_rmse.get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=len(labels), frameon=False, fontsize=9)
    fig.suptitle("特征按组置换重要性", color=INK, fontsize=13)
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    output_path.parent.mkdir(exist_ok=True)
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


def main():
    """命令行入口：python -m viz.feature_importance"""
    setup_logging("viz.log")

    conn = sqlite3.connect(DB_PATH)
    try:
        scores = load_importance(conn)
        fixed = load_fixed_multiplier(conn)
    finally:
        conn.close()

    output_path = FIGURES_DIR / OUTPUT_NAME
    draw(scores, fixed, output_path)
    logger.info("图存在 %s", output_path)


if __name__ == "__main__":
    main()
