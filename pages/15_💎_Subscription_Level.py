# ============================================================
# FILE: pages/14_💎_Subscription_Level.py
# PURPOSE: SmartBetPro NBA subscription management page.
#          Shows pricing, feature comparison, and handles
#          Stripe Checkout redirects for new subscribers.
#          Existing subscribers can manage their plan via the
#          Stripe Customer Portal.
# ============================================================

import streamlit as st
import datetime

# ============================================================
# SECTION: Page Configuration (must be first Streamlit call)
# ============================================================

st.set_page_config(
    page_title="Premium — SmartBetPro NBA",
    page_icon="💎",
    layout="wide",
)

# ─── Inject Global CSS Theme ──────────────────────────────────
from styles.theme import get_global_css, get_education_box_html, get_premium_footer_html
st.markdown(get_global_css(), unsafe_allow_html=True)

# ── Joseph M. Smith Floating Widget ────────────────────────────
from utils.components import inject_joseph_floating
st.session_state["joseph_page_context"] = "page_premium"
inject_joseph_floating()

# ─── Premium Page Custom CSS ──────────────────────────────────
st.markdown("""
<style>
/* ── Hero Section ─────────────────────────────────────── */
.premium-hero {
    background: linear-gradient(135deg, #0a1428 0%, #0d1f3c 50%, #0a1428 100%);
    border: 1px solid rgba(0, 213, 89, 0.25);
    border-radius: 18px;
    padding: 40px 48px;
    text-align: center;
    position: relative;
    overflow: hidden;
    margin-bottom: 32px;
    box-shadow: 0 0 60px rgba(0,213,89,0.07), 0 8px 40px rgba(0,0,0,0.6);
}
.premium-hero::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0; height: 3px;
    background: linear-gradient(90deg,
        #00D559 0%, #00D559 25%, #F9C62B 60%, #2D9EFF 100%);
    background-size: 200% 100%;
    animation: heroShimmer 4s ease infinite;
}
@keyframes heroShimmer {
    0%   { background-position: 200% 0; }
    100% { background-position: -200% 0; }
}
.hero-diamond {
    font-size: 4rem;
    animation: diamondFloat 3s ease-in-out infinite;
    display: block;
    margin-bottom: 12px;
}
@keyframes diamondFloat {
    0%, 100% { transform: translateY(0);   }
    50%       { transform: translateY(-8px); }
}
.hero-title {
    font-family: 'Inter', 'Courier New', monospace;
    font-size: 2.4rem;
    font-weight: 900;
    background: linear-gradient(90deg, #00D559, #00D559);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin: 0 0 8px;
}
.hero-subtitle {
    color: #A0AABE;
    font-size: 1.1rem;
    max-width: 560px;
    margin: 0 auto 24px;
    line-height: 1.7;
}
.hero-badge {
    display: inline-block;
    background: rgba(255, 94, 0, 0.18);
    border: 1px solid rgba(255, 94, 0, 0.45);
    color: #F9C62B;
    border-radius: 20px;
    padding: 4px 18px;
    font-size: 0.83rem;
    font-weight: 700;
    letter-spacing: 1px;
    text-transform: uppercase;
}

/* ── Pricing Card ─────────────────────────────────────── */
.pricing-card {
    background: rgba(14, 20, 40, 0.95);
    border: 2px solid rgba(0, 213, 89, 0.4);
    border-radius: 18px;
    padding: 36px 32px;
    text-align: center;
    position: relative;
    overflow: hidden;
    box-shadow: 0 0 40px rgba(0,213,89,0.13), 0 8px 32px rgba(0,0,0,0.5);
    max-width: 380px;
    margin: 0 auto;
}
.pricing-card::after {
    content: 'MOST POPULAR';
    position: absolute;
    top: 16px; right: -28px;
    background: linear-gradient(135deg, #F9C62B, #ff8c00);
    color: white;
    font-size: 0.65rem;
    font-weight: 800;
    padding: 4px 36px;
    transform: rotate(40deg);
    letter-spacing: 1.5px;
}
.price-amount {
    font-family: 'Inter', monospace;
    font-size: 3.2rem;
    font-weight: 900;
    color: #00D559;
    line-height: 1;
    text-shadow: 0 0 30px rgba(0,213,89,0.45);
}
.price-period {
    color: #607080;
    font-size: 0.9rem;
    margin-bottom: 20px;
}
.price-plan-name {
    font-family: 'Inter', monospace;
    font-size: 1.1rem;
    color: #00D559;
    margin-bottom: 4px;
    text-transform: uppercase;
    letter-spacing: 2px;
}
.price-feature-list {
    list-style: none;
    padding: 0;
    margin: 16px 0 24px;
    text-align: left;
}
.price-feature-list li {
    color: #EEF0F6;
    font-size: 0.87rem;
    padding: 6px 0 6px 28px;
    position: relative;
    border-bottom: 1px solid rgba(0,213,89,0.06);
}
.price-feature-list li:last-child { border-bottom: none; }
.price-feature-list li::before {
    content: '✓';
    position: absolute;
    left: 4px;
    color: #00D559;
    font-weight: 800;
}

/* ── Feature Comparison Table ─────────────────────────── */
.compare-table {
    width: 100%;
    border-collapse: separate;
    border-spacing: 0;
    margin: 16px 0;
    font-size: 0.88rem;
}
.compare-table th {
    background: rgba(0, 213, 89, 0.08);
    color: #00D559;
    font-family: 'Inter', monospace;
    font-size: 0.78rem;
    letter-spacing: 1px;
    text-transform: uppercase;
    padding: 12px 16px;
    border-bottom: 2px solid rgba(0,213,89,0.22);
    text-align: center;
}
.compare-table th:first-child { text-align: left; }
.compare-table td {
    padding: 10px 16px;
    border-bottom: 1px solid rgba(0,213,89,0.06);
    color: #b8c8e0;
    text-align: center;
    vertical-align: middle;
}
.compare-table td:first-child {
    text-align: left;
    color: #d0e0f8;
    font-weight: 500;
}
.compare-table tr:hover td {
    background: rgba(0,213,89,0.04);
}
.check-yes  { color: #00D559; font-size: 1.1rem; }
.check-no   { color: #3a4a60; font-size: 1.0rem; }
.check-limit { color: #ff9d00; font-size: 0.82rem; font-weight: 700; }

/* ── Status Cards ─────────────────────────────────────── */
.sub-status-card {
    background: rgba(0, 213, 89, 0.06);
    border: 1.5px solid rgba(0, 213, 89, 0.35);
    border-radius: 14px;
    padding: 24px 28px;
    margin-bottom: 24px;
    box-shadow: 0 0 24px rgba(0,213,89,0.08);
}
.sub-status-title {
    font-family: 'Inter', monospace;
    color: #00D559;
    font-size: 1.1rem;
    margin: 0 0 6px;
}
.sub-detail {
    color: #90aac8;
    font-size: 0.87rem;
    margin: 3px 0;
}
.sub-detail strong { color: #c8d8f0; }
</style>
""", unsafe_allow_html=True)

