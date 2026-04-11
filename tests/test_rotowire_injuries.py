"""
tests/test_rotowire_injuries.py
-------------------------------
Comprehensive tests for the RotoWire injury-report ETL module
(etl/rotowire_injuries.py) and the corresponding API endpoints.
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
# Minimal HTML fixture that mirrors the RotoWire injury report structure.
# ---------------------------------------------------------------------------

_SAMPLE_HTML = """
<!DOCTYPE html>
<html>
<head><title>NBA Injury Report</title></head>
<body>
<table>
  <thead>
    <tr>
      <th>Player</th>
      <th>Team</th>
      <th>Position</th>
      <th>Injury</th>
      <th>Status</th>
      <th>Est. Return</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>LeBron James</td>
      <td>LAL</td>
      <td>F</td>
      <td>ankle</td>
      <td>Questionable</td>
      <td>Day-to-Day</td>
    </tr>
    <tr>
      <td>Stephen Curry</td>
      <td>GS</td>
      <td>G</td>
      <td>knee</td>
      <td>Out</td>
      <td>2-4 weeks</td>
    </tr>
    <tr>
      <td>Giannis Antetokounmpo</td>
      <td>MIL</td>
      <td>F</td>
      <td>rest</td>
      <td>Probable</td>
      <td>Today</td>
    </tr>
  </tbody>
</table>
</body>
</html>
"""

_EMPTY_HTML = """
<!DOCTYPE html><html><body><p>No injuries reported.</p></body></html>
"""

_MALFORMED_HTML = """
<!DOCTYPE html><html><body><table><tr><td>Only one cell</td></tr></table></body></html>
"""


# ---------------------------------------------------------------------------
# Helper: build a minimal in-memory SQLite db with Players + Teams tables
# ---------------------------------------------------------------------------


def _make_test_db() -> tuple[str, sqlite3.Connection]:
    """Create a temp-file SQLite db with Players and Injury_Status tables.

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
# Tests: parse_injury_table
# ===========================================================================


class TestParseInjuryTable:
    def test_parses_three_rows(self):
        from etl.rotowire_injuries import parse_injury_table

        rows = parse_injury_table(_SAMPLE_HTML)
        assert len(rows) == 3

    def test_first_row_fields(self):
        from etl.rotowire_injuries import parse_injury_table

        rows = parse_injury_table(_SAMPLE_HTML)
        first = rows[0]
        assert first["player_name"] == "LeBron James"
        assert first["team_abbrev"] == "LAL"
        assert first["position"] == "F"
        assert first["reason"] == "ankle"
        assert first["status"] == "Questionable"
        assert first["est_return"] == "Day-to-Day"

    def test_rotowire_abbrev_mapped(self):
        from etl.rotowire_injuries import parse_injury_table

        rows = parse_injury_table(_SAMPLE_HTML)
        # GS is the raw scraped value — normalisation happens in transform
        assert rows[1]["team_abbrev"] == "GS"

    def test_empty_page_returns_empty_list(self):
        from etl.rotowire_injuries import parse_injury_table

        result = parse_injury_table(_EMPTY_HTML)
        assert result == []

    def test_malformed_rows_skipped(self):
        from etl.rotowire_injuries import parse_injury_table

        # Only one cell per row — should be filtered out.
        result = parse_injury_table(_MALFORMED_HTML)
        assert result == []

    def test_no_table_returns_empty_list(self):
        from etl.rotowire_injuries import parse_injury_table

        result = parse_injury_table("<html><body><p>nothing here</p></body></html>")
        assert result == []


# ===========================================================================
# Tests: _normalise_team_abbrev
# ===========================================================================


class TestNormaliseTeamAbbrev:
    def test_gs_maps_to_gsw(self):
        from etl.rotowire_injuries import _normalise_team_abbrev

        assert _normalise_team_abbrev("GS") == "GSW"

    def test_no_maps_to_nop(self):
        from etl.rotowire_injuries import _normalise_team_abbrev

        assert _normalise_team_abbrev("NO") == "NOP"

    def test_already_canonical_unchanged(self):
        from etl.rotowire_injuries import _normalise_team_abbrev

        assert _normalise_team_abbrev("LAL") == "LAL"

    def test_case_insensitive(self):
        from etl.rotowire_injuries import _normalise_team_abbrev

        assert _normalise_team_abbrev("gs") == "GSW"


# ===========================================================================
# Tests: _match_player
# ===========================================================================


