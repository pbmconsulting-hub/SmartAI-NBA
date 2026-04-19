# ============================================================
# FILE: utils/auth_gate.py
# PURPOSE: Signup / Login gate for Smart Pick Pro.
#          Users must create an account or log in before they
#          can see ANY page in the app.
#
# HOW IT WORKS:
#   1. Call  require_login()  at the very top of every page
#      (after st.set_page_config).
#   2. If the user has NOT logged in this session, the function
#      renders a full-screen signup/login form and returns False.
#      The calling page should then call  st.stop().
#   3. Once the user signs up or logs in, the session-state flag
#      is set and require_login() returns True on all subsequent
#      reruns — no database hit on every page load.
#
# PASSWORD STORAGE:
#   • Passwords are hashed with bcrypt (or hashlib-based PBKDF2
#     fallback if bcrypt is not installed).
#   • Plaintext passwords are NEVER stored or logged.
# ============================================================

from __future__ import annotations

import hashlib
import logging
import os
import re
import secrets
import sqlite3

import streamlit as st

from tracking.database import initialize_database, get_database_connection

_logger = logging.getLogger(__name__)

# ── Session-state keys ────────────────────────────────────────
_SS_LOGGED_IN     = "_auth_logged_in"      # bool
_SS_USER_EMAIL    = "_auth_user_email"     # str
_SS_USER_NAME     = "_auth_user_name"      # str
_SS_USER_ID       = "_auth_user_id"        # int

# ── Password hashing helpers ──────────────────────────────────

try:
    import bcrypt as _bcrypt  # type: ignore
    _HAS_BCRYPT = True
except ImportError:
    _bcrypt = None  # type: ignore
    _HAS_BCRYPT = False


def _hash_password(plain: str) -> str:
    """Hash a plaintext password. Uses bcrypt if available, else PBKDF2."""
    if _HAS_BCRYPT:
        return _bcrypt.hashpw(plain.encode("utf-8"), _bcrypt.gensalt()).decode("utf-8")
    # Fallback: PBKDF2-SHA256
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", plain.encode("utf-8"), salt.encode("utf-8"), 260_000)
    return f"pbkdf2:sha256:260000${salt}${dk.hex()}"


def _verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against a stored hash."""
    if _HAS_BCRYPT and hashed.startswith("$2"):
        return _bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    if hashed.startswith("pbkdf2:"):
        parts = hashed.split("$")
        if len(parts) != 3:
            return False
        _, salt, expected_hex = parts
        dk = hashlib.pbkdf2_hmac("sha256", plain.encode("utf-8"), salt.encode("utf-8"), 260_000)
        return secrets.compare_digest(dk.hex(), expected_hex)
    return False


# ── Database helpers ──────────────────────────────────────────

def _create_user(email: str, password: str, display_name: str = "") -> bool:
    """Create a new user account. Returns True on success."""
    initialize_database()
    pw_hash = _hash_password(password)
    try:
        with get_database_connection() as conn:
            conn.execute(
                "INSERT INTO users (email, password_hash, display_name) VALUES (?, ?, ?)",
                (email.strip().lower(), pw_hash, display_name.strip() or email.split("@")[0]),
            )
            conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False  # Email already registered
    except Exception as exc:
        _logger.error("Failed to create user: %s", exc)
        return False


def _authenticate_user(email: str, password: str) -> dict | None:
    """Verify credentials. Returns user dict on success, None on failure."""
    initialize_database()
    try:
        with get_database_connection() as conn:
            cursor = conn.execute(
                "SELECT user_id, email, password_hash, display_name FROM users WHERE email = ?",
                (email.strip().lower(),),
            )
            row = cursor.fetchone()
            if not row:
                return None
            user = dict(row)
            if _verify_password(password, user["password_hash"]):
                # Update last_login_at
                conn.execute(
                    "UPDATE users SET last_login_at = datetime('now') WHERE user_id = ?",
                    (user["user_id"],),
                )
                conn.commit()
                return user
    except Exception as exc:
        _logger.error("Authentication error: %s", exc)
    return None


def _email_exists(email: str) -> bool:
    """Check if an email is already registered."""
    initialize_database()
    try:
        with get_database_connection() as conn:
            row = conn.execute(
                "SELECT 1 FROM users WHERE email = ?",
                (email.strip().lower(),),
            ).fetchone()
            return row is not None
    except Exception:
        return False


# ── Validation ────────────────────────────────────────────────

_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")


def _valid_email(email: str) -> bool:
    return bool(_EMAIL_RE.match(email.strip()))


def _valid_password(pw: str) -> str | None:
    """Return an error message if password is weak, else None."""
    if len(pw) < 8:
        return "Password must be at least 8 characters."
    if not any(c.isdigit() for c in pw):
        return "Password must contain at least one number."
    if not any(c.isalpha() for c in pw):
        return "Password must contain at least one letter."
    return None


# ── Session helpers ───────────────────────────────────────────

def _set_logged_in(user: dict) -> None:
    st.session_state[_SS_LOGGED_IN]  = True
    st.session_state[_SS_USER_EMAIL] = user.get("email", "")
    st.session_state[_SS_USER_NAME]  = user.get("display_name", "")
    st.session_state[_SS_USER_ID]    = user.get("user_id", 0)


def is_logged_in() -> bool:
    """Check if the user is logged into an account this session."""
    return bool(st.session_state.get(_SS_LOGGED_IN))


def get_logged_in_email() -> str:
    """Return the logged-in user's email, or ''."""
    return st.session_state.get(_SS_USER_EMAIL, "")


