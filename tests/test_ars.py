import sqlite3

from crawler.ars import import_ars, parse_players, read_rows

HEADER = "Title, Players Estimate ,Steam App ID"


def test_parse_players_real_format():
    # 原件里的真实写法：两边有空格，中间有千分位逗号
    assert parse_players(" 50,191,347 ") == 50191347


def test_read_rows_duplicate_keeps_first(tmp_path):
    # 原件里有 6 个 appid 出现两次（内容相同），只应保留第一条
    path = tmp_path / "ars.csv"
    path.write_text(
        HEADER + '\nUnavowed," 1,776 ",336140\nUnavowed," 1,776 ",336140\n',
        encoding="utf-8",
    )
    assert read_rows(path) == [(336140, "Unavowed", 1776)]


def test_read_rows_real_file():
    # 用真实原件做一次整体核对：13,281 行减去 6 条重复的
    path = "data/source/games_achievements_players_2018-07-01_ars_original.csv"
    rows = read_rows(path)
    assert len(rows) == 13275
    assert rows[0] == (440, "Team Fortress 2", 50191347)


def test_import_ars_is_rerunnable(tmp_path):
    # 重跑结果不变：导入两遍，表里仍然只有 1 行
    csv_path = tmp_path / "ars.csv"
    csv_path.write_text(HEADER + '\nTeam Fortress 2," 50,191,347 ",440\n', encoding="utf-8")
    db_path = tmp_path / "test.db"

    import_ars(csv_path, db_path)
    import_ars(csv_path, db_path)

    conn = sqlite3.connect(db_path)
    count = conn.execute("SELECT COUNT(*) FROM raw_ars_players_2018").fetchone()[0]
    conn.close()
    assert count == 1
