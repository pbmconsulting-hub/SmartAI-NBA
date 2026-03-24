"""
Backward-compatibility shim.
This module has been renamed to ``data.nba_stats_backup``.
All names are re-exported here so existing imports continue to work.
"""
from data.nba_stats_backup import *  # noqa: F401,F403

# Re-export renamed functions under their old names
from data.nba_stats_backup import get_team_stats_backup as fetch_team_stats_fallback  # noqa: F401
from data.nba_stats_backup import get_players_backup as fetch_players_fallback  # noqa: F401
from data.nba_stats_backup import get_player_stats_backup as fetch_player_stats_fallback  # noqa: F401
from data.nba_stats_backup import get_nba_team_stats_backup as fetch_nba_team_stats_fallback  # noqa: F401
from data.nba_stats_backup import get_nba_player_stats_backup as fetch_nba_player_stats_fallback  # noqa: F401