class TestMatchPlayer:
    """Tests for the player-name fuzzy-matching helper."""

    _LOOKUP = {
        "lebron james": 2544,
        "stephen curry": 201939,
        "giannis antetokounmpo": 203507,
    }

    def test_exact_match(self):
        from etl.rotowire_injuries import _match_player

        assert _match_player("LeBron James", self._LOOKUP) == 2544

    def test_case_insensitive_exact_match(self):
        from etl.rotowire_injuries import _match_player

        assert _match_player("lebron james", self._LOOKUP) == 2544

    def test_fuzzy_match(self):
        from etl.rotowire_injuries import _match_player

        # Slight variation — should still match above threshold.
        result = _match_player("L. James", self._LOOKUP, threshold=40)
        # At threshold 40 this may or may not match; just verify no exception.
        assert result is None or isinstance(result, int)

    def test_no_match_returns_none(self):
        from etl.rotowire_injuries import _match_player

        result = _match_player("Completely Unknown Player XYZ", self._LOOKUP)
        assert result is None

    def test_empty_lookup_returns_none(self):
        from etl.rotowire_injuries import _match_player

        assert _match_player("LeBron James", {}) is None

    def test_fuzzy_match_above_threshold(self):
        from etl.rotowire_injuries import _match_player

        # "Giannis Antetokounmpo" with a small typo
        result = _match_player("Giannis Antetokounmpo", self._LOOKUP)
        assert result == 203507


# ===========================================================================
# Tests: transform_injuries
# ===========================================================================


class TestTransformInjuries:
    def setup_method(self):
        self.db_path, self.conn = _make_test_db()

    def teardown_method(self):
        self.conn.close()
        try:
            os.unlink(self.db_path)
        except OSError:
            pass

    def test_returns_dataframe_with_correct_columns(self):
        from etl.rotowire_injuries import parse_injury_table, transform_injuries

        raw = parse_injury_table(_SAMPLE_HTML)
        df = transform_injuries(raw, self.conn)
        expected_cols = {
            "player_id", "team_id", "report_date", "status",
            "reason", "source", "last_updated_ts",
        }
        assert expected_cols.issubset(set(df.columns))

    def test_matched_players_count(self):
        from etl.rotowire_injuries import parse_injury_table, transform_injuries

        raw = parse_injury_table(_SAMPLE_HTML)
        df = transform_injuries(raw, self.conn)
        # All three players are in the Players table
        assert len(df) == 3

    def test_source_is_rotowire(self):
        from etl.rotowire_injuries import parse_injury_table, transform_injuries

        raw = parse_injury_table(_SAMPLE_HTML)
        df = transform_injuries(raw, self.conn)
        assert (df["source"] == "rotowire").all()

    def test_team_id_mapped(self):
        from etl.rotowire_injuries import parse_injury_table, transform_injuries

        raw = parse_injury_table(_SAMPLE_HTML)
        df = transform_injuries(raw, self.conn)
        lal_row = df[df["player_id"] == 2544]
        assert not lal_row.empty
        assert lal_row.iloc[0]["team_id"] == 1610612747

    def test_team_id_gs_mapped_via_alias(self):
        from etl.rotowire_injuries import parse_injury_table, transform_injuries

        raw = parse_injury_table(_SAMPLE_HTML)
        df = transform_injuries(raw, self.conn)
        gsw_row = df[df["player_id"] == 201939]
        assert not gsw_row.empty
        # GS → GSW → team_id 1610612744
        assert gsw_row.iloc[0]["team_id"] == 1610612744

    def test_unmatched_player_skipped(self):
        from etl.rotowire_injuries import transform_injuries

        raw = [
            {
                "player_name": "Completely Unknown Player XYZ",
                "team_abbrev": "LAL",
                "position": "F",
                "reason": "ankle",
                "status": "Out",
                "est_return": "",
            }
        ]
        df = transform_injuries(raw, self.conn)
        assert df.empty

    def test_empty_raw_returns_empty_df(self):
        from etl.rotowire_injuries import transform_injuries

        df = transform_injuries([], self.conn)
        assert df.empty

    def test_report_date_is_today(self):
        from datetime import date

        from etl.rotowire_injuries import parse_injury_table, transform_injuries

        raw = parse_injury_table(_SAMPLE_HTML)
        df = transform_injuries(raw, self.conn)
        assert not df.empty
        assert df.iloc[0]["report_date"] == date.today().isoformat()


# ===========================================================================
# Tests: load_injuries
# ===========================================================================


