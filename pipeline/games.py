"""清洗商店信息：raw_appdetails -> cleaned_games。

raw_appdetails 存的是商店页原文，这里把它整理成后面能直接用的样子：
- 只留游戏，去掉 DLC、原声带等
- 发行日从 "Sep 26, 2013" 换成 "2013-09-26"
- 类型里去掉不是类型的词

cleaned 表是派生数据：每次运行都整张表重建，结果只取决于 raw 表。

进了这张表的行保证是干净的：发行日解析不了的游戏不写入，原文记到日志里。
看日志补全解析规则后重跑，这些游戏就会进来。
"""

import logging
from collections import Counter
from datetime import datetime

logger = logging.getLogger(__name__)

# 商店页发行日的写法，如 "Sep 26, 2013"（采集时指定了英文）
STORE_DATE_FORMAT = "%b %d, %Y"

# 发行日的出处。现在只有商店一种；以后抢先体验的游戏会改用第一条评测的日期，
# 那时这一列会多出一个取值
RELEASE_DATE_SOURCE_STORE = "store"

# 商店把这两个词也放在 genres 里，但它们说的是游戏“现在”的状态，不是类型。
# 训练样例的截止日是 2018 年，留着它们等于用了未来的信息
NOT_GENRES = {"Early Access", "Free To Play"}

CREATE_TABLE_SQL = """
CREATE TABLE cleaned_games (
    appid               INTEGER PRIMARY KEY,
    name                TEXT NOT NULL,
    release_date        TEXT NOT NULL,
    release_date_source TEXT NOT NULL,
    genres              TEXT NOT NULL
)
"""

INSERT_SQL = """
INSERT INTO cleaned_games (appid, name, release_date, release_date_source, genres)
VALUES (:appid, :name, :release_date, :release_date_source, :genres)
"""


def parse_release_date(text):
    """把商店页的发行日原文换成 YYYY-MM-DD；解析不了时返回 None。

    目前只认 "Sep 26, 2013" 这一种写法，已采集的数据里全是它。
    别的写法（如 "Coming soon"）等全量采集后看日志里有哪些，再决定怎么处理。
    """
    try:
        # %b 是英文月份缩写（Sep），%d 是日，%Y 是四位年份
        parsed = datetime.strptime(text, STORE_DATE_FORMAT)
    except ValueError:
        # strptime 对不上格式时抛 ValueError
        return None
    return parsed.strftime("%Y-%m-%d")


def date_shape(text):
    """把一段文字换成它的“形状”：数字换成 9，字母换成 a，其余字符不动。

    例如 "Mar 2017" 和 "Apr 2018" 都是 "aaa 9999"。
    用来把没认出来的发行日按写法归类，而不是每个具体日期各算一种。
    """
    shape = ""
    for char in text:
        if char.isdigit():
            shape += "9"
        elif char.isalpha():
            shape += "a"
        else:
            shape += char
    return shape


def clean_genres(text):
    """去掉 genres 里不是类型的词。输入输出都是用 | 连接的字符串。"""
    kept = []
    for genre in text.split("|"):
        if genre not in NOT_GENRES:
            kept.append(genre)
    return "|".join(kept)


def build_cleaned_games(conn):
    """读 raw_appdetails，重建 cleaned_games。

    不是游戏的、发行日解析不了的不写入，各记一行日志；最后打印汇总。
    """
    raw_rows = conn.execute(
        "SELECT appid, name, app_type, release_date, genres FROM raw_appdetails ORDER BY appid"
    ).fetchall()

    cleaned_rows = []
    not_game_count = 0
    # Counter 是“计数用的字典”：记下每种认不出的发行日写法出现了几次。
    # 键是写法的形状，不是原文，这样 "Mar 2017" 和 "Apr 2018" 会数到一起
    unparsed_shapes = Counter()
    # 每种形状留一个原文当例子，光看 "aaa 9999" 不如看 "Mar 2017" 直观
    shape_examples = {}

    for appid, name, app_type, release_text, genres in raw_rows:
        if app_type != "game":
            logger.info("appid=%d 不是游戏（%s），不写入", appid, app_type)
            not_game_count += 1
            continue

        release_date = parse_release_date(release_text)
        if release_date is None:
            # %r 会带上引号，空字符串、多余空格都能看出来
            logger.warning("appid=%d 发行日解析不了，不写入: %r", appid, release_text)
            shape = date_shape(release_text)
            unparsed_shapes[shape] += 1
            shape_examples.setdefault(shape, release_text)  # 只在第一次遇到时记下
            continue

        cleaned_rows.append(
            {
                "appid": appid,
                "name": name,
                "release_date": release_date,
                "release_date_source": RELEASE_DATE_SOURCE_STORE,
                "genres": clean_genres(genres),
            }
        )

    # 删旧表、建新表、写入放在同一个事务里：中途出错就整体撤销，旧表原样还在。
    # 要手动写 BEGIN，因为 sqlite3 模块只在 INSERT 这类语句前才自动开事务，
    # DROP 和 CREATE 不在其列
    with conn:
        conn.execute("BEGIN")
        conn.execute("DROP TABLE IF EXISTS cleaned_games")
        conn.execute(CREATE_TABLE_SQL)
        conn.executemany(INSERT_SQL, cleaned_rows)

    unparsed_count = sum(unparsed_shapes.values())
    logger.info(
        "raw_appdetails 共 %d 行：写入 %d，不是游戏 %d，发行日解析不了 %d",
        len(raw_rows),
        len(cleaned_rows),
        not_game_count,
        unparsed_count,
    )
    # most_common() 按出现次数从多到少排，先补哪种写法一目了然
    for shape, count in unparsed_shapes.most_common():
        logger.info("未识别的发行日写法 %r（例如 %r）：%d 次", shape, shape_examples[shape], count)


def main():
    """命令行入口：python -m pipeline.games"""


if __name__ == "__main__":
    main()
