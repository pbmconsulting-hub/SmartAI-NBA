# ============================================================
# FILE: data/nba_context_fetcher.py
# PURPOSE: Enrich betting data with real NBA player context
#          and season stats.  Returns headshot URLs, position,
#          team logo URLs, next opponent, and season averages
#          (PPG, RPG, APG, Minutes) for use in the Player
#          Spotlight modal and Trading-Card grid.
#
# USAGE:
#   from data.nba_context_fetcher import enrich_player_data
#   vitals = enrich_player_data("LeBron James", players_data, todays_games)
# ============================================================

import html as _html
import logging as _logging

_logger = _logging.getLogger(__name__)

# ── NBA CDN helpers ─────────────────────────────────────────
# The official NBA CDN serves headshots at a predictable URL
# keyed by a numeric player ID.  We maintain a lightweight
# lookup of marquee player IDs so the UI never needs a live
# API call for the image.

_KNOWN_PLAYER_IDS: dict[str, int] = {
    "lebron james": 2544,
    "stephen curry": 201939,
    "kevin durant": 201142,
    "giannis antetokounmpo": 203507,
    "luka doncic": 1629029,
    "jayson tatum": 1628369,
    "nikola jokic": 203999,
    "joel embiid": 203954,
    "anthony davis": 203076,
    "damian lillard": 203081,
    "devin booker": 1626164,
    "jimmy butler": 202710,
    "anthony edwards": 1630162,
    "shai gilgeous-alexander": 1628983,
    "ja morant": 1629630,
    "donovan mitchell": 1628378,
    "trae young": 1629027,
    "paolo banchero": 1631094,
    "tyrese haliburton": 1630169,
    "de'aaron fox": 1628368,
    "jalen brunson": 1628973,
    "chet holmgren": 1631096,
    "victor wembanyama": 1641705,
    "lamelo ball": 1630163,
    "zion williamson": 1629627,
    "bam adebayo": 1628389,
    "karl-anthony towns": 1626157,
    "domantas sabonis": 1627734,
    "pascal siakam": 1627783,
    "lauri markkanen": 1628374,
    "desmond bane": 1630217,
    "tyler herro": 1629639,
    "cade cunningham": 1630595,
    "franz wagner": 1630532,
    "scottie barnes": 1630567,
    "mikal bridges": 1628969,
    "jalen williams": 1631114,
    "alperen sengun": 1630578,
}

# ── Team logo CDN ───────────────────────────────────────────
_NBA_TEAM_LOGO_TMPL = (
    "https://cdn.nba.com/logos/nba/{team_id}/global/L/logo.svg"
)

_TEAM_ABBREV_TO_ID: dict[str, int] = {
    "ATL": 1610612737, "BOS": 1610612738, "BKN": 1610612751,
    "CHA": 1610612766, "CHI": 1610612741, "CLE": 1610612739,
    "DAL": 1610612742, "DEN": 1610612743, "DET": 1610612765,
    "GSW": 1610612744, "HOU": 1610612745, "IND": 1610612754,
    "LAC": 1610612746, "LAL": 1610612747, "MEM": 1610612763,
    "MIA": 1610612748, "MIL": 1610612749, "MIN": 1610612750,
    "NOP": 1610612740, "NYK": 1610612752, "OKC": 1610612760,
    "ORL": 1610612753, "PHI": 1610612755, "PHX": 1610612756,
    "POR": 1610612757, "SAC": 1610612758, "SAS": 1610612759,
    "TOR": 1610612761, "UTA": 1610612762, "WAS": 1610612764,
}


def get_headshot_url(player_name: str) -> str:
    """Return the NBA CDN headshot URL for a player.

    Falls back to a generic silhouette if the player ID is unknown.

    Parameters
    ----------
    player_name : str
        Full player name (case-insensitive).

    Returns
    -------
    str
        URL string pointing to a player headshot image.
    """
    key = str(player_name).lower().strip()
    pid = _KNOWN_PLAYER_IDS.get(key)
    if pid:
        return (
            f"https://cdn.nba.com/headshots/nba/latest/1040x760/{pid}.png"
        )
    return "https://cdn.nba.com/headshots/nba/latest/1040x760/fallback.png"


