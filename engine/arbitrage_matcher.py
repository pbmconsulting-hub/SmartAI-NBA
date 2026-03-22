"""
engine/arbitrage_matcher.py
---------------------------
Triangulates sportsbook player-prop lines across multiple books to
surface EV discrepancies for the Vegas Vault dashboard.

Public API
----------
find_ev_discrepancies(sportsbook_props) -> list[dict]
"""

import re
import logging

try:
    from utils.logger import get_logger
    _logger = get_logger(__name__)
except ImportError:
    _logger = logging.getLogger(__name__)

try:
    from data.odds_api_client import calculate_implied_probability
except ImportError:
    def calculate_implied_probability(american_odds: float) -> float:
        """Fallback: convert American odds to implied probability percentage."""
        odds = float(american_odds)
        if odds < 0:
            return abs(odds) / (abs(odds) + 100.0) * 100
        return 100.0 / (odds + 100.0) * 100


# ── Name-normalisation helpers ────────────────────────────────────────────────

_PUNCT_RE = re.compile(r"[^a-z\s]")


def _normalise_name(name: str) -> str:
    """Lower-case, strip, remove punctuation."""
    return _PUNCT_RE.sub("", name.strip().lower()).strip()


def _names_match(a: str, b: str) -> bool:
    """Return True when two player names refer to the same person.

    Handles exact matches and abbreviated first names such as
    ``"L. James"`` vs ``"LeBron James"`` using a token-match ratio:
    if the last name matches exactly AND the first initial matches,
    treat as the same player.
    """
    na = _normalise_name(a)
    nb = _normalise_name(b)
    if na == nb:
        return True

    tokens_a = na.split()
    tokens_b = nb.split()
    if len(tokens_a) < 2 or len(tokens_b) < 2:
        return False

    # Last name must match exactly.
    if tokens_a[-1] != tokens_b[-1]:
        return False

    # First initial must match.
    if tokens_a[0][0] == tokens_b[0][0]:
        return True

    return False


# ── Canonical-name grouping key ───────────────────────────────────────────────

def _group_key(name: str, stat_type: str, line: float) -> tuple:
    return (_normalise_name(name), stat_type.strip().lower(), float(line))


# ── Public API ────────────────────────────────────────────────────────────────

