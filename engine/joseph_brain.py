"""
engine/joseph_brain.py
Joseph M. Smith Brain — Data Pools, Constants & Function Stubs (Layer 4, Part A)

PURPOSE
-------
Joseph's reasoning brain — fragment pools for combinatorial rant building,
body-template libraries keyed by verdict, ambient/commentary colour pools,
and stub signatures for every public function that Phase 1B will implement.

Every data structure is FULLY populated.  No ``pass``, no ``...``, no ``# TODO``.
The file is importable and every stub returns a type-correct default so
downstream callers won't crash.
"""

# ═══════════════════════════════════════════════════════════════
# STANDARD-LIBRARY IMPORTS
# ═══════════════════════════════════════════════════════════════
import random
import math
import itertools
import copy
import logging
import datetime

# ═══════════════════════════════════════════════════════════════
# EXTERNAL / SIBLING IMPORTS  (each wrapped in try/except)
# ═══════════════════════════════════════════════════════════════

try:
    from engine.joseph_eval import joseph_grade_player, ARCHETYPE_PROFILES
except ImportError:
    def joseph_grade_player(*a, **kw):
        return {
            "grade": "C",
            "archetype": "Unknown",
            "score": 50.0,
            "gravity": 50.0,
            "switchability": 50.0,
        }
    ARCHETYPE_PROFILES = {}

try:
    from engine.joseph_strategy import analyze_game_strategy, detect_narrative_tags
except ImportError:
    def analyze_game_strategy(*a, **kw):
        return {
            "scheme": "unknown",
            "strategy": "unknown",
            "scheme_match": 0.0,
            "mismatch_tags": [],
        }
    def detect_narrative_tags(*a, **kw):
        return []

try:
    from engine.simulation import run_quantum_matrix_simulation
except ImportError:
    def run_quantum_matrix_simulation(*a, **kw):
        return {
            "probability_over": 0.5,
            "probability_under": 0.5,
            "simulated_mean": 0.0,
            "simulated_std": 1.0,
            "simulations_run": 0,
        }

try:
    from engine.edge_detection import analyze_directional_forces, should_avoid_prop
except ImportError:
    def analyze_directional_forces(*a, **kw):
        return {
            "over_forces": [],
            "under_forces": [],
            "net_direction": "neutral",
            "net_strength": 0.0,
        }
    def should_avoid_prop(*a, **kw):
        return False

try:
    from engine.confidence import calculate_confidence_score
except ImportError:
    def calculate_confidence_score(*a, **kw):
        return {"confidence_score": 50.0, "tier": "Bronze"}

try:
    from engine.explainer import generate_pick_explanation
except ImportError:
    def generate_pick_explanation(*a, **kw):
        return {"summary": "", "details": [], "indicators": {}}

try:
    from engine.game_script import (
        BLOWOUT_DIFFERENTIAL_MILD,
        BLOWOUT_DIFFERENTIAL_HEAVY,
    )
except ImportError:
    BLOWOUT_DIFFERENTIAL_MILD = 12
    BLOWOUT_DIFFERENTIAL_HEAVY = 20

try:
    from engine.correlation import build_correlation_matrix, adjust_parlay_probability
except ImportError:
    def build_correlation_matrix(*a, **kw):
        return {}
    def adjust_parlay_probability(*a, **kw):
        return 0.0

try:
    from engine.entry_optimizer import (
        calculate_entry_expected_value,
        PLATFORM_FLEX_TABLES,
    )
except ImportError:
    def calculate_entry_expected_value(*a, **kw):
        return {
            "expected_value_dollars": 0.0,
            "return_on_investment": 0.0,
            "probability_per_hits": {},
            "payout_per_hits": {},
        }
    PLATFORM_FLEX_TABLES = {}

try:
    from engine.odds_engine import implied_probability_to_american_odds
