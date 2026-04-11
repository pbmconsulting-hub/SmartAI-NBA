"""
tests/test_cbs_injuries.py
--------------------------
Comprehensive tests for the CBS Sports injury-report ETL module
(etl/cbs_injuries.py) and multi-source coexistence with RotoWire data.
"""

from __future__ import annotations

import sqlite3
import sys
import tempfile
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ── Ensure repo root is on sys.path ──────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ---------------------------------------------------------------------------
# Sample CBS HTML fixture — mirrors CBS Sports div.TeamCard structure
# ---------------------------------------------------------------------------

_CBS_SAMPLE_HTML = """
<!DOCTYPE html>
<html>
<head><title>NBA Injuries</title></head>
<body>
<div class="TeamCard">
  <a class="team-name" href="/nba/teams/LAL/">Los Angeles Lakers</a>
  <table>
    <thead><tr><th>Player</th><th>Status</th><th>Injury</th><th>Date</th></tr></thead>
    <tbody>
      <tr><td>LeBron James</td><td>Questionable</td><td>ankle</td><td>Apr 10</td></tr>
    </tbody>
  </table>
</div>
<div class="TeamCard">
  <a class="team-name" href="/nba/teams/GSW/">Golden State Warriors</a>
  <table>
    <thead><tr><th>Player</th><th>Status</th><th>Injury</th><th>Date</th></tr></thead>
    <tbody>
      <tr><td>Stephen Curry</td><td>Out</td><td>knee</td><td>Apr 9</td></tr>
    </tbody>
  </table>
</div>
<div class="TeamCard">
  <a class="team-name" href="/nba/teams/MIL/">Milwaukee Bucks</a>
  <table>
    <thead><tr><th>Player</th><th>Status</th><th>Injury</th><th>Date</th></tr></thead>
    <tbody>
      <tr><td>Giannis Antetokounmpo</td><td>Probable</td><td>rest</td><td>Apr 10</td></tr>
    </tbody>
  </table>
</div>
</body>
</html>
"""

_CBS_EMPTY_HTML = """
<!DOCTYPE html><html><body><p>No injuries reported.</p></body></html>
"""

_CBS_MALFORMED_HTML = """
<!DOCTYPE html><html><body>
<div class="TeamCard">
  <a class="team-name">Chicago Bulls</a>
  <table><tr><td>Only one cell</td></tr></table>
</div>
</body></html>
"""


# ---------------------------------------------------------------------------
# Helper: build a minimal in-memory SQLite db with Players + Teams tables
# ---------------------------------------------------------------------------


