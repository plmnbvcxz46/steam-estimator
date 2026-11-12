"""探查图：评测数和真实玩家数是什么关系。

横轴是每款游戏截至 2018-07-01 的评测总数，纵轴是同一时间的真实玩家数，一款游戏一个点。
整个项目的出发点是“玩家数 ≈ 评测数 × k”，这张图用来看这个说法到底有多准。

这是临时的探查图，直接读了两张 raw 表。按设计 viz 应该读清洗后的 cleaned_samples，
等那张表建好，这里的查询就换成读它。
"""

import logging
import sqlite3

import matplotlib

# 只把图存成文件，不弹窗口。要在导入 pyplot 之前设置
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from common.log import setup_logging
from common.paths import DB_PATH, FIGURES_DIR

logger = logging.getLogger(__name__)

CUTOFF_DATE = "2018-07-01"  # 真实玩家数是这一天的，评测数也只数到这一天
OUTPUT_NAME = "reviews_vs_players.png"

# 每款游戏在评测表里有 15 行（15 种数法），这里只要“全部评测”那一行（query = 'all'）。
# JOIN 只留下两张表里都有的游戏：已下架的游戏查不到评测数，不会出现在结果里
POINTS_SQL = """
SELECT p.appid, r.total, p.players
FROM raw_ars_players_2018 AS p
JOIN raw_review_counts AS r ON r.appid = p.appid
WHERE r.cutoff_date = ? AND r.query = 'all'
"""

# matplotlib 默认字体没有中文，会画成方块。按顺序找，用第一个机器上有的
CHINESE_FONTS = ["Noto Sans CJK SC", "Microsoft YaHei", "SimHei"]


def load_points(conn):
    """查出每款游戏的 (appid, 评测数, 玩家数)。"""
    return conn.execute(POINTS_SQL, (CUTOFF_DATE,)).fetchall()


def split_zero_reviews(rows):
    """把评测数为 0 的游戏分出来单独数，不悄悄丢掉。返回（评测数大于 0 的行，评测数为 0 的款数）。

    评测数为 0 时对数坐标上画不出，k（玩家数 ÷ 评测数）也算不出来。
    """
    points = []
    zero_count = 0
    for row in rows:
        if row[1] > 0:
            points.append(row)
        else:
            zero_count += 1
    return points, zero_count


def draw(points, zero_count, output_path):
    """把每款游戏画成一个点，存成图片。points 里的评测数都大于 0。"""
    reviews = [total for _, total, _ in points]
    players = [player_count for _, _, player_count in points]

    plt.rcParams["font.sans-serif"] = CHINESE_FONTS
    fig, ax = plt.subplots(figsize=(8, 6))

    # 一万多个点会互相盖住，所以点画小、画半透明：颜色越深的地方游戏越多
    ax.scatter(reviews, players, s=6, alpha=0.25, color="#2a6fb0", linewidths=0)

    # 游戏之间差几万倍，不取对数的话绝大多数点会挤在左下角
    ax.set_xscale("log")
    ax.set_yscale("log")

    ax.set_xlabel(f"截至 {CUTOFF_DATE} 的评测数（对数坐标，底数 10）")
    ax.set_ylabel(f"{CUTOFF_DATE} 的真实玩家数（对数坐标，底数 10）")
    ax.set_title("评测数与真实玩家数")
    ax.grid(True, color="#dddddd", linewidth=0.5)
    ax.set_axisbelow(True)  # 网格线画在点的下面

    # 对数坐标上没有 0 的位置，评测数为 0 的游戏画不出来，在图上写明有多少
    note = (
        f"样本量 {len(points)} 款；另有 {zero_count} 款评测数为 0，对数坐标上画不出。\n"
        "数据来源：玩家数为 Ars Technica 整理的 2018-07-01 玩家数表，评测数为 Steam 评测接口。"
    )
    fig.text(0.01, 0.01, note, fontsize=8, color="#555555")
    fig.subplots_adjust(bottom=0.17)

    output_path.parent.mkdir(exist_ok=True)
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


def main():
    """命令行入口：python -m viz.reviews_vs_players"""
    setup_logging("viz.log")

    conn = sqlite3.connect(DB_PATH)
    try:
        rows = load_points(conn)
        truth_count = conn.execute(
            "SELECT COUNT(*) FROM raw_ars_players_2018"
        ).fetchone()[0]
    finally:
        conn.close()

    points, zero_count = split_zero_reviews(rows)

    logger.info(
        "有真实玩家数的游戏 %d 款：查到评测数 %d 款（其中评测数为 0 的 %d 款），查不到 %d 款",
        truth_count,
        len(rows),
        zero_count,
        truth_count - len(rows),
    )

    output_path = FIGURES_DIR / OUTPUT_NAME
    draw(points, zero_count, output_path)
    logger.info("画了 %d 个点，图存在 %s", len(points), output_path)


if __name__ == "__main__":
    main()