def logout_user() -> None:
    """Clear the login session."""
    for key in (_SS_LOGGED_IN, _SS_USER_EMAIL, _SS_USER_NAME, _SS_USER_ID):
        st.session_state.pop(key, None)


# ── Logo helper ───────────────────────────────────────────────

def _get_logo_b64() -> str:
    """Return base64-encoded SPP logo for inline embedding."""
    import base64 as _b64
    _logo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "Smart_Pick_Pro_Logo.png")
    try:
        with open(_logo_path, "rb") as f:
            return _b64.b64encode(f.read()).decode()
    except OSError:
        return ""


# ── CSS for the gate ──────────────────────────────────────────

_GATE_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

/* ── Hide Streamlit chrome while on gate ────────────────────── */
[data-testid="stSidebar"], header[data-testid="stHeader"],
[data-testid="stDecoration"], .stDeployButton {
    display: none !important;
}
[data-testid="stAppViewContainer"] {
    padding-top: 0 !important;
}
.stApp { background: transparent !important; }

/* ── Keyframes ──────────────────────────────────────────────── */
@keyframes authOrbFloat {
    0%, 100% { transform: translate(0, 0) scale(1); }
    25%  { transform: translate(30px, -20px) scale(1.08); }
    50%  { transform: translate(-15px, 15px) scale(0.95); }
    75%  { transform: translate(20px, 25px) scale(1.04); }
}
@keyframes authOrbFloat2 {
    0%, 100% { transform: translate(0, 0) scale(1); }
    33%  { transform: translate(-40px, 20px) scale(1.1); }
    66%  { transform: translate(25px, -30px) scale(0.92); }
}
@keyframes authGradShift {
    0%   { background-position: 0% 50%; }
    50%  { background-position: 100% 50%; }
    100% { background-position: 0% 50%; }
}
@keyframes authFadeInUp {
    from { opacity: 0; transform: translateY(32px); }
    to   { opacity: 1; transform: translateY(0); }
}
@keyframes authPulseGlow {
    0%, 100% { box-shadow: 0 0 40px rgba(0,213,89,0.08), 0 0 80px rgba(45,158,255,0.04); }
    50%      { box-shadow: 0 0 60px rgba(0,213,89,0.14), 0 0 120px rgba(45,158,255,0.08); }
}
@keyframes authScanLine {
    0%   { top: -2px; opacity: 0.7; }
    100% { top: 100%; opacity: 0; }
}
@keyframes authShimmer {
    0%   { background-position: -200% 0; }
    100% { background-position: 200% 0; }
}
@keyframes authLogoSpin {
    from { transform: rotate(0deg); }
    to   { transform: rotate(360deg); }
}
@keyframes authTickerScroll {
    0%   { transform: translateX(0%); }
    100% { transform: translateX(-50%); }
}