def _make_test_db() -> tuple[str, sqlite3.Connection]:
    """Create a temp-file SQLite db with Players, Teams, and Injury_Status tables.

    Returns:
        (db_path, conn) — caller is responsible for closing conn.
    """
    fd, tmp = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = sqlite3.connect(tmp)
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS Teams (
            team_id       INTEGER PRIMARY KEY,
            abbreviation  TEXT NOT NULL,
            team_name     TEXT NOT NULL,
            conference    TEXT,
            division      TEXT,
            pace          REAL,
            ortg          REAL,
            drtg          REAL
        );
        CREATE TABLE IF NOT EXISTS Players (
            player_id         INTEGER PRIMARY KEY,
            first_name        TEXT NOT NULL,
            last_name         TEXT NOT NULL,
            full_name         TEXT,
            team_id           INTEGER,
            team_abbreviation TEXT,
            position          TEXT,
            is_active         INTEGER DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS Injury_Status (
            player_id       INTEGER NOT NULL REFERENCES Players(player_id),
            team_id         INTEGER,
            report_date     TEXT    NOT NULL,
            status          TEXT    NOT NULL,
            reason          TEXT,
            source          TEXT    NOT NULL DEFAULT 'unknown',
            last_updated_ts TEXT,
            PRIMARY KEY (player_id, report_date, source)
        );
        """
    )

    # Seed Teams
    conn.executemany(
        "INSERT INTO Teams (team_id, abbreviation, team_name) VALUES (?, ?, ?)",
        [
            (1610612747, "LAL", "Los Angeles Lakers"),
            (1610612744, "GSW", "Golden State Warriors"),
            (1610612749, "MIL", "Milwaukee Bucks"),
            (1610612741, "CHI", "Chicago Bulls"),
        ],
    )

    # Seed Players
    conn.executemany(
        "INSERT INTO Players (player_id, first_name, last_name, full_name) "
        "VALUES (?, ?, ?, ?)",
        [
            (2544,    "LeBron",  "James",          "LeBron James"),
            (201939,  "Stephen", "Curry",          "Stephen Curry"),
            (203507,  "Giannis", "Antetokounmpo",  "Giannis Antetokounmpo"),
        ],
    )
    conn.commit()
    return tmp, conn


# ===========================================================================
# Tests: parse_injury_table (CBS HTML)
# ===========================================================================


class TestParseCbsInjuryTable:
    def test_parses_three_rows(self):
        from etl.cbs_injuries import parse_injury_table

        rows = parse_injury_table(_CBS_SAMPLE_HTML)
        assert len(rows) == 3

    def test_first_row_fields(self):
        from etl.cbs_injuries import parse_injury_table

        rows = parse_injury_table(_CBS_SAMPLE_HTML)
        first = rows[0]
        assert first["player_name"] == "LeBron James"
        assert first["team_name"] == "Los Angeles Lakers"
        assert first["status"] == "Questionable"
        assert first["reason"] == "ankle"
        assert first["date"] == "Apr 10"

    def test_second_row_team(self):
        from etl.cbs_injuries import parse_injury_table

        rows = parse_injury_table(_CBS_SAMPLE_HTML)
        assert rows[1]["team_name"] == "Golden State Warriors"
        assert rows[1]["player_name"] == "Stephen Curry"
        assert rows[1]["status"] == "Out"

    def test_empty_page_returns_empty_list(self):
        from etl.cbs_injuries import parse_injury_table

        result = parse_injury_table(_CBS_EMPTY_HTML)
        assert result == []

    def test_malformed_rows_skipped(self):
        from etl.cbs_injuries import parse_injury_table

        result = parse_injury_table(_CBS_MALFORMED_HTML)
        assert result == []

    def test_no_team_cards_returns_empty_list(self):
        from etl.cbs_injuries import parse_injury_table

        result = parse_injury_table("<html><body><p>nothing here</p></body></html>")
        assert result == []


# ===========================================================================
# Tests: _normalise_team_name
# ===========================================================================


class TestNormaliseTeamName:
    def test_golden_state_maps_to_gsw(self):
        from etl.cbs_injuries import _normalise_team_name

        assert _normalise_team_name("Golden State Warriors") == "GSW"

    def test_chicago_maps_to_chi(self):
        from etl.cbs_injuries import _normalise_team_name

        assert _normalise_team_name("Chicago Bulls") == "CHI"

    def test_los_angeles_lakers_maps_to_lal(self):
        from etl.cbs_injuries import _normalise_team_name

        assert _normalise_team_name("Los Angeles Lakers") == "LAL"

    def test_la_clippers_maps_to_lac(self):
        from etl.cbs_injuries import _normalise_team_name

        assert _normalise_team_name("LA Clippers") == "LAC"

    def test_case_insensitive(self):
        from etl.cbs_injuries import _normalise_team_name

        assert _normalise_team_name("golden state warriors") == "GSW"

    def test_all_30_teams_mapped(self):
        from etl.cbs_injuries import _CBS_TEAM_NAME_MAP

        expected_abbrevs = {
            "ATL", "BOS", "BKN", "CHA", "CHI", "CLE", "DAL", "DEN", "DET",
            "GSW", "HOU", "IND", "LAC", "LAL", "MEM", "MIA", "MIL", "MIN",
            "NOP", "NYK", "OKC", "ORL", "PHI", "PHX", "POR", "SAC", "SAS",
            "TOR", "UTA", "WAS",
        }
        actual_abbrevs = set(_CBS_TEAM_NAME_MAP.values())
        assert expected_abbrevs == actual_abbrevs

    def test_unknown_team_returns_uppercased(self):
        from etl.cbs_injuries import _normalise_team_name

        result = _normalise_team_name("Springfield Isotopes")
        assert result == "SPRINGFIELD ISOTOPES"


# ===========================================================================
# Tests: transform_injuries (CBS)
# ===========================================================================


class TestTransformCbsInjuries:
    def setup_method(self):
        self.db_path, self.conn = _make_test_db()

    def teardown_method(self):
        self.conn.close()
        try:
            os.unlink(self.db_path)
        except OSError:
            pass

    def test_returns_dataframe_with_correct_columns(self):
        from etl.cbs_injuries import parse_injury_table, transform_injuries

        raw = parse_injury_table(_CBS_SAMPLE_HTML)
        df = transform_injuries(raw, self.conn)
        expected_cols = {
            "player_id", "team_id", "report_date", "status",
            "reason", "source", "last_updated_ts",
        }
        assert expected_cols.issubset(set(df.columns))

    def test_matched_players_count(self):
        from etl.cbs_injuries import parse_injury_table, transform_injuries

        raw = parse_injury_table(_CBS_SAMPLE_HTML)
        df = transform_injuries(raw, self.conn)
        # All three players are in the Players table
        assert len(df) == 3

    def test_source_is_cbssports(self):
        from etl.cbs_injuries import parse_injury_table, transform_injuries

        raw = parse_injury_table(_CBS_SAMPLE_HTML)
        df = transform_injuries(raw, self.conn)
        assert (df["source"] == "cbssports").all()

    def test_team_id_mapped(self):
        from etl.cbs_injuries import parse_injury_table, transform_injuries

        raw = parse_injury_table(_CBS_SAMPLE_HTML)
        df = transform_injuries(raw, self.conn)
        lal_row = df[df["player_id"] == 2544]
        assert not lal_row.empty
        assert lal_row.iloc[0]["team_id"] == 1610612747

    def test_team_id_gsw_mapped_from_full_name(self):
        from etl.cbs_injuries import parse_injury_table, transform_injuries

        raw = parse_injury_table(_CBS_SAMPLE_HTML)
        df = transform_injuries(raw, self.conn)
        gsw_row = df[df["player_id"] == 201939]
        assert not gsw_row.empty
        # "Golden State Warriors" → GSW → team_id 1610612744
        assert gsw_row.iloc[0]["team_id"] == 1610612744

    def test_unmatched_player_skipped(self):
        from etl.cbs_injuries import transform_injuries

        raw = [
            {
                "player_name": "Completely Unknown Player XYZ",
                "team_name": "Los Angeles Lakers",
                "status": "Out",
                "reason": "ankle",
                "date": "Apr 10",
            }
        ]
        df = transform_injuries(raw, self.conn)
        assert df.empty

    def test_empty_raw_returns_empty_df(self):
        from etl.cbs_injuries import transform_injuries

        df = transform_injuries([], self.conn)
        assert df.empty

    def test_report_date_is_today(self):
        from datetime import date

        from etl.cbs_injuries import parse_injury_table, transform_injuries

        raw = parse_injury_table(_CBS_SAMPLE_HTML)
        df = transform_injuries(raw, self.conn)
        assert not df.empty
        assert df.iloc[0]["report_date"] == date.today().isoformat()


# ===========================================================================
# Tests: load_injuries (CBS)
# ===========================================================================


class TestLoadCbsInjuries:
    def setup_method(self):
        self.db_path, self.conn = _make_test_db()

    def teardown_method(self):
        self.conn.close()
        try:
            os.unlink(self.db_path)
        except OSError:
            pass

    def test_load_returns_row_count(self):
        import pandas as pd

        from etl.cbs_injuries import load_injuries, parse_injury_table, transform_injuries

        raw = parse_injury_table(_CBS_SAMPLE_HTML)
        df = transform_injuries(raw, self.conn)
        count = load_injuries(df, self.conn)
        assert count == len(df)

    def test_rows_persisted_in_db(self):
        from etl.cbs_injuries import load_injuries, parse_injury_table, transform_injuries

        raw = parse_injury_table(_CBS_SAMPLE_HTML)
        df = transform_injuries(raw, self.conn)
        load_injuries(df, self.conn)
        self.conn.commit()
        rows = self.conn.execute("SELECT COUNT(*) FROM Injury_Status").fetchone()[0]
        assert rows == len(df)

    def test_load_empty_df_returns_zero(self):
        import pandas as pd

        from etl.cbs_injuries import load_injuries

        empty_df = pd.DataFrame(
            columns=["player_id", "team_id", "report_date", "status",
                     "reason", "source", "last_updated_ts"]
        )
        count = load_injuries(empty_df, self.conn)
        assert count == 0

    def test_upsert_idempotent(self):
        """Loading the same CBS rows twice should not duplicate them."""
        from etl.cbs_injuries import load_injuries, parse_injury_table, transform_injuries

        raw = parse_injury_table(_CBS_SAMPLE_HTML)
        df = transform_injuries(raw, self.conn)
        load_injuries(df, self.conn)
        load_injuries(df, self.conn)
        self.conn.commit()
        rows = self.conn.execute("SELECT COUNT(*) FROM Injury_Status").fetchone()[0]
        assert rows == len(df)


# ===========================================================================
# Tests: sync_cbs_injuries (full pipeline with mocked HTTP)
# ===========================================================================


class TestSyncCbsInjuries:
    def setup_method(self):
        self.db_path, self.conn = _make_test_db()
        self.conn.close()

    def teardown_method(self):
        try:
            os.unlink(self.db_path)
        except OSError:
            pass

    @patch("etl.cbs_injuries.fetch_injury_page")
    def test_full_sync_inserts_rows(self, mock_fetch):
        from etl.cbs_injuries import sync_cbs_injuries

        mock_fetch.return_value = _CBS_SAMPLE_HTML
        count = sync_cbs_injuries(self.db_path)
        assert count == 3

    @patch("etl.cbs_injuries.fetch_injury_page")
    def test_sync_empty_page_returns_zero(self, mock_fetch):
        from etl.cbs_injuries import sync_cbs_injuries

        mock_fetch.return_value = _CBS_EMPTY_HTML
        count = sync_cbs_injuries(self.db_path)
        assert count == 0

    @patch("etl.cbs_injuries.fetch_injury_page", side_effect=Exception("Network error"))
    def test_network_error_returns_zero(self, _mock):
        from etl.cbs_injuries import sync_cbs_injuries

        count = sync_cbs_injuries(self.db_path)
        assert count == 0

    @patch("etl.cbs_injuries.fetch_injury_page")
    def test_sync_is_idempotent(self, mock_fetch):
        from etl.cbs_injuries import sync_cbs_injuries

        mock_fetch.return_value = _CBS_SAMPLE_HTML
        sync_cbs_injuries(self.db_path)
        count2 = sync_cbs_injuries(self.db_path)
        assert count2 == 3
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute(
            "SELECT COUNT(*) FROM Injury_Status WHERE source='cbssports'"
        ).fetchone()[0]
        conn.close()
        assert rows == 3


# ===========================================================================
# Tests: CBS API endpoint
# ===========================================================================


def _make_api_client(db_path: str):
    """Create a TestClient for etl.api with the DB_PATH patched."""
    try:
        from fastapi.testclient import TestClient
    except ImportError:
        pytest.skip("fastapi[testclient] not installed")

    import etl.api as api_module
    original_db_path = api_module.DB_PATH
    api_module.DB_PATH = db_path
    import etl.setup_db as setup_mod
    original_setup_path = setup_mod.DB_PATH
    setup_mod.DB_PATH = db_path

    client = TestClient(api_module.app)
    return client, api_module, original_db_path, setup_mod, original_setup_path


class TestCbsApiEndpoint:
    """Verify /api/injuries?source=cbssports returns only CBS rows."""

    def setup_method(self):
        self.db_path, self.conn = _make_test_db()
        # Pre-seed a CBS injury row
        self.conn.execute(
            "INSERT INTO Injury_Status "
            "(player_id, team_id, report_date, status, reason, source, last_updated_ts) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (2544, 1610612747, "2026-04-10", "Questionable", "ankle",
             "cbssports", "2026-04-10T21:00:00Z"),
        )
        # Also seed a rotowire row for a different player
        self.conn.execute(
            "INSERT INTO Injury_Status "
            "(player_id, team_id, report_date, status, reason, source, last_updated_ts) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (201939, 1610612744, "2026-04-10", "Out", "knee",
             "rotowire", "2026-04-10T21:00:00Z"),
        )
        self.conn.commit()
        self.conn.close()

    def teardown_method(self):
        try:
            os.unlink(self.db_path)
        except OSError:
            pass

    def test_cbs_source_filter(self):
        client, api_mod, orig_db, setup_mod, orig_setup = _make_api_client(self.db_path)
        try:
            resp = client.get("/api/injuries?source=cbssports")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["injuries"]) == 1
            assert data["injuries"][0]["source"] == "cbssports"
            assert data["injuries"][0]["player_id"] == 2544
        finally:
            api_mod.DB_PATH = orig_db
            setup_mod.DB_PATH = orig_setup

    def test_no_filter_returns_both(self):
        client, api_mod, orig_db, setup_mod, orig_setup = _make_api_client(self.db_path)
        try:
            resp = client.get("/api/injuries")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["injuries"]) == 2
            sources = {r["source"] for r in data["injuries"]}
            assert sources == {"rotowire", "cbssports"}
        finally:
            api_mod.DB_PATH = orig_db
            setup_mod.DB_PATH = orig_setup


# ===========================================================================
# Tests: multi-source coexistence (CBS + RotoWire for same player/date)
# ===========================================================================


class TestMultiSourceCoexistence:
    """Insert both rotowire and cbssports for same player/date, verify both survive."""

    def setup_method(self):
        self.db_path, self.conn = _make_test_db()

    def teardown_method(self):
        self.conn.close()
        try:
            os.unlink(self.db_path)
        except OSError:
            pass

    def _insert(self, player_id, report_date, source, status="Questionable"):
        self.conn.execute(
            "INSERT OR REPLACE INTO Injury_Status "
            "(player_id, team_id, report_date, status, reason, source, last_updated_ts) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (player_id, 1610612747, report_date, status, "ankle", source,
             "2026-04-10T21:00:00Z"),
        )
        self.conn.commit()

    def test_both_sources_coexist(self):
        """RotoWire + CBS rows for same player/date should both persist."""
        self._insert(2544, "2026-04-10", "rotowire")
        self._insert(2544, "2026-04-10", "cbssports")
        count = self.conn.execute(
            "SELECT COUNT(*) FROM Injury_Status "
            "WHERE player_id=2544 AND report_date='2026-04-10'"
        ).fetchone()[0]
        assert count == 2

    def test_api_returns_both_sources(self):
        """GET /api/injuries returns both RotoWire and CBS rows."""
        self._insert(2544, "2026-04-10", "rotowire", status="Questionable")
        self._insert(2544, "2026-04-10", "cbssports", status="Out")
        self.conn.close()
        client, api_mod, orig_db, setup_mod, orig_setup = _make_api_client(self.db_path)
        try:
            resp = client.get("/api/injuries")
            assert resp.status_code == 200
            data = resp.json()
            assert len(data["injuries"]) == 2
            sources = {r["source"] for r in data["injuries"]}
            assert sources == {"rotowire", "cbssports"}
        finally:
            api_mod.DB_PATH = orig_db
            setup_mod.DB_PATH = orig_setup
            self.conn = sqlite3.connect(self.db_path)

    def test_player_endpoint_all_sources(self):
        """GET /api/players/{id}/injury includes all_sources for latest date."""
        self._insert(2544, "2026-04-10", "rotowire", status="Questionable")
        self._insert(2544, "2026-04-10", "cbssports", status="Out")
        self.conn.close()
        client, api_mod, orig_db, setup_mod, orig_setup = _make_api_client(self.db_path)
        try:
            resp = client.get("/api/players/2544/injury")
            assert resp.status_code == 200
            data = resp.json()
            assert "all_sources" in data
            assert len(data["all_sources"]) == 2
            source_names = {r["source"] for r in data["all_sources"]}
            assert source_names == {"rotowire", "cbssports"}
        finally:
            api_mod.DB_PATH = orig_db
            setup_mod.DB_PATH = orig_setup
            self.conn = sqlite3.connect(self.db_path)
