# ============================================================
# FILE: engine/calibration.py
# PURPOSE: Historical Calibration Engine (C10)
#          Loads historical bet results from the tracking database,
#          computes calibration curves (predicted probability vs actual
#          hit rate), and exports a get_calibration_adjustment() function.
#
#          If model says 70% but actual hit rate is 62%, this module
#          provides a calibration offset to apply to the confidence score.
#
#          Cold start: if no historical data exists yet, returns 0 adjustment.
#
# CONNECTS TO: tracking/database.py (historical results)
# CONCEPTS COVERED: Probability calibration, expected vs actual,
#                   reliability diagrams, calibration offset
# ============================================================

import math


# ============================================================
# SECTION: Calibration Constants
# ============================================================

# Minimum number of historical bets in a probability bucket before
# we trust the calibration estimate (otherwise cold start applies).
MIN_BETS_FOR_CALIBRATION = 20

# Probability bucket width for building the calibration curve.
# 0.10 = 10% buckets: [0.50-0.60), [0.60-0.70), [0.70-0.80), etc.
CALIBRATION_BUCKET_WIDTH = 0.10

# Maximum adjustment magnitude in confidence score points.
# Caps adjustments to avoid over-correcting on small samples.
MAX_CALIBRATION_ADJUSTMENT = 10.0

# ============================================================
# END SECTION: Calibration Constants
# ============================================================


# ============================================================
# SECTION: Calibration Data Loading
# ============================================================

def _load_historical_predictions(days=90):
    """
    Load historical prediction records from the tracking database.

    Args:
        days (int): Number of past days to include. Default 90.

    Returns:
        list of dict: Prediction records. Each record should have:
            - 'probability_over': float, the model's predicted probability
            - 'result': int/bool, 1=hit (over was correct), 0=miss
        Empty list on cold start or database errors.
    """
    try:
        from tracking.database import load_recent_predictions
        records = load_recent_predictions(days=days)
        # Filter to records with both probability and result
        return [
            r for r in (records or [])
            if r.get("probability_over") is not None
            and r.get("result") is not None
        ]
    except Exception:
        return []


def _build_calibration_curve(records):
    """
    Build a calibration curve from historical prediction records.

    Groups predictions into probability buckets and computes the actual
    hit rate within each bucket.

    Args:
        records (list of dict): Historical prediction records.

    Returns:
        dict: {bucket_midpoint: {'predicted': float, 'actual': float, 'count': int}}
        Empty dict if insufficient data.
    """
    if not records:
        return {}

    # Initialize buckets: [0.50-0.60), [0.60-0.70), ..., [0.90-1.00)
    buckets = {}
    for b in range(5, 10):  # b=5 → [0.50-0.60), ..., b=9 → [0.90-1.00)
        low = b * CALIBRATION_BUCKET_WIDTH
        mid = round(low + CALIBRATION_BUCKET_WIDTH / 2.0, 3)
        buckets[mid] = {"predicted": mid, "actual_sum": 0, "count": 0}

    # Fill buckets
    for record in records:
        prob = float(record.get("probability_over", 0.5) or 0.5)
        result = int(record.get("result", 0) or 0)

        # Normalize probability to [0.5, 1.0) — we only track high-confidence picks
        prob = max(0.5, min(0.999, prob))

        # Find the bucket
        bucket_idx = math.floor(prob / CALIBRATION_BUCKET_WIDTH) * CALIBRATION_BUCKET_WIDTH
        mid = round(bucket_idx + CALIBRATION_BUCKET_WIDTH / 2.0, 3)

        if mid in buckets:
            buckets[mid]["actual_sum"] += result
            buckets[mid]["count"] += 1

    # Compute actual hit rates
    curve = {}
    for mid, data in buckets.items():
        if data["count"] >= MIN_BETS_FOR_CALIBRATION:
            curve[mid] = {
                "predicted": data["predicted"],
                "actual": data["actual_sum"] / data["count"],
                "count": data["count"],
            }

    return curve