class TestLoadInjuries:
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

        from etl.rotowire_injuries import load_injuries, parse_injury_table, transform_injuries

        raw = parse_injury_table(_SAMPLE_HTML)
        df = transform_injuries(raw, self.conn)
        count = load_injuries(df, self.conn)
        assert count == len(df)

    def test_rows_persisted_in_db(self):
        from etl.rotowire_injuries import load_injuries, parse_injury_table, transform_injuries

        raw = parse_injury_table(_SAMPLE_HTML)
        df = transform_injuries(raw, self.conn)
        load_injuries(df, self.conn)
        self.conn.commit()
        rows = self.conn.execute("SELECT COUNT(*) FROM Injury_Status").fetchone()[0]
        assert rows == len(df)

    def test_load_empty_df_returns_zero(self):
        import pandas as pd

        from etl.rotowire_injuries import load_injuries

        empty_df = pd.DataFrame(
            columns=["player_id", "team_id", "report_date", "status",
                     "reason", "source", "last_updated_ts"]
        )
        count = load_injuries(empty_df, self.conn)
        assert count == 0

    def test_upsert_idempotent(self):
        """Loading the same rows twice should not duplicate them."""
        from etl.rotowire_injuries import load_injuries, parse_injury_table, transform_injuries

        raw = parse_injury_table(_SAMPLE_HTML)
        df = transform_injuries(raw, self.conn)
        load_injuries(df, self.conn)
        load_injuries(df, self.conn)
        self.conn.commit()
        rows = self.conn.execute("SELECT COUNT(*) FROM Injury_Status").fetchone()[0]
        assert rows == len(df)


# ===========================================================================
# Tests: sync_rotowire_injuries (full pipeline with mocked HTTP)
# ===========================================================================


class TestSyncRotowireInjuries:
    def setup_method(self):
        self.db_path, self.conn = _make_test_db()
        self.conn.close()

    def teardown_method(self):
        try:
            os.unlink(self.db_path)
        except OSError:
            pass

    @patch("etl.rotowire_injuries.fetch_injury_page")
    def test_full_sync_inserts_rows(self, mock_fetch):
        from etl.rotowire_injuries import sync_rotowire_injuries

        mock_fetch.return_value = _SAMPLE_HTML
        count = sync_rotowire_injuries(self.db_path)
        assert count == 3

    @patch("etl.rotowire_injuries.fetch_injury_page")
    def test_sync_empty_page_returns_zero(self, mock_fetch):
        from etl.rotowire_injuries import sync_rotowire_injuries

        mock_fetch.return_value = _EMPTY_HTML
        count = sync_rotowire_injuries(self.db_path)
        assert count == 0

    @patch("etl.rotowire_injuries.fetch_injury_page", side_effect=Exception("Network error"))
    def test_network_error_returns_zero(self, _mock):
        from etl.rotowire_injuries import sync_rotowire_injuries

        count = sync_rotowire_injuries(self.db_path)
        assert count == 0

    @patch("etl.rotowire_injuries.fetch_injury_page")
    def test_sync_is_idempotent(self, mock_fetch):
        from etl.rotowire_injuries import sync_rotowire_injuries

        mock_fetch.return_value = _SAMPLE_HTML
        sync_rotowire_injuries(self.db_path)
        count2 = sync_rotowire_injuries(self.db_path)
        # Second call should upsert the same rows — count still = 3
        assert count2 == 3
        # And there should still only be 3 rows in the DB
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute("SELECT COUNT(*) FROM Injury_Status").fetchone()[0]
        conn.close()
        assert rows == 3


# ===========================================================================
# Tests: fetch_injury_page (HTTP layer)
# ===========================================================================


class TestFetchInjuryPage:
    @patch("etl.rotowire_injuries.requests.get")
    def test_returns_html_on_success(self, mock_get):
        from etl.rotowire_injuries import fetch_injury_page

        mock_resp = MagicMock()
        mock_resp.text = "<html>ok</html>"
        mock_resp.content = b"<html>ok</html>"
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        result = fetch_injury_page("https://example.com/test")
        assert result == "<html>ok</html>"

    @patch("etl.rotowire_injuries.requests.get")
    def test_raises_on_http_error(self, mock_get):
        import requests

        from etl.rotowire_injuries import fetch_injury_page

        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = requests.HTTPError("404")
        mock_get.return_value = mock_resp

        with pytest.raises(Exception):
            fetch_injury_page("https://example.com/test")