def find_ev_discrepancies(sportsbook_props: list) -> list:
    """Find EV discrepancies across sportsbook player-prop lines.

    Parameters
    ----------
    sportsbook_props : list[dict]
        Raw output of ``fetch_player_props()``.  Each dict has keys:
        ``player_name``, ``stat_type``, ``line``, ``platform``,
        ``over_odds``, ``under_odds``.

    Returns
    -------
    list[dict]
        Discrepancies sorted by *ev_edge* descending.  Only includes
        props with ``ev_edge >= 7.0``.
    """
    if not sportsbook_props:
        return []

    # ── 1. Build groups by (normalised_name, stat_type, line) ─────────
    # We need to merge names like "LeBron James" and "L. James".
    # First pass: collect canonical names per normalised name.
    canonical_names: dict[str, str] = {}  # normalised -> longest original
    groups: dict[tuple, list] = {}

    for prop in sportsbook_props:
        try:
            name = prop.get("player_name", "")
            stat = prop.get("stat_type", "")
            line = prop.get("line")
            if not name or not stat or line is None:
                continue
            line = float(line)
        except (TypeError, ValueError):
            continue

        norm = _normalise_name(name)

        # Track best (longest) display name.
        if norm not in canonical_names or len(name) > len(canonical_names[norm]):
            canonical_names[norm] = name

        key = _group_key(name, stat, line)
        groups.setdefault(key, []).append(prop)

    # Second pass: merge groups whose normalised names match via
    # _names_match (handles abbreviated first names).
    merged_groups: dict[tuple, list] = {}
    norm_to_merged: dict[str, str] = {}  # maps normalised name -> canonical norm

    for key, props in groups.items():
        norm_name, stat, line = key
        # Check if we already have a merged key for this name.
        merged_norm = norm_to_merged.get(norm_name)
        if merged_norm is None:
            # Check against all existing merged norms.
            for existing_norm in list(norm_to_merged.values()):
                if _names_match(norm_name, existing_norm):
                    merged_norm = existing_norm
                    break
            if merged_norm is None:
                merged_norm = norm_name
            norm_to_merged[norm_name] = merged_norm

        merged_key = (merged_norm, stat, line)
        merged_groups.setdefault(merged_key, []).extend(props)

        # Also update canonical display name.
        orig = canonical_names.get(norm_name, "")
        existing = canonical_names.get(merged_norm, "")
        if len(orig) > len(existing):
            canonical_names[merged_norm] = orig

    # ── 2. For each group, find best Over/Under across books ──────────
    discrepancies = []

    for (norm_name, stat, line), props in merged_groups.items():
        if len(props) < 1:
            continue

        best_over_odds = None
        best_over_book = ""
        best_under_odds = None
        best_under_book = ""
        book_set = set()

        for p in props:
            platform = p.get("platform", "Unknown")
            book_set.add(platform)

            over = p.get("over_odds")
            under = p.get("under_odds")

            # Best Over = highest implied probability = most aggressive pricing
            # (most negative odds for favourites, or lowest positive odds).
            # We compare implied probabilities to select the strongest signal.
            if over is not None:
                try:
                    over_int = int(over)
                    if best_over_odds is None:
                        best_over_odds = over_int
                        best_over_book = platform
                    else:
                        over_ip = calculate_implied_probability(over_int)
                        best_ip = calculate_implied_probability(best_over_odds)
                        if over_ip > best_ip:
                            best_over_odds = over_int
                            best_over_book = platform
                except (TypeError, ValueError):
                    pass

            # Best Under = highest implied probability = most aggressive pricing.
            if under is not None:
                try:
                    under_int = int(under)
                    if best_under_odds is None:
                        best_under_odds = under_int
                        best_under_book = platform
                    else:
                        under_ip = calculate_implied_probability(under_int)
                        best_uip = calculate_implied_probability(best_under_odds)
                        if under_ip > best_uip:
                            best_under_odds = under_int
                            best_under_book = platform
                except (TypeError, ValueError):
                    pass

        if best_over_odds is None and best_under_odds is None:
            continue

        # ── 3. Calculate implied probabilities ────────────────────────
        over_prob = 0.0
        under_prob = 0.0
        if best_over_odds is not None:
            over_prob = calculate_implied_probability(best_over_odds)
        if best_under_odds is not None:
            under_prob = calculate_implied_probability(best_under_odds)

        # ── 4. EV edge = max implied prob - 50 ───────────────────────
        max_prob = max(over_prob, under_prob)
        ev_edge = round(max_prob - 50.0, 2)

        # ── 5. Filter: ev_edge >= 7.0 ────────────────────────────────
        if ev_edge < 7.0:
            continue

        # ── 6. God Mode Lock: any side >= 60% implied ────────────────
        is_god_mode = over_prob >= 60.0 or under_prob >= 60.0

        display_name = canonical_names.get(norm_name, norm_name)

        discrepancies.append({
            "player_name": display_name,
            "stat_type": stat,
            "true_line": line,
            "best_over_odds": best_over_odds if best_over_odds is not None else 0,
            "best_over_book": best_over_book,
            "best_under_odds": best_under_odds if best_under_odds is not None else 0,
            "best_under_book": best_under_book,
            "best_over_implied_prob": round(over_prob, 2),
            "best_under_implied_prob": round(under_prob, 2),
            "ev_edge": ev_edge,
            "is_god_mode_lock": is_god_mode,
            "book_count": len(book_set),
        })

    # ── 7. Sort by ev_edge descending ─────────────────────────────────
    discrepancies.sort(key=lambda d: d["ev_edge"], reverse=True)

    _logger.info("find_ev_discrepancies: %d props passed filter.", len(discrepancies))
    return discrepancies
