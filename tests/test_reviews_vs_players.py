"""探查图的取数：读样本表的训练行。"""

import sqlite3

from viz.reviews_vs_players import fit_fixed_multiplier, load_points


def test_load_points_reads_train_rows_of_sample_table():
    conn = sqlite3.connect(":memory:")
    # 只建 load_points 会读的几列，样本表以后加特征列不影响这个测试
    conn.execute(
        "CREATE TABLE cleaned_samples (sample_id TEXT, appid INTEGER, cutoff_date TEXT,"
        " split TEXT, truth_value INTEGER, total_reviews INTEGER)"
    )
    conn.execute(
        "INSERT INTO cleaned_samples (sample_id, appid, cutoff_date, split, truth_value, total_reviews)"
        " VALUES ('train:10:2018-07-01', 10, '2018-07-01', 'train', 5000, 120)"
    )

    assert load_points(conn) == [(10, 120, 5000)]


def test_fixed_multiplier_ignores_games_below_review_threshold():
    # 两款 10 条以上的 k 是 50 和 200，ln k 平均后换回来是 100；
    # 5 条评测的那款 k 再大也不算进去
    points = [(1, 10, 500), (2, 10, 2000), (3, 5, 99999)]

    multiplier, in_band_rate = fit_fixed_multiplier(points)

    assert round(multiplier, 6) == 100
    # 估计 100 对真值 50（估计是真值 2 倍）和 200（0.5 倍），都不在带里
    assert in_band_rate == 0