# ============================================================
# SECTION: Handle Stripe Checkout Redirect
# ============================================================

# When Stripe redirects back after payment, the URL contains
# ?session_id=XXX — we capture and verify it here.
from utils.auth import (
    handle_checkout_redirect,
    is_premium_user,
    get_subscription_status,
    restore_subscription_by_email,
    logout_premium,
)
from utils.stripe_manager import (
    is_stripe_configured,
    create_checkout_session,
    create_customer_portal_session,
    get_publishable_key,
)

# Check for cancelled checkout (user clicked "back" on Stripe)
params = st.query_params
if params.get("cancelled"):
    st.warning("⚠️ Checkout cancelled. You can try again anytime!")

# Process successful checkout redirect
newly_subscribed = handle_checkout_redirect()
if newly_subscribed:
    st.balloons()
    st.success(
        "🎉 **Welcome to SmartBetPro Premium!** "
        "Your subscription is now active. All premium features are unlocked."
    )

# ============================================================
# SECTION: Hero Banner
# ============================================================

st.markdown("""
<div class="premium-hero">
  <span class="hero-diamond">💎</span>
  <p class="hero-title">SmartBetPro Premium</p>
  <p class="hero-subtitle">
    Four tiers. One mission — give you the sharpest edge in NBA prop betting.
    From free access to lifetime Insider Circle, pick the plan that fits your game.
  </p>
  <span class="hero-badge">🏀 NBA Season 2025-26</span>
</div>
""", unsafe_allow_html=True)

