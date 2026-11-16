"""校准里年龄项的依据：按游戏年龄分档，看倍数 k 随年龄怎么变。

四条线，每个年龄档一个点，纵轴是这一档 k 的几何平均（ln k 取平均再换回 k）：
- 训练集的真值：2018 年的规律，越老 k 越大，涨得很陡；
- 校准集上树模型的估计：树照 2018 年的规律估；
- 校准集的真值：近年游戏的 k 随年龄基本持平；
- 校准集上校准后的信号 A：加了年龄项之后，回到真值附近。

读样本表（年龄、训练集的真值）和 result_cv_predictions 里 experiment = 'calibration' 的行，
先运行 python -m analysis.calibration 写入。
"""

import logging
import sqlite3

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from analysis.evaluation import load_train_samples
from common.log import setup_logging
from common.paths import DB_PATH, FIGURES_DIR
from viz.method_comparison import INK, MUTED, style_axes
from viz.reviews_vs_players import CHINESE_FONTS

logger = logging.getLogger(__name__)

OUTPUT_NAME = "calibration_age.png"

# 年龄档的分界（年）和图上的名字
AGE_EDGES = [0, 0.1, 0.5, 2, 5, 100]
AGE_LABELS = ["不到 0.1 年", "0.1–0.5 年", "0.5–2 年", "2–5 年", "5 年以上"]

# 颜色沿用前面的图：树模型原样灰、信号 A 绿；训练集真值用橙，校准集真值用黑
LINES = {
    "train_truth": ("训练集的真值（2018 年）", "#eb6834"),
    "tree_raw": ("校准集：树模型原样", "#a3a29c"),
    "signal_a": ("校准集：信号 A（校准后）", "#1baf7a"),
    "calib_truth": ("校准集的真值", INK),
}


def load_points(conn):
    """读出要画的数，返回 {线的代号: 每个年龄档 ln k 的平均}，以及校准集每档的游戏数。"""
    # 训练集：年龄和真值的 ln k 都在样本表里
    train = load_train_samples(conn)
    train_bins = pd.cut(train["game_age_years"], AGE_EDGES, include_lowest=True)
    points = {"train_truth": train.groupby(train_bins, observed=True)["ln_k"].mean().to_numpy()}

    # 校准集：预测表里每款游戏的真值、树模型原样的估计、校准后的信号 A，年龄从样本表按编号对上
    calib = pd.read_sql_query(
        "SELECT p.variant, p.true_ln_k, p.predicted_ln_k, s.game_age_years"
        " FROM result_cv_predictions p JOIN cleaned_samples s ON s.sample_id = p.sample_id"
        " WHERE p.experiment = 'calibration' AND p.variant IN ('tree_raw', 'signal_a')",
        conn,
    )
    calib["bin"] = pd.cut(calib["game_age_years"], AGE_EDGES, include_lowest=True)
    for variant in ["tree_raw", "signal_a"]:
        rows = calib[calib["variant"] == variant]
        points[variant] = rows.groupby("bin", observed=True)["predicted_ln_k"].mean().to_numpy()
    # 两种做法的真值是同一批，取其中一种的就行
    rows = calib[calib["variant"] == "tree_raw"]
    points["calib_truth"] = rows.groupby("bin", observed=True)["true_ln_k"].mean().to_numpy()
    counts = rows.groupby("bin", observed=True).size().to_numpy()
    return points, counts


def draw(points, counts, output_path):
    """一张图：横轴年龄档，纵轴 k（对数刻度），四条折线。"""
    plt.rcParams["font.sans-serif"] = CHINESE_FONTS
    plt.rcParams["axes.unicode_minus"] = False
    fig, ax = plt.subplots(figsize=(9, 5.5))

    positions = np.arange(len(AGE_LABELS))
    for variant, (name, color) in LINES.items():
        # 画的是 k 本身：ln k 的平均换回 k
        ax.plot(positions, np.exp(points[variant]), marker="o", color=color, linewidth=2, label=name)

    ax.set_yscale("log")
    ticks = [20, 30, 50, 100, 200]
    ax.set_yticks(ticks, [str(t) for t in ticks])
    ax.minorticks_off()
    # 横轴标签下面写校准集每档的游戏数，游戏少的点更不稳
    ax.set_xticks(positions, [f"{label}\n校准集 {count} 款" for label, count in zip(AGE_LABELS, counts)])
    ax.set_xlabel("游戏年龄（截止日减上架日）", color=MUTED)
    ax.set_ylabel("倍数 k 的几何平均（对数刻度，底数 10）", color=MUTED)
    ax.set_title("倍数 k 随游戏年龄的变化：训练集、校准集和树模型的估计", color=INK, fontsize=13)
    ax.legend(frameon=False)
    style_axes(ax)

    fig.tight_layout()
    output_path.parent.mkdir(exist_ok=True)
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


def main():
    """命令行入口：python -m viz.calibration_age"""
    setup_logging("viz.log")

    conn = sqlite3.connect(DB_PATH)
    try:
        points, counts = load_points(conn)
    finally:
        conn.close()

    output_path = FIGURES_DIR / OUTPUT_NAME
    draw(points, counts, output_path)
    logger.info("图存在 %s", output_path)


if __name__ == "__main__":
    main()
