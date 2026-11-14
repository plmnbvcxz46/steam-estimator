"""样本表 -> 模型输入：把样本表的列变成一张全是数字的表。

样本表为了好查，标签存成一串文字、语言存 14 列占比；模型要的是一列一个数字。
线性回归对照和树模型都从这里取输入，两边用的是同一套列。

怎么变在这里写成参数（标签至少多少款、语言怎么合并），换方案不用重建样本表。
"""

import pandas as pd

# 一个标签至少有多少款训练游戏打了才单独成一列；太少的学不出规律
MIN_TAG_GAMES = 100

# 语言合并成 9 组：组名 -> 样本表里要相加的占比列。
# 拉美西语并进西语：2018 年以前它几乎为 0，单独一列学不到，以后的年份却不为 0
LANGUAGE_GROUPS = {
    "lang_english": ["share_english"],
    "lang_russian": ["share_russian"],
    "lang_chinese": ["share_schinese", "share_tchinese"],
    "lang_german": ["share_german"],
    "lang_french": ["share_french"],
    "lang_spanish": ["share_spanish", "share_latam"],
    "lang_brazilian": ["share_brazilian"],
    "lang_minor": ["share_japanese", "share_koreana", "share_polish", "share_turkish"],
    "lang_other": ["share_other"],
}

# 原样进模型的数值列
NUMERIC_COLUMNS = [
    "total_reviews",
    "positive_rate",
    "steam_purchase_ratio",
    "playtime_median_hrs",
    "game_age_years",
    "price_at_cutoff_usd",
    "avg_price_usd",
    "frac_time_cut25",
    "frac_time_cut50",
    "frac_time_cut75",
]


def choose_tags(tags, min_games=MIN_TAG_GAMES):
    """选出单独成列的标签：至少 min_games 款游戏有的。

    tags 是样本表的 tags 列（每款一串 "A|B|C"）。返回标签名的列表，顺序固定，
    查询时要按同一份清单、同样的顺序展开。
    """
    # 数每个标签有几款游戏打了。一款里同一个标签只出现一次，所以数次数就是数款数
    counts = {}
    for tag_string in tags:
        # 空串表示这款没有标签（真实数据里有 2 款），split 会切出一个 ""，要跳过
        if tag_string == "":
            continue
        for tag in tag_string.split("|"):
            counts[tag] = counts.get(tag, 0) + 1

    chosen = [tag for tag, count in counts.items() if count >= min_games]
    # 按名字排序：清单的顺序只取决于有哪些标签，不取决于游戏的先后
    return sorted(chosen)


def expand_tags(tags, tag_list):
    """把标签串展开成 0/1 表：一个标签一列，这款有这个标签记 1。

    tag_list 之外的标签直接忽略。列名是 "tag_" 加标签名，如 "tag_Action"。
    """
    rows = []
    for tag_string in tags:
        # 用集合查“有没有”，比在列表里一个个找快
        game_tags = set(tag_string.split("|"))
        rows.append([1 if tag in game_tags else 0 for tag in tag_list])
    columns = ["tag_" + tag for tag in tag_list]
    # index 跟着 tags 走，拼表时才能按行对上
    return pd.DataFrame(rows, columns=columns, index=tags.index)


def merge_languages(samples):
    """把 14 列语言占比按 LANGUAGE_GROUPS 加成 9 列。"""
    merged = pd.DataFrame(index=samples.index)
    for group, columns in LANGUAGE_GROUPS.items():
        # 一组里的几列逐行相加
        merged[group] = samples[columns].sum(axis=1)
    return merged


def build_inputs(samples, tag_list):
    """拼出模型输入：数值列 + 9 列语言 + 标签 0/1 列。缺失的照样留空，不填。"""
    numeric = samples[NUMERIC_COLUMNS]
    languages = merge_languages(samples)
    tag_columns = expand_tags(samples["tags"], tag_list)
    # axis=1 是左右拼：行数不变，列接在后面
    return pd.concat([numeric, languages, tag_columns], axis=1)