/* ── Full-screen dark canvas ───────────────────────────────── */
.auth-gate-bg {
    position: fixed; inset: 0; z-index: 9998;
    background: linear-gradient(160deg, #04060c 0%, #080d1a 25%, #0a1428 50%, #0c1020 75%, #060a14 100%);
    background-size: 400% 400%;
    animation: authGradShift 20s ease infinite;
    overflow-y: auto;
    overflow-x: hidden;
}

/* Ambient orbs */
.auth-orb {
    position: fixed; border-radius: 50%;
    pointer-events: none; z-index: 9998;
    filter: blur(100px);
}
.auth-orb-1 {
    width: 500px; height: 500px;
    background: radial-gradient(circle, rgba(0,213,89,0.1) 0%, transparent 70%);
    top: -120px; left: -80px;
    animation: authOrbFloat 14s ease-in-out infinite;
}
.auth-orb-2 {
    width: 450px; height: 450px;
    background: radial-gradient(circle, rgba(45,158,255,0.08) 0%, transparent 70%);
    bottom: -100px; right: -100px;
    animation: authOrbFloat2 18s ease-in-out infinite;
}
.auth-orb-3 {
    width: 300px; height: 300px;
    background: radial-gradient(circle, rgba(249,198,43,0.05) 0%, transparent 70%);
    top: 40%; left: 60%;
    animation: authOrbFloat 22s ease-in-out infinite reverse;
}

/* Scan line */
.auth-scan-line {
    position: fixed; left: 0; width: 100%; height: 2px; z-index: 9999;
    background: linear-gradient(90deg, transparent 0%, rgba(0,213,89,0.25) 30%, rgba(45,158,255,0.2) 70%, transparent 100%);
    animation: authScanLine 8s linear infinite;
    pointer-events: none;
}

/* Grid pattern overlay */
.auth-grid-overlay {
    position: fixed; inset: 0; z-index: 9998; pointer-events: none;
    background-image:
        linear-gradient(rgba(255,255,255,0.015) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255,255,255,0.015) 1px, transparent 1px);
    background-size: 60px 60px;
    mask-image: radial-gradient(ellipse at 50% 50%, black 30%, transparent 80%);
    -webkit-mask-image: radial-gradient(ellipse at 50% 50%, black 30%, transparent 80%);
}

