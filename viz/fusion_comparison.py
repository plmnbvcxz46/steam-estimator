"""融合的对比图：只用信号 A、简单平均、按档加权三种做法的五折交叉验证成绩。

版式和三种方法的对比图（viz.method_comparison）相同：
上半张是“估计 ÷ 真值”的分布，灰带是 ±30% 命中范围；下半张是命中率和均方根误差两组柱子。

画两张：全部训练游戏一张（最终成绩），有信号 B 的游戏一张（融合真正改变的那部分；
没有 B 的游戏三种做法结果相同，放在一起会把差别冲淡）。

读 result_cv_predictions 里 experiment = 'fusion' 的行，先运行 python -m analysis.fusion 写入；
哪些游戏有 B 看 experiment = 'signal_b' 的行。成绩表只存了全部游戏的成绩，这里两张都按预测现算。
"""

import logging
import sqlite3

import numpy as np
import pandas as pd

from analysis.evaluation import score
from common.log import setup_logging
from common.paths import DB_PATH, FIGURES_DIR
from viz.method_comparison import draw

logger = logging.getLogger(__name__)

# A 沿用前面几张图里树模型的颜色
VARIANTS = {
    "signal_a": ("只用信号 A", "#1baf7a"),
    "simple_mean": ("简单平均", "#eb6834"),
    "binned_weighted": ("按档加权", "#8e5bd6"),
}


def load_predictions(conn):
    """读融合的五折预测，返回每款游戏一行：真值、三种做法的预测、有没有 B。"""
    predictions = pd.read_sql_query(
        "SELECT sample_id, variant, true_ln_k, predicted_ln_k FROM result_cv_predictions"
        " WHERE experiment = 'fusion'",
        conn,
    )
    table = predictions.pivot(index="sample_id", columns="variant", values="predicted_ln_k")
    table["true_ln_k"] = predictions.groupby("sample_id")["true_ln_k"].first()

    # 信号 B 的预测只存了有 B 的游戏
    with_b = pd.read_sql_query(
        "SELECT sample_id FROM result_cv_predictions"
        " WHERE experiment = 'signal_b' AND variant = 'signal_b'",
        conn,
    )["sample_id"]
    table["has_b"] = table.index.isin(with_b)
    return table


def scores_and_ratios(table):
    """按一批游戏算各做法的成绩和“估计 ÷ 真值”，格式和 method_comparison.draw 要的一样。"""
    scores = {}
    ratios = {}
    for variant in VARIANTS:
        scores[variant] = score(table["true_ln_k"], table[variant])
        ratios[variant] = np.exp(table[variant] - table["true_ln_k"]).to_numpy()
    return scores, ratios


def main():
    """命令行入口：python -m viz.fusion_comparison"""
    setup_logging("viz.log")

    conn = sqlite3.connect(DB_PATH)
    try:
        table = load_predictions(conn)
    finally:
        conn.close()

    figures = [
        ("fusion_comparison_all.png", table, "全部"),
        ("fusion_comparison_with_b.png", table[table["has_b"]], "有信号 B 的"),
    ]
    for output_name, subset, label in figures:
        scores, ratios = scores_and_ratios(subset)
        for variant, result in scores.items():
            logger.info("%s %s：均方根误差 %.3f，±30%% 命中率 %.1f%%", label, variant, result["rmse"], result["hit_rate"] * 100)
        title = f"只用信号 A 与两种融合的五折交叉验证成绩（{label} {len(subset)} 款游戏）"
        output_path = FIGURES_DIR / output_name
        draw(scores, ratios, output_path, VARIANTS, title)
        logger.info("图存在 %s", output_path)


if __name__ == "__main__":
    main()