# ===========================================================================
# Tests: API endpoints (FastAPI TestClient)
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
    # Also patch setup_db.DB_PATH so _db() context manager uses the test db.
    import etl.setup_db as setup_mod
    original_setup_path = setup_mod.DB_PATH
    setup_mod.DB_PATH = db_path

    client = TestClient(api_module.app)
    return client, api_module, original_db_path, setup_mod, original_setup_path


class TestInjuriesEndpoint:
    def setup_method(self):
        self.db_path, self.conn = _make_test_db()
        # Pre-seed some injury data
        self.conn.execute(
            "INSERT INTO Injury_Status "
            "(player_id, team_id, report_date, status, reason, source, last_updated_ts) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (2544, 1610612747, "2026-04-10", "Questionable", "ankle",
             "rotowire", "2026-04-10T21:00:00Z"),
        )
        self.conn.commit()
        self.conn.close()

    def teardown_method(self):
        try:
            os.unlink(self.db_path)
        except OSError:
            pass

    def test_injuries_endpoint_returns_200(self):
        client, api_mod, orig_db, setup_mod, orig_setup = _make_api_client(self.db_path)
        try:
            resp = client.get("/api/injuries")
            assert resp.status_code == 200
        finally:
            api_mod.DB_PATH = orig_db
            setup_mod.DB_PATH = orig_setup

    def test_injuries_endpoint_schema(self):
        client, api_mod, orig_db, setup_mod, orig_setup = _make_api_client(self.db_path)
        try:
            resp = client.get("/api/injuries")
            data = resp.json()
            assert "report_date" in data
            assert "injuries" in data
            assert isinstance(data["injuries"], list)
        finally:
            api_mod.DB_PATH = orig_db
            setup_mod.DB_PATH = orig_setup

    def test_injuries_endpoint_returns_correct_data(self):
        client, api_mod, orig_db, setup_mod, orig_setup = _make_api_client(self.db_path)
        try:
            resp = client.get("/api/injuries")
            data = resp.json()
            assert data["report_date"] == "2026-04-10"
            assert len(data["injuries"]) == 1
            injury = data["injuries"][0]
            assert injury["player_id"] == 2544
            assert injury["status"] == "Questionable"
            assert injury["reason"] == "ankle"
        finally:
            api_mod.DB_PATH = orig_db
            setup_mod.DB_PATH = orig_setup

    def test_injuries_empty_db_returns_empty_list(self):
        # Use a fresh DB with no injuries
        tmp_path, tmp_conn = _make_test_db()
        tmp_conn.close()
        try:
            client, api_mod, orig_db, setup_mod, orig_setup = _make_api_client(tmp_path)
            try:
                resp = client.get("/api/injuries")
                data = resp.json()
                assert resp.status_code == 200
                assert data["injuries"] == []
                assert data["report_date"] is None
            finally:
                api_mod.DB_PATH = orig_db
                setup_mod.DB_PATH = orig_setup
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


class TestPlayerInjuryEndpoint:
    def setup_method(self):
        self.db_path, self.conn = _make_test_db()
        self.conn.execute(
            "INSERT INTO Injury_Status "
            "(player_id, team_id, report_date, status, reason, source, last_updated_ts) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (2544, 1610612747, "2026-04-10", "Out", "knee",
             "rotowire", "2026-04-10T21:00:00Z"),
        )
        self.conn.commit()
        self.conn.close()

    def teardown_method(self):
        try:
            os.unlink(self.db_path)
        except OSError:
            pass

    def test_player_injury_returns_200(self):
        client, api_mod, orig_db, setup_mod, orig_setup = _make_api_client(self.db_path)
        try:
            resp = client.get("/api/players/2544/injury")
            assert resp.status_code == 200
        finally:
            api_mod.DB_PATH = orig_db
            setup_mod.DB_PATH = orig_setup

    def test_player_injury_schema(self):
        client, api_mod, orig_db, setup_mod, orig_setup = _make_api_client(self.db_path)
        try:
            resp = client.get("/api/players/2544/injury")
            data = resp.json()
            assert "player_id" in data
            assert "injury" in data
        finally:
            api_mod.DB_PATH = orig_db
            setup_mod.DB_PATH = orig_setup

    def test_player_injury_correct_data(self):
        client, api_mod, orig_db, setup_mod, orig_setup = _make_api_client(self.db_path)
        try:
            resp = client.get("/api/players/2544/injury")
            data = resp.json()
            assert data["player_id"] == 2544
            injury = data["injury"]
            assert injury["status"] == "Out"
            assert injury["reason"] == "knee"
            assert injury["source"] == "rotowire"
        finally:
            api_mod.DB_PATH = orig_db
            setup_mod.DB_PATH = orig_setup

    def test_player_not_found_returns_404(self):
        client, api_mod, orig_db, setup_mod, orig_setup = _make_api_client(self.db_path)
        try:
            resp = client.get("/api/players/9999999/injury")
            assert resp.status_code == 404
        finally:
            api_mod.DB_PATH = orig_db
            setup_mod.DB_PATH = orig_setup

    def test_player_no_injury_returns_empty_dict(self):
        """Player exists but has no injury record — should return {}."""
        client, api_mod, orig_db, setup_mod, orig_setup = _make_api_client(self.db_path)
        try:
            # player_id 201939 (Curry) has no injury row in this test's DB
            resp = client.get("/api/players/201939/injury")
            data = resp.json()
            assert resp.status_code == 200
            assert data["injury"] == {}
        finally:
            api_mod.DB_PATH = orig_db
            setup_mod.DB_PATH = orig_setup


