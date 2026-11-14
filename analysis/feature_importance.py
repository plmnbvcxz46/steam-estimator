"""特征按组的重要性：模型训练好后，把一组列打乱，看误差涨多少。

好比考试时把某道题的条件涂乱：分数掉得越多，说明模型越靠这组信息。
按组打乱而不是按单列：标签有 192 列，单列看每列都很小；价格几列意思相近，
只打乱一列，模型还能靠另一列补上。

换 5 种分折方式各跑一遍，涨幅每种都为正才算这组有用。
只写成绩表（result_cv_scores），viz.feature_importance 读表画图。

入口：python -m analysis.feature_importance
"""

import sqlite3

import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor

from analysis.evaluation import N_FOLDS, load_train_samples, make_folds, save_experiment
from analysis.model_inputs import LANGUAGE_GROUPS, build_inputs, choose_tags
from analysis.signal_a import TREE_PARAMS
from common.paths import DB_PATH

# 和参数比较的分折方式检验用同样 5 个种子
FOLD_SEEDS = [0, 1, 2, 3, 4]

# 特征分组：组名 -> 这组的列。标签列太多，在 feature_groups 里按 "tag_" 开头找出来
FIXED_GROUPS = {
    "game_age": ["game_age_years"],
    "steam_purchase": ["steam_purchase_ratio"],
    "price": ["price_at_cutoff_usd", "avg_price_usd",
              "frac_time_cut25", "frac_time_cut50", "frac_time_cut75"],
    "languages": list(LANGUAGE_GROUPS),
    "playtime": ["playtime_median_hrs"],
    "positive_rate": ["positive_rate"],
    "total_reviews": ["total_reviews"],
}


def feature_groups(inputs):
    """返回 {组名: 列名列表}：固定的 7 组，再加上所有标签列组成的 tags 组。"""
    # dict(...) 复制一份，往里加 tags 时不改动 FIXED_GROUPS 本身
    groups = dict(FIXED_GROUPS)
    groups["tags"] = [column for column in inputs.columns if column.startswith("tag_")]

    # 每一列都要恰好属于一组：漏了的列不会被打乱，重要性就少算了
    grouped = [column for columns in groups.values() for column in columns]
    if sorted(grouped) != sorted(inputs.columns):
        raise ValueError("特征分组和模型输入的列对不上")
    return groups


def shuffle_group(test_inputs, columns, rng):
    """把考题里一组列的值打乱，返回打乱后的副本，原表不动。

    一组里的几列用同一种打乱顺序：组内几列之间的搭配保留，只切断它们和这款游戏的对应。
    """
    shuffled = test_inputs.copy()
    # 一个打乱后的行号顺序，这组所有列共用
    order = rng.permutation(len(test_inputs))
    # .to_numpy() 去掉原来的行标签再放回去，否则 pandas 会按行标签对齐，等于没打乱
    shuffled[columns] = test_inputs[columns].to_numpy()[order]
    return shuffled


def importance_cv(inputs, ln_k, folds, groups, rng):
    """一种分折方式下的五折：每折训练一次，先在原样的考题上预测，再每组打乱后各预测一次。

    返回 {"baseline": 每款预测, 组名: 每款预测, ...}，顺序和输入相同。
    打乱只换考题、不重新训练，所以只比原来多几次预测，不多训练。
    """
    # TODO 下一步填


def main():
    """读训练样本，5 种分折方式各跑一遍，写进 experiment = feature_importance。"""
    # TODO 下一步填


if __name__ == "__main__":
    main()