except ImportError:
    def implied_probability_to_american_odds(prob):
        prob = max(0.001, min(0.999, float(prob)))
        if prob >= 0.5:
            return round(-(prob / (1.0 - prob)) * 100.0, 1)
        return round(((1.0 - prob) / prob) * 100.0, 1)

try:
    from engine.calibration import log_prediction
except ImportError:
    def log_prediction(*a, **kw):
        return None

try:
    from engine.math_helpers import _safe_float
except ImportError:
    def _safe_float(value, fallback=0.0):
        try:
            v = float(value)
            if math.isfinite(v):
                return v
            return fallback
        except (TypeError, ValueError):
            return fallback

try:
    from data.data_manager import load_players_data, load_teams_data
except ImportError:
    def load_players_data():
        return []
    def load_teams_data():
        return []

try:
    from data.advanced_metrics import (
        enrich_player_data,
        classify_player_archetype,
        normalize,
    )
except ImportError:
    def enrich_player_data(*a, **kw):
        return a[0] if a else {}
    def classify_player_archetype(*a, **kw):
        return "Unknown"
    def normalize(value, min_val, max_val, out_min=0.0, out_max=100.0):
        if max_val == min_val:
            return (out_min + out_max) / 2.0
        clamped = max(min_val, min(max_val, value))
        return out_min + (clamped - min_val) / (max_val - min_val) * (out_max - out_min)

# ═══════════════════════════════════════════════════════════════
# MODULE-LEVEL LOGGER
# ═══════════════════════════════════════════════════════════════
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
# MODULE-LEVEL ANTI-REPETITION STATE
# ═══════════════════════════════════════════════════════════════
_used_fragments: dict = {}      # keyed by pool name → set of used IDs
_used_ambient: dict = {}        # keyed by context → set of used indices
_used_commentary: dict = {}     # keyed by context_type → set of used indices

# ═══════════════════════════════════════════════════════════════
# A) FRAGMENT POOLS — For combinatorial rant builder
# ═══════════════════════════════════════════════════════════════

OPENER_POOL = [
    {"id": "opener_01", "text": "Now let me tell you something..."},
    {"id": "opener_02", "text": "Let me be VERY clear about something..."},
    {"id": "opener_03", "text": "You want to know what the REAL story is?"},
    {"id": "opener_04", "text": "I have been doing this for a LONG time..."},
    {"id": "opener_05", "text": "Quite frankly, I'm not sure people UNDERSTAND..."},
    {"id": "opener_06", "text": "This is something that NEEDS to be said..."},
    {"id": "opener_07", "text": "I was JUST talking to someone about this..."},
    {"id": "opener_08", "text": "LISTEN to me very carefully..."},
    {"id": "opener_09", "text": "I have TWO words for you..."},
    {"id": "opener_10", "text": "Before we go any further, let me say THIS..."},
    {"id": "opener_11", "text": "I don't say this LIGHTLY..."},
    {"id": "opener_12", "text": "If you know me — and I think you DO..."},
    {"id": "opener_13", "text": "I've been watching this game since I was TWELVE years old..."},
    {"id": "opener_14", "text": "People keep asking me about this, so let me ADDRESS it..."},
    {"id": "opener_15", "text": "I sat down. I looked at the numbers. And I said to myself..."},
]

PIVOT_POOL = [
    {"id": "pivot_01", "text": "HOWEVER..."},
    {"id": "pivot_02", "text": "But here's the thing..."},
    {"id": "pivot_03", "text": "Now with all DUE respect..."},
    {"id": "pivot_04", "text": "But let me tell you what CONCERNS me..."},
    {"id": "pivot_05", "text": "And THIS is where it gets interesting..."},
    {"id": "pivot_06", "text": "BUT — and this is a BIG but..."},
    {"id": "pivot_07", "text": "Now I don't want to hear the EXCUSES..."},
    {"id": "pivot_08", "text": "That being said..."},
    {"id": "pivot_09", "text": "BUT HERE'S WHAT NOBODY IS TALKING ABOUT..."},
    {"id": "pivot_10", "text": "Having said ALL of that..."},
]

