import pandas as pd

from analysis.model_inputs import choose_tags, expand_tags, merge_languages


def test_choose_tags_keeps_common_tags_and_skips_empty():
    # Action 3 款、RPG 2 款、Indie 1 款；还有一款没有标签（真实数据里有 2 款是空串）
    tags = pd.Series(["Action|RPG", "Action|Indie", "RPG|Action", ""])

    assert choose_tags(tags, min_games=2) == ["Action", "RPG"]


def test_expand_tags_marks_one_when_game_has_tag():
    tags = pd.Series(["Action|RPG", "Indie", ""])

    expanded = expand_tags(tags, ["Action", "RPG"])

    # 清单之外的 Indie 被忽略；没有标签的那款全是 0
    assert list(expanded.columns) == ["tag_Action", "tag_RPG"]
    assert expanded.values.tolist() == [[1, 1], [0, 0], [0, 0]]


def test_merge_languages_adds_up_groups():
    # 一款游戏：简中 0.2、繁中 0.1、西语 0.1、拉美西语 0.05，其余都给 0，英语 0.55
    columns = [
        "english", "russian", "schinese", "tchinese", "german", "french", "spanish",
        "latam", "brazilian", "japanese", "koreana", "polish", "turkish", "other",
    ]
    row = {"share_" + name: 0.0 for name in columns}
    row.update(share_english=0.55, share_schinese=0.2, share_tchinese=0.1,
               share_spanish=0.1, share_latam=0.05)

    merged = merge_languages(pd.DataFrame([row]))

    assert merged.shape == (1, 9)
    assert merged["lang_chinese"][0] == 0.2 + 0.1
    assert merged["lang_spanish"][0] == 0.1 + 0.05
