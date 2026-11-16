"""信号 A、B 的对比图：在能算 B 的游戏上，两路各自的五折交叉验证成绩。

版式和三种方法的对比图（viz.method_comparison）相同：
上半张是“估计 ÷ 真值”的分布，灰带是 ±30% 命中范围；下半张是命中率和均方根误差两组柱子。

只读 result_cv_scores、result_cv_predictions 里 experiment = 'signal_b' 的行，
先运行 python -m analysis.signal_b 写入。
"""

import logging
import sqlite3

from common.log import setup_logging
from common.paths import DB_PATH, FIGURES_DIR
from viz.method_comparison import draw, load_ratios, load_scores

logger = logging.getLogger(__name__)

OUTPUT_NAME = "signal_b_comparison.png"
EXPERIMENT = "signal_b"

# A 用三种方法对比图里树模型的颜色，B 用拟合图里散点的颜色，同一样东西在各张图里同一个颜色
VARIANTS = {
    "signal_a": ("信号 A（树模型）", "#1baf7a"),
    "signal_b": ("信号 B（在线人数）", "#2a78d6"),
}


def main():
    """命令行入口：python -m viz.signal_b_comparison"""
    setup_logging("viz.log")

    conn = sqlite3.connect(DB_PATH)
    try:
        scores = load_scores(conn, EXPERIMENT)
        ratios = load_ratios(conn, EXPERIMENT)
    finally:
        conn.close()

    n_games = len(ratios["signal_a"])
    for variant, result in scores.items():
        logger.info("%s：均方根误差 %.3f，±30%% 命中率 %.1f%%", variant, result["rmse"], result["hit_rate"] * 100)

    output_path = FIGURES_DIR / OUTPUT_NAME
    title = f"信号 A 与信号 B 的五折交叉验证成绩（{n_games} 款游戏）"
    draw(scores, ratios, output_path, VARIANTS, title)
    logger.info("图存在 %s", output_path)


if __name__ == "__main__":
    main()
