"""导入 Ars Technica 2018-07-01 玩家数表，写入 raw_ars_players_2018。"""


def parse_players(text):
    """把 ' 50,191,347 ' 这样的字符串转成整数 50191347。

    转不了就抛 ValueError，由调用者决定怎么记日志、跳不跳过。
    不在这里返回默认值：悄悄给个 0 会让坏数据混进数据库。
    """
    # 原件里数字两边有空格，中间有千分位逗号，先都去掉
    cleaned = text.strip().replace(",", "")

    # isdigit 只认 0-9，所以空串、字母、负号、小数点都会被挡住
    if not cleaned.isdigit():
        raise ValueError(f"玩家数不是合法的非负整数: {text!r}")

    return int(cleaned)
