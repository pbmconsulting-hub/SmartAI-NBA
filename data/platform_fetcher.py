"""
Backward-compatibility shim.
This module has been renamed to ``data.sportsbook_service``.
All names are re-exported here so existing imports continue to work.
"""
from data.sportsbook_service import *  # noqa: F401,F403

# Re-export renamed functions under their old names
from data.sportsbook_service import get_prizepicks_props as fetch_prizepicks_props  # noqa: F401
from data.sportsbook_service import get_underdog_props as fetch_underdog_props  # noqa: F401
from data.sportsbook_service import get_draftkings_props as fetch_draftkings_props  # noqa: F401
from data.sportsbook_service import get_all_sportsbook_props as fetch_all_platform_props  # noqa: F401
from data.sportsbook_service import get_all_sportsbooks_async as fetch_all_platforms_async  # noqa: F401
