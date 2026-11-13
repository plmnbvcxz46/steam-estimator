"""样本表的评测计数类特征：好评率、Steam 内购买占比、各语言占比。

数据来自 cleaned_review_counts 的条数，这里只做除法。
"""

from pipeline.review_counts import LANGUAGES


def review_count_features(total_reviews, positive_reviews, steam_purchase_reviews, language_reviews):
    """评测计数这一类特征：都是“某类评测数 ÷ 评测总数”。

    language_reviews 是 {语言代码: 该语言评测数}，13 种语言。
    返回一个 dict：好评率、Steam 内购买占比、13 种语言的占比和 13 种之外的占比，共 16 项。

    存占比不存条数：条数 = 评测数 × 占比，两者重复；
    占比在评测多的游戏和评测少的游戏之间才能比。
    """
    features = {
        "positive_rate": positive_reviews / total_reviews,
        "steam_purchase_ratio": steam_purchase_reviews / total_reviews,
    }

    known_language_reviews = 0
    for language in LANGUAGES:
        count = language_reviews[language]
        features["share_" + language] = count / total_reviews
        known_language_reviews += count

    # 用条数相减再除，不用 1 减 13 个占比：小数相减会留下 -0.00000001 这样的尾巴
    features["share_other"] = (total_reviews - known_language_reviews) / total_reviews
    return features