def get_team_logo_url(team_abbrev: str) -> str:
    """Return the NBA CDN team logo SVG URL.

    Parameters
    ----------
    team_abbrev : str
        Three-letter NBA team abbreviation (e.g. ``"LAL"``).

    Returns
    -------
    str
        URL string pointing to a team logo SVG.
    """
    tid = _TEAM_ABBREV_TO_ID.get(str(team_abbrev).upper().strip(), 0)
    if tid:
        return _NBA_TEAM_LOGO_TMPL.format(team_id=tid)
    return ""


def _find_next_opponent(player_team: str, todays_games: list) -> str:
    """Derive the next opponent from today's game list.

    Parameters
    ----------
    player_team : str
        Player's team abbreviation.
    todays_games : list[dict]
        List of today's game dicts (keys: ``home_team``, ``away_team``).

    Returns
    -------
    str
        Opponent abbreviation or ``"TBD"`` if not found.
    """
    if not todays_games or not player_team:
        return "TBD"
    abbrev = str(player_team).upper().strip()
    for g in todays_games:
        home = str(g.get("home_team", "")).upper().strip()
        away = str(g.get("away_team", "")).upper().strip()
        if abbrev == home:
            return away
        if abbrev == away:
            return home
    return "TBD"


def _extract_season_stats(player_data: dict) -> dict:
    """Pull season averages from the players CSV row.

    The data_manager's ``load_players_data`` returns dicts whose
    keys vary by source (``"ppg"`` or ``"pts_per_game"`` etc.).
    This helper normalises to a stable shape.

    Parameters
    ----------
    player_data : dict
        A single player record from ``load_players_data()``.

    Returns
    -------
    dict
        ``{"ppg": float, "rpg": float, "apg": float, "avg_minutes": float}``
    """
    def _f(val):
        try:
            return round(float(val), 1)
        except (TypeError, ValueError):
            return 0.0

    ppg = _f(
        player_data.get("ppg")
        or player_data.get("pts_per_game")
        or player_data.get("points", 0)
    )
    rpg = _f(
        player_data.get("rpg")
        or player_data.get("reb_per_game")
        or player_data.get("rebounds", 0)
    )
    apg = _f(
        player_data.get("apg")
        or player_data.get("ast_per_game")
        or player_data.get("assists", 0)
    )
    avg_min = _f(
        player_data.get("avg_minutes")
        or player_data.get("min_per_game")
        or player_data.get("minutes", 0)
    )
    return {"ppg": ppg, "rpg": rpg, "apg": apg, "avg_minutes": avg_min}


def enrich_player_data(
    player_name: str,
    players_data: list,
    todays_games: list | None = None,
) -> dict:
    """Build a vitals dict for the Player Spotlight modal.

    Parameters
    ----------
    player_name : str
        Full player name.
    players_data : list[dict]
        Full players dataset from ``load_players_data()``.
    todays_games : list[dict] | None
        Today's game list for opponent resolution.

    Returns
    -------
    dict
        Keys: ``headshot_url``, ``position``, ``team``,
        ``team_logo_url``, ``next_opponent``, ``season_stats``.
    """
    safe_name = _html.escape(str(player_name))
    key = str(player_name).lower().strip()

    # Find player in dataset
    player_row: dict = {}
    if isinstance(players_data, list):
        for p in players_data:
            if str(p.get("name", "")).lower().strip() == key:
                player_row = p
                break
    elif isinstance(players_data, dict):
        player_row = players_data.get(player_name, {})

    team = str(player_row.get("team", player_row.get("team_abbrev", ""))).upper().strip()
    position = str(player_row.get("position", player_row.get("pos", ""))).strip()

    return {
        "player_name": safe_name,
        "headshot_url": get_headshot_url(player_name),
        "position": position or "N/A",
        "team": team or "N/A",
        "team_logo_url": get_team_logo_url(team),
        "next_opponent": _find_next_opponent(team, todays_games or []),
        "season_stats": _extract_season_stats(player_row),
    }
