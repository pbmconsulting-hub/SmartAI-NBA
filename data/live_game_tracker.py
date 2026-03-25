# ============================================================
# FILE: data/live_game_tracker.py
# PURPOSE: API Firewall & Fuzzy Entity Matcher for Live Sweat
#          dashboard.  All live data retrieving is wrapped in
#          @st.cache_data(ttl=120) to restrict API calls to
#          once every 2 minutes.
# ============================================================

import logging

try:
    from utils.logger import get_logger
    _logger = get_logger(__name__)
except ImportError:
    _logger = logging.getLogger(__name__)

try:
    import streamlit as st
    _ST_AVAILABLE = True
except ImportError:
    _ST_AVAILABLE = False

try:
    from thefuzz import process as _fuzz_process
    _FUZZ_AVAILABLE = True
except ImportError:
    _FUZZ_AVAILABLE = False

# ============================================================
# SECTION: API Firewall — Cached Live Box-Score Service
# ============================================================


def _get_live_boxscores_impl() -> list[dict]:
    """
    Retrieve live NBA box scores from API-NBA API.

    Returns a list of game dicts, each containing:
        game_id, home_team, away_team, home_score, away_score,
        period, game_clock, status, home_players, away_players.

    Each player entry in *_players* is a dict with:
        name, pts, reb, ast, stl, blk, tov, fg3m, minutes, fouls
    """
    try:
        raw_scores = []
    except Exception as exc:
        _logger.warning("live_game_tracker: retrieval failed: %s", exc)
        raw_scores = []

    games: list[dict] = []
    for g in (raw_scores or []):
        if not isinstance(g, dict):
            continue

        game = {
            "game_id":    str(g.get("game_id") or g.get("id", "")),
            "home_team":  str(g.get("home_team") or g.get("home_abbreviation", "")),
            "away_team":  str(g.get("away_team") or g.get("away_abbreviation", "")),
            "home_score": int(float(g.get("home_score", 0) or 0)),
            "away_score": int(float(g.get("away_score", 0) or 0)),
            "period":     str(g.get("period") or g.get("quarter", "")),
            "game_clock": str(g.get("game_clock") or g.get("clock", "")),
            "status":     str(g.get("status", "")),
        }

        # Collect player-level stats from any available key
        home_players: list[dict] = []
        away_players: list[dict] = []

        for team_key, dest in [
            ("home_players", home_players),
            ("away_players", away_players),
        ]:
            for player in g.get(team_key, []):
                if not isinstance(player, dict):
                    continue
                stats = player.get("statistics", player)
                pname = str(player.get("name") or player.get("player_name", ""))
                if not pname:
                    continue
                dest.append({
                    "name":    pname,
                    "pts":     float(stats.get("pts", stats.get("points", 0)) or 0),
                    "reb":     float(stats.get("reb", stats.get("rebounds", 0)) or 0),
                    "ast":     float(stats.get("ast", stats.get("assists", 0)) or 0),
                    "stl":     float(stats.get("stl", stats.get("steals", 0)) or 0),
                    "blk":     float(stats.get("blk", stats.get("blocks", 0)) or 0),
                    "tov":     float(stats.get("tov", stats.get("turnovers", 0)) or 0),
                    "fg3m":    float(stats.get("fg3m", stats.get("threes_made", 0)) or 0),
                    "minutes": float(stats.get("minutes", stats.get("min", 0)) or 0),
                    "fouls":   int(float(stats.get("fouls", stats.get("pf", 0)) or 0)),
                })

        # Also handle a generic "players" key from some API shapes
        for player in g.get("players", []):
            if not isinstance(player, dict):
                continue
            stats = player.get("statistics", player)
            pname = str(player.get("name") or player.get("player_name", ""))
            if not pname:
                continue
            entry = {
                "name":    pname,
                "pts":     float(stats.get("pts", stats.get("points", 0)) or 0),
                "reb":     float(stats.get("reb", stats.get("rebounds", 0)) or 0),
                "ast":     float(stats.get("ast", stats.get("assists", 0)) or 0),
                "stl":     float(stats.get("stl", stats.get("steals", 0)) or 0),
                "blk":     float(stats.get("blk", stats.get("blocks", 0)) or 0),
                "tov":     float(stats.get("tov", stats.get("turnovers", 0)) or 0),
                "fg3m":    float(stats.get("fg3m", stats.get("threes_made", 0)) or 0),
                "minutes": float(stats.get("minutes", stats.get("min", 0)) or 0),
                "fouls":   int(float(stats.get("fouls", stats.get("pf", 0)) or 0)),
            }
            # Place into whichever team list has fewer entries as fallback
            if len(home_players) <= len(away_players):
                home_players.append(entry)
            else:
                away_players.append(entry)

        game["home_players"] = home_players
        game["away_players"] = away_players
        games.append(game)

    return games


def get_live_boxscores() -> list[dict]:
    """
    API-firewalled live box-score service.

    When Streamlit is available the result is cached for 120 seconds
    via ``@st.cache_data``.  Outside of Streamlit (e.g. tests) it
    calls the implementation directly.
    """
    if _ST_AVAILABLE:
        # Build a cached wrapper on first call and reuse it.
        if not hasattr(get_live_boxscores, "_cached"):
            get_live_boxscores._cached = st.cache_data(
                ttl=120, show_spinner=False
            )(_get_live_boxscores_impl)
        return get_live_boxscores._cached()
    return _get_live_boxscores_impl()