with st.expander("📖 How Subscriptions Work", expanded=False):
    st.markdown("""
    ### SmartBetPro — Tier Breakdown
    
    **⭐ Smart Rookie** — *"Welcome to the smart side."*
    - Free forever — no credit card required
    - Live Sweat, Live Games, Smart NBA Data, Settings
    - Prop Scanner with up to 5 manual props
    - QAM limited to 10 props
    
    **🔥 Sharp IQ** — *"Your IQ just passed the books."*
    - $9.99/mo or $107.89/yr (SAVE 10%)
    - 25 QAM props, unlimited Prop Scanner + CSV + Live Retrieval
    - Entry Builder, Risk Shield, Game Report, Player Simulator, Bet Tracker
    
    **💎 Smart Money** — *"You are the smart money."*
    - $24.99/mo or $269.89/yr (SAVE 10%)
    - All 300+ QAM props, Smart Money Bets, Correlation Matrix, Proving Grounds, The Studio
    
    **👑 Insider Circle** — *"You knew before everyone."*
    - $499.99 one-time lifetime access (75 seats only)
    - Everything in Smart Money + exclusive 👑 Insider Circle features
    
    **How Payment Works**
    - Secure checkout through Stripe (industry-standard payment processor)
    - Cancel anytime on monthly/annual — no long-term commitment
    - Insider Circle is a one-time payment for lifetime access
    
    💡 **Already subscribed?** Your status appears at the top of this page. Use "Manage Subscription" to update billing or cancel.
    """)

# ============================================================
# SECTION: Subscriber View (already premium)
# ============================================================

sub_status = get_subscription_status()

if sub_status["is_premium"]:
    st.markdown("""
<div class="sub-status-card">
  <p class="sub-status-title">✅ Premium Active</p>
  <p class="sub-detail">You have full access to all SmartBetPro NBA features.</p>
</div>
""", unsafe_allow_html=True)

    # Show subscription details
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.metric("Plan", sub_status["plan_name"] or "Premium")
    with col_b:
        status_label = sub_status["status"].capitalize() if sub_status["status"] else "Active"
        st.metric("Status", status_label)
    with col_c:
        period_end = sub_status["period_end"]
        if period_end:
            try:
                end_dt = datetime.datetime.fromisoformat(period_end)
                next_billing = end_dt.strftime("%b %d, %Y")
            except Exception:
                next_billing = period_end[:10]
        else:
            next_billing = "—"
        st.metric("Next Billing", next_billing)

    st.divider()

    # Customer Portal Button (manage billing, cancel, etc.)
    customer_id = st.session_state.get("_sub_customer_id", "")
    if customer_id and is_stripe_configured():
        col_portal, col_logout, _ = st.columns([1, 1, 2])
        with col_portal:
            if st.button("⚙️ Manage Subscription", use_container_width=True):
                with st.spinner("Opening Stripe Customer Portal…"):
                    portal = create_customer_portal_session(customer_id)
                    if portal["success"]:
                        st.markdown(
                            f'<meta http-equiv="refresh" content="0; url={portal["url"]}">',
                            unsafe_allow_html=True,
                        )
                        st.info(
                            f"Redirecting to Stripe… [Click here if not redirected]({portal['url']})"
                        )
                    else:
                        st.error(f"Could not open portal: {portal['error']}")
        with col_logout:
            if st.button("🚪 Sign Out", use_container_width=True):
                logout_premium()
                st.rerun()
    elif is_stripe_configured():
        st.info(
            "To manage your subscription, visit "
            "[Stripe Customer Portal](https://billing.stripe.com) directly."
        )

    # Premium features quick-links
    st.subheader("🚀 Your Premium Features")
    feat_cols = st.columns(3)
    features = [
        ("🧬", "Entry Builder",     "pages/8_🧬_Entry_Builder.py"),
        ("🛡️", "Risk Shield",        "pages/9_🛡️_Risk_Shield.py"),
        ("📋", "Game Report",        "pages/6_📋_Game_Report.py"),
        ("🔮", "Player Simulator",  "pages/7_🔮_Player_Simulator.py"),
        ("📈", "Bet Tracker",        "pages/12_📈_Bet_Tracker.py"),
        ("🔬", "Full Prop Scanner",  "pages/2_🔬_Prop_Scanner.py"),
    ]
    for i, (icon, name, page) in enumerate(features):
        with feat_cols[i % 3]:
            if st.button(f"{icon} {name}", use_container_width=True, key=f"_prem_link_{i}"):
                st.switch_page(page)

    st.markdown(get_premium_footer_html(), unsafe_allow_html=True)
    st.stop()  # Don't show pricing section to existing subscribers

