"""Unit tests for scripts/load_bronze.py (idempotent upsert logic)."""
import json

import load_bronze


class FakeCursor:
    def __init__(self):
        self.executed = []

    def execute(self, sql, params=None):
        self.executed.append((sql, params))


class FakeConn:
    def __init__(self):
        self.commits = 0

    def commit(self):
        self.commits += 1


def test_map_covers_all_bronze_tables():
    tables = {row[1] for row in load_bronze.MAP}
    assert tables == {
        "bronze.matches",
        "bronze.leagues",
        "bronze.players",
        "bronze.teams",
        "bronze.hero_stats",
        "bronze.constants",
    }


def test_load_group_one_row_per_file_strips_timestamp(tmp_path):
    d = tmp_path / "proMatches"
    d.mkdir()
    for mid in (1, 2):
        (d / f"{mid}.json").write_text(
            json.dumps({"match_id": mid, "timestamp_fetched": "2026-01-01T00:00:00Z", "players": []}),
            encoding="utf-8",
        )

    cur = FakeCursor()
    conn = FakeConn()
    count = load_bronze.load_group(cur, conn, d / "*.json", "bronze.matches", "match_id", True)

    assert count == 2
    assert conn.commits == 0  # commit happens in main(), not load_group, for small groups
    keys = [params[0] for _, params in cur.executed]
    assert keys == [1, 2]
    for _, params in cur.executed:
        payload = params[1].obj
        assert "timestamp_fetched" not in payload
        assert payload["players"] == []


def test_load_group_list_branch(tmp_path):
    d = tmp_path / "leagues"
    d.mkdir()
    (d / "leagues.json").write_text(
        json.dumps([
            {"leagueid": 1, "timestamp_fetched": "x"},
            {"leagueid": 2, "timestamp_fetched": "x"},
        ]),
        encoding="utf-8",
    )

    cur = FakeCursor()
    conn = FakeConn()
    count = load_bronze.load_group(cur, conn, d / "leagues.json", "bronze.leagues", "leagueid", False)

    assert count == 2
    keys = [params[0] for _, params in cur.executed]
    assert keys == [1, 2]
    assert all("timestamp_fetched" not in params[1].obj for _, params in cur.executed)


def test_upsert_sql_is_idempotent():
    sql = load_bronze.UPSERT_SQL.format(table="bronze.matches", key="match_id")
    assert "ON CONFLICT (match_id) DO UPDATE" in sql
