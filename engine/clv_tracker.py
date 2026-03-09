# ============================================================
# FILE: engine/clv_tracker.py
# PURPOSE: Closing Line Value (CLV) Tracker (C12)
#          Stores the model's projection vs the prop line at time
#          of analysis, and later tracks the closing line.
#          Computes CLV = (closing_line - opening_line) in the
#          direction the model recommended.
#
#          Positive CLV = model had real edge (book moved toward model)
#          Negative CLV = model was wrong (book moved away from model)
#
#          CLV is the gold standard for validating whether the model
#          has real predictive edge vs market efficiency.
#
# STORAGE: SQLite via tracking/database.py (if available),
#          otherwise falls back to a local JSON file.
# CONNECTS TO: tracking/database.py (persistence layer)
# CONCEPTS COVERED: Closing Line Value, market efficiency,
#                   model validation, edge measurement
# ============================================================

import json
import datetime
import os
from pathlib import Path


# ============================================================
# SECTION: Module-Level Constants
# ============================================================

# Fallback storage path when tracking/database.py is unavailable
_CLV_JSON_PATH = Path(__file__).parent.parent / "tracking" / "clv_log.json"

# ============================================================
# END SECTION: Module-Level Constants
# ============================================================


# ============================================================
# SECTION: CLV Record Management
# ============================================================

def store_opening_line(
    player_name,
    stat_type,
    opening_line,
    model_projection,
    model_direction,
    confidence_score,
    tier,
    edge_percentage,
):
    """
    Record the opening line and model projection at time of analysis. (C12)

    Call this when the model produces a pick. Later call update_closing_line()
    to record the final closing line and compute CLV.

    Args:
        player_name (str): Player being analyzed
        stat_type (str): Stat category (e.g., 'points', 'rebounds')
        opening_line (float): The prop line at time of analysis
        model_projection (float): The model's projected value
        model_direction (str): 'OVER' or 'UNDER'
        confidence_score (float): 0-100 confidence score from engine
        tier (str): 'Platinum', 'Gold', 'Silver', 'Bronze'
        edge_percentage (float): Model's edge in percentage points

    Returns:
        str: Record ID (player_stat_timestamp) for use in update_closing_line()
    """
    record_id = f"{player_name.lower().replace(' ', '_')}_{stat_type}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"

    record = {
        "record_id":        record_id,
        "player_name":      player_name,
        "stat_type":        stat_type,
        "opening_line":     opening_line,
        "model_projection": model_projection,
        "model_direction":  model_direction,
        "confidence_score": confidence_score,
        "tier":             tier,
        "edge_percentage":  edge_percentage,
        "opening_timestamp": datetime.datetime.now().isoformat(),
        "closing_line":     None,
        "closing_timestamp": None,
        "clv":              None,
        "clv_direction":    None,
    }

    _save_clv_record(record)
    return record_id


def update_closing_line(record_id, closing_line):
    """
    Record the closing line and compute CLV for a stored pick. (C12)

    CLV = (closing_line - opening_line) in the direction the model recommended.
    Positive CLV means the market moved toward the model's view = real edge.
    Negative CLV means the market moved against the model = model was wrong.

    Args:
        record_id (str): The ID returned by store_opening_line()
        closing_line (float): The final prop line when the market closed

    Returns:
        float or None: CLV value, or None if record not found
    """
    records = _load_all_clv_records()
    record = records.get(record_id)
    if not record:
        return None

    opening = record.get("opening_line")
    direction = record.get("model_direction", "OVER")

    if opening is None:
        return None

    # CLV calculation:
    # For OVER picks: positive CLV means the line moved up (harder to hit)
    #   but this means the book agrees the player will perform well.
    #   CLV = closing_line - opening_line (in points, positive = line moved up)
    # For UNDER picks: positive CLV means the line moved down
    #   CLV = opening_line - closing_line
    if direction == "OVER":
        clv = closing_line - opening
    else:
        clv = opening - closing_line

    record["closing_line"] = closing_line
    record["closing_timestamp"] = datetime.datetime.now().isoformat()
    record["clv"] = round(clv, 2)
    record["clv_direction"] = "positive" if clv > 0 else "negative" if clv < 0 else "neutral"

    records[record_id] = record
    _save_all_clv_records(records)
    return clv