# ============================================================
# SECTION: Upgrade / Pricing Section (non-premium users)
# ============================================================

# ── 4-Tier Pricing Cards ─────────────────────────────────────
st.markdown("""
<style>
/* ── 4-Tier Pricing Grid ───────────────────────────────── */
.tier-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 16px;
    margin: 24px 0 32px;
}
@media (max-width: 900px) {
    .tier-grid { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 560px) {
    .tier-grid { grid-template-columns: 1fr; }
}
.tier-card {
    background: rgba(14, 20, 40, 0.95);
    border: 2px solid rgba(255,255,255,0.08);
    border-radius: 16px;
    padding: 28px 22px;
    text-align: center;
    position: relative;
    overflow: hidden;
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}
.tier-card:hover {
    transform: translateY(-4px);
    box-shadow: 0 8px 32px rgba(0,0,0,0.5);
}
.tier-card.tier-rookie  { border-color: rgba(160,170,190,0.35); }
.tier-card.tier-sharp   { border-color: rgba(249,198,43,0.45); }
.tier-card.tier-smart   { border-color: rgba(0,213,89,0.5); box-shadow: 0 0 40px rgba(0,213,89,0.12); }
.tier-card.tier-insider { border-color: rgba(192,132,252,0.5); box-shadow: 0 0 40px rgba(192,132,252,0.12); }

.tier-card.tier-smart::after {
    content: 'MOST POPULAR';
    position: absolute;
    top: 14px; right: -30px;
    background: linear-gradient(135deg, #00D559, #00a847);
    color: #fff;
    font-size: 0.58rem;
    font-weight: 800;
    padding: 4px 36px;
    transform: rotate(40deg);
    letter-spacing: 1.5px;
}
.tier-card.tier-insider::after {
    content: '75 SEATS';
    position: absolute;
    top: 14px; right: -30px;
    background: linear-gradient(135deg, #c084fc, #9333ea);
    color: #fff;
    font-size: 0.58rem;
    font-weight: 800;
    padding: 4px 36px;
    transform: rotate(40deg);
    letter-spacing: 1.5px;
}

.tier-icon { font-size: 2.2rem; margin-bottom: 6px; display: block; }
.tier-name {
    font-family: 'Inter', monospace;
    font-size: 1rem;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    margin: 0 0 4px;
}
.tier-card.tier-rookie  .tier-name { color: #A0AABE; }
.tier-card.tier-sharp   .tier-name { color: #F9C62B; }
.tier-card.tier-smart   .tier-name { color: #00D559; }
.tier-card.tier-insider .tier-name { color: #c084fc; }

.tier-tagline {
    color: #607080;
    font-size: 0.78rem;
    font-style: italic;
    margin: 0 0 16px;
    min-height: 18px;
}
.tier-price {
    font-family: 'Inter', monospace;
    font-size: 2.4rem;
    font-weight: 900;
    line-height: 1;
    margin: 0;
}
.tier-card.tier-rookie  .tier-price { color: #A0AABE; }
.tier-card.tier-sharp   .tier-price { color: #F9C62B; }
.tier-card.tier-smart   .tier-price { color: #00D559; text-shadow: 0 0 20px rgba(0,213,89,0.4); }
.tier-card.tier-insider .tier-price { color: #c084fc; text-shadow: 0 0 20px rgba(192,132,252,0.4); }

.tier-period {
    color: #607080;
    font-size: 0.8rem;
    margin: 4px 0 6px;
}
.tier-annual {
    display: inline-block;
    background: rgba(0,213,89,0.1);
    border: 1px solid rgba(0,213,89,0.25);
    color: #00D559;
    border-radius: 20px;
    padding: 2px 12px;
    font-size: 0.7rem;
    font-weight: 700;
    margin-bottom: 16px;
}
.tier-card.tier-insider .tier-annual {
    background: rgba(192,132,252,0.1);
    border-color: rgba(192,132,252,0.25);
    color: #c084fc;
}
.tier-highlights {
    list-style: none;
    padding: 0;
    margin: 12px 0 0;
    text-align: left;
    font-size: 0.8rem;
}
.tier-highlights li {
    color: #b8c8e0;
    padding: 5px 0 5px 22px;
    position: relative;
    border-bottom: 1px solid rgba(255,255,255,0.04);
}
.tier-highlights li:last-child { border-bottom: none; }
.tier-highlights li::before {
    content: '✓';
    position: absolute;
    left: 2px;
    font-weight: 800;
}
.tier-card.tier-rookie  .tier-highlights li::before { color: #A0AABE; }
.tier-card.tier-sharp   .tier-highlights li::before { color: #F9C62B; }
.tier-card.tier-smart   .tier-highlights li::before { color: #00D559; }
.tier-card.tier-insider .tier-highlights li::before { color: #c084fc; }

.tier-payment {
    margin-top: 14px;
    padding-top: 10px;
    border-top: 1px solid rgba(255,255,255,0.06);
    font-size: 0.72rem;
    color: #607080;
}
</style>

<div class="tier-grid">
  <!-- Smart Rookie -->
  <div class="tier-card tier-rookie">
    <span class="tier-icon">⭐</span>
    <p class="tier-name">Smart Rookie</p>
    <p class="tier-tagline">"Welcome to the smart side."</p>
    <p class="tier-price">$0</p>
    <p class="tier-period">free forever</p>
    <div style="height:22px;"></div>
    <ul class="tier-highlights">
      <li>10 QAM Props</li>
      <li>💦 Live Sweat</li>
      <li>📡 Live Games</li>
      <li>📡 Smart NBA Data</li>
      <li>⚙️ Settings</li>
      <li>🔬 Prop Scanner — Up to 5 props</li>
    </ul>
    <p class="tier-payment">💳 Free forever</p>
  </div>

  <!-- Sharp IQ -->
  <div class="tier-card tier-sharp">
    <span class="tier-icon">🔥</span>
    <p class="tier-name">Sharp IQ</p>
    <p class="tier-tagline">"Your IQ just passed the books."</p>
    <p class="tier-price">$9<span style="font-size:1.2rem">.99</span></p>
    <p class="tier-period">per month</p>
    <span class="tier-annual">$107.89/yr — SAVE 10%</span>
    <ul class="tier-highlights">
      <li>25 QAM Props</li>
      <li>🔬 Unlimited Prop Scanner + CSV + Live</li>
      <li>🧬 Entry Builder</li>
      <li>🛡️ Risk Shield</li>
      <li>📋 Game Report</li>
      <li>🔮 Player Simulator</li>
      <li>📈 Bet Tracker</li>
    </ul>
    <p class="tier-payment">💳 Stripe · Cancel anytime</p>
  </div>

  <!-- Smart Money -->
  <div class="tier-card tier-smart">
    <span class="tier-icon">💎</span>
    <p class="tier-name">Smart Money</p>
    <p class="tier-tagline">"You are the smart money."</p>
    <p class="tier-price">$24<span style="font-size:1.2rem">.99</span></p>
    <p class="tier-period">per month</p>
    <span class="tier-annual">$269.89/yr — SAVE 10%</span>
    <ul class="tier-highlights">
      <li>✅ All 300+ QAM Props</li>
      <li>Everything in Sharp IQ, plus:</li>
      <li>💰 Smart Money Bets</li>
      <li>🗺️ Correlation Matrix</li>
      <li>📊 Proving Grounds</li>
      <li>🎙️ The Studio</li>
    </ul>
    <p class="tier-payment">💳 Stripe · Cancel anytime</p>
  </div>

  <!-- Insider Circle -->
  <div class="tier-card tier-insider">
    <span class="tier-icon">👑</span>
    <p class="tier-name">Insider Circle</p>
    <p class="tier-tagline">"You knew before everyone."</p>
    <p class="tier-price">$499<span style="font-size:1.2rem">.99</span></p>
    <p class="tier-period">one-time · lifetime</p>
    <span class="tier-annual" style="background:rgba(192,132,252,0.1);border-color:rgba(192,132,252,0.25);color:#c084fc;">75 seats only</span>
    <ul class="tier-highlights">
      <li>✅ All 300+ QAM Props + 👑</li>
      <li>Everything in Smart Money, plus:</li>
      <li>👑 Insider Circle Exclusive Access</li>
      <li>Lifetime — never pay again</li>
    </ul>
    <p class="tier-payment">💳 One-time · Lifetime access</p>
  </div>
</div>
""", unsafe_allow_html=True)