/* ── Main container ────────────────────────────────────────── */
.auth-gate-container {
    position: relative; z-index: 10000;
    max-width: 480px; margin: 0 auto;
    padding: 40px 24px 32px;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

/* ── Sports ticker (top) ───────────────────────────────────── */
.auth-ticker-wrap {
    position: relative; z-index: 10001;
    overflow: hidden; margin-bottom: 32px;
    background: linear-gradient(90deg, rgba(0,213,89,0.06), rgba(45,158,255,0.06), rgba(249,198,43,0.06));
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 12px; padding: 0;
    height: 38px; display: flex; align-items: center;
}
.auth-ticker-track {
    display: flex; white-space: nowrap;
    animation: authTickerScroll 30s linear infinite;
}
.auth-ticker-item {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 0 28px; font-size: 0.76rem; font-weight: 600;
    color: rgba(255,255,255,0.6); letter-spacing: 0.03em;
}
.auth-ticker-item .ticker-dot {
    width: 6px; height: 6px; border-radius: 50%;
    display: inline-block; flex-shrink: 0;
}
.ticker-dot-live { background: #00D559; box-shadow: 0 0 6px rgba(0,213,89,0.6); }
.ticker-dot-soon { background: #F9C62B; opacity: 0.7; }

/* ── Logo section ──────────────────────────────────────────── */
.auth-logo-section {
    text-align: center; margin-bottom: 8px;
    animation: authFadeInUp 0.7s cubic-bezier(0.22,1,0.36,1) both;
}
.auth-logo-ring {
    display: inline-block; position: relative;
    width: 96px; height: 96px; margin-bottom: 16px;
}
.auth-logo-ring::before {
    content: ''; position: absolute; inset: -4px;
    border-radius: 50%;
    background: conic-gradient(from 0deg, #00D559, #2D9EFF, #F9C62B, #c084fc, #00D559);
    animation: authLogoSpin 6s linear infinite;
    mask: radial-gradient(farthest-side, transparent calc(100% - 2px), black calc(100% - 2px));
    -webkit-mask: radial-gradient(farthest-side, transparent calc(100% - 2px), black calc(100% - 2px));
}
.auth-logo-ring img {
    width: 96px; height: 96px; border-radius: 50%;
    position: relative; z-index: 1;
}
.auth-brand-name {
    font-size: 1.65rem; font-weight: 900;
    background: linear-gradient(135deg, #FFFFFF 0%, #00D559 50%, #2D9EFF 100%);
    background-size: 200% 200%;
    animation: authGradShift 6s ease infinite;
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text;
    letter-spacing: -0.03em; line-height: 1.1;
}
.auth-brand-sub {
    font-size: 0.72rem; font-weight: 500; letter-spacing: 0.18em;
    text-transform: uppercase; margin-top: 6px;
    color: rgba(255,255,255,0.35);
}

/* ── Headline ──────────────────────────────────────────────── */
.auth-headline {
    text-align: center; margin: 28px 0 6px;
    font-size: 1.75rem; font-weight: 900; color: #FFFFFF;
    line-height: 1.2; letter-spacing: -0.03em;
    animation: authFadeInUp 0.7s 0.12s cubic-bezier(0.22,1,0.36,1) both;
}
.auth-headline .hl-accent {
    background: linear-gradient(135deg, #00D559, #2D9EFF);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text;
}
.auth-subheadline {
    text-align: center; font-size: 0.88rem; font-weight: 400;
    color: rgba(255,255,255,0.5); margin-bottom: 28px;
    line-height: 1.55;
    animation: authFadeInUp 0.7s 0.2s cubic-bezier(0.22,1,0.36,1) both;
}

/* ── Stats bar ─────────────────────────────────────────────── */
.auth-stats-bar {
    display: flex; justify-content: center; gap: 8px;
    margin-bottom: 28px; flex-wrap: wrap;
    animation: authFadeInUp 0.7s 0.28s cubic-bezier(0.22,1,0.36,1) both;
}
.auth-stat-chip {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 7px 14px; border-radius: 100px;
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.06);
    font-size: 0.74rem; font-weight: 600;
    color: rgba(255,255,255,0.6);
    backdrop-filter: blur(8px);
}
.auth-stat-chip .stat-val {
    color: #00D559; font-weight: 800;
}

/* ── Glass card wrapping Streamlit forms ───────────────────── */
/* We style the Streamlit tab container + form elements */
.auth-gate-container [data-testid="stTabs"] {
    animation: authFadeInUp 0.7s 0.35s cubic-bezier(0.22,1,0.36,1) both;
}
.auth-gate-container [data-testid="stTabs"] > [data-baseweb="tab-list"] {
    background: rgba(255,255,255,0.03);
    border-radius: 14px; padding: 4px;
    border: 1px solid rgba(255,255,255,0.06);
    gap: 4px; margin-bottom: 24px;
    justify-content: center;
}
.auth-gate-container [data-testid="stTabs"] [data-baseweb="tab"] {
    border-radius: 10px !important; font-weight: 700 !important;
    font-size: 0.88rem !important; padding: 10px 28px !important;
    color: rgba(255,255,255,0.45) !important;
    background: transparent !important;
    border: none !important;
    transition: all 0.25s ease !important;
}
.auth-gate-container [data-testid="stTabs"] [data-baseweb="tab"][aria-selected="true"] {
    background: linear-gradient(135deg, rgba(0,213,89,0.15), rgba(45,158,255,0.12)) !important;
    color: #FFFFFF !important;
    box-shadow: 0 2px 12px rgba(0,213,89,0.15) !important;
    border: 1px solid rgba(0,213,89,0.2) !important;
}
/* Tab highlight bar — hide default */
.auth-gate-container [data-testid="stTabs"] [data-baseweb="tab-highlight"] {
    display: none !important;
}
.auth-gate-container [data-testid="stTabs"] [data-baseweb="tab-border"] {
    display: none !important;
}

/* Form panel area */
.auth-gate-container [data-testid="stForm"] {
    background: rgba(14, 20, 38, 0.7) !important;
    border: 1px solid rgba(255,255,255,0.06) !important;
    border-radius: 20px !important;
    padding: 32px 28px 28px !important;
    backdrop-filter: blur(30px) saturate(1.2) !important;
    -webkit-backdrop-filter: blur(30px) saturate(1.2) !important;
    box-shadow:
        0 24px 80px rgba(0,0,0,0.45),
        0 0 0 1px rgba(255,255,255,0.04) inset,
        0 1px 0 rgba(255,255,255,0.06) inset !important;
    animation: authPulseGlow 6s ease-in-out infinite;
}

/* Inputs */
.auth-gate-container [data-testid="stForm"] input {
    background: rgba(255,255,255,0.04) !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    border-radius: 12px !important;
    color: #FFFFFF !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 0.9rem !important;
    padding: 12px 16px !important;
    transition: border-color 0.25s, box-shadow 0.25s !important;
}
.auth-gate-container [data-testid="stForm"] input:focus {
    border-color: rgba(0,213,89,0.45) !important;
    box-shadow: 0 0 0 3px rgba(0,213,89,0.1), 0 0 20px rgba(0,213,89,0.06) !important;
    outline: none !important;
}
.auth-gate-container [data-testid="stForm"] input::placeholder {
    color: rgba(255,255,255,0.25) !important;
}
/* Labels */
.auth-gate-container [data-testid="stForm"] label {
    color: rgba(255,255,255,0.6) !important;
    font-weight: 600 !important; font-size: 0.82rem !important;
    letter-spacing: 0.01em !important;
}

/* Submit buttons */
.auth-gate-container [data-testid="stForm"] button[kind="primaryFormSubmit"],
.auth-gate-container [data-testid="stForm"] button[type="submit"] {
    background: linear-gradient(135deg, #00D559 0%, #00B84D 40%, #00A043 100%) !important;
    color: #FFFFFF !important;
    font-weight: 800 !important; font-size: 1rem !important;
    letter-spacing: -0.01em !important;
    border: none !important; border-radius: 14px !important;
    padding: 14px 32px !important;
    margin-top: 8px !important;
    box-shadow: 0 4px 24px rgba(0,213,89,0.3), 0 1px 0 rgba(255,255,255,0.1) inset !important;
    transition: all 0.2s ease !important;
    position: relative; overflow: hidden;
}
.auth-gate-container [data-testid="stForm"] button[kind="primaryFormSubmit"]:hover,
.auth-gate-container [data-testid="stForm"] button[type="submit"]:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 32px rgba(0,213,89,0.4), 0 1px 0 rgba(255,255,255,0.15) inset !important;
}

/* ── Feature cards grid (below forms) ──────────────────────── */
.auth-features-grid {
    display: grid; grid-template-columns: 1fr 1fr 1fr;
    gap: 10px; margin-top: 28px;
    animation: authFadeInUp 0.7s 0.5s cubic-bezier(0.22,1,0.36,1) both;
}
.auth-feat-card {
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 14px; padding: 16px 12px;
    text-align: center;
    transition: border-color 0.25s, transform 0.25s, box-shadow 0.25s;
}
.auth-feat-card:hover {
    border-color: rgba(0,213,89,0.2);
    transform: translateY(-3px);
    box-shadow: 0 8px 24px rgba(0,0,0,0.3);
}
.auth-feat-icon {
    font-size: 1.4rem; margin-bottom: 6px; display: block;
}
.auth-feat-label {
    font-size: 0.72rem; font-weight: 700;
    color: rgba(255,255,255,0.75);
    line-height: 1.3; letter-spacing: -0.01em;
}
.auth-feat-sublabel {
    font-size: 0.62rem; font-weight: 500;
    color: rgba(255,255,255,0.3); margin-top: 3px;
}

/* ── Trust strip ───────────────────────────────────────────── */
.auth-trust-strip {
    display: flex; justify-content: center; align-items: center;
    gap: 20px; margin-top: 24px; flex-wrap: wrap;
    animation: authFadeInUp 0.7s 0.6s cubic-bezier(0.22,1,0.36,1) both;
}
.auth-trust-item {
    display: flex; align-items: center; gap: 5px;
    font-size: 0.68rem; font-weight: 500;
    color: rgba(255,255,255,0.28);
}
.auth-trust-icon { font-size: 0.72rem; }

/* ── Footer ────────────────────────────────────────────────── */
.auth-footer {
    text-align: center; margin-top: 36px;
    font-size: 0.65rem; color: rgba(255,255,255,0.18);
    line-height: 1.6;
    animation: authFadeInUp 0.7s 0.7s cubic-bezier(0.22,1,0.36,1) both;
}

/* ── Responsive ────────────────────────────────────────────── */
@media (max-width: 520px) {
    .auth-gate-container { padding: 28px 14px 24px; }
    .auth-gate-container [data-testid="stForm"] {
        padding: 24px 18px 22px !important;
        border-radius: 16px !important;
    }
    .auth-headline { font-size: 1.35rem; }
    .auth-features-grid { grid-template-columns: 1fr 1fr; }
    .auth-logo-ring { width: 76px; height: 76px; }
    .auth-logo-ring img { width: 76px; height: 76px; }
    .auth-brand-name { font-size: 1.35rem; }
    .auth-stats-bar { gap: 6px; }
    .auth-stat-chip { font-size: 0.68rem; padding: 6px 10px; }
    .auth-ticker-wrap { margin-bottom: 24px; }
}
@media (max-width: 360px) {
    .auth-features-grid { grid-template-columns: 1fr; }
}
</style>
"""

# ── Main gate function ────────────────────────────────────────

def require_login() -> bool:
    """Render a signup/login gate if the user is not logged in.

    Returns True if the user is authenticated. Returns False (and
    renders the full-screen gate) if they are not — the caller
    should call ``st.stop()`` immediately.

    Non-production bypass: when ``SMARTAI_PRODUCTION`` is not
    "true", the gate is skipped entirely so local dev is
    friction-free.
    """
    # Dev bypass
    if os.environ.get("SMARTAI_PRODUCTION", "").lower() not in ("true", "1", "yes"):
        return True

    if is_logged_in():
        return True

    # ── Render the gate ───────────────────────────────────────
    st.markdown(_GATE_CSS, unsafe_allow_html=True)

    # Logo base64
    _logo_b64 = _get_logo_b64()
    _logo_tag = f'<img src="data:image/png;base64,{_logo_b64}" alt="Smart Pick Pro">' if _logo_b64 else '<div style="font-size:2.8rem;">🏀</div>'

    st.markdown(f"""
    <!-- Ambient background layers -->
    <div class="auth-gate-bg"></div>
    <div class="auth-orb auth-orb-1"></div>
    <div class="auth-orb auth-orb-2"></div>
    <div class="auth-orb auth-orb-3"></div>
    <div class="auth-scan-line"></div>
    <div class="auth-grid-overlay"></div>

    <div class="auth-gate-container">

      <!-- Sports ticker -->
      <div class="auth-ticker-wrap">
        <div class="auth-ticker-track">
          <div class="auth-ticker-item"><span class="ticker-dot ticker-dot-live"></span> NBA PLAYOFFS LIVE</div>
          <div class="auth-ticker-item"><span class="ticker-dot ticker-dot-soon"></span> MLB COMING SOON</div>
          <div class="auth-ticker-item"><span class="ticker-dot ticker-dot-soon"></span> NFL COMING SOON</div>
          <div class="auth-ticker-item">⚡ 300+ PROPS ANALYZED NIGHTLY</div>
          <div class="auth-ticker-item">🧠 QUANTUM MATRIX ENGINE</div>
          <div class="auth-ticker-item">📊 62% HIT RATE VERIFIED</div>
          <!-- duplicate for seamless loop -->
          <div class="auth-ticker-item"><span class="ticker-dot ticker-dot-live"></span> NBA PLAYOFFS LIVE</div>
          <div class="auth-ticker-item"><span class="ticker-dot ticker-dot-soon"></span> MLB COMING SOON</div>
          <div class="auth-ticker-item"><span class="ticker-dot ticker-dot-soon"></span> NFL COMING SOON</div>
          <div class="auth-ticker-item">⚡ 300+ PROPS ANALYZED NIGHTLY</div>
          <div class="auth-ticker-item">🧠 QUANTUM MATRIX ENGINE</div>
          <div class="auth-ticker-item">📊 62% HIT RATE VERIFIED</div>
        </div>
      </div>

      <!-- Logo + Brand -->
      <div class="auth-logo-section">
        <div class="auth-logo-ring">{_logo_tag}</div>
        <div class="auth-brand-name">Smart Pick Pro</div>
        <div class="auth-brand-sub">The Sharpest Prop Engine on the Internet</div>
      </div>

      <!-- Headline -->
      <div class="auth-headline">
        The House Has a Problem.<br><span class="hl-accent">It's Us.</span>
      </div>
      <div class="auth-subheadline">
        Create your free account to access the full platform.<br>No credit card required. Ever.
      </div>

      <!-- Social proof chips -->
      <div class="auth-stats-bar">
        <div class="auth-stat-chip">🏀 <span class="stat-val">300+</span> Props / Night</div>
        <div class="auth-stat-chip">🎯 <span class="stat-val">62%</span> Hit Rate</div>
        <div class="auth-stat-chip">🤖 <span class="stat-val">AI</span> Powered</div>
      </div>

    </div>
    """, unsafe_allow_html=True)

    # Tabs for signup / login
    tab_signup, tab_login = st.tabs(["⚡  Create Account", "🔓  Log In"])

    with tab_signup:
        with st.form("signup_form", clear_on_submit=False):
            su_name = st.text_input("Display Name", placeholder="e.g. Joseph", key="_su_name")
            su_email = st.text_input("Email Address", placeholder="you@example.com", key="_su_email")
            su_pw = st.text_input("Password", type="password", placeholder="Min 8 chars, 1 letter, 1 number", key="_su_pw")
            su_pw2 = st.text_input("Confirm Password", type="password", placeholder="Re-enter your password", key="_su_pw2")
            su_submit = st.form_submit_button("⚡ Create Free Account", use_container_width=True, type="primary")

        if su_submit:
            if not su_email or not _valid_email(su_email):
                st.error("Please enter a valid email address.")
            elif pw_err := _valid_password(su_pw):
                st.error(pw_err)
            elif su_pw != su_pw2:
                st.error("Passwords don't match.")
            elif _email_exists(su_email):
                st.error("An account with this email already exists. Please log in instead.")
            else:
                ok = _create_user(su_email, su_pw, su_name)
                if ok:
                    user = _authenticate_user(su_email, su_pw)
                    if user:
                        _set_logged_in(user)
                        st.success("Account created! Welcome to Smart Pick Pro.")
                        st.rerun()
                    else:
                        st.error("Account created but login failed. Please try logging in.")
                else:
                    st.error("Could not create account. Please try again.")

    with tab_login:
        with st.form("login_form", clear_on_submit=False):
            li_email = st.text_input("Email Address", placeholder="you@example.com", key="_li_email")
            li_pw = st.text_input("Password", type="password", placeholder="Enter your password", key="_li_pw")
            li_submit = st.form_submit_button("🔓 Log In", use_container_width=True, type="primary")

        if li_submit:
            if not li_email or not _valid_email(li_email):
                st.error("Please enter a valid email address.")
            elif not li_pw:
                st.error("Please enter your password.")
            else:
                user = _authenticate_user(li_email, li_pw)
                if user:
                    _set_logged_in(user)
                    st.success(f"Welcome back, {user.get('display_name', '')}!")
                    st.rerun()
                else:
                    st.error("Invalid email or password.")

    # Feature cards
    st.markdown("""
    <div class="auth-features-grid">
      <div class="auth-feat-card">
        <span class="auth-feat-icon">🎯</span>
        <div class="auth-feat-label">SAFE Score™</div>
        <div class="auth-feat-sublabel">Every pick rated</div>
      </div>
      <div class="auth-feat-card">
        <span class="auth-feat-icon">🧠</span>
        <div class="auth-feat-label">Quantum Engine</div>
        <div class="auth-feat-sublabel">AI-powered analysis</div>
      </div>
      <div class="auth-feat-card">
        <span class="auth-feat-icon">📡</span>
        <div class="auth-feat-label">Live Sweat</div>
        <div class="auth-feat-sublabel">Real-time tracking</div>
      </div>
      <div class="auth-feat-card">
        <span class="auth-feat-icon">🔬</span>
        <div class="auth-feat-label">Prop Scanner</div>
        <div class="auth-feat-sublabel">Find edge instantly</div>
      </div>
      <div class="auth-feat-card">
        <span class="auth-feat-icon">🎙️</span>
        <div class="auth-feat-label">The Studio</div>
        <div class="auth-feat-sublabel">Joseph's AI brain</div>
      </div>
      <div class="auth-feat-card">
        <span class="auth-feat-icon">🛡️</span>
        <div class="auth-feat-label">Risk Shield</div>
        <div class="auth-feat-sublabel">Protect your bankroll</div>
      </div>
    </div>

    <div class="auth-trust-strip">
      <div class="auth-trust-item"><span class="auth-trust-icon">🔒</span> 256-bit Encryption</div>
      <div class="auth-trust-item"><span class="auth-trust-icon">🚫</span> No Credit Card</div>
      <div class="auth-trust-item"><span class="auth-trust-icon">🤝</span> Never Sold Data</div>
    </div>

    <div class="auth-footer">
      © 2026 Smart Pick Pro · For entertainment &amp; educational purposes only · 21+ · <a href="https://www.ncpgambling.org/" target="_blank" style="color:rgba(255,255,255,0.3);text-decoration:underline;">1-800-GAMBLER</a>
    </div>
    """, unsafe_allow_html=True)

    return False
