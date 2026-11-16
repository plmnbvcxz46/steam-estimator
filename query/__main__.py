"""单款查询：python -m query <appid> [--workers 路数]

估一款游戏到今天为止卖了多少份，给出估计值、80% 预测区间和置信标签。四步：
1. 记下要查谁：raw_query_targets 加一行（这款, 今天）；
2. 现场采这一款：调总采集用的同一批函数，名单只有这一款、截止日是今天；
3. 重跑清洗：样本表里多出这一款的 query 行，特征和训练、校准走同一段代码；
4. 读这一行和冻结的模型（analysis.calibration 存的），套公式。

要先跑过 python -m analysis.calibration，冻结文件才存在。
已经采过的这一款的商店信息、价格历史、在线人数会被跳过（按游戏采的只采一次），
用的是当时采到的数据；评测按截止日采，每天查都会重采。
"""

import argparse
import sqlite3
import subprocess
import sys
from datetime import UTC, datetime

import joblib
import numpy as np
import pandas as pd

from analysis.calibration import INTERVAL_LEVEL, MIN_AGE_YEARS
from analysis.evaluation import DEFAULT_MIN_REVIEWS
from analysis.fusion import REVIEW_BIN_STARTS
from analysis.model_inputs import build_inputs
from common.clock import now_utc_str
from common.log import setup_logging
from common.paths import DB_PATH, FROZEN_MODEL_PATH
from crawler.appids import CREATE_QUERY_TABLE_SQL
from crawler.sources.itad import crawl_itad_ids, crawl_price_history, load_api_key
from crawler.sources.review_counts import crawl_review_counts
from crawler.sources.reviews import crawl_reviews
from crawler.sources.steamcharts import crawl_steamcharts
from crawler.sources.store_items import crawl_store_items, crawl_tag_names
from pipeline.samples.build import SPLIT_QUERY, make_sample_id


def estimate(sample, frozen):
    """用冻结的模型估一款游戏，返回 (估计销量, 区间下限, 区间上限, 有没有 B)。

    sample 是样本表里这一款的一行（pandas 表，只有一行）。公式和 analysis.calibration 一样，
    只是系数都从冻结文件里取，不再拟合。
    """
    reviews = sample["total_reviews"].iloc[0]

    # 信号 A：树的估计，再按冻结的 γ0、β、c 校准。年龄不足 30 天按 30 天算，和校准时一样
    ln_tree = frozen["tree"].predict(build_inputs(sample, frozen["tag_list"]))[0]
    ln_age = np.log(max(sample["game_age_years"].iloc[0], MIN_AGE_YEARS))
    gamma0, beta, c = frozen["a_calibration"]
    signal_a = gamma0 + beta * ln_tree + c * ln_age

    # 信号 B：总小时 ÷ 人均小时 ÷ 评测数，再加冻结的平移量。没有总小时或人均时长就没有 B
    hours = sample["charts_total_hours"].iloc[0]
    playtime = sample["playtime_median_hrs"].iloc[0]
    has_b = pd.notna(hours) and pd.notna(playtime)

    if has_b:
        a, b = frozen["b_line"]
        signal_b = np.log(hours) - (a + b * np.log(playtime)) - np.log(reviews) + frozen["b_shift"]
        # 融合：按评测数所在的档取 A 的占比
        a_share = frozen["a_share_by_bin"][np.digitize(reviews, REVIEW_BIN_STARTS[1:])]
        ln_k = a_share * signal_a + (1 - a_share) * signal_b
    else:
        ln_k = signal_a

    # 销量 = 评测数 × k；区间 = 估计 × 上下倍数，有 B、没 B 各用各的
    units = reviews * np.exp(ln_k)
    low, high = frozen["interval_ratios"][has_b]
    return units, units * low, units * high, has_b


def main():
    parser = argparse.ArgumentParser(description="估一款游戏到今天为止的销量")
    parser.add_argument("appid", type=int, help="Steam 上的游戏编号")
    parser.add_argument("--workers", type=int, default=4, help="评测和在线人数同时发请求的线程数，默认 4")
    args = parser.parse_args()
    appid = args.appid

    setup_logging("query.log")
    api_key = load_api_key()
    # 冻结文件先读：没有就在联网之前报错
    frozen = joblib.load(FROZEN_MODEL_PATH)
    # 截止日取今天（UTC），和其他时间戳一样用 UTC
    today = datetime.now(UTC).strftime("%Y-%m-%d")

    conn = sqlite3.connect(DB_PATH)
    try:
        # 1. 记下要查谁。同一款同一天查第二次，主键相同，忽略即可
        with conn:
            conn.execute(CREATE_QUERY_TABLE_SQL)
            conn.execute(
                "INSERT OR IGNORE INTO raw_query_targets VALUES (?, ?, ?)",
                (appid, today, now_utc_str()),
            )

        # 2. 采这一款，顺序和总采集一样：商店信息在评测抽样前面，ITAD 先换编号再查价格
        crawl_store_items(conn, [appid])
        crawl_tag_names(conn)
        crawl_itad_ids(conn, [appid], api_key)
        crawl_price_history(conn, [appid], api_key)
        crawl_steamcharts(conn, [appid], args.workers)
        crawl_review_counts(conn, [appid], today, args.workers)
        crawl_reviews(conn, [appid], today, args.workers)
    finally:
        conn.close()

    # 3. 重跑清洗：用另一个进程跑总入口，和手动敲 python -m pipeline 完全一样
    subprocess.run([sys.executable, "-m", "pipeline"], check=True)

    # 4. 读这一款的样本行
    conn = sqlite3.connect(DB_PATH)
    try:
        sample = pd.read_sql_query(
            "SELECT * FROM cleaned_samples WHERE sample_id = ?",
            conn,
            params=(make_sample_id(SPLIT_QUERY, appid, today),),
        )
        title_row = conn.execute("SELECT name FROM raw_store_items WHERE appid = ?", (appid,)).fetchone()
    finally:
        conn.close()

    if sample.empty:
        sys.exit(f"appid={appid} 没进样本表：不是游戏（DLC、原声带等）、还没上架，或者一条评测都没有")

    units, low, high, has_b = estimate(sample, frozen)
    reviews = sample["total_reviews"].iloc[0]
    title = title_row[0] if title_row else "（未知名称）"

    # 置信标签：有 B 的多一路信息，区间窄得多；评测太少的在模型学过的范围之外
    if reviews < DEFAULT_MIN_REVIEWS:
        label = f"不可信（评测只有 {reviews} 条，模型只学过 {DEFAULT_MIN_REVIEWS} 条以上的）"
    elif has_b:
        label = "较可信（有在线人数数据）"
    else:
        label = "仅供参考（没有在线人数数据）"

    print(f"{title}（{appid}）  截止 {today}，评测 {reviews} 条")
    print(f"估计销量：约 {units:,.0f} 份")
    print(f"{INTERVAL_LEVEL:.0%} 区间：{low:,.0f} ～ {high:,.0f} 份")
    print(f"置信标签：{label}")


main()