# ── Subscribe Buttons ─────────────────────────────────────────
sub_cols = st.columns(4)
with sub_cols[0]:
    st.markdown("##### ⭐ Smart Rookie")
    st.success("**Free** — you're already here!")

with sub_cols[1]:
    st.markdown("##### 🔥 Sharp IQ")
    if is_stripe_configured():
        with st.form("checkout_sharp_iq"):
            email_sharp = st.text_input(
                "Email (optional)",
                placeholder="you@example.com",
                key="_email_sharp",
            )
            if st.form_submit_button(
                "🚀 Subscribe — $9.99/mo",
                type="primary",
                use_container_width=True,
            ):
                with st.spinner("Creating checkout…"):
                    result = create_checkout_session(
                        customer_email=email_sharp.strip() if email_sharp else "",
                        price_lookup="sharp_iq",
                    )
                if result["success"]:
                    st.markdown(
                        f'<meta http-equiv="refresh" content="0; url={result["url"]}">',
                        unsafe_allow_html=True,
                    )
                    st.info(f"Redirecting… [Click here]({result['url']})")
                else:
                    st.error(f"Checkout error: {result['error']}")
    else:
        st.info("Stripe not configured yet — coming soon!")

with sub_cols[2]:
    st.markdown("##### 💎 Smart Money")
    if is_stripe_configured():
        with st.form("checkout_smart_money"):
            email_smart = st.text_input(
                "Email (optional)",
                placeholder="you@example.com",
                key="_email_smart",
            )
            if st.form_submit_button(
                "🚀 Subscribe — $24.99/mo",
                type="primary",
                use_container_width=True,
            ):
                with st.spinner("Creating checkout…"):
                    result = create_checkout_session(
                        customer_email=email_smart.strip() if email_smart else "",
                        price_lookup="smart_money",
                    )
                if result["success"]:
                    st.markdown(
                        f'<meta http-equiv="refresh" content="0; url={result["url"]}">',
                        unsafe_allow_html=True,
                    )
                    st.info(f"Redirecting… [Click here]({result['url']})")
                else:
                    st.error(f"Checkout error: {result['error']}")
    else:
        st.info("Stripe not configured yet — coming soon!")

