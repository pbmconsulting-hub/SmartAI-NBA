"""
Backward-compatibility shim.
This module has been renamed to ``data.player_profile_service``.
All names are re-exported here so existing imports continue to work.
"""
from data.player_profile_service import *  # noqa: F401,F403

# Re-export renamed functions under their old names
from data.player_profile_service import get_player_id as lookup_player_id  # noqa: F401
