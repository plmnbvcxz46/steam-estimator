"""清洗商店信息：raw_appdetails -> cleaned_games。

raw_appdetails 存的是商店页原文，这里把它整理成后面能直接用的样子：
- 只留游戏，去掉 DLC、原声带等
- 发行日从 "Sep 26, 2013" 换成 "2013-09-26"
- 类型里去掉不是类型的词

cleaned 表是派生数据：每次运行都整张表重建，结果只取决于 raw 表。
"""

import logging

logger = logging.getLogger(__name__)

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
    release_date        TEXT,
    release_date_source TEXT,
    genres              TEXT NOT NULL
)
"""


def parse_release_date(text):
    """把商店页的发行日原文换成 YYYY-MM-DD；解析不了时返回 None。"""


def clean_genres(text):
    """去掉 genres 里不是类型的词。输入输出都是用 | 连接的字符串。"""


def build_cleaned_games(conn):
    """读 raw_appdetails，重建 cleaned_games。"""


def main():
    """命令行入口：python -m pipeline.games"""


if __name__ == "__main__":
    main()
