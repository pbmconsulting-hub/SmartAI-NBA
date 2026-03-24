"""
Backward-compatibility shim.
This module has been renamed to ``data.live_game_tracker``.
All names are re-exported here so existing imports continue to work.
"""
from data.live_game_tracker import *  # noqa: F401,F403

# Re-export renamed functions under their old names
from data.live_game_tracker import get_live_boxscores as fetch_live_boxscores  # noqa: F401