CLOSER_POOL = [
    {"id": "closer_01", "text": "And I say that with GREAT conviction!"},
    {"id": "closer_02", "text": "Don't get it TWISTED!"},
    {"id": "closer_03", "text": "I'm not ASKING you — I'm TELLING you!"},
    {"id": "closer_04", "text": "And you can take THAT to the bank!"},
    {"id": "closer_05", "text": "MARK my words!"},
    {"id": "closer_06", "text": "This is Joseph M. Smith. I have SPOKEN!"},
    {"id": "closer_07", "text": "And if you disagree with me... you are WRONG!"},
    {"id": "closer_08", "text": "That's not an OPINION — that's a FACT!"},
    {"id": "closer_09", "text": "And I don't want to hear NOTHING about it!"},
    {"id": "closer_10", "text": "PERIOD. End of DISCUSSION!"},
]

CATCHPHRASE_POOL = [
    {"id": "catch_01", "text": "Stay off the WEED!"},
    {"id": "catch_02", "text": "This man is a DEAR, DEAR friend of mine..."},
    {"id": "catch_03", "text": "How DARE you!"},
    {"id": "catch_04", "text": "PREPOSTEROUS!"},
    {"id": "catch_05", "text": "BLASPHEMOUS!"},
    {"id": "catch_06", "text": "EGREGIOUS!"},
    {"id": "catch_07", "text": "This is COACHING MALPRACTICE!"},
    {"id": "catch_08", "text": "I, Joseph M. Smith, am TELLING you..."},
    {"id": "catch_09", "text": "I don't want to HEAR about it!"},
    {"id": "catch_10", "text": "ABOMINATION!"},
    {"id": "catch_11", "text": "TRAVESTY!"},
    {"id": "catch_12", "text": "With all DUE respect — and I mean that SINCERELY..."},
    {"id": "catch_13", "text": "He's a FIRST-BALLOT Hall of Famer in my book!"},
]

BODY_TEMPLATES = {
    "SMASH": [
        "{player} OVER {line} {stat}? That's not even a QUESTION! {edge}% edge — the numbers are SCREAMING at you!",
        "I'm looking at {player} and I see a man on a MISSION. {prob}% probability to clear {line} {stat}. SMASH IT!",
        "The Quantum Matrix Engine says {edge}% edge on {player} {stat}. And you know what? I AGREE. This is a LOCK!",
        "{player} is going to FEAST tonight. {line} {stat} is DISRESPECTFUL to this man's talent. I'm all OVER it!",
        "You want to know my BEST play? {player} OVER {line} {stat}. {edge}% edge. I'd bet my REPUTATION on this one!",
    ],
    "LEAN": [
        "I LIKE {player} tonight. {edge}% edge on {line} {stat}. Not my strongest conviction but the VALUE is there.",
        "{player} at {line} {stat}? The numbers say {prob}% and I tend to AGREE. Solid lean, not a pound-the-table.",
        "There's a quiet little edge on {player} — {edge}% on {line} {stat}. Smart money NOTICES these things.",
        "{player} should get there. {line} {stat} with a {edge}% edge. I'm not screaming but I'm definitely LEANING.",
        "The model likes {player} at {line} {stat} and so does Joseph M. Smith. {edge}% — that's a PLAYABLE number.",
    ],
    "FADE": [
        "I'm FADING {player} tonight. {line} {stat} is a TRAP and I can see it from a MILE away!",
        "{player} at {line} {stat}? The edge is only {edge}%. That's not enough for me to put my NAME on it.",
        "Be CAREFUL with {player}. The number says {line} {stat} but the CONTEXT says fade. Trust the CONTEXT!",
        "I see the line on {player} at {line} {stat} and I'm walking the OTHER way. {edge}% is not worth the risk.",
        "{player} {stat} at {line}? The books got this one RIGHT. I'm fading and I suggest you do the SAME.",
    ],
    "STAY_AWAY": [
        "Do NOT touch {player} tonight. I don't care WHAT the line says. {line} {stat} is a TRAP!",
        "{player} at {line} {stat}? {edge}% edge? That's NOTHING! Stay AWAY and thank me later!",
        "I wouldn't bet {player} {stat} tonight if you PAID me. The edge isn't there. The context is WRONG. STAY AWAY!",
        "This is a PUBLIC SERVICE ANNOUNCEMENT: {player} {line} {stat} is DANGEROUS. Keep your money in your POCKET!",
        "{player} {stat} at {line}? I have TWO words for you: STAY. AWAY. And I mean that with CONVICTION!",
    ],
    "OVERRIDE": [
        "The machine says one thing. Joseph M. Smith says ANOTHER. I'm OVERRIDING the engine on {player} {line} {stat}!",
        "I DISAGREE with the Quantum Matrix Engine on {player}. {line} {stat}? The machine is MISSING something and I see it!",
        "This is where HUMAN intelligence beats artificial intelligence. {player} at {line} {stat}? The engine is WRONG!",
        "OVERRIDE ALERT! The numbers say {edge}% but my eyes tell me DIFFERENT on {player} {stat}. Trust the EYE TEST!",
        "The computer doesn't watch the GAMES. I DO. And I'm telling you — {player} {line} {stat} needs an OVERRIDE!",
    ],
}

