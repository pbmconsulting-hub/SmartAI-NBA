# ============================================================
# FILE: tests/test_expanded_stat_types.py
# PURPOSE: Tests that new stat types are properly registered
#          across platform_mappings, engine/__init__, and
#          engine/backtester.
# ============================================================
import unittest


NEW_STAT_TYPES = [
    "ftm", "fga", "fgm", "fta",
    "minutes", "personal_fouls",
    "offensive_rebounds", "defensive_rebounds",
]


class TestSimpleStatTypes(unittest.TestCase):
    """Verify new stats are in SIMPLE_STAT_TYPES."""

    def setUp(self):
        try:
            from engine import SIMPLE_STAT_TYPES
            self.simple_stats = SIMPLE_STAT_TYPES
        except ImportError as exc:
            self.skipTest(f"engine not importable: {exc}")

    def test_all_new_stats_in_simple_stat_types(self):
        for stat in NEW_STAT_TYPES:
            self.assertIn(stat, self.simple_stats,
                          f"'{stat}' missing from SIMPLE_STAT_TYPES")

    def test_original_stats_still_present(self):
        original = ["points", "rebounds", "assists", "threes", "steals", "blocks", "turnovers"]
        for stat in original:
            self.assertIn(stat, self.simple_stats,
                          f"Original stat '{stat}' missing from SIMPLE_STAT_TYPES")


class TestPrizePicksStatMap(unittest.TestCase):
    """Verify new stats are in PRIZEPICKS_STAT_MAP."""

    def setUp(self):
        try:
            from data.platform_mappings import PRIZEPICKS_STAT_MAP
            self.stat_map = PRIZEPICKS_STAT_MAP
        except ImportError as exc:
            self.skipTest(f"platform_mappings not importable: {exc}")

    def test_free_throws_made_maps_to_ftm(self):
        self.assertEqual(self.stat_map.get("Free Throws Made"), "ftm")

    def test_fg_attempted_maps_to_fga(self):
        self.assertEqual(self.stat_map.get("FG Attempted"), "fga")

    def test_fg_made_maps_to_fgm(self):
        self.assertEqual(self.stat_map.get("FG Made"), "fgm")

    def test_ft_attempted_maps_to_fta(self):
        self.assertEqual(self.stat_map.get("FT Attempted"), "fta")

    def test_double_double_maps_correctly(self):
        self.assertEqual(self.stat_map.get("Double Double"), "double_double")

    def test_triple_double_maps_correctly(self):
        self.assertEqual(self.stat_map.get("Triple Double"), "triple_double")

    def test_minutes_maps_correctly(self):
        self.assertEqual(self.stat_map.get("Minutes"), "minutes")

    def test_personal_fouls_maps_correctly(self):
        self.assertEqual(self.stat_map.get("Personal Fouls"), "personal_fouls")

    def test_offensive_rebounds_maps_correctly(self):
        self.assertEqual(self.stat_map.get("Offensive Rebounds"), "offensive_rebounds")

    def test_defensive_rebounds_maps_correctly(self):
        self.assertEqual(self.stat_map.get("Defensive Rebounds"), "defensive_rebounds")


class TestDraftKingsStatMap(unittest.TestCase):
    """Verify new stats are in DRAFTKINGS_STAT_MAP."""

    def setUp(self):
        try:
            from data.platform_mappings import DRAFTKINGS_STAT_MAP
            self.stat_map = DRAFTKINGS_STAT_MAP
        except ImportError as exc:
            self.skipTest(f"platform_mappings not importable: {exc}")

    def test_free_throws_made(self):
        self.assertEqual(self.stat_map.get("Free Throws Made"), "ftm")

    def test_ftm_abbreviation(self):
        self.assertEqual(self.stat_map.get("FTM"), "ftm")

    def test_fg_attempted(self):
        self.assertEqual(self.stat_map.get("FG Attempted"), "fga")

    def test_fga_abbreviation(self):
        self.assertEqual(self.stat_map.get("FGA"), "fga")

    def test_fg_made(self):
        self.assertEqual(self.stat_map.get("FG Made"), "fgm")

    def test_fgm_abbreviation(self):
        self.assertEqual(self.stat_map.get("FGM"), "fgm")

    def test_ft_attempted(self):
        self.assertEqual(self.stat_map.get("FT Attempted"), "fta")

    def test_fta_abbreviation(self):
        self.assertEqual(self.stat_map.get("FTA"), "fta")

    def test_minutes(self):
        self.assertEqual(self.stat_map.get("Minutes"), "minutes")

    def test_personal_fouls(self):
        self.assertEqual(self.stat_map.get("Personal Fouls"), "personal_fouls")

    def test_offensive_rebounds(self):
        self.assertEqual(self.stat_map.get("Offensive Rebounds"), "offensive_rebounds")

    def test_defensive_rebounds(self):
        self.assertEqual(self.stat_map.get("Defensive Rebounds"), "defensive_rebounds")