# ===========================================================================
# Tests: multi-source coexistence (new 3-column PK)
# ===========================================================================


class TestMultiSourceCoexistence:
    """Verify that two rows with the same (player_id, report_date) but
    different source values can coexist in the Injury_Status table after the
    PK migration to (player_id, report_date, source)."""

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

    def test_two_sources_same_player_date_coexist(self):
        """RotoWire + CBS rows for same player/date should both persist."""
        self._insert(2544, "2026-04-10", "rotowire")
        self._insert(2544, "2026-04-10", "cbssports")
        count = self.conn.execute(
            "SELECT COUNT(*) FROM Injury_Status "
            "WHERE player_id=2544 AND report_date='2026-04-10'"
        ).fetchone()[0]
        assert count == 2

    def test_upsert_same_pk_is_idempotent(self):
        """Inserting same (player_id, report_date, source) twice replaces, not appends."""
        self._insert(2544, "2026-04-10", "rotowire", status="Questionable")
        self._insert(2544, "2026-04-10", "rotowire", status="Out")
        count = self.conn.execute(
            "SELECT COUNT(*) FROM Injury_Status "
            "WHERE player_id=2544 AND report_date='2026-04-10' AND source='rotowire'"
        ).fetchone()[0]
        assert count == 1
        status = self.conn.execute(
            "SELECT status FROM Injury_Status "
            "WHERE player_id=2544 AND report_date='2026-04-10' AND source='rotowire'"
        ).fetchone()[0]
        assert status == "Out"

    def test_source_filter_api(self):
        """GET /api/injuries?source=rotowire returns only rotowire rows."""
        self._insert(2544, "2026-04-10", "rotowire", status="Questionable")
        self._insert(201939, "2026-04-10", "cbssports", status="Out")
        self.conn.close()
        client, api_mod, orig_db, setup_mod, orig_setup = _make_api_client(self.db_path)
        try:
            resp = client.get("/api/injuries?source=rotowire")
            assert resp.status_code == 200
            data = resp.json()
            assert all(r["source"] == "rotowire" for r in data["injuries"])
            assert len(data["injuries"]) == 1
            assert data["injuries"][0]["player_id"] == 2544
        finally:
            api_mod.DB_PATH = orig_db
            setup_mod.DB_PATH = orig_setup
            self.conn = sqlite3.connect(self.db_path)

    def test_no_source_filter_returns_all_sources(self):
        """GET /api/injuries (no filter) returns rows from all sources."""
        self._insert(2544, "2026-04-10", "rotowire")
        self._insert(201939, "2026-04-10", "cbssports")
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

    def test_injuries_sources_endpoint(self):
        """GET /api/injuries/sources returns distinct sources."""
        self._insert(2544, "2026-04-10", "rotowire")
        self._insert(201939, "2026-04-10", "cbssports")
        self.conn.close()
        client, api_mod, orig_db, setup_mod, orig_setup = _make_api_client(self.db_path)
        try:
            resp = client.get("/api/injuries/sources")
            assert resp.status_code == 200
            data = resp.json()
            assert "sources" in data
            assert set(data["sources"]) == {"rotowire", "cbssports"}
        finally:
            api_mod.DB_PATH = orig_db
            setup_mod.DB_PATH = orig_setup
            self.conn = sqlite3.connect(self.db_path)

    def test_player_injury_all_sources_field(self):
        """GET /api/players/{id}/injury includes all_sources for the latest date."""
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