with sub_cols[3]:
    st.markdown("##### 👑 Insider Circle")
    if is_stripe_configured():
        with st.form("checkout_insider"):
            email_insider = st.text_input(
                "Email (optional)",
                placeholder="you@example.com",
                key="_email_insider",
            )
            if st.form_submit_button(
                "👑 Get Lifetime — $499.99",
                type="primary",
                use_container_width=True,
            ):
                with st.spinner("Creating checkout…"):
                    result = create_checkout_session(
                        customer_email=email_insider.strip() if email_insider else "",
                        price_lookup="insider_circle",
                    )
                if result["success"]:
                    st.markdown(
                        f'<meta http-equiv="refresh" content="0; url={result["url"]}">',
                        unsafe_allow_html=True,
                    )
                    st.info(f"Redirecting… [Click here]({result['url']})")
                else:
                    st.error(f"Checkout error: {result['error']}")
    else:
        st.info("Stripe not configured yet — coming soon!")

# ── Restore Access ────────────────────────────────────────────
with st.expander("🔑 Already subscribed? Restore access"):
    st.markdown(
        "Enter the email you used when subscribing to restore your premium access."
    )
    restore_email = st.text_input(
        "Email address",
        key="_restore_email",
        placeholder="you@example.com",
    )
    if st.button("Restore Access", key="_restore_btn"):
        if not restore_email.strip():
            st.error("Please enter your email address.")
        else:
            with st.spinner("Looking up your subscription…"):
                found = restore_subscription_by_email(restore_email.strip())
            if found:
                st.success("✅ Premium access restored! Refreshing…")
                st.rerun()
            else:
                st.error(
                    "No active subscription found for that email. "
                    "Please check the address or contact support."
                )