def get_clv_summary(days=90, min_records=5):
    """
    Return summary CLV statistics for the Model Health page. (C12)

    Args:
        days (int): Number of past days to include. Default 90.
        min_records (int): Minimum records needed to report meaningful stats.

    Returns:
        dict: {
            'has_data': bool,
            'total_records': int,
            'records_with_clv': int,
            'avg_clv': float or None,
            'positive_clv_rate': float or None (pct of picks with +CLV),
            'clv_by_tier': dict {tier: avg_clv},
            'interpretation': str,
        }
    """
    try:
        records = _load_all_clv_records()
        total = len(records)

        if total < min_records:
            return {
                "has_data": False, "total_records": total,
                "records_with_clv": 0, "avg_clv": None,
                "positive_clv_rate": None, "clv_by_tier": {},
                "interpretation": "Insufficient data (cold start)",
            }

        # Filter to recent records
        cutoff = datetime.datetime.now() - datetime.timedelta(days=days)
        recent = [
            r for r in records.values()
            if r.get("closing_line") is not None
            and r.get("opening_timestamp")
            and datetime.datetime.fromisoformat(r["opening_timestamp"]) >= cutoff
        ]

        if not recent:
            return {
                "has_data": False, "total_records": total,
                "records_with_clv": 0, "avg_clv": None,
                "positive_clv_rate": None, "clv_by_tier": {},
                "interpretation": "No closed picks in the last {} days".format(days),
            }

        clv_values = [r["clv"] for r in recent if r.get("clv") is not None]
        if not clv_values:
            return {
                "has_data": False, "total_records": total,
                "records_with_clv": 0, "avg_clv": None,
                "positive_clv_rate": None, "clv_by_tier": {},
                "interpretation": "No CLV data available yet",
            }

        avg_clv = sum(clv_values) / len(clv_values)
        positive_rate = sum(1 for v in clv_values if v > 0) / len(clv_values)

        # CLV by tier
        clv_by_tier = {}
        for r in recent:
            tier = r.get("tier", "Unknown")
            clv = r.get("clv")
            if clv is not None:
                if tier not in clv_by_tier:
                    clv_by_tier[tier] = []
                clv_by_tier[tier].append(clv)
        clv_by_tier = {t: round(sum(v) / len(v), 3) for t, v in clv_by_tier.items() if v}

        # Interpretation
        if avg_clv > 0.5:
            interpretation = "✅ Strong positive CLV — model has real market edge"
        elif avg_clv > 0:
            interpretation = "🟡 Weak positive CLV — marginal edge, monitor"
        elif avg_clv > -0.5:
            interpretation = "🟠 Slightly negative CLV — model lagging the market"
        else:
            interpretation = "❌ Negative CLV — model has no market edge, review assumptions"

        return {
            "has_data": True,
            "total_records": total,
            "records_with_clv": len(clv_values),
            "avg_clv": round(avg_clv, 3),
            "positive_clv_rate": round(positive_rate, 4),
            "clv_by_tier": clv_by_tier,
            "interpretation": interpretation,
        }
    except Exception:
        return {
            "has_data": False, "total_records": 0, "records_with_clv": 0,
            "avg_clv": None, "positive_clv_rate": None, "clv_by_tier": {},
            "interpretation": "Error loading CLV data",
        }

# ============================================================
# END SECTION: CLV Record Management
# ============================================================


# ============================================================
# SECTION: Storage Helpers
# ============================================================

def _load_all_clv_records():
    """Load all CLV records from JSON file. Returns dict {record_id: record}."""
    try:
        if _CLV_JSON_PATH.exists():
            with open(_CLV_JSON_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _save_all_clv_records(records):
    """Save all CLV records to JSON file."""
    try:
        _CLV_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(_CLV_JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2, default=str)
    except Exception as exc:
        print(f"CLV tracker: could not save records — {exc}")


def _save_clv_record(record):
    """Save a single CLV record (append to existing store)."""
    records = _load_all_clv_records()
    records[record["record_id"]] = record
    _save_all_clv_records(records)

# ============================================================
# END SECTION: Storage Helpers
# ============================================================
