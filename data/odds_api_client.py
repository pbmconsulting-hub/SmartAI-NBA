"""
Backward-compatibility shim.
This module has been renamed to ``data.odds_client``.
All names are re-exported here so existing imports continue to work.
"""
from data.odds_client import *  # noqa: F401,F403

# Re-export renamed functions under their old names
from data.odds_client import validate_odds_api_key as validate_api_key  # noqa: F401
from data.odds_client import get_sports as fetch_sports  # noqa: F401
from data.odds_client import get_events as fetch_events  # noqa: F401
from data.odds_client import get_event_odds as fetch_event_odds  # noqa: F401
from data.odds_client import get_game_odds as fetch_game_odds  # noqa: F401
from data.odds_client import get_player_props as fetch_player_props  # noqa: F401
from data.odds_client import get_recent_scores as fetch_recent_scores  # noqa: F401