# ============================================================
# END SECTION: Calibration Data Loading
# ============================================================


# ============================================================
# SECTION: Calibration Adjustment Function
# ============================================================

def get_calibration_adjustment(raw_probability, days=90):
    """
    Compute the calibration adjustment for a given raw probability. (C10)

    Compares the model's predicted probability to the historical hit rate
    at that probability level. Returns an offset in confidence score points
    to subtract (positive adjustment = model overestimates confidence).

    Cold start behavior:
        If fewer than MIN_BETS_FOR_CALIBRATION bets exist for the relevant
        probability bucket, returns 0.0 (no adjustment applied).

    Args:
        raw_probability (float): The model's predicted P(over), 0-1.
        days (int): Days of historical data to consider. Default 90.

    Returns:
        float: Calibration offset in confidence score points.
            Positive = model is overconfident → reduce score.
            Negative = model is underconfident → increase score.
            0.0 if insufficient historical data (cold start).

    Example:
        Model says 70% → historical hit rate at that bucket is 62%
        → calibration gap = 8% → adjustment = +4.0 pts (reduce confidence)
    """
    try:
        records = _load_historical_predictions(days=days)
        if not records:
            return 0.0  # Cold start: no historical data

        curve = _build_calibration_curve(records)
        if not curve:
            return 0.0  # Insufficient data in all buckets

        # Find the bucket for this probability
        prob = max(0.5, min(0.999, float(raw_probability)))
        bucket_idx = math.floor(prob / CALIBRATION_BUCKET_WIDTH) * CALIBRATION_BUCKET_WIDTH
        mid = round(bucket_idx + CALIBRATION_BUCKET_WIDTH / 2.0, 3)

        bucket_data = curve.get(mid)
        if bucket_data is None:
            return 0.0  # No calibration data for this bucket

        predicted = bucket_data["predicted"]
        actual = bucket_data["actual"]

        # Calibration gap: positive = model overestimates
        calibration_gap = predicted - actual

        # Convert probability gap to score adjustment
        # A 10% calibration gap maps to roughly 5 confidence score points
        adjustment = calibration_gap * 50.0  # 0.10 gap → 5 pts

        # Cap the adjustment
        adjustment = max(-MAX_CALIBRATION_ADJUSTMENT, min(MAX_CALIBRATION_ADJUSTMENT, adjustment))

        return round(adjustment, 2)

    except Exception:
        return 0.0  # Always safe to return 0 on any error


def get_calibration_summary(days=90):
    """
    Return a summary of calibration statistics for the Model Health page.

    Args:
        days (int): Days of historical data to consider.

    Returns:
        dict: {
            'has_data': bool,
            'total_bets': int,
            'calibration_curve': dict,
            'overall_accuracy': float or None,
            'overconfidence_buckets': list of float (midpoints that are overconfident),
        }
    """
    try:
        records = _load_historical_predictions(days=days)
        if not records:
            return {"has_data": False, "total_bets": 0, "calibration_curve": {},
                    "overall_accuracy": None, "overconfidence_buckets": []}

        curve = _build_calibration_curve(records)

        total = len(records)
        hits = sum(int(r.get("result", 0) or 0) for r in records)
        overall_accuracy = hits / total if total > 0 else None

        overconfident = [
            mid for mid, data in curve.items()
            if data["predicted"] > data["actual"] + 0.05  # 5%+ overconfident
        ]

        return {
            "has_data": bool(curve),
            "total_bets": total,
            "calibration_curve": curve,
            "overall_accuracy": round(overall_accuracy, 4) if overall_accuracy else None,
            "overconfidence_buckets": overconfident,
        }
    except Exception:
        return {"has_data": False, "total_bets": 0, "calibration_curve": {},
                "overall_accuracy": None, "overconfidence_buckets": []}

# ============================================================
# END SECTION: Calibration Adjustment Function
# ============================================================