class TestUnderdogStatMap(unittest.TestCase):
    """Verify new stats are in UNDERDOG_STAT_MAP."""

    def setUp(self):
        try:
            from data.platform_mappings import UNDERDOG_STAT_MAP
            self.stat_map = UNDERDOG_STAT_MAP
        except ImportError as exc:
            self.skipTest(f"platform_mappings not importable: {exc}")

    def test_free_throws_made(self):
        self.assertEqual(self.stat_map.get("Free Throws Made"), "ftm")

    def test_fg_attempted(self):
        self.assertEqual(self.stat_map.get("FG Attempted"), "fga")

    def test_fg_made(self):
        self.assertEqual(self.stat_map.get("FG Made"), "fgm")

    def test_ft_attempted(self):
        self.assertEqual(self.stat_map.get("FT Attempted"), "fta")

    def test_minutes(self):
        self.assertEqual(self.stat_map.get("Minutes"), "minutes")

    def test_personal_fouls(self):
        self.assertEqual(self.stat_map.get("Personal Fouls"), "personal_fouls")

    def test_offensive_rebounds(self):
        self.assertEqual(self.stat_map.get("Offensive Rebounds"), "offensive_rebounds")

    def test_defensive_rebounds(self):
        self.assertEqual(self.stat_map.get("Defensive Rebounds"), "defensive_rebounds")


class TestBacktesterStatKeyMap(unittest.TestCase):
    """Verify new stats are in STAT_KEY_MAP in engine/backtester.py."""

    def setUp(self):
        try:
            from engine.backtester import STAT_KEY_MAP
            self.stat_map = STAT_KEY_MAP
        except ImportError as exc:
            self.skipTest(f"engine.backtester not importable: {exc}")

    def test_ftm_in_map(self):
        self.assertIn("ftm", self.stat_map)
        self.assertEqual(self.stat_map["ftm"], "FTM")

    def test_fta_in_map(self):
        self.assertIn("fta", self.stat_map)
        self.assertEqual(self.stat_map["fta"], "FTA")

    def test_fga_in_map(self):
        self.assertIn("fga", self.stat_map)
        self.assertEqual(self.stat_map["fga"], "FGA")

    def test_fgm_in_map(self):
        self.assertIn("fgm", self.stat_map)
        self.assertEqual(self.stat_map["fgm"], "FGM")

    def test_minutes_in_map(self):
        self.assertIn("minutes", self.stat_map)
        self.assertEqual(self.stat_map["minutes"], "MIN")

    def test_personal_fouls_in_map(self):
        self.assertIn("personal_fouls", self.stat_map)
        self.assertEqual(self.stat_map["personal_fouls"], "PF")

    def test_offensive_rebounds_in_map(self):
        self.assertIn("offensive_rebounds", self.stat_map)
        self.assertEqual(self.stat_map["offensive_rebounds"], "OREB")

    def test_defensive_rebounds_in_map(self):
        self.assertIn("defensive_rebounds", self.stat_map)
        self.assertEqual(self.stat_map["defensive_rebounds"], "DREB")

    def test_original_stats_still_present(self):
        originals = {
            "points": "PTS", "rebounds": "REB", "assists": "AST",
            "steals": "STL", "blocks": "BLK", "threes": "FG3M", "turnovers": "TOV",
        }
        for stat, expected_key in originals.items():
            self.assertEqual(self.stat_map.get(stat), expected_key,
                             f"Original stat '{stat}' → '{expected_key}' not in STAT_KEY_MAP")


class TestNormalizeStatType(unittest.TestCase):
    """Verify normalize_stat_type correctly maps new stat names."""

    def setUp(self):
        try:
            from data.platform_mappings import normalize_stat_type
            self._normalize = normalize_stat_type
        except ImportError as exc:
            self.skipTest(f"platform_mappings not importable: {exc}")

    def test_free_throws_made_prizepicks(self):
        self.assertEqual(self._normalize("Free Throws Made", "PrizePicks"), "ftm")

    def test_fg_attempted_prizepicks(self):
        self.assertEqual(self._normalize("FG Attempted", "PrizePicks"), "fga")

    def test_fg_made_prizepicks(self):
        self.assertEqual(self._normalize("FG Made", "PrizePicks"), "fgm")

    def test_ft_attempted_prizepicks(self):
        self.assertEqual(self._normalize("FT Attempted", "PrizePicks"), "fta")

    def test_minutes_prizepicks(self):
        self.assertEqual(self._normalize("Minutes", "PrizePicks"), "minutes")

    def test_personal_fouls_prizepicks(self):
        self.assertEqual(self._normalize("Personal Fouls", "PrizePicks"), "personal_fouls")

    def test_offensive_rebounds_prizepicks(self):
        self.assertEqual(self._normalize("Offensive Rebounds", "PrizePicks"), "offensive_rebounds")

    def test_defensive_rebounds_prizepicks(self):
        self.assertEqual(self._normalize("Defensive Rebounds", "PrizePicks"), "defensive_rebounds")

    def test_ftm_draftkings(self):
        self.assertEqual(self._normalize("FTM", "DraftKings"), "ftm")

    def test_fga_draftkings(self):
        self.assertEqual(self._normalize("FGA", "DraftKings"), "fga")


if __name__ == "__main__":
    unittest.main()
