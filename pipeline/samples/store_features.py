"""样本表的商店信息类特征：游戏年龄、标签。

数据来自 cleaned_games 的上架日和标签，这里不读数据库，只做换算。
"""

from datetime import date

# 一年按 365.25 天算，把闰年摊进去
DAYS_PER_YEAR = 365.25


def store_features(cutoff_date, release_date, tags):
    """商店信息这一类特征。

    cutoff_date、release_date 是 "YYYY-MM-DD" 文字；tags 是 cleaned_games.tags 那一串。
    返回一个 dict：game_age_years、tags，共 2 项。
    """
    # 两个日期相减得到相差的天数，再换成年。不取对数、不截断，线性回归对照里再取对数
    days = (date.fromisoformat(cutoff_date) - date.fromisoformat(release_date)).days
    return {
        "game_age_years": days / DAYS_PER_YEAR,
        # 原样抄过去，样本表里还是一列；训练时再展开成 0/1 列
        "tags": tags,
    }
