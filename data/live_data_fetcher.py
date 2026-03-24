"""
Backward-compatibility shim.
This module has been renamed to ``data.nba_data_service``.
All names are re-exported here so existing imports continue to work.
"""
from data.nba_data_service import *  # noqa: F401,F403

# Re-export renamed functions under their old names
from data.nba_data_service import get_todays_games as fetch_todays_games  # noqa: F401
from data.nba_data_service import get_todays_players as fetch_todays_players_only  # noqa: F401
from data.nba_data_service import get_player_recent_form as fetch_player_recent_form  # noqa: F401
from data.nba_data_service import get_player_stats as fetch_player_stats  # noqa: F401
from data.nba_data_service import get_team_stats as fetch_team_stats  # noqa: F401
from data.nba_data_service import get_defensive_ratings as fetch_defensive_ratings  # noqa: F401
from data.nba_data_service import get_player_game_log as fetch_player_game_log  # noqa: F401
from data.nba_data_service import get_all_data as fetch_all_data  # noqa: F401
from data.nba_data_service import get_all_todays_data as fetch_all_todays_data  # noqa: F401
from data.nba_data_service import get_active_rosters as fetch_active_rosters  # noqa: F401
from data.nba_data_service import get_standings as fetch_standings  # noqa: F401
from data.nba_data_service import get_player_news as fetch_player_news  # noqa: F401