# ═══════════════════════════════════════════════════════════════
# B) AMBIENT COLOUR POOLS — scene-setting flavour text
# ═══════════════════════════════════════════════════════════════

AMBIENT_CONTEXT_POOL = {
    "high_stakes": [
        "The lights are BRIGHT and the pressure is ON!",
        "This is a PRIMETIME matchup and the whole world is watching!",
        "You can FEEL the energy through your screen tonight!",
        "This is what the NBA is ALL about — big games, big moments!",
        "The stakes could NOT be higher tonight!",
    ],
    "rivalry": [
        "This rivalry goes DEEP and the players know it!",
        "There's BAD BLOOD here and it's going to show on the court!",
        "You want INTENSITY? This matchup HAS it!",
        "When these two teams meet, you THROW the records out the window!",
        "This is a GRUDGE match and both sides know it!",
    ],
    "blowout_risk": [
        "Be CAREFUL — if this game gets out of hand, starters are sitting!",
        "Blowout risk is REAL tonight. Watch the spread!",
        "If one team takes control early, the benches could be in by the FOURTH!",
        "This mismatch SCREAMS early blowout — manage your expectations!",
        "Garbage time is a prop KILLER and I see it lurking tonight!",
    ],
    "back_to_back": [
        "Back-to-back games are NO joke — fatigue is a FACTOR!",
        "Second night of a back-to-back. Legs get HEAVY, shots fall SHORT!",
        "Rest matters in this league. And this team did NOT get it!",
        "The schedule-maker is the invisible DEFENDER tonight!",
        "Back-to-backs separate the MEN from the boys!",
    ],
    "neutral": [
        "Just another night in the NBA — but EVERY night matters!",
        "Let's break down the numbers and find the VALUE!",
        "The board is set. The pieces are moving. Let's ANALYZE!",
        "I've been studying this slate ALL day. Here's what I see...",
        "No drama tonight — just cold, hard ANALYSIS!",
    ],
}

# ═══════════════════════════════════════════════════════════════
# C) COMMENTARY COLOUR POOLS — per-stat flavour lines
# ═══════════════════════════════════════════════════════════════

