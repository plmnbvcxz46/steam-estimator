"""探查图：评测数和真实玩家数是什么关系，一个固定倍数能猜中多少。

横轴是每款游戏截至 2018-07-01 的评测总数，纵轴是同一时间的真实玩家数，一款游戏一个点。
整个项目的出发点是“玩家数 ≈ 评测数 × k”，这张图用来看这个说法到底有多准。

图上再画出固定倍数基线：所有游戏用同一个 k（训练集 ln k 的平均值），
在对数坐标上是一条斜线；±30% 的命中范围是贴着它的一条带子，落在带里的点就是猜中的。
评测 1 到 9 条的游戏不进训练，画成灰色，不算进带内比例。

读样本表 cleaned_samples 的训练行：图上的游戏和算成绩用的是同一批
（已排除非游戏、已下架和评测数为 0 的）。
"""

import logging
import sqlite3

import matplotlib

# 只把图存成文件，不弹窗口。要在导入 pyplot 之前设置
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from analysis.evaluation import DEFAULT_MIN_REVIEWS, HIT_HIGH, HIT_LOW
from common.log import setup_logging
from common.paths import DB_PATH, FIGURES_DIR

logger = logging.getLogger(__name__)

CUTOFF_DATE = "2018-07-01"  # 真实玩家数是这一天的，评测数也只数到这一天
OUTPUT_NAME = "reviews_vs_players.png"

# 样本表的训练行已经筛过：是游戏、有玩家数、截止日前评测数大于 0
POINTS_SQL = """
SELECT appid, total_reviews, truth_value
FROM cleaned_samples
WHERE split = 'train' AND cutoff_date = ?
ORDER BY appid
"""

# matplotlib 默认字体没有中文，会画成方块。按顺序找，用第一个机器上有的
CHINESE_FONTS = ["Noto Sans CJK SC", "Microsoft YaHei", "SimHei"]


def load_points(conn):
    """查出每款游戏的 (appid, 评测数, 玩家数)，评测数都大于 0。"""
    return conn.execute(POINTS_SQL, (CUTOFF_DATE,)).fetchall()


def fit_fixed_multiplier(points):
    """用评测数达到门槛的游戏，算出固定倍数和落在命中带里的比例。

    倍数取 ln k 的平均值再换回来，和 analysis.baselines 的固定倍数同一种算法。
    这里用全部训练游戏算一次，只为画图；正式成绩是五折交叉验证的，
    跑 python -m analysis.baselines 看，两者只差一点点。
    """
    ln_k = []
    for _, reviews, players in points:
        if reviews >= DEFAULT_MIN_REVIEWS:
            ln_k.append(np.log(players / reviews))
    ln_k = np.array(ln_k)
    multiplier = np.exp(ln_k.mean())

    # 估计 ÷ 真值 = 固定的 k ÷ 这款的 k
    ratio = multiplier / np.exp(ln_k)
    in_band = (ratio >= HIT_LOW) & (ratio <= HIT_HIGH)
    return multiplier, in_band.mean()


def draw(points, multiplier, in_band_rate, output_path):
    """画散点、固定倍数线和 ±30% 命中带，存成图片。points 里的评测数都大于 0。"""
    reviews = np.array([total for _, total, _ in points])
    players = np.array([player_count for _, _, player_count in points])
    in_training = reviews >= DEFAULT_MIN_REVIEWS

    plt.rcParams["font.sans-serif"] = CHINESE_FONTS
    fig, ax = plt.subplots(figsize=(8, 6))

    # 一万多个点会互相盖住，所以点画小、画半透明：颜色越深的地方游戏越多
    ax.scatter(
        reviews[~in_training], players[~in_training],
        s=6, alpha=0.25, color="#999999", linewidths=0,
        label=f"评测数 < {DEFAULT_MIN_REVIEWS}",
    )
    ax.scatter(
        reviews[in_training], players[in_training],
        s=6, alpha=0.25, color="#2a6fb0", linewidths=0,
        label=f"评测数 ≥ {DEFAULT_MIN_REVIEWS}（训练集）",
    )

    # 命中的条件是 0.7 ≤ 估计 ÷ 真值 ≤ 1.3，估计 = 倍数 × 评测数，
    # 换成真值的范围就是 估计 ÷ 1.3 到 估计 ÷ 0.7：上沿离中线比下沿远
    line_x = np.array([reviews.min(), reviews.max()])
    estimate = multiplier * line_x
    ax.fill_between(
        line_x, estimate / HIT_HIGH, estimate / HIT_LOW,
        color="#e8892b", alpha=0.3, linewidth=0,
        label=f"±30% 命中范围（{in_band_rate:.1%}）",
    )
    ax.plot(
        line_x, estimate, color="#c0561b", linewidth=1.2,
        label=f"固定倍数 k = {multiplier:.0f}",
    )

    # 游戏之间差几万倍，不取对数的话绝大多数点会挤在左下角
    ax.set_xscale("log")
    ax.set_yscale("log")

    ax.set_xlabel("评测数")
    ax.set_ylabel("玩家数")
    ax.set_title(f"评测数与玩家数（{CUTOFF_DATE}）")
    ax.grid(True, color="#dddddd", linewidth=0.5)
    ax.set_axisbelow(True)  # 网格线画在点的下面
    # 图例里的点放大、不透明，不然看不清颜色
    legend = ax.legend(loc="upper left", fontsize=8, markerscale=3)
    for handle in legend.legend_handles[:2]:
        handle.set_alpha(1)

    output_path.parent.mkdir(exist_ok=True)
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


def main():
    """命令行入口：python -m viz.reviews_vs_players"""
    setup_logging("viz.log")

    conn = sqlite3.connect(DB_PATH)
    try:
        points = load_points(conn)
    finally:
        conn.close()

    multiplier, in_band_rate = fit_fixed_multiplier(points)
    logger.info(
        "画了 %d 款；固定倍数 %.1f，训练集落在 ±30%% 带内的 %.1f%%",
        len(points),
        multiplier,
        in_band_rate * 100,
    )

    output_path = FIGURES_DIR / OUTPUT_NAME
    draw(points, multiplier, in_band_rate, output_path)
    logger.info("图存在 %s", output_path)


if __name__ == "__main__":
    main()
