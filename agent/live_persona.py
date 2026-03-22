# ============================================================
# FILE: agent/live_persona.py
# PURPOSE: Joseph M. Smith's "Live Vibe Check" persona for the
#          Live Sweat dashboard.  Generates in-game reactions
#          based on pacing-engine output.
# ============================================================

import random
import logging

try:
    from utils.logger import get_logger
    _logger = get_logger(__name__)
except ImportError:
    _logger = logging.getLogger(__name__)

# ── Fragment pools for rant assembly ─────────────────────────

_BLOWOUT_SCREAMS = [
    "🚨 BLOWOUT ALERT! Your guy is about to ride the pine, folks!",
    "📢 Game's a WRAP! Coach is pulling starters — PRAY!",
    "😱 Down 25 in the 3rd?! That bench is calling your player's NAME!",
    "🪑 SIT-DOWN CITY! The garbage-time lineup is warming up!",
    "💀 Your player is about to get BENCHED into oblivion!",
]

_FOUL_RANTS = [
    "🤦 THREE FOULS in the FIRST HALF?! These refs are ON ONE!",
    "⚖️ The refs are TARGETING your guy! This is CRIMINAL!",
    "🔴 Foul trouble ALREADY? Blame the zebras — I DO!",
    "😤 Three personals before halftime — TYPICAL ref ball!",
    "🗣️ HEY REF! You wanna call a foul on ME too while you're at it?!",
]

_CASHED_BRAGS = [
    "💰 CASHED! I told you — Joseph M. Smith NEVER misses!",
    "🎉 MONEY IN THE BANK! We called that HOURS ago!",
    "👑 That's what GREATNESS looks like! CASHED before the 4th!",
    "🤑 EASY MONEY! Did anyone doubt us? I DIDN'T!",
    "🏆 Another WIN in the books! Joseph M. Smith stays UNDEFEATED!",
    "💸 RING THE REGISTER! That prop is DONE and DUSTED!",
]

_ON_PACE_VIBES = [
    "📈 Looking GOOD! Your guy is ON PACE — stay calm, stay confident.",
    "🔥 Pace is right where we need it. Trust the process — MY process!",
    "✅ On track! Keep sweating — but the GOOD kind of sweat!",
    "💪 Stat line is building beautifully. Joseph M. Smith SEES the future!",
]

_BEHIND_PACE_WORRY = [
    "😬 Falling behind pace… but there's still time. MANIFEST IT!",
    "📉 Stat line is lagging — need a BIG quarter to catch up!",
    "🥶 Cold stretch right now. Come on, HEAT UP!",
    "⏰ Clock is ticking and we need MORE. Let's GO!",
]

_SYSTEM_PROMPT = """You are Joseph M. Smith, the world's most legendary NBA
analyst.  You speak with ABSOLUTE conviction and fire.  You react to live
game situations with passion — you brag when you're right, you blame the
refs when fouls pile up, and you scream about benching when blowouts hit.
Keep it under 2 sentences.  Be dramatic.  Use CAPS for emphasis."""


def get_joseph_live_reaction(pace_result: dict) -> str:
    """
    Generate Joseph M. Smith's live vibe-check reaction.

    Parameters
    ----------
    pace_result : dict
        Output from :func:`engine.live_math.calculate_live_pace`.

    Returns
    -------
    str — Joseph's dramatic one-liner reaction.
    """
    if not isinstance(pace_result, dict):
        return random.choice(_ON_PACE_VIBES)

    cashed = pace_result.get("cashed", False)
    blowout = pace_result.get("blowout_risk", False)
    foul = pace_result.get("foul_trouble", False)
    on_pace = pace_result.get("on_pace", False)

    # Priority order: cashed > blowout > foul > on_pace > behind
    if cashed:
        return random.choice(_CASHED_BRAGS)
    if blowout:
        return random.choice(_BLOWOUT_SCREAMS)
    if foul:
        return random.choice(_FOUL_RANTS)
    if on_pace:
        return random.choice(_ON_PACE_VIBES)
    return random.choice(_BEHIND_PACE_WORRY)


def stream_joseph_text(text: str):
    """
    Yield *text* character-by-character for ``st.write_stream``
    typing-effect rendering.
    """
    for char in text:
        yield char