STAT_COMMENTARY_POOL = {
    "points": [
        "Scoring is an ART and {player} is a MASTER of it!",
        "{player} can get a bucket from ANYWHERE on the floor!",
        "When {player} gets going, there is NO stopping this man!",
        "The scoring title isn't given — it's TAKEN. And {player} is taking it!",
        "Points are the CURRENCY of the NBA and {player} is RICH!",
    ],
    "rebounds": [
        "{player} attacks the glass like it OWES him money!",
        "Rebounding is about EFFORT and WANT — {player} has BOTH!",
        "The boards belong to {player} tonight — mark my WORDS!",
        "{player} is going to be a MONSTER on the glass!",
        "You can't teach rebounding INSTINCTS. {player} was BORN with them!",
    ],
    "assists": [
        "{player} sees passes that NOBODY else can see!",
        "Court vision like {player}? That's a GIFT from the basketball GODS!",
        "{player} makes everyone around him BETTER — that's what assists DO!",
        "The ball moves DIFFERENT when {player} has it in his hands!",
        "{player} is a MAESTRO with the basketball — conducting the OFFENSE!",
    ],
    "threes": [
        "{player} from DOWNTOWN — that's MONEY in the bank!",
        "The three-point line is {player}'s HOME ADDRESS!",
        "When {player} gets HOT from three, you better PRAY!",
        "Deep threes are the GREAT equalizer and {player} has the RANGE!",
        "{player} is LETHAL from beyond the arc!",
    ],
    "steals": [
        "{player} has HANDS like a PICKPOCKET out there!",
        "Active hands, quick feet — {player} is a NIGHTMARE for ball-handlers!",
        "{player} turns defense into OFFENSE with those steals!",
        "You can't be CARELESS with the ball when {player} is on the floor!",
        "{player} is a THIEF and he's PROUD of it!",
    ],
    "blocks": [
        "{player} is a WALL at the rim — good LUCK getting past him!",
        "Shot-blocking is about TIMING and {player} has a CLOCK in his head!",
        "{player} is going to send some shots into the FIFTH ROW tonight!",
        "The paint belongs to {player} — enter at your OWN risk!",
        "{player} is a RIM PROTECTOR of the highest ORDER!",
    ],
    "turnovers": [
        "Turnovers are the SILENT killer of NBA props!",
        "{player}'s handle can get LOOSE under pressure — watch for it!",
        "Ball security is NO joke and {player} needs to be CAREFUL!",
        "Turnovers are like TAXES — they come for EVERYONE eventually!",
        "If {player} gets sloppy, the turnovers WILL pile up!",
    ],
    "fantasy": [
        "{player} stuffs the stat sheet like NOBODY else!",
        "Fantasy points reward VERSATILITY and {player} has it in SPADES!",
        "{player} contributes in EVERY category — that's ELITE!",
        "When you look at fantasy production, {player} is a ONE-MAN army!",
        "{player} is a SWISS ARMY KNIFE of basketball production!",
    ],
}

# ═══════════════════════════════════════════════════════════════
# D) VERDICT THRESHOLDS & CONFIGURATION
# ═══════════════════════════════════════════════════════════════

VERDICT_THRESHOLDS = {
    "SMASH": {"min_edge": 8.0, "min_confidence": 70.0},
    "LEAN": {"min_edge": 4.0, "min_confidence": 55.0},
    "FADE": {"max_edge": 3.0, "max_confidence": 50.0},
    "STAY_AWAY": {"max_edge": 1.0, "max_confidence": 35.0},
    "OVERRIDE": {"min_edge": 0.0, "min_confidence": 0.0},
}

JOSEPH_CONFIG = {
    "max_picks_per_slate": 10,
    "min_edge_threshold": 2.0,
    "parlay_max_legs": 6,
    "parlay_min_legs": 2,
    "default_entry_fee": 10.0,
    "commentary_style": "emphatic",
    "enable_overrides": True,
    "enable_ambient": True,
    "rant_min_fragments": 3,
    "rant_max_fragments": 5,
}


