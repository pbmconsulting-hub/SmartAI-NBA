# ============================================================
# FILE: agent/live_persona.py
# PURPOSE: Joseph M. Smith's "Live Vibe Check" persona for the
#          Live Sweat dashboard.  Generates in-game reactions
#          based on pacing-engine output.
# ============================================================

import random
import time
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
    "🏳️ WHITE FLAG TERRITORY! Starters are done for the night!",
    "📉 Blowout mode ACTIVATED — your guy's stat line just FROZE!",
]

_FOUL_RANTS = [
    "🤦 THREE FOULS in the FIRST HALF?! These refs are ON ONE!",
    "⚖️ The refs are TARGETING your guy! This is CRIMINAL!",
    "🔴 Foul trouble ALREADY? Blame the zebras — I DO!",
    "😤 Three personals before halftime — TYPICAL ref ball!",
    "🗣️ HEY REF! You wanna call a foul on ME too while you're at it?!",
    "👨‍⚖️ The whistle happy refs are RUINING this man's stat line!",
    "🚫 Coach just pulled him for foul trouble — BLAME THE REFS!",
]

_CASHED_BRAGS = [
    "💰 CASHED! I told you — Joseph M. Smith NEVER misses!",
    "🎉 MONEY IN THE BANK! We called that HOURS ago!",
    "👑 That's what GREATNESS looks like! CASHED before the 4th!",
    "🤑 EASY MONEY! Did anyone doubt us? I DIDN'T!",
    "🏆 Another WIN in the books! Joseph M. Smith stays UNDEFEATED!",
    "💸 RING THE REGISTER! That prop is DONE and DUSTED!",
    "🔔 DING DING DING! That's the sound of WINNING, baby!",
    "🎯 BULLSEYE! Called it. Locked it. CASHED it. That's the Joseph way!",
]

_ON_PACE_VIBES = [
    "📈 Looking GOOD! Your guy is ON PACE — stay calm, stay confident.",
    "🔥 Pace is right where we need it. Trust the process — MY process!",
    "✅ On track! Keep sweating — but the GOOD kind of sweat!",
    "💪 Stat line is building beautifully. Joseph M. Smith SEES the future!",
    "😎 Smooth sailing so far. The numbers don't lie and neither do I!",
    "🎯 Right on target! This is EXACTLY how we drew it up!",
]

_BEHIND_PACE_WORRY = [
    "😬 Falling behind pace… but there's still time. MANIFEST IT!",
    "📉 Stat line is lagging — need a BIG quarter to catch up!",
    "🥶 Cold stretch right now. Come on, HEAT UP!",
    "⏰ Clock is ticking and we need MORE. Let's GO!",
    "😰 Not where we want to be, but a big run can change EVERYTHING!",
    "🙏 Send positive energy — your guy needs a SURGE right now!",
]

_UNDER_CASHED_BRAGS = [
    "💰 UNDER CASHED! The game clock ran out and your guy fell SHORT! PERFECT!",
    "🧊 ICE COLD stat line — exactly what we NEEDED for the UNDER!",
    "📉 That's the FINAL and your guy couldn't reach the line! WE WIN!",
]

_UNDER_ON_PACE_VIBES = [
    "❄️ UNDER looking SAFE! Stat line is nice and quiet — just how we want it!",
    "🛡️ Defense is LOCKING HIM UP! The UNDER is cruising!",
    "📊 Pace is LOW and the clock keeps ticking — UNDER gang EATS!",
    "😎 Under the line and staying there. Joseph called it AGAIN!",
]

_UNDER_LOSING_WORRY = [
    "😳 He's HEATING UP! The UNDER is in DANGER!",
    "🔥 Too many stats too fast — the UNDER needs this man to CHILL!",
    "📈 Pace is way too hot for the UNDER. Need him to SIT DOWN!",
    "😤 SLOW DOWN! Every bucket puts our UNDER at risk!",
]

_OVERTIME_ALERT = [
    "⏱️ OVERTIME! Extra minutes means extra stats — buckle up!",
    "🔄 OT! The game won't end and neither will the STRESS!",
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
    direction = str(pace_result.get("direction", "OVER")).upper()
    is_ot = pace_result.get("is_overtime", False)

    # OT notice (prepend to reaction if in overtime)
    ot_prefix = random.choice(_OVERTIME_ALERT) + " " if is_ot else ""

    # Priority order: cashed > blowout > foul > on_pace > behind
    if cashed:
        return ot_prefix + random.choice(_CASHED_BRAGS)

    if direction == "UNDER":
        if blowout:
            # Blowout is actually GOOD for under bets (starters pulled)
            return ot_prefix + random.choice(_UNDER_ON_PACE_VIBES)
        if foul:
            return ot_prefix + random.choice(_UNDER_ON_PACE_VIBES)
        if on_pace:
            return ot_prefix + random.choice(_UNDER_ON_PACE_VIBES)
        return ot_prefix + random.choice(_UNDER_LOSING_WORRY)

    # OVER direction
    if blowout:
        return ot_prefix + random.choice(_BLOWOUT_SCREAMS)
    if foul:
        return ot_prefix + random.choice(_FOUL_RANTS)
    if on_pace:
        return ot_prefix + random.choice(_ON_PACE_VIBES)
    return ot_prefix + random.choice(_BEHIND_PACE_WORRY)


# ── Typing delay (seconds per character) for st.write_stream ──
_TYPING_DELAY = 0.012


def stream_joseph_text(text: str, delay: float = _TYPING_DELAY):
    """
    Yield *text* character-by-character with a small delay for a
    realistic typing effect with ``st.write_stream``.

    Parameters
    ----------
    text : str
        The text to stream.
    delay : float
        Seconds to pause between characters (default 0.012 s).
    """
    for char in text:
        yield char
        if delay > 0:
            time.sleep(delay)
