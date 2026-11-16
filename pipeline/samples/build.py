"""建样本表：各 cleaned 表 + raw_ars_players_2018 + cleaned_sales_truth -> cleaned_samples。

样本表是训练唯一要读的表，一行是“一款游戏 × 一个截止日”，放三样东西：
- 身份：sample_id、appid、cutoff_date、split（train / calib / query）
- 答案：truth_value（训练集是 2018 年玩家数，校准集是公布的销量）
- 特征：四类（商店信息、评测计数、评测抽样、历史价格），给信号 A 用
- 信号 B 的输入：在线人数总小时 charts_total_hours，不进信号 A 的模型

现在有训练集（train）和校准集（calib）的行，查询要等查询入口。
两组的区别只在“从哪张表出发、截止日是哪天”：
- 训练集从 Ars 玩家数表出发，截止日都是 2018-07-01；
- 校准集从销量真值表出发，截止日是每条真值自己的公布日期。
同一款游戏两边都有时各有一行，编号不同，互不干扰。

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
from pipeline.samples.charts_features import charts_features, load_monthly_hours
from pipeline.samples.playtime_features import load_playtime_inputs, playtime_features
from pipeline.samples.price_features import (
    CUT_LEVELS,
    load_price_segments,
    price_features,
)
from pipeline.samples.review_count_features import review_count_features
from pipeline.samples.store_features import store_features

logger = logging.getLogger(__name__)

# 训练集的截止日：Ars Technica 公开玩家数表的日期
TRAIN_CUTOFF = "2018-07-01"

SPLIT_TRAIN = "train"
SPLIT_CALIB = "calib"

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
    sample_n             INTEGER NOT NULL,
    game_age_years       REAL NOT NULL,
    tags                 TEXT NOT NULL,
    price_at_cutoff_usd  REAL,
    avg_price_usd        REAL,
    frac_time_cut25      REAL,
    frac_time_cut50      REAL,
    frac_time_cut75      REAL,
    charts_total_hours   REAL
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
SAMPLE_COLUMNS.append("game_age_years")
SAMPLE_COLUMNS.append("tags")
SAMPLE_COLUMNS.append("price_at_cutoff_usd")
SAMPLE_COLUMNS.append("avg_price_usd")
for level in CUT_LEVELS:
    SAMPLE_COLUMNS.append(f"frac_time_cut{level}")
SAMPLE_COLUMNS.append("charts_total_hours")

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


# 两组样本的查询都返回这几列，顺序固定：
# appid、截止日、答案、评测数、好评数、Steam 内购买评测数、上架日、标签，最后是 13 种语言的条数
LANGUAGE_COLUMNS = ", ".join("r.reviews_" + language for language in LANGUAGES)


def select_train(conn):
    """选出训练集的（游戏, 截止日）和答案，四个条件同时满足才要：

    1. Ars 表里有（有玩家数，才有答案）
    2. 在 cleaned_games 里（是游戏，不是 DLC、原声带）
    3. 截止日前已开卖（抢先体验也算，上架日已取三个时刻里最早的）
    4. 截止日前评测数大于 0（k = 玩家数 ÷ 评测数，分母不能是 0；
       cleaned_review_counts 里本来就没有 0 条的）
    """
    # JOIN 要求三张表里都找得到这款游戏，条件 1、2、4 就靠它完成；只有 3 要写 WHERE。
    # 条件 3 现在其实删不掉任何游戏：上架日含“抽到的最早评测”，有评测就一定早于截止日。
    # 留着它是保险，上架日的规则以后变了也不会放进还没开卖的游戏
    return conn.execute(
        f"""
        SELECT a.appid, r.cutoff_date, a.players, r.total_reviews, r.positive_reviews,
               r.steam_purchase_reviews, g.release_date, g.tags, {LANGUAGE_COLUMNS}
        FROM raw_ars_players_2018 a
        JOIN cleaned_games g ON g.appid = a.appid
        JOIN cleaned_review_counts r ON r.appid = a.appid AND r.cutoff_date = ?
        WHERE g.release_date < r.cutoff_date
        ORDER BY a.appid
        """,
        (TRAIN_CUTOFF,),
    ).fetchall()


def select_calib(conn):
    """选出校准集的（游戏, 截止日）和答案。条件和训练集一样，只是从销量真值表出发，
    截止日是每条真值的公布日期。

    同一款游戏有几条真值时各写一行，这里不挑：每款用哪一条是校准时的取舍，放在校准的代码里。
    """
    rows = conn.execute(
        f"""
        SELECT t.appid, t.report_date, t.units_sold, r.total_reviews, r.positive_reviews,
               r.steam_purchase_reviews, g.release_date, g.tags, {LANGUAGE_COLUMNS}
        FROM cleaned_sales_truth t
        JOIN cleaned_games g ON g.appid = t.appid
        JOIN cleaned_review_counts r ON r.appid = t.appid AND r.cutoff_date = t.report_date
        WHERE g.release_date < t.report_date
        ORDER BY t.appid, t.report_date
        """
    ).fetchall()

    # 没进校准集的真值都记进日志，不悄悄丢
    kept = {(row[0], row[1]) for row in rows}
    for appid, report_date, title in conn.execute(
        "SELECT appid, report_date, title FROM cleaned_sales_truth ORDER BY appid, report_date"
    ):
        if (appid, report_date) not in kept:
            logger.info(
                "真值 appid=%d %s（%s）没进校准集：不是游戏、截止日评测数为 0，或截止日前未上架",
                appid,
                report_date,
                title,
            )
    return rows


def build_samples(conn):
    """重建 cleaned_samples：删旧表、建新表、写入，放在同一个事务里。"""
    # 算特征要用的数据一次读完，训练和校准共用
    window_totals, playtimes = load_playtime_inputs(conn)
    price_segments = load_price_segments(conn)
    monthly_hours = load_monthly_hours(conn)

    rows = []
    counts = {}
    for split, selected in [
        (SPLIT_TRAIN, select_train(conn)),
        (SPLIT_CALIB, select_calib(conn)),
    ]:
        counts[split] = len(selected)
        for selected_row in selected:
            appid, cutoff_date, truth_value = selected_row[:3]
            total_reviews, positive_reviews, steam_purchase_reviews = selected_row[3:6]
            release_date, tags = selected_row[6:8]
            # 前 8 个之后就是 13 种语言的条数，和 LANGUAGES 一一配对
            language_reviews = dict(zip(LANGUAGES, selected_row[8:]))

            # 下面每类特征都用这个样本自己的截止日，训练和校准走的是同一段代码
            row = {
                "sample_id": make_sample_id(split, appid, cutoff_date),
                "appid": appid,
                "cutoff_date": cutoff_date,
                "split": split,
                "truth_value": truth_value,
                "total_reviews": total_reviews,
            }
            row.update(
                review_count_features(
                    total_reviews,
                    positive_reviews,
                    steam_purchase_reviews,
                    language_reviews,
                )
            )
            # 评测抽样按（游戏, 截止日）取自己那一组；一条有时长的评测都没抽到的给空的
            key = (appid, cutoff_date)
            row.update(
                playtime_features(window_totals.get(key, {}), playtimes.get(key, []))
            )
            row.update(store_features(cutoff_date, release_date, tags))
            # 没有价格历史的游戏给空列表，五列都会是空
            row.update(price_features(price_segments.get(appid, []), cutoff_date))
            # SteamCharts 没收录的游戏给空列表，总小时为空
            row.update(
                charts_features(monthly_hours.get(appid, []), release_date, cutoff_date)
            )
            rows.append(row)

    # 中途出错就整体撤销，旧表原样还在。要手动写 BEGIN，
    # 因为 sqlite3 模块只在 INSERT 这类语句前才自动开事务
    with conn:
        conn.execute("BEGIN")
        conn.execute("DROP TABLE IF EXISTS cleaned_samples")
        conn.execute(CREATE_TABLE_SQL)
        conn.executemany(INSERT_SQL, rows)

    logger.info(
        "cleaned_samples 写入训练集 %d 行（截止日 %s），校准集 %d 行",
        counts[SPLIT_TRAIN],
        TRAIN_CUTOFF,
        counts[SPLIT_CALIB],
    )


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
