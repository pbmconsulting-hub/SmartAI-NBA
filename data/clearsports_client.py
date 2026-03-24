"""
Backward-compatibility shim.
This module has been renamed to ``data.nba_api_client``.
All names are re-exported here so existing imports continue to work.
"""
from data.nba_api_client import *  # noqa: F401,F403

# Re-export renamed functions under their old names
from data.nba_api_client import validate_nba_api_key as validate_api_key  # noqa: F401
from data.nba_api_client import get_teams as fetch_teams  # noqa: F401
from data.nba_api_client import get_games as fetch_games  # noqa: F401
from data.nba_api_client import get_players as fetch_players  # noqa: F401
from data.nba_api_client import get_todays_games as fetch_games_today  # noqa: F401
from data.nba_api_client import get_player_stats as fetch_player_stats  # noqa: F401
from data.nba_api_client import get_team_stats as fetch_team_stats  # noqa: F401
from data.nba_api_client import get_injury_report as fetch_injury_report  # noqa: F401
from data.nba_api_client import get_live_scores as fetch_live_scores  # noqa: F401
from data.nba_api_client import get_rosters as fetch_rosters  # noqa: F401
from data.nba_api_client import get_player_id as lookup_player_id  # noqa: F401
from data.nba_api_client import get_player_game_log as fetch_player_game_log  # noqa: F401
from data.nba_api_client import get_standings as fetch_standings  # noqa: F401
from data.nba_api_client import get_news as fetch_news  # noqa: F401
from data.nba_api_client import get_season_game_logs_batch as fetch_season_game_logs_batch  # noqa: F401
from data.nba_api_client import get_api_key_info as fetch_api_key_info  # noqa: F401
from data.nba_api_client import get_api_key_usage as fetch_api_key_usage  # noqa: F401
from data.nba_api_client import get_api_key_stats as fetch_api_key_stats  # noqa: F401
from data.nba_api_client import get_team_by_id as fetch_team_by_id  # noqa: F401
from data.nba_api_client import get_game_odds as fetch_game_odds  # noqa: F401
from data.nba_api_client import get_nba_team_stats as fetch_nba_team_stats  # noqa: F401
from data.nba_api_client import get_nba_player_stats as fetch_nba_player_stats  # noqa: F401
from data.nba_api_client import get_predictions as fetch_predictions  # noqa: F401
