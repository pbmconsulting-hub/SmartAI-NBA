# ============================================================
# FILE: utils/tier_gate.py
# PURPOSE: Subscription-tier gating helper for Streamlit pages.
#
# Usage (at the top of any gated page):
#
#   from utils.tier_gate import require_tier
#   if not require_tier():
#       st.stop()
#
# The function auto-detects the current page filename, looks up
# the minimum tier in PAGE_TIER_REQUIREMENTS, and either returns
# True (access granted) or renders a blurred preview overlay with
# an upgrade prompt and returns False.
# ============================================================

import os
import streamlit as st

from utils.auth import (
    get_user_tier,
    tier_has_access,
    get_tier_label,
    PAGE_TIER_REQUIREMENTS,
    TIER_LABELS,
    _TIER_ORDER,
)

try:
    from utils.stripe_manager import _PREMIUM_PAGE_PATH
except Exception:
    _PREMIUM_PAGE_PATH = "/15_%F0%9F%92%8E_Subscription_Level"


def _current_page_key() -> str:
    """Extract the page filename stem (e.g. '4_💰_Smart_Money_Bets')
    from Streamlit's internal state or the script path."""
    try:
        # Streamlit >= 1.30 exposes the page script path
        ctx = st.runtime.scriptrunner.get_script_run_ctx()
        if ctx and hasattr(ctx, "page_script_hash"):
            pages = st.source_util.get_pages(ctx.main_script_path) if hasattr(st, "source_util") else {}
            for _hash, info in pages.items():
                if _hash == ctx.page_script_hash:
                    return os.path.splitext(info.get("page_name", ""))[0]
    except Exception:
        pass

    # Fallback: parse __file__ of the caller's caller
    import inspect
    for frame_info in inspect.stack():
        fname = os.path.basename(frame_info.filename)
        if fname.startswith(("0_", "1_", "2_", "3_", "4_", "5_",
                             "6_", "7_", "8_", "9_", "10_", "11_",
                             "12_", "13_", "14_", "15_")):
            return os.path.splitext(fname)[0]
    return ""


def require_tier(page_key: str | None = None) -> bool:
    """Check if the current user's tier meets this page's requirement.

    Args:
        page_key: Override the auto-detected page key (e.g. for
                  gating individual *sections* within a page).

    Returns:
        True  → user has access, page should render normally.
        False → access denied, blur overlay + upgrade prompt rendered.
                Caller should call ``st.stop()``.
    """
    if page_key is None:
        page_key = _current_page_key()

    required_tier = PAGE_TIER_REQUIREMENTS.get(page_key)
    if required_tier is None:
        # Page not in the requirements map → open to everyone
        return True

    user_tier = get_user_tier()
    if tier_has_access(user_tier, required_tier):
        return True

    # ── Access denied — render blur overlay + upgrade CTA ──────
    required_label = get_tier_label(required_tier)
    user_label = get_tier_label(user_tier)

    # Which plans unlock this page?
    req_idx = _TIER_ORDER.index(required_tier)
    unlock_tiers = [
        get_tier_label(t) for t in _TIER_ORDER[req_idx:]
    ]

    st.markdown(_BLUR_CSS, unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class="tier-gate-overlay">
          <div class="tier-gate-card">
            <div class="tier-gate-lock">🔒</div>
            <p class="tier-gate-title">
              {required_label} Feature
            </p>
            <p class="tier-gate-subtitle">
              This page requires <strong>{required_label}</strong> or higher.<br>
              You're currently on <strong>{user_label}</strong>.
            </p>
            <div class="tier-gate-plans">
              <p class="tier-gate-plans-label">Available with:</p>
              {''.join(f'<span class="tier-gate-badge">{t}</span>' for t in unlock_tiers)}
            </div>
            <a class="tier-gate-cta" href="{_PREMIUM_PAGE_PATH}">
              ⚡ Upgrade Now
            </a>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    return False


# ── Inline CSS for the blur gate ──────────────────────────────
_BLUR_CSS = """
<style>
/* Blur everything rendered AFTER this overlay */
.tier-gate-overlay {
    position: fixed;
    inset: 0;
    z-index: 9998;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(10, 14, 20, 0.82);
    backdrop-filter: blur(18px);
    -webkit-backdrop-filter: blur(18px);
}
.tier-gate-card {
    background: linear-gradient(135deg, rgba(20, 27, 45, 0.97), rgba(15, 20, 35, 0.97));
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 20px;
    padding: 48px 40px 40px;
    max-width: 480px;
    width: 90vw;
    text-align: center;
    box-shadow: 0 24px 80px rgba(0,0,0,0.6);
}
.tier-gate-lock {
    font-size: 3.2rem;
    margin-bottom: 12px;
}
.tier-gate-title {
    font-size: 1.6rem;
    font-weight: 800;
    color: #F9C62B;
    margin: 0 0 8px;
    letter-spacing: -0.02em;
}
.tier-gate-subtitle {
    font-size: 0.95rem;
    color: #A0B4D0;
    margin: 0 0 24px;
    line-height: 1.55;
}
.tier-gate-plans {
    margin-bottom: 28px;
}
.tier-gate-plans-label {
    font-size: 0.78rem;
    color: #667;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 10px;
}
.tier-gate-badge {
    display: inline-block;
    background: rgba(255,255,255,0.06);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 8px;
    padding: 6px 14px;
    margin: 0 4px 6px;
    font-size: 0.85rem;
    color: #EEF0F6;
    font-weight: 600;
}
.tier-gate-cta {
    display: inline-block;
    background: linear-gradient(135deg, #F9C62B, #FF8C00);
    color: #0A0E14 !important;
    font-weight: 800;
    font-size: 1.05rem;
    padding: 14px 40px;
    border-radius: 12px;
    text-decoration: none !important;
    letter-spacing: -0.01em;
    transition: transform 0.15s, box-shadow 0.15s;
    box-shadow: 0 4px 20px rgba(249,198,43,0.3);
}
.tier-gate-cta:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 30px rgba(249,198,43,0.45);
}
</style>
"""