# ═══════════════════════════════════════════════════════════════
# FUNCTION STUBS  (Phase 1B will fill bodies)
# ═══════════════════════════════════════════════════════════════

def _pick_fragment(pool, pool_name):
    """Pick a random fragment from *pool* without repeating until exhausted.

    Uses module-level ``_used_fragments`` to track which IDs have been served.
    When every entry in a pool has been used, the tracking set resets.

    Parameters
    ----------
    pool : list[dict]
        One of the fragment pools (OPENER_POOL, PIVOT_POOL, etc.).
    pool_name : str
        Key used in ``_used_fragments`` for tracking.

    Returns
    -------
    str
        The ``"text"`` value of the chosen fragment.
    """
    if not pool:
        return ""
    used = _used_fragments.setdefault(pool_name, set())
    available = [f for f in pool if f["id"] not in used]
    if not available:
        used.clear()
        available = list(pool)
    choice = random.choice(available)
    used.add(choice["id"])
    return choice["text"]


def _pick_ambient(context):
    """Pick ambient colour text for the given context without repeating.

    Parameters
    ----------
    context : str
        Key into ``AMBIENT_CONTEXT_POOL`` (e.g. ``"rivalry"``, ``"blowout_risk"``).

    Returns
    -------
    str
        A single ambient colour sentence, or ``""`` if context is unknown.
    """
    lines = AMBIENT_CONTEXT_POOL.get(context, [])
    if not lines:
        return ""
    used = _used_ambient.setdefault(context, set())
    available = [i for i in range(len(lines)) if i not in used]
    if not available:
        used.clear()
        available = list(range(len(lines)))
    idx = random.choice(available)
    used.add(idx)
    return lines[idx]


def _pick_commentary(stat_type):
    """Pick stat-specific commentary colour without repeating.

    Parameters
    ----------
    stat_type : str
        Stat key into ``STAT_COMMENTARY_POOL`` (e.g. ``"points"``).

    Returns
    -------
    str
        A single commentary sentence, or ``""`` if stat is unknown.
    """
    lines = STAT_COMMENTARY_POOL.get(stat_type, [])
    if not lines:
        return ""
    used = _used_commentary.setdefault(stat_type, set())
    available = [i for i in range(len(lines)) if i not in used]
    if not available:
        used.clear()
        available = list(range(len(lines)))
    idx = random.choice(available)
    used.add(idx)
    return lines[idx]


def determine_verdict(edge, confidence_score, avoid=False):
    """Map edge % and confidence score to a verdict string.

    Parameters
    ----------
    edge : float
        Edge percentage from the Quantum Matrix Engine.
    confidence_score : float
        Confidence score (0-100).
    avoid : bool
        If ``True``, force ``"STAY_AWAY"`` regardless of numbers.

    Returns
    -------
    str
        One of ``"SMASH"``, ``"LEAN"``, ``"FADE"``, ``"STAY_AWAY"``, ``"OVERRIDE"``.
    """
    return "LEAN"


def build_rant(verdict, player="", stat="", line="", edge="", prob=""):
    """Assemble a full Joseph M. Smith rant from fragment pools.

    Combines an opener, a body template (chosen by *verdict*), a pivot,
    a catchphrase, and a closer into a multi-sentence tirade.

    Parameters
    ----------
    verdict : str
        Verdict key (``"SMASH"``, ``"LEAN"``, etc.).
    player : str
        Player display name.
    stat : str
        Stat type label (e.g. ``"points"``).
    line : str
        Prop line value as a string (e.g. ``"24.5"``).
    edge : str
        Edge percentage as a string (e.g. ``"8.2"``).
    prob : str
        Probability percentage as a string (e.g. ``"62.1"``).

    Returns
    -------
    str
        The assembled rant string.
    """
    return ""


