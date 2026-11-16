"""信号 B 的拟合图：评测者游玩时长的中位数和人均游玩小时是什么关系。

横轴是评测者时长的中位数 t，纵轴是人均游玩小时 h = 总小时 H ÷ 真实玩家数，一款游戏一个点。
图上画出拟合的直线 ln h = a + b × ln t，再画一条虚线 h = t 作参照：
拟合线比虚线平，短游戏的 h 和 t 差不多，越耐玩的游戏 h 比 t 低得越多，
说明越耐玩，写评测的人比普通玩家多玩得越多。

读样本表 cleaned_samples 的训练行，和 analysis.signal_b 是同一批游戏（评测数达到门槛、能算出 H）。
直线用全部这些游戏拟合一次，只为画图；正式成绩是五折交叉验证的，跑 python -m analysis.signal_b 看。
"""

import logging
import sqlite3

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from analysis.evaluation import load_train_samples
from analysis.signal_b import fit_line
from common.log import setup_logging
from common.paths import DB_PATH, FIGURES_DIR
from viz.method_comparison import GRID, INK, MUTED, style_axes
from viz.reviews_vs_players import CHINESE_FONTS

logger = logging.getLogger(__name__)

OUTPUT_NAME = "signal_b_fit.png"

POINT_COLOR = "#2a78d6"
LINE_COLOR = "#eb6834"

# 两条轴共用的范围（小时）
AXIS_MIN = 0.005
AXIS_MAX = 500


def load_points(samples):
    """从训练样本里取出能算 H 的游戏，返回 (评测者时长 t, 人均小时 h) 两列。"""
    has_hours = samples["charts_total_hours"].notna()
    subset = samples[has_hours]
    playtime = subset["playtime_median_hrs"].to_numpy()
    # 人均小时用到了答案（真实玩家数），只在训练和画图时能算
    hours_per_player = (subset["charts_total_hours"] / subset["truth_value"]).to_numpy()
    return playtime, hours_per_player


def draw(playtime, hours_per_player, a, b, output_path):
    """画散点、拟合线和 h = t 参照线，存成图片。"""
    plt.rcParams["font.sans-serif"] = CHINESE_FONTS
    plt.rcParams["axes.unicode_minus"] = False
    fig, ax = plt.subplots(figsize=(7, 7))

    # 三千多个点会互相盖住，画小、半透明：颜色越深的地方游戏越多
    ax.scatter(playtime, hours_per_player, s=6, alpha=0.3, color=POINT_COLOR, linewidths=0,
               label=f"游戏（{len(playtime)} 款）")

    # 直线在对数坐标上才是直的：在 ln t 上取等距的点，换回小时再画
    line_t = np.geomspace(playtime.min(), playtime.max(), 100)
    line_h = np.exp(a + b * np.log(line_t))
    ax.plot(line_t, line_h, color=LINE_COLOR, linewidth=2,
            label=f"拟合：ln h = {a:.2f} + {b:.2f} × ln t")
    ax.plot(line_t, line_t, color=MUTED, linewidth=1.2, linestyle="--", label="参照：h = t")

    # 对数坐标，刻度直接写小时数
    ax.set_xscale("log")
    ax.set_yscale("log")
    # 两条轴同样的范围、同样的比例：h = t 才是一条 45 度的对角线，偏离多少一眼能看出。
    # 下限放到 0.005：少数游戏的人均小时不到 0.1，玩家数里有很多买了没怎么玩的
    ax.set_xlim(AXIS_MIN, AXIS_MAX)
    ax.set_ylim(AXIS_MIN, AXIS_MAX)
    ax.set_aspect("equal")
    ticks = [0.01, 0.1, 1, 10, 100]
    ax.set_xticks(ticks, [f"{t:g}" for t in ticks])
    ax.set_yticks(ticks, [f"{t:g}" for t in ticks])
    ax.minorticks_off()
    ax.set_xlabel("评测者游玩时长中位数 t（小时）", color=MUTED)
    ax.set_ylabel("人均游玩小时 h（小时）", color=MUTED)
    ax.set_title("信号 B：评测者时长与人均游玩小时", color=INK, fontsize=13)
    # 图例里的点放大一些，不然看不见
    ax.legend(frameon=False, loc="upper left", markerscale=3)
    style_axes(ax)
    # style_axes 只画横向网格，散点图两个方向都要
    ax.grid(True, axis="both", color=GRID, linewidth=0.6)

    fig.tight_layout()
    output_path.parent.mkdir(exist_ok=True)
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


def main():
    """命令行入口：python -m viz.signal_b_fit"""
    setup_logging("viz.log")

    conn = sqlite3.connect(DB_PATH)
    try:
        samples = load_train_samples(conn)
    finally:
        conn.close()

    playtime, hours_per_player = load_points(samples)
    a, b = fit_line(np.log(playtime), np.log(hours_per_player))
    logger.info("%d 款游戏，拟合 a = %.3f，b = %.3f", len(playtime), a, b)

    output_path = FIGURES_DIR / OUTPUT_NAME
    draw(playtime, hours_per_player, a, b, output_path)
    logger.info("图存在 %s", output_path)


if __name__ == "__main__":
    main()
