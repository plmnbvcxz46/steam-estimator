"""建样本表：各 cleaned 表 + raw_ars_players_2018 -> cleaned_samples。

样本表是训练唯一要读的表，一行是“一款游戏 × 一个截止日”，放三样东西：
- 身份：sample_id、appid、cutoff_date、split（train / calib / query）
- 答案：truth_value（训练集是 2018 年玩家数）
- 特征：四类（商店信息、评测计数、评测抽样、历史价格），之后逐类加

现在只有训练集（train）的行：校准集要等真值表导入，查询要等查询入口。

这个文件只管汇总：建表、选出哪些游戏、调各类特征的模块、写入。
每类特征怎么算放在各自的模块里（如 review_count_features.py），
训练、校准、查询三组样本调的是同一个函数，算法不会两样。

不在这里设评测数门槛（如至少 10 条）：门槛要用交叉验证比较几个值，
放在训练时筛，换门槛不用重建表。

cleaned 表是派生数据：每次运行都整张表重建，结果只取决于上游的表。
"""

import logging
import sqlite3

from common.log import setup_logging
from common.paths import DB_PATH
from pipeline.review_counts import LANGUAGES
from pipeline.samples.playtime_features import load_playtime_inputs, playtime_features
from pipeline.samples.review_count_features import review_count_features

logger = logging.getLogger(__name__)

# 训练集的截止日：Ars Technica 公开玩家数表的日期
TRAIN_CUTOFF = "2018-07-01"

SPLIT_TRAIN = "train"

CREATE_TABLE_SQL = """
CREATE TABLE cleaned_samples (
    sample_id            TEXT PRIMARY KEY,
    appid                INTEGER NOT NULL,
    cutoff_date          TEXT NOT NULL,
    split                TEXT NOT NULL,
    truth_value          INTEGER,
    total_reviews        INTEGER NOT NULL,
    positive_rate        REAL NOT NULL,
    steam_purchase_ratio REAL NOT NULL,
    share_brazilian      REAL NOT NULL,
    share_english        REAL NOT NULL,
    share_french         REAL NOT NULL,
    share_german         REAL NOT NULL,
    share_japanese       REAL NOT NULL,
    share_koreana        REAL NOT NULL,
    share_latam          REAL NOT NULL,
    share_polish         REAL NOT NULL,
    share_russian        REAL NOT NULL,
    share_schinese       REAL NOT NULL,
    share_spanish        REAL NOT NULL,
    share_tchinese       REAL NOT NULL,
    share_turkish        REAL NOT NULL,
    share_other          REAL NOT NULL,
    playtime_median_hrs  REAL,
    sample_n             INTEGER NOT NULL
)
"""

# 插入时要列出全部列名。列一多手写容易漏，所以从这份清单拼出 INSERT 语句；
# 清单的顺序和上面建表的顺序一致
SAMPLE_COLUMNS = [
    "sample_id",
    "appid",
    "cutoff_date",
    "split",
    "truth_value",
    "total_reviews",
    "positive_rate",
    "steam_purchase_ratio",
]
for language in LANGUAGES:
    SAMPLE_COLUMNS.append("share_" + language)
SAMPLE_COLUMNS.append("share_other")
SAMPLE_COLUMNS.append("playtime_median_hrs")
SAMPLE_COLUMNS.append("sample_n")

INSERT_SQL = (
    "INSERT INTO cleaned_samples (" + ", ".join(SAMPLE_COLUMNS) + ")"
    " VALUES (" + ", ".join(":" + column for column in SAMPLE_COLUMNS) + ")"
)


def make_sample_id(split, appid, cutoff_date):
    """拼出样本编号，如 "train:220:2018-07-01"。

    用文字不用自增数字：编号只取决于内容，重建表后不变，
    以后结果表 result_estimates 靠它对回样本。带上组名，
    同一款游戏同一天既在校准集又被查询时也不会撞。
    """
    return f"{split}:{appid}:{cutoff_date}"


def load_train_rows(conn):
    """取出训练集的样本，四个条件同时满足才要：

    1. Ars 表里有（有玩家数，才有答案）
    2. 在 cleaned_games 里（是游戏，不是 DLC、原声带）
    3. 截止日前已开卖（抢先体验也算，上架日已取三个时刻里最早的）
    4. 截止日前评测数大于 0（k = 玩家数 ÷ 评测数，分母不能是 0；
       cleaned_review_counts 里本来就没有 0 条的）

    返回 dict 的列表，每个 dict 是样本表的一行。
    """
    # JOIN 要求三张表里都找得到这款游戏，条件 1、2、4 就靠它完成；只有 3 要写 WHERE。
    # 条件 3 现在其实删不掉任何游戏：上架日含“抽到的最早评测”，有评测就一定早于截止日。
    # 留着它是保险，上架日的规则以后变了也不会放进还没开卖的游戏
    # 13 种语言的条数列，按 LANGUAGES 的顺序排在最后
    language_columns = ", ".join("r.reviews_" + language for language in LANGUAGES)
    raw_rows = conn.execute(
        f"""
        SELECT a.appid, a.players, r.total_reviews, r.positive_reviews,
               r.steam_purchase_reviews, {language_columns}
        FROM raw_ars_players_2018 a
        JOIN cleaned_games g ON g.appid = a.appid
        JOIN cleaned_review_counts r ON r.appid = a.appid AND r.cutoff_date = ?
        WHERE g.release_date < ?
        ORDER BY a.appid
        """,
        (TRAIN_CUTOFF, TRAIN_CUTOFF),
    ).fetchall()

    # 算时长要用的抽样数据，一次读完
    window_totals, playtimes = load_playtime_inputs(conn, TRAIN_CUTOFF)

    rows = []
    for raw_row in raw_rows:
        appid, players, total_reviews, positive_reviews, steam_purchase_reviews = raw_row[:5]
        # 前 5 个之后就是 13 种语言的条数，和 LANGUAGES 一一配对
        language_reviews = dict(zip(LANGUAGES, raw_row[5:]))

        row = {
            "sample_id": make_sample_id(SPLIT_TRAIN, appid, TRAIN_CUTOFF),
            "appid": appid,
            "cutoff_date": TRAIN_CUTOFF,
            "split": SPLIT_TRAIN,
            "truth_value": players,
            "total_reviews": total_reviews,
        }
        row.update(
            review_count_features(
                total_reviews, positive_reviews, steam_purchase_reviews, language_reviews
            )
        )
        # 一条有时长的评测都没抽到的游戏，两个字典里都没有它，给空的
        row.update(playtime_features(window_totals.get(appid, {}), playtimes.get(appid, [])))
        rows.append(row)
    return rows


def build_samples(conn):
    """重建 cleaned_samples：删旧表、建新表、写入，放在同一个事务里。"""
    rows = load_train_rows(conn)

    # 中途出错就整体撤销，旧表原样还在。要手动写 BEGIN，
    # 因为 sqlite3 模块只在 INSERT 这类语句前才自动开事务
    with conn:
        conn.execute("BEGIN")
        conn.execute("DROP TABLE IF EXISTS cleaned_samples")
        conn.execute(CREATE_TABLE_SQL)
        conn.executemany(INSERT_SQL, rows)

    logger.info("cleaned_samples 写入训练集 %d 行（截止日 %s）", len(rows), TRAIN_CUTOFF)


def main():
    """命令行入口：python -m pipeline.samples（经由 __main__.py）"""
    setup_logging("cleaned_samples.log")

    conn = sqlite3.connect(DB_PATH)
    try:
        build_samples(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