def joseph_analyze_pick(player_data, prop_line, stat_type, game_context,
                        platform="PrizePicks", recent_games=None):
    """Run full Joseph M. Smith analysis on a single player prop.

    Orchestrates simulation, edge detection, confidence scoring,
    grading, strategy analysis, and rant generation.

    Parameters
    ----------
    player_data : dict
        Player season stats dictionary.
    prop_line : float
        The betting line (e.g. 24.5).
    stat_type : str
        Stat type string (e.g. ``"points"``).
    game_context : dict
        Game info (opponent, is_home, rest_days, etc.).
    platform : str
        Platform name (default ``"PrizePicks"``).
    recent_games : list or None
        Recent game logs for the player.

    Returns
    -------
    dict
        Analysis result with keys: ``verdict``, ``edge``, ``confidence``,
        ``rant``, ``explanation``, ``grade``, ``strategy``.
    """
    return {
        "verdict": "LEAN",
        "edge": 0.0,
        "confidence": 50.0,
        "rant": "",
        "explanation": {},
        "grade": {},
        "strategy": {},
    }


def joseph_rank_picks(picks, game_contexts=None):
    """Rank a list of analysed picks by Joseph's priority.

    Parameters
    ----------
    picks : list[dict]
        List of pick analysis dicts (output of ``joseph_analyze_pick``).
    game_contexts : dict or None
        Map of game IDs to game context dicts.

    Returns
    -------
    list[dict]
        The same picks sorted from best to worst with a ``"rank"`` key added.
    """
    return []


def joseph_evaluate_parlay(picks, platform="PrizePicks", entry_fee=10.0):
    """Evaluate a parlay / flex-play slate using correlation adjustments.

    Parameters
    ----------
    picks : list[dict]
        Analysed picks to combine into a parlay.
    platform : str
        Platform for payout table lookup.
    entry_fee : float
        Entry fee in dollars.

    Returns
    -------
    dict
        Parlay evaluation with keys: ``expected_value``, ``correlation_matrix``,
        ``adjusted_probability``, ``rant``.
    """
    return {
        "expected_value": 0.0,
        "correlation_matrix": {},
        "adjusted_probability": 0.0,
        "rant": "",
    }


def joseph_generate_full_slate_analysis(players, props, game_contexts,
                                        platform="PrizePicks"):
    """Produce a complete Joseph M. Smith slate analysis.

    Iterates over every player/prop pair, runs ``joseph_analyze_pick``,
    ranks the results, and builds top-parlay suggestions.

    Parameters
    ----------
    players : list[dict]
        Player data dicts.
    props : list[dict]
        Prop dicts with ``stat_type``, ``line``, ``player_name``.
    game_contexts : dict
        Map of game identifiers to game context dicts.
    platform : str
        Platform name for payout table lookup.

    Returns
    -------
    dict
        Full slate result with keys: ``picks``, ``parlays``,
        ``top_plays``, ``summary_rant``.
    """
    return {
        "picks": [],
        "parlays": [],
        "top_plays": [],
        "summary_rant": "",
    }


def joseph_commentary_for_stat(player_name, stat_type, context="neutral"):
    """Generate a short stat-specific colour commentary line.

    Parameters
    ----------
    player_name : str
        Player display name.
    stat_type : str
        Stat key (``"points"``, ``"rebounds"``, etc.).
    context : str
        Ambient context key for scene-setting.

    Returns
    -------
    str
        A colourful one-liner about the player and stat.
    """
    return ""


def joseph_blowout_warning(spread, game_total):
    """Produce a Joseph-style blowout-risk warning if applicable.

    Parameters
    ----------
    spread : float
        Vegas spread for the game.
    game_total : float
        Vegas over/under game total.

    Returns
    -------
    str
        Warning string, or ``""`` if no blowout risk detected.
    """
    return ""


def reset_fragment_state():
    """Clear all anti-repetition tracking dicts.

    Useful between slates or test runs to get a fresh fragment cycle.
    """
    _used_fragments.clear()
    _used_ambient.clear()
    _used_commentary.clear()