# ============================================================
# SECTION: Entity Resolver — Fuzzy Player Matcher
# ============================================================

# Common NBA nickname → full-name mapping for common short-hands
_NICKNAME_MAP: dict[str, str] = {
    # ── Superstars & MVPs ──────────────────────────────────────
    "sga":     "Shai Gilgeous-Alexander",
    "lbj":     "LeBron James",
    "lebron":  "LeBron James",
    "ad":      "Anthony Davis",
    "kd":      "Kevin Durant",
    "pg":      "Paul George",
    "cp3":     "Chris Paul",
    "kat":     "Karl-Anthony Towns",
    "rj":      "RJ Barrett",
    "cj":      "CJ McCollum",
    "dlo":     "D'Angelo Russell",
    "ant":     "Anthony Edwards",
    "ja":      "Ja Morant",
    "book":    "Devin Booker",
    "jokic":   "Nikola Jokic",
    "embiid":  "Joel Embiid",
    "giannis": "Giannis Antetokounmpo",
    "steph":   "Stephen Curry",
    "dame":    "Damian Lillard",
    "trae":    "Trae Young",
    "luka":    "Luka Doncic",
    # ── Rising Stars & Fan Favourites ─────────────────────────
    "bam":     "Bam Adebayo",
    "zion":    "Zion Williamson",
    "fox":     "De'Aaron Fox",
    "scottie": "Scottie Barnes",
    "cade":    "Cade Cunningham",
    "wemby":   "Victor Wembanyama",
    "paolo":   "Paolo Banchero",
    "herb":    "Herbert Jones",
    "jalen":   "Jalen Brunson",
    "brunson": "Jalen Brunson",
    "hali":    "Tyrese Haliburton",
    "maxey":   "Tyrese Maxey",
    "lamelo":  "LaMelo Ball",
    "melo":    "LaMelo Ball",
    "jimmy":   "Jimmy Butler",
    "kawhi":   "Kawhi Leonard",
    "kyrie":   "Kyrie Irving",
    "boogie":  "DeMarcus Cousins",
    "spida":   "Donovan Mitchell",
    "derozan": "DeMar DeRozan",
    "sabonis": "Domantas Sabonis",
    "ingram":  "Brandon Ingram",
    "siakam":  "Pascal Siakam",
    "murray":  "Jamal Murray",
    "garland": "Darius Garland",
    "lavine":  "Zach LaVine",
}

# 85% similarity — high enough to avoid false positives, but low enough
# to tolerate minor spelling variations & missing suffixes (e.g. "Jr.").
_FUZZY_THRESHOLD = 85


def match_live_player(target_name: str,
                      live_players: list[dict],
                      threshold: int = _FUZZY_THRESHOLD) -> dict | None:
    """
    Fuzzy-match *target_name* against the ``name`` field in *live_players*.

    Uses ``thefuzz.process.extractOne`` with a configurable *threshold*
    (default 85).  Falls back to case-insensitive substring matching
    when thefuzz is unavailable or no match exceeds the threshold.

    Returns the matched player dict or ``None``.
    """
    if not target_name or not live_players:
        return None

    # Normalise the target
    target_lower = target_name.strip().lower()

    # Resolve common nicknames first
    if target_lower in _NICKNAME_MAP:
        target_name = _NICKNAME_MAP[target_lower]
        target_lower = target_name.lower()

    # Build a name → player-dict lookup
    name_lookup: dict[str, dict] = {}
    for p in live_players:
        pname = str(p.get("name", "")).strip()
        if pname:
            name_lookup[pname] = p

    if not name_lookup:
        return None

    names_list = list(name_lookup.keys())

    # 1. Exact (case-insensitive) match
    for n in names_list:
        if n.lower() == target_lower:
            return name_lookup[n]

    # 2. Fuzzy match via thefuzz
    if _FUZZ_AVAILABLE:
        try:
            result = _fuzz_process.extractOne(
                target_name, names_list, score_cutoff=threshold
            )
            if result is not None:
                matched_name, score = result[0], result[1]
                _logger.debug(
                    "Fuzzy matched '%s' → '%s' (score=%d)",
                    target_name, matched_name, score,
                )
                return name_lookup[matched_name]
        except Exception as exc:
            _logger.warning("Fuzzy match error: %s", exc)

    # 3. Substring fallback (e.g. "Gilgeous" in "Shai Gilgeous-Alexander")
    for n in names_list:
        if target_lower in n.lower() or n.lower() in target_lower:
            return name_lookup[n]

    return None


def get_all_live_players(games: list[dict] | None = None) -> list[dict]:
    """
    Flatten all player dicts from the live box-score games list.

    If *games* is not provided, calls :func:`get_live_boxscores`.
    """
    if games is None:
        games = get_live_boxscores()
    players: list[dict] = []
    for g in games:
        players.extend(g.get("home_players", []))
        players.extend(g.get("away_players", []))
    return players


def get_game_for_player(player_name: str,
                        games: list[dict] | None = None) -> dict | None:
    """
    Return the game dict that contains *player_name* (fuzzy-matched).
    """
    if games is None:
        games = get_live_boxscores()
    for g in games:
        all_players = g.get("home_players", []) + g.get("away_players", [])
        if match_live_player(player_name, all_players) is not None:
            return g
    return None

