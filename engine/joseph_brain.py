"""
engine/joseph_brain.py
Joseph M. Smith Brain — Data Pools, Constants & Function Stubs (Layer 4, Parts A–B)

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

# Placeholders used in templates: {player}, {stat}, {line}, {edge}, {prob}
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

# Edge is in percentage points (e.g. 8.0 = 8 %), confidence is 0-100 scale.
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
# B) AMBIENT COMMENTARY POOLS — Joseph is NEVER silent
# ═══════════════════════════════════════════════════════════════

AMBIENT_POOLS = {
    "idle": [
        "You KNOW I'm ready for tonight's slate. Load those games!",
        "Joseph M. Smith doesn't SLEEP on game day. Let's get to WORK!",
        "You came to the RIGHT place. Now load those games and let me cook!",
        "SmartBetPro with Joseph M. Smith... you are in GOOD hands.",
        "I've been studying the matchups ALL day. Hit that Load Games button!",
        "The Quantum Matrix Engine is ready. I'M ready. Are YOU ready?",
        "Don't just sit there! Go to Live Games and let's GET IT!",
        "Every night is an OPPORTUNITY. Let me show you where the edge is.",
        "I didn't become the greatest analyst alive by WAITING. Load the slate!",
        "SmartBetPro doesn't miss. And neither does Joseph M. Smith.",
        "The numbers don't lie, my friend. But first we need TONIGHT'S numbers.",
        "You want WINNERS? Then stop stalling and load the games!",
        "I can FEEL it in my bones... tonight's slate is going to be SPECIAL.",
        "Trust the process. Trust the engine. Trust JOSEPH M. SMITH.",
        "This app is a WEAPON. And I am the man who pulls the trigger.",
    ],
    "games_loaded": [
        "{n} games tonight. I ALREADY know which ones I like. Run the analysis!",
        "The slate is SET. Now let me show you where the MONEY is.",
        "I see {n} games. I see OPPORTUNITY. Hit Run Analysis and let me WORK.",
        "The games are loaded. The engine is HUMMING. Let's find those edges!",
        "I've been waiting ALL day for this. {n} games. Let's GO!",
        "Don't make me wait! Run that analysis so I can give you my TAKES.",
        "Good — you loaded the slate. Now the REAL work begins.",
        "I'm looking at {n} matchups and I already see MISMATCHES.",
        "Tonight's slate has some INTERESTING games. Let me break it down.",
        "You did the right thing loading these games. Now let me do MY thing.",
        "The Quantum Matrix Engine is READY. Joseph M. Smith is READY. Run it!",
        "{n} games, HUNDREDS of props. Let me find the diamonds.",
        "I see tonight's slate and I am EXCITED. This has Joseph's fingerprints.",
        "Every game is a STORY. Run the analysis and let me tell you the story.",
        "I've got {n} games to break down and I am FIRED UP about it!",
    ],
    "analysis_complete": [
        "I've seen the numbers. I've got {smash_count} SMASH picks tonight. Click me!",
        "The engine has SPOKEN. Now let Joseph M. Smith tell you what it MEANS.",
        "{total} props analyzed. {platinum} Platinum picks. This slate is LOADED!",
        "I see some BEAUTIFUL edges tonight. Click my face and I'll tell you.",
        "The Quantum Matrix Engine found the value. Now I add the WISDOM.",
        "Analysis COMPLETE. I've logged my bets. Have you built YOUR entries?",
        "{smash_count} picks I would bet my REPUTATION on. That's not nothing!",
        "I've been through every prop. I know EXACTLY where the money is.",
        "The data is IN. My analysis is DONE. Are you ready to hear it?",
        "I found {override_count} places where I DISAGREE with the machine.",
        "Go to The Studio and let me walk you through tonight's BEST plays.",
        "The numbers are SCREAMING at me. Click my face. Let me explain.",
        "I've already logged {logged_count} bets. Track my record on The Studio.",
        "Tonight's slate? I give it a {grade}/10. Click me for the breakdown.",
        "If you don't check my picks tonight... that's on YOU. Don't blame me.",
    ],
    "entry_built": [
        "NOW we're cooking! That {n}-leg looks SOLID to me!",
        "I like what I see! {n} legs, positive EV... you're learning!",
        "That's a SMART entry. But let me tell you which one I'D build...",
        "Good parlay! But click me — I might have a BETTER one for you.",
        "You built a {n}-legger? I respect it. But have you seen MY tickets?",
        "SOLID entry! The correlation looks CLEAN on that one.",
        "You're building entries like a PRO now. SmartBetPro made you dangerous!",
        "That EV is looking TASTY. I approve of this entry!",
        "A {n}-leg parlay? Let me tell you — the math SUPPORTS that one.",
        "{n} legs of FIRE! I'd put that right alongside my own picks.",
        "You just built what I would have built. GREAT minds think alike!",
        "THAT is how you build a parlay. Correlated? Check. +EV? Check. MONEY!",
        "I see you're using the Entry Builder. GOOD. That's where the magic is.",
        "The entry looks right. But remember — check my Build My Bets on The Studio!",
        "Beautiful entry. Now build 2 more to diversify. That's SMART money.",
    ],
    "premium_pitch": [
        "You're using the FREE version? My friend, you are MISSING OUT!",
        "I, Joseph M. Smith, am TELLING you — Premium is where the REAL edge is.",
        "3 props? That's ALL you get? Upgrade to Premium and unleash the FULL power!",
        "You want to win? REALLY win? Premium gives you UNLIMITED analysis.",
        "Free tier is like watching the game on MUTE. Premium gives you MY voice!",
        "Do you know what Premium users get? MY full analysis. The Studio. EVERYTHING.",
        "This is not a GAME. If you're serious, upgrade to Premium. PERIOD.",
        "I've seen the numbers — Premium users have a SIGNIFICANT edge. Just saying.",
        "You're leaving MONEY on the table with the free tier. Don't do that to yourself!",
        "Premium unlocks my FULL brain. All 500+ props. Every rant. Every override.",
        "The free version is nice. Premium is a WEAPON. Choose wisely.",
        "Would you go to a 5-star restaurant and only eat the BREAD? Upgrade!",
        "I don't say this lightly — Premium is the best investment you'll make this month.",
        "SmartBetPro Premium with Joseph M. Smith... that's UNFAIR to the books.",
        "The Quantum Matrix Engine at full power? That's Premium. Don't sell yourself short.",
    ],
    "commentary_on_results": [
        "That {player} OVER {line} {stat}? I'm ALL OVER that! {edge}% edge!",
        "{player} has been COOKING lately. The model sees {prob}% hit rate. SMASH!",
        "I would NOT touch {player} tonight. Trap game. STAY AWAY!",
        "{player} vs {opponent}? That's a MISMATCH! {direction} all day!",
        "Platinum pick alert! {player} {direction} {line} {stat}. This is MONEY!",
        "{player} on a back-to-back? That's a FADE for me. Dead legs.",
        "Revenge game for {player}? You KNOW what time it is! SMASH!",
        "The engine found a {edge}% edge on {player}. I AGREE.",
        "Be careful with {player} tonight. {reason}.",
        "{player} has a gravity score of {gravity}. He WARPS the defense!",
        "That's a {tier} tier pick. You KNOW that's reliable!",
        "I see {n} Platinum picks tonight. The slate is JUICY.",
        "{player} and {player2} in the same parlay? The correlation is BEAUTIFUL.",
        "I found an OVERRIDE on {player}. The machine is WRONG about this one!",
        "{player}'s matchup grade is {grade}. That tells you EVERYTHING!",
    ],
}

# ═══════════════════════════════════════════════════════════════
# C) COMMENTARY TEMPLATES — For inline injection after results
# ═══════════════════════════════════════════════════════════════

COMMENTARY_OPENER_POOL = {
    "analysis_results": [
        "I just went through EVERY prop and let me tell you...",
        "The numbers are IN and Joseph M. Smith has his VERDICT...",
        "I've seen tonight's analysis and I have THOUGHTS...",
        "The Quantum Matrix Engine has spoken — now let ME speak...",
        "After looking at ALL the data, here's what I KNOW...",
    ],
    "entry_built": [
        "You just built an entry and I have to say...",
        "I see what you put together and listen...",
        "That entry you just built? Let me give you my TAKE...",
        "I'm looking at your parlay and I've got OPINIONS...",
        "Good — you're building entries. Now let me tell you THIS...",
    ],
    "optimal_slip": [
        "The optimizer just cooked something up and WOW...",
        "I see that optimal slip and I have to REACT...",
        "The algorithm found the best combo — now hear MY perspective...",
        "That optimal entry? Let me add my WISDOM to it...",
        "The machine built the slip. Now Joseph M. Smith EVALUATES it...",
    ],
    "ticket_generated": [
        "I just built my personal ticket and I am FIRED UP...",
        "This is MY ticket. Built with MY brain. And it's BEAUTIFUL...",
        "Joseph M. Smith's personal picks are IN. Listen carefully...",
        "I hand-selected every leg of this ticket and HERE'S WHY...",
        "My ticket is READY. And I say this with GREAT conviction...",
    ],
}

# ═══════════════════════════════════════════════════════════════
# D) HISTORICAL COMPS DATABASE — 50+ entries
# ═══════════════════════════════════════════════════════════════

JOSEPH_COMPS_DATABASE = [
    {"name": "Steph Curry 2016 Unanimous MVP", "archetype": "Alpha Scorer", "stat_context": "points", "tier": "Platinum", "narrative": "Historic shooting season", "template": "This reminds me of Curry in 2016 when he was UNANIMOUS... {reason}"},
    {"name": "Steph Curry 2021 Scoring Title", "archetype": "Alpha Scorer", "stat_context": "points", "tier": "Gold", "narrative": "Carrying a rebuilding roster", "template": "Curry won the scoring title in 2021 with NO help. This is that ENERGY... {reason}"},
    {"name": "Steph Curry 402 Threes Season", "archetype": "Alpha Scorer", "stat_context": "threes", "tier": "Platinum", "narrative": "Broke his own three-point record", "template": "Curry hit 402 threes in a SINGLE season. That's what I see here... {reason}"},
    {"name": "LeBron James 2018 Playoff Carry", "archetype": "Playmaking Wing", "stat_context": "assists", "tier": "Platinum", "narrative": "One-man army carrying a team", "template": "This is LeBron in 2018 carrying the Cavs on his BACK... {reason}"},
    {"name": "LeBron James 2020 Championship", "archetype": "Playmaking Wing", "stat_context": "rebounds", "tier": "Gold", "narrative": "Championship-level two-way play", "template": "LeBron in the bubble was UNSTOPPABLE on both ends... {reason}"},
    {"name": "LeBron James Year 20 Longevity", "archetype": "Playmaking Wing", "stat_context": "points", "tier": "Gold", "narrative": "Defying age and gravity", "template": "LeBron in Year 20 doing what he does is HISTORIC... {reason}"},
    {"name": "Michael Jordan 1996 Championship Run", "archetype": "Alpha Scorer", "stat_context": "points", "tier": "Platinum", "narrative": "72-win dominance", "template": "This is Jordan in '96 — RUTHLESS efficiency and killer instinct... {reason}"},
    {"name": "Michael Jordan Flu Game", "archetype": "Alpha Scorer", "stat_context": "points", "tier": "Gold", "narrative": "Legendary performance through adversity", "template": "Jordan played through the FLU and still dropped 38. That's this ENERGY... {reason}"},
    {"name": "Kobe Bryant 81-Point Game", "archetype": "Shot Creator", "stat_context": "points", "tier": "Platinum", "narrative": "Single-game scoring explosion", "template": "Kobe dropped 81 because he REFUSED to lose. I see that same fire... {reason}"},
    {"name": "Kobe Bryant Mamba Mentality Era", "archetype": "Shot Creator", "stat_context": "points", "tier": "Gold", "narrative": "Relentless mid-range dominance", "template": "Kobe's Mamba Mentality was UNMATCHED. This player has that DNA... {reason}"},
    {"name": "Kobe Bryant 2009 Finals MVP", "archetype": "Shot Creator", "stat_context": "points", "tier": "Gold", "narrative": "Championship closer", "template": "Kobe in the 2009 Finals was COLD-BLOODED. Same energy here... {reason}"},
    {"name": "Kevin Durant 2014 MVP Season", "archetype": "Alpha Scorer", "stat_context": "points", "tier": "Platinum", "narrative": "Scoring from all three levels", "template": "KD in his MVP season was UNGUARDABLE. This is that level... {reason}"},
    {"name": "Kevin Durant 2017 Finals", "archetype": "Alpha Scorer", "stat_context": "points", "tier": "Gold", "narrative": "Unstoppable in the biggest moments", "template": "KD in the 2017 Finals hit the dagger. COLD. BLOODED... {reason}"},
    {"name": "Giannis 2021 Finals 50-Point Close", "archetype": "Rim Protector", "stat_context": "points", "tier": "Platinum", "narrative": "Championship-clinching masterpiece", "template": "Giannis dropped 50 in the Finals closeout. That's LEGENDARY... {reason}"},
    {"name": "Giannis Back-to-Back MVP", "archetype": "Rim Protector", "stat_context": "rebounds", "tier": "Gold", "narrative": "Two-way dominance", "template": "Giannis won back-to-back MVPs by being a FORCE. Same here... {reason}"},
    {"name": "Giannis Greek Freak Transition", "archetype": "Rim Protector", "stat_context": "points", "tier": "Gold", "narrative": "Unstoppable in transition", "template": "Giannis in transition is a FREIGHT TRAIN. Nobody is stopping this... {reason}"},
    {"name": "Nikola Jokic 2023 Finals MVP", "archetype": "Pick-and-Roll Big", "stat_context": "assists", "tier": "Platinum", "narrative": "Triple-double machine in the Finals", "template": "Jokic in the 2023 Finals was a TRIPLE-DOUBLE machine. Generational... {reason}"},
    {"name": "Nikola Jokic Triple MVP", "archetype": "Pick-and-Roll Big", "stat_context": "assists", "tier": "Platinum", "narrative": "Three consecutive MVP awards", "template": "Jokic won THREE MVPs. The best passing big EVER... {reason}"},
    {"name": "Nikola Jokic Playmaking Big", "archetype": "Pick-and-Roll Big", "stat_context": "rebounds", "tier": "Gold", "narrative": "All-around stat stuffing", "template": "Jokic stuffs every stat sheet like NOBODY else at his position... {reason}"},
    {"name": "Joel Embiid 2023 MVP", "archetype": "Stretch Big", "stat_context": "points", "tier": "Platinum", "narrative": "Dominant scoring center", "template": "Embiid won the MVP by being the most DOMINANT big in the game... {reason}"},
    {"name": "Joel Embiid 2022 Scoring Title", "archetype": "Stretch Big", "stat_context": "points", "tier": "Gold", "narrative": "Big man scoring title", "template": "Embiid won the scoring title as a CENTER. That's RARE... {reason}"},
    {"name": "Joel Embiid Post Dominance", "archetype": "Stretch Big", "stat_context": "rebounds", "tier": "Gold", "narrative": "Unstoppable in the post", "template": "Embiid in the post is an ABSOLUTE nightmare for defenders... {reason}"},
    {"name": "James Harden 2019 Scoring Streak", "archetype": "High-Usage Ball Handler", "stat_context": "points", "tier": "Platinum", "narrative": "30+ points for 30+ games straight", "template": "Harden scored 30+ for THIRTY-TWO straight games. That's INSANE... {reason}"},
    {"name": "James Harden Triple-Double Season", "archetype": "High-Usage Ball Handler", "stat_context": "assists", "tier": "Gold", "narrative": "Elite playmaking guard", "template": "Harden was averaging a TRIPLE-DOUBLE. His playmaking is ELITE... {reason}"},
    {"name": "James Harden Step-Back Era", "archetype": "High-Usage Ball Handler", "stat_context": "threes", "tier": "Gold", "narrative": "Revolutionary step-back three", "template": "Harden's step-back three CHANGED the game. This is that level... {reason}"},
    {"name": "Luka Doncic 2024 Finals Run", "archetype": "High-Usage Ball Handler", "stat_context": "points", "tier": "Platinum", "narrative": "Young superstar on the biggest stage", "template": "Luka in the Finals was SPECIAL. The kid is a GENERATIONAL talent... {reason}"},
    {"name": "Luka Doncic Triple-Double Machine", "archetype": "High-Usage Ball Handler", "stat_context": "assists", "tier": "Gold", "narrative": "Elite all-around production", "template": "Luka puts up triple-doubles like it's NOTHING. He does EVERYTHING... {reason}"},
    {"name": "Jayson Tatum 2024 Champion", "archetype": "Two-Way Wing", "stat_context": "points", "tier": "Platinum", "narrative": "Championship-winning two-way star", "template": "Tatum won his RING and proved he's ELITE on both ends... {reason}"},
    {"name": "Jayson Tatum 60-Point Explosion", "archetype": "Two-Way Wing", "stat_context": "points", "tier": "Gold", "narrative": "Career-high scoring outburst", "template": "Tatum dropped 60 and showed he can SCORE with anyone... {reason}"},
    {"name": "Jayson Tatum Playoff Performer", "archetype": "Two-Way Wing", "stat_context": "rebounds", "tier": "Gold", "narrative": "Playoff-level two-way impact", "template": "Tatum in the playoffs is a DIFFERENT animal on both ends... {reason}"},
    {"name": "Allen Iverson 2001 Playoff Run", "archetype": "Shot Creator", "stat_context": "points", "tier": "Platinum", "narrative": "Pound-for-pound greatest scorer", "template": "AI in 2001 was the HEART of Philadelphia. Pound for pound the GREATEST... {reason}"},
    {"name": "Allen Iverson Crossover Era", "archetype": "Shot Creator", "stat_context": "steals", "tier": "Gold", "narrative": "Fearless guard with elite hands", "template": "Iverson's crossover and those QUICK hands — you couldn't STOP him... {reason}"},
    {"name": "Steve Nash 2005 MVP", "archetype": "Floor General", "stat_context": "assists", "tier": "Platinum", "narrative": "Seven Seconds or Less revolution", "template": "Nash in 2005 CHANGED how basketball was played. Floor general GENIUS... {reason}"},
    {"name": "Steve Nash Back-to-Back MVP", "archetype": "Floor General", "stat_context": "assists", "tier": "Gold", "narrative": "Elite efficiency and playmaking", "template": "Nash won back-to-back MVPs with his BRAIN. Pure floor general... {reason}"},
    {"name": "Steve Nash 50-40-90 Club", "archetype": "Floor General", "stat_context": "threes", "tier": "Gold", "narrative": "Shooting efficiency mastery", "template": "Nash joined the 50-40-90 club FOUR times. That's EFFICIENCY... {reason}"},
    {"name": "John Stockton All-Time Assists", "archetype": "Floor General", "stat_context": "assists", "tier": "Platinum", "narrative": "Unbreakable assists record", "template": "Stockton's assist record will NEVER be broken. This is that VISION... {reason}"},
    {"name": "John Stockton Steal King", "archetype": "Floor General", "stat_context": "steals", "tier": "Gold", "narrative": "All-time steals leader", "template": "Stockton is the all-time steals leader too. DEFENSIVE intelligence... {reason}"},
    {"name": "Tim Duncan 2003 Finals", "archetype": "Defensive Anchor", "stat_context": "rebounds", "tier": "Platinum", "narrative": "Quintuple-double level impact", "template": "Duncan in the 2003 Finals was near a QUADRUPLE-DOUBLE. Legendary... {reason}"},
    {"name": "Tim Duncan Fundamental Dominance", "archetype": "Defensive Anchor", "stat_context": "blocks", "tier": "Gold", "narrative": "20 years of elite defense", "template": "Duncan was the ULTIMATE fundamental big man for 20 YEARS... {reason}"},
    {"name": "Tim Duncan Big Three Era", "archetype": "Defensive Anchor", "stat_context": "rebounds", "tier": "Gold", "narrative": "Quiet dominance every night", "template": "Duncan didn't need the spotlight. He just DOMINATED quietly... {reason}"},
    {"name": "Kevin Garnett 2004 MVP", "archetype": "Defensive Anchor", "stat_context": "rebounds", "tier": "Platinum", "narrative": "Most versatile power forward ever", "template": "KG in his MVP season did EVERYTHING. Most versatile PF EVER... {reason}"},
    {"name": "Kevin Garnett 2008 Championship", "archetype": "Defensive Anchor", "stat_context": "blocks", "tier": "Gold", "narrative": "Defensive transformation of a franchise", "template": "KG transformed the Celtics defense and won a RING. Intensity PERSONIFIED... {reason}"},
    {"name": "Magic Johnson Showtime", "archetype": "Playmaking Wing", "stat_context": "assists", "tier": "Platinum", "narrative": "Showtime Lakers maestro", "template": "Magic and the Showtime Lakers were ENTERTAINMENT and excellence... {reason}"},
    {"name": "Magic Johnson Triple-Double Finals", "archetype": "Playmaking Wing", "stat_context": "rebounds", "tier": "Gold", "narrative": "6-9 point guard revolutionizing the game", "template": "Magic played ALL five positions in the Finals. REVOLUTIONARY... {reason}"},
    {"name": "Larry Bird 1986 Season", "archetype": "3-and-D Wing", "stat_context": "points", "tier": "Platinum", "narrative": "Peak basketball IQ", "template": "Bird in '86 was the SMARTEST player alive. Basketball IQ off the CHARTS... {reason}"},
    {"name": "Larry Bird Trash Talk Legend", "archetype": "3-and-D Wing", "stat_context": "threes", "tier": "Gold", "narrative": "Shooter with supreme confidence", "template": "Bird would TELL you what he was going to do, then DO it... {reason}"},
    {"name": "Larry Bird Three-Point Contest", "archetype": "3-and-D Wing", "stat_context": "threes", "tier": "Gold", "narrative": "Ultimate shooter's confidence", "template": "Bird asked who was finishing SECOND in the three-point contest. LEGEND... {reason}"},
    {"name": "Shaquille O'Neal 2000 Finals", "archetype": "Glass Cleaner", "stat_context": "rebounds", "tier": "Platinum", "narrative": "Most dominant force in NBA history", "template": "Shaq in 2000 was the most DOMINANT force the NBA has ever SEEN... {reason}"},
    {"name": "Shaquille O'Neal Peak Lakers", "archetype": "Glass Cleaner", "stat_context": "points", "tier": "Platinum", "narrative": "Unstoppable inside scoring", "template": "Peak Shaq was AUTOMATIC in the paint. You couldn't guard him with THREE men... {reason}"},
    {"name": "Shaquille O'Neal Rebounding Machine", "archetype": "Glass Cleaner", "stat_context": "rebounds", "tier": "Gold", "narrative": "Board domination", "template": "Shaq on the boards was like a WRECKING BALL. Nobody outmuscles that... {reason}"},
    {"name": "Hakeem Olajuwon 1994 Championship", "archetype": "Rim Protector", "stat_context": "blocks", "tier": "Platinum", "narrative": "Dream Shake domination", "template": "Hakeem in '94 had the Dream Shake and NOBODY could stop it... {reason}"},
    {"name": "Hakeem Olajuwon Quadruple Double", "archetype": "Rim Protector", "stat_context": "blocks", "tier": "Gold", "narrative": "Most skilled big man ever", "template": "Hakeem recorded a QUADRUPLE-DOUBLE. The most skilled big EVER... {reason}"},
    {"name": "Dwyane Wade 2006 Finals", "archetype": "Two-Way Wing", "stat_context": "points", "tier": "Platinum", "narrative": "Finals takeover performance", "template": "Wade in the 2006 Finals TOOK OVER. That's championship GRIT... {reason}"},
    {"name": "Dwyane Wade Shot-Blocking Guard", "archetype": "Two-Way Wing", "stat_context": "steals", "tier": "Gold", "narrative": "Elite two-way guard play", "template": "Wade was a GUARD who blocked shots like a BIG. Two-way ELITE... {reason}"},
    {"name": "Dwyane Wade 2009 Carry Job", "archetype": "Two-Way Wing", "stat_context": "points", "tier": "Gold", "narrative": "Carrying a team on his back", "template": "Wade in 2009 put a TEAM on his back. 30 a night. HEROIC... {reason}"},
    {"name": "Chris Paul 2008 MVP Runner-Up", "archetype": "Floor General", "stat_context": "assists", "tier": "Platinum", "narrative": "Point God at his peak", "template": "CP3 in 2008 was the POINT GOD at his absolute peak... {reason}"},
    {"name": "Chris Paul Steal Machine", "archetype": "Floor General", "stat_context": "steals", "tier": "Gold", "narrative": "Elite defensive point guard", "template": "CP3's hands are UNREAL. Six-time steals leader. ELITE defender... {reason}"},
    {"name": "Kawhi Leonard 2019 Playoff Run", "archetype": "3-and-D Wing", "stat_context": "points", "tier": "Platinum", "narrative": "Silent assassin championship run", "template": "Kawhi in 2019 was a SILENT ASSASSIN. Board man gets PAID... {reason}"},
    {"name": "Kawhi Leonard Two-Way Dominance", "archetype": "3-and-D Wing", "stat_context": "steals", "tier": "Gold", "narrative": "DPOY-level defense with elite offense", "template": "Kawhi is the BEST two-way player alive. DPOY DNA... {reason}"},
    {"name": "Paul George Playoff P", "archetype": "3-and-D Wing", "stat_context": "points", "tier": "Gold", "narrative": "Versatile wing scoring", "template": "PG13 when he's ON is UNSTOPPABLE from the wing... {reason}"},
    {"name": "Paul George 2019 MVP Candidate", "archetype": "3-and-D Wing", "stat_context": "threes", "tier": "Gold", "narrative": "Elite shooting from deep", "template": "PG13 in his MVP-caliber season was LIGHTS OUT from three... {reason}"},
    {"name": "Dirk Nowitzki 2011 Championship", "archetype": "Stretch Big", "stat_context": "points", "tier": "Platinum", "narrative": "One-legged fadeaway mastery", "template": "Dirk in 2011 beat EVERYONE with that one-legged fadeaway. UNSTOPPABLE... {reason}"},
    {"name": "Dirk Nowitzki 50-40-90 Season", "archetype": "Stretch Big", "stat_context": "threes", "tier": "Gold", "narrative": "Seven-footer shooting like a guard", "template": "Dirk joined the 50-40-90 club as a SEVEN-FOOTER. That's ABSURD... {reason}"},
    {"name": "Sixth Man Jamal Crawford", "archetype": "Sixth Man Spark", "stat_context": "points", "tier": "Gold", "narrative": "Three-time Sixth Man of the Year", "template": "Crawford won Sixth Man THREE times. Instant OFFENSE off the bench... {reason}"},
    {"name": "Sixth Man Manu Ginobili", "archetype": "Sixth Man Spark", "stat_context": "points", "tier": "Gold", "narrative": "Hall of Fame bench player", "template": "Manu was a Hall of Famer who came off the BENCH. That's IMPACT... {reason}"},
    {"name": "Sixth Man Lou Williams", "archetype": "Sixth Man Spark", "stat_context": "points", "tier": "Silver", "narrative": "Underground GOAT sixth man", "template": "Lou Will was the KING of the second unit. Instant buckets... {reason}"},
    {"name": "Dennis Rodman Rebounding Savant", "archetype": "Glass Cleaner", "stat_context": "rebounds", "tier": "Platinum", "narrative": "Greatest rebounder pound-for-pound", "template": "Rodman grabbed rebounds like his LIFE depended on it. RELENTLESS... {reason}"},
    {"name": "Ben Wallace Defensive Force", "archetype": "Defensive Anchor", "stat_context": "blocks", "tier": "Gold", "narrative": "Undrafted to DPOY four times", "template": "Ben Wallace was UNDRAFTED and won DPOY four times. HEART over talent... {reason}"},
    {"name": "Draymond Green 2016 DPOY", "archetype": "Defensive Anchor", "stat_context": "steals", "tier": "Gold", "narrative": "Defensive quarterback", "template": "Draymond is the defensive QUARTERBACK. He makes EVERYONE better... {reason}"},
    {"name": "Jimmy Butler 2023 Playoff Run", "archetype": "Two-Way Wing", "stat_context": "points", "tier": "Platinum", "narrative": "Playoff Jimmy is a different beast", "template": "Playoff Jimmy is a DIFFERENT ANIMAL. He turns it UP when it matters... {reason}"},
    {"name": "Anthony Davis 2020 Championship", "archetype": "Rim Protector", "stat_context": "blocks", "tier": "Gold", "narrative": "Elite rim protection with scoring", "template": "AD in 2020 was a MONSTER on both ends. Rim protector AND scorer... {reason}"},
    {"name": "Russell Westbrook Triple-Double Season", "archetype": "High-Usage Ball Handler", "stat_context": "rebounds", "tier": "Platinum", "narrative": "Averaged a triple-double for a season", "template": "Westbrook averaged a TRIPLE-DOUBLE. Sheer FORCE of will... {reason}"},
    {"name": "Damian Lillard Deep Threes", "archetype": "Shot Creator", "stat_context": "threes", "tier": "Gold", "narrative": "Logo-range shooting", "template": "Dame shoots from the LOGO and it goes IN. That range is LETHAL... {reason}"},
    {"name": "Damian Lillard Playoff Buzzer Beaters", "archetype": "Shot Creator", "stat_context": "points", "tier": "Gold", "narrative": "Clutch gene personified", "template": "Dame TIME is REAL. When the moment is biggest, he's at his BEST... {reason}"},
    {"name": "Kyrie Irving Handle Mastery", "archetype": "Shot Creator", "stat_context": "points", "tier": "Gold", "narrative": "Best ball handler ever", "template": "Kyrie has the BEST handle in NBA history. He creates shots from NOTHING... {reason}"},
    {"name": "Karl Malone Pick-and-Roll", "archetype": "Pick-and-Roll Big", "stat_context": "points", "tier": "Gold", "narrative": "Stockton-to-Malone perfection", "template": "The Stockton-to-Malone pick-and-roll was UNSTOPPABLE. That chemistry... {reason}"},
    {"name": "Bam Adebayo Switchable Big", "archetype": "Pick-and-Roll Big", "stat_context": "rebounds", "tier": "Silver", "narrative": "Modern switchable center", "template": "Bam can guard ONE through FIVE. The modern big man PROTOTYPE... {reason}"},
    {"name": "Scottie Pippen Two-Way Excellence", "archetype": "Playmaking Wing", "stat_context": "steals", "tier": "Gold", "narrative": "Elite perimeter defender and playmaker", "template": "Pippen was the ultimate TWO-WAY wing. Defense AND playmaking... {reason}"},
]


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
    if avoid:
        return "STAY_AWAY"
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