st.divider()

# ── Full Feature Comparison Table ─────────────────────────────
st.markdown("### 📊 Full Feature Comparison")
st.markdown("""
<table class="compare-table">
  <thead>
    <tr>
      <th>Feature</th>
      <th>⭐ Smart Rookie</th>
      <th>🔥 Sharp IQ</th>
      <th>💎 Smart Money</th>
      <th>👑 Insider Circle</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>QAM Props</td>
      <td><span class="check-limit">10</span></td>
      <td><span class="check-limit">25</span></td>
      <td><span class="check-yes">All 300+</span></td>
      <td><span class="check-yes">All 300+ + 👑</span></td>
    </tr>
    <tr>
      <td>💦 Live Sweat</td>
      <td><span class="check-yes">✓</span></td>
      <td><span class="check-yes">✓</span></td>
      <td><span class="check-yes">✓</span></td>
      <td><span class="check-yes">✓</span></td>
    </tr>
    <tr>
      <td>📡 Live Games</td>
      <td><span class="check-yes">✓</span></td>
      <td><span class="check-yes">✓</span></td>
      <td><span class="check-yes">✓</span></td>
      <td><span class="check-yes">✓</span></td>
    </tr>
    <tr>
      <td>📡 Smart NBA Data</td>
      <td><span class="check-yes">✓</span></td>
      <td><span class="check-yes">✓</span></td>
      <td><span class="check-yes">✓</span></td>
      <td><span class="check-yes">✓</span></td>
    </tr>
    <tr>
      <td>⚙️ Settings</td>
      <td><span class="check-yes">✓</span></td>
      <td><span class="check-yes">✓</span></td>
      <td><span class="check-yes">✓</span></td>
      <td><span class="check-yes">✓</span></td>
    </tr>
    <tr>
      <td>🔬 Prop Scanner — Manual Entry</td>
      <td><span class="check-limit">Up to 5 props</span></td>
      <td><span class="check-yes">✓ Unlimited</span></td>
      <td><span class="check-yes">✓ Unlimited</span></td>
      <td><span class="check-yes">✓ Unlimited</span></td>
    </tr>
    <tr>
      <td>🔬 Prop Scanner — CSV Upload</td>
      <td><span class="check-no">✗</span></td>
      <td><span class="check-yes">✓</span></td>
      <td><span class="check-yes">✓</span></td>
      <td><span class="check-yes">✓</span></td>
    </tr>
    <tr>
      <td>🔬 Prop Scanner — Live Platform Retrieval</td>
      <td><span class="check-no">✗</span></td>
      <td><span class="check-yes">✓</span></td>
      <td><span class="check-yes">✓</span></td>
      <td><span class="check-yes">✓</span></td>
    </tr>
    <tr>
      <td>⚡ Quantum Analysis Matrix</td>
      <td><span class="check-limit">10 props</span></td>
      <td><span class="check-limit">25 props</span></td>
      <td><span class="check-yes">✓ All 300+</span></td>
      <td><span class="check-yes">✓ All 300+ + 👑</span></td>
    </tr>
    <tr>
      <td>🧬 Entry Builder</td>
      <td><span class="check-no">✗</span></td>
      <td><span class="check-yes">✓</span></td>
      <td><span class="check-yes">✓</span></td>
      <td><span class="check-yes">✓</span></td>
    </tr>
    <tr>
      <td>🛡️ Risk Shield</td>
      <td><span class="check-no">✗</span></td>
      <td><span class="check-yes">✓</span></td>
      <td><span class="check-yes">✓</span></td>
      <td><span class="check-yes">✓</span></td>
    </tr>
    <tr>
      <td>📋 Game Report</td>
      <td><span class="check-no">✗</span></td>
      <td><span class="check-yes">✓</span></td>
      <td><span class="check-yes">✓</span></td>
      <td><span class="check-yes">✓</span></td>
    </tr>
    <tr>
      <td>🔮 Player Simulator</td>
      <td><span class="check-no">✗</span></td>
      <td><span class="check-yes">✓</span></td>
      <td><span class="check-yes">✓</span></td>
      <td><span class="check-yes">✓</span></td>
    </tr>
    <tr>
      <td>📈 Bet Tracker</td>
      <td><span class="check-no">✗</span></td>
      <td><span class="check-yes">✓</span></td>
      <td><span class="check-yes">✓</span></td>
      <td><span class="check-yes">✓</span></td>
    </tr>
    <tr>
      <td>💰 Smart Money Bets</td>
      <td><span class="check-no">✗</span></td>
      <td><span class="check-no">✗</span></td>
      <td><span class="check-yes">✓</span></td>
      <td><span class="check-yes">✓</span></td>
    </tr>
    <tr>
      <td>🗺️ Correlation Matrix</td>
      <td><span class="check-no">✗</span></td>
      <td><span class="check-no">✗</span></td>
      <td><span class="check-yes">✓</span></td>
      <td><span class="check-yes">✓</span></td>
    </tr>
    <tr>
      <td>📊 Proving Grounds</td>
      <td><span class="check-no">✗</span></td>
      <td><span class="check-no">✗</span></td>
      <td><span class="check-yes">✓</span></td>
      <td><span class="check-yes">✓</span></td>
    </tr>
    <tr>
      <td>🎙️ The Studio</td>
      <td><span class="check-no">✗</span></td>
      <td><span class="check-no">✗</span></td>
      <td><span class="check-yes">✓</span></td>
      <td><span class="check-yes">✓</span></td>
    </tr>
    <tr>
      <td>👑 Insider Circle Exclusive Access</td>
      <td><span class="check-no">✗</span></td>
      <td><span class="check-no">✗</span></td>
      <td><span class="check-no">✗</span></td>
      <td><span class="check-yes">✓</span></td>
    </tr>
    <tr style="border-top:2px solid rgba(0,213,89,0.15);">
      <td><strong>Payment</strong></td>
      <td style="color:#A0AABE;">Free forever</td>
      <td style="color:#F9C62B;">Stripe · Cancel anytime</td>
      <td style="color:#00D559;">Stripe · Cancel anytime</td>
      <td style="color:#c084fc;">One-time · Lifetime</td>
    </tr>
  </tbody>
</table>
""", unsafe_allow_html=True)

# ============================================================
# SECTION: Footer
# ============================================================

st.divider()
st.markdown(get_premium_footer_html(), unsafe_allow_html=True)
