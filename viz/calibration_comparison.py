"""校准的对比图：校准集上各种做法的留一法成绩。

版式和三种方法的对比图（viz.method_comparison）相同：
上半张是“估计 ÷ 真值”的分布，灰带是 ±30% 命中范围；下半张是命中率和均方根误差两组柱子。

画两张：
- 全部校准游戏：固定倍数、树模型原样（校准前）、信号 A、融合；
- 两路都有的游戏：信号 A、信号 B、融合。
图上的信号 A、信号 B 都是校准后的。

读 result_cv_scores、result_cv_predictions 里 experiment = 'calibration'、'calibration_with_b' 的行，
先运行 python -m analysis.calibration 写入。
"""

import logging
import sqlite3

from common.log import setup_logging
from common.paths import DB_PATH, FIGURES_DIR
from viz.method_comparison import draw, load_ratios, load_scores

logger = logging.getLogger(__name__)

# 校准集只有一百来款，分布曲线用 16 格（默认 60 格时每格只有一两款）
N_BINS = 16

# 颜色沿用前面几张图：固定倍数蓝、信号 A 绿、融合紫；校准前的树模型用灰色
FIGURES = [
    (
        "calibration_comparison_all.png",
        "calibration",
        "全部",
        {
            "fixed": ("固定倍数", "#2a78d6"),
            "tree_raw": ("树模型原样", "#a3a29c"),
            "signal_a": ("信号 A", "#1baf7a"),
            "fused": ("融合", "#8e5bd6"),
        },
    ),
    (
        "calibration_comparison_with_b.png",
        "calibration_with_b",
        "两路信号都有的",
        {
            "signal_a": ("信号 A", "#1baf7a"),
            "signal_b": ("信号 B", "#2a78d6"),
            "fused": ("融合", "#8e5bd6"),
        },
    ),
]


def main():
    """命令行入口：python -m viz.calibration_comparison"""
    setup_logging("viz.log")

    conn = sqlite3.connect(DB_PATH)
    try:
        for output_name, experiment, label, variants in FIGURES:
            scores = load_scores(conn, experiment)
            ratios = load_ratios(conn, experiment)
            n_games = len(ratios["fused"])
            title = f"校准集上的留一法成绩（{label} {n_games} 款游戏）"
            output_path = FIGURES_DIR / output_name
            draw(scores, ratios, output_path, variants, title, N_BINS)
            logger.info("图存在 %s", output_path)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
