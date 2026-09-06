import json
import time
import pandas as pd
import requests
import streamlit as st
from curl_cffi import requests as crequests

# ==========================================
# 1. PAGE CONFIG & STYLING
# ==========================================
st.set_page_config(
    page_title="PSX Full Market Scanner",
    page_icon="🇵🇰",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .main { padding: 1.5rem; }
    .stMetric { background-color: #0f172a; border-radius: 8px; padding: 10px; border: 1px solid #1e293b; }
    </style>
""",
    unsafe_allow_html=True,
)

if "portfolio" not in st.session_state:
    st.session_state["portfolio"] = pd.DataFrame(
        [
            {"Symbol": "SYS", "Avg Price": 129.00, "Shares": 1000},
            {"Symbol": "ASL", "Avg Price": 16.95, "Shares": 5000},
            {"Symbol": "CLVL", "Avg Price": 12.50, "Shares": 2000},
        ]
    )


# ==========================================
# 2. MULTI-FALLBACK PSX FETCH ENGINE
# ==========================================
def fetch_full_psx_market():
    """Fetches full PSX summary by rotating through TLS impersonation and proxy gateways."""
    sources = [
        # Option 1: Direct PSX via Chrome TLS impersonation
        (
            "direct",
            "https://dps.psx.com.pk/data/summary",
            {"impersonate": "chrome120"},
        ),
        # Option 2: AllOrigins Proxy
        (
            "proxy",
            "https://api.allorigins.win/get?url=https%3A%2F%2Fdps.psx.com.pk%2Fdata%2Fsummary",
            {},
        ),
        # Option 3: Corsproxy Gateway
        (
            "proxy_alt",
            "https://corsproxy.io/?url=https%3A%2F%2Fdps.psx.com.pk%2Fdata%2Fsummary",
            {},
        ),
    ]

    for mode, url, kwargs in sources:
        try:
            if mode == "direct":
                res = crequests.get(url, timeout=10, **kwargs)
                if res.status_code == 200:
                    data = res.json()
                    if isinstance(data, list) and len(data) > 50:
                        return data
            else:
                res = requests.get(url, timeout=12)
                if res.status_code == 200:
                    payload = res.json()

                    if "contents" in payload:
                        raw_contents = payload["contents"]
                        data = (
                            json.loads(raw_contents)
                            if isinstance(raw_contents, str)
                            else raw_contents
                        )
                    else:
                        data = payload

                    if isinstance(data, list) and len(data) > 50:
                        return data
        except Exception:
            continue

    return []


def process_market_summary(raw_summary, min_volume=0):
    """Processes 500+ stocks into quantitative scanner metrics."""
    records = []

    for item in raw_summary:
        try:
            symbol = str(
                item.get("code") or item.get("symbol") or ""
            ).strip().upper()
            if not symbol:
                continue

            close_p = float(item.get("close") or item.get("current") or 0.0)
            prev_close = float(item.get("prev") or item.get("previous") or close_p)
            vol = int(item.get("volume") or item.get("vol") or 0)
            high_p = float(item.get("high") or close_p)
            low_p = float(item.get("low") or close_p)
            change_pct = (
                ((close_p - prev_close) / prev_close) * 100
                if prev_close > 0
                else 0.0
            )

            # Volume filter logic (bypassed for Right Shares ending with 'R')
            if min_volume > 0 and vol < min_volume and not symbol.endswith("R"):
                continue

            # --- BTST QUANT SCORE ---
            btst_score = 0.0
            btst_tags = []

            clr = (
                (close_p - low_p) / (high_p - low_p)
                if (high_p - low_p) > 0
                else 0.8
            )
            if clr >= 0.75:
                btst_score += 1.5
                btst_tags.append("Strong High Close")

            if 1.0 <= change_pct <= 7.5:
                btst_score += 1.5
                btst_tags.append(f"+{change_pct:.1f}% Momentum")

            if vol > 100000 or symbol.endswith("R"):
                btst_score += 1.0
                btst_tags.append("Active Liquidity")

            # --- SWING QUANT SCORE ---
            swing_score = 0.0
            swing_tags = []

            if -3.0 <= change_pct <= 2.0:
                swing_score += 2.0
                swing_tags.append("Consolidation Zone")

            if vol > 50000:
                swing_score += 1.5
                swing_tags.append("Volume Support")

            if symbol.endswith("R") or close_p < 20.0:
                swing_score += 1.0
                swing_tags.append("Low Float / Right Share")

            records.append({
                "Ticker": symbol,
                "Close": round(close_p, 2),
                "Change %": round(change_pct, 2),
                "Volume": vol,
                "BTST_Score": round(min(btst_score, 5.0), 1),
                "BTST_Buy_Zone": f"{round(close_p * 0.99, 2)} - {round(close_p, 2)}",
                "BTST_Reason": (
                    " + ".join(btst_tags) if btst_tags else "Neutral setup"
                ),
                "Swing_Score": round(min(swing_score, 5.0), 1),
                "Swing_Buy_Zone": f"{round(close_p * 0.98, 2)} - {round(close_p * 1.01, 2)}",
                "Swing_Reason": (
                    " + ".join(swing_tags) if swing_tags else "Base structure"
                ),
            })
        except Exception:
            continue

    return pd.DataFrame(records)


# ==========================================
# 3. STREAMLIT INTERFACE
# ==========================================
st.sidebar.title("🇵🇰 PSX Engine")

strategy_view = st.sidebar.radio(
    "Select Mode:",
    [
        "⚡ BTST / Overnight Setups",
        "📈 Multi-Day Swing Setups",
        "🔍 Single Stock Search & Analysis",
    ],
)

st.sidebar.divider()

min_vol_input = st.sidebar.number_input(
    "Minimum Daily Volume Filter:",
    value=0,
    step=5000,
    help="Set to 0 to include micro-caps, low floats, and LOR right shares.",
)

st.sidebar.divider()

st.sidebar.markdown("### 💼 My Portfolio Manager")
edited_pf = st.sidebar.data_editor(
    st.session_state["portfolio"],
    num_rows="dynamic",
    use_container_width=True,
    key="pf_editor",
)
st.session_state["portfolio"] = edited_pf

st.sidebar.divider()

if st.sidebar.button("🚀 Fast Scan ALL PSX Equities & Rights", type="primary"):
    with st.spinner(
        "Bypassing Cloudflare WAF & fetching full PSX market summary..."
    ):
        raw_data = fetch_full_psx_market()
        if raw_data:
            st.session_state["scan_data"] = process_market_summary(
                raw_data, min_vol_input
            )
            st.session_state["scanned_count"] = len(
                st.session_state["scan_data"]
            )
            st.session_state["last_scan_time"] = time.strftime("%I:%M %p PKT")
        else:
            st.error(
                "Unable to fetch data. PSX endpoint unreachable from current IP."
            )

st.title("PSX All-Share Quant Scanner")

if "last_scan_time" in st.session_state:
    st.caption(
        f"Last Scan Executed: **{st.session_state['last_scan_time']}** | Total Active Equities Captured: **{st.session_state.get('scanned_count', 0)}**"
    )

if "scan_data" in st.session_state and not st.session_state["scan_data"].empty:
    df_raw = st.session_state["scan_data"]
    user_symbols = [
        str(s).upper() for s in st.session_state["portfolio"]["Symbol"].dropna()
    ]
    pf_matches = df_raw[df_raw["Ticker"].isin(user_symbols)].copy()

    if not pf_matches.empty:
        with st.expander("💼 My Portfolio Technical Breakdown", expanded=True):
            st.dataframe(
                pf_matches[[
                    "Ticker",
                    "Close",
                    "Change %",
                    "Volume",
                    "BTST_Score",
                    "BTST_Buy_Zone",
                    "Swing_Score",
                    "Swing_Buy_Zone",
                ]],
                use_container_width=True,
            )

# MODE 1: BTST STRATEGY
if strategy_view == "⚡ BTST / Overnight Setups":
    st.header("⚡ BTST Candidates (Buy Today 3:15 PM, Sell Tomorrow)")
    st.caption("Evaluates all 500+ equities, micro-caps, and LOR right shares.")

    if "scan_data" not in st.session_state or st.session_state["scan_data"].empty:
        st.info(
            "Click **'Fast Scan ALL PSX Equities & Rights'** in the sidebar to load all 500+ stocks."
        )
    else:
        btst_df = df_raw[df_raw["BTST_Score"] >= 2.0].sort_values(
            by="BTST_Score", ascending=False
        )

        if not btst_df.empty:
            btst_df["Target (+3.0%)"] = (btst_df["Close"] * 1.03).round(2)
            btst_df["Stop Loss (-1.8%)"] = (btst_df["Close"] * 0.982).round(2)

            st.dataframe(
                btst_df[[
                    "Ticker",
                    "Close",
                    "Change %",
                    "Volume",
                    "BTST_Buy_Zone",
                    "Target (+3.0%)",
                    "Stop Loss (-1.8%)",
                    "BTST_Score",
                    "BTST_Reason",
                ]],
                use_container_width=True,
            )
        else:
            st.info("No stocks currently meet BTST thresholds.")

# MODE 2: MULTI-DAY SWING STRATEGY
elif strategy_view == "📈 Multi-Day Swing Setups":
    st.header("📈 Swing Trade Setups (2–10 Days Horizon)")
    st.caption("Filters market for support floors and low-float volume setups.")

    if "scan_data" not in st.session_state or st.session_state["scan_data"].empty:
        st.info(
            "Click **'Fast Scan ALL PSX Equities & Rights'** in the sidebar to load all 500+ stocks."
        )
    else:
        swing_df = df_raw[df_raw["Swing_Score"] >= 2.0].sort_values(
            by="Swing_Score", ascending=False
        )

        if not swing_df.empty:
            swing_df["Target (+8.5%)"] = (swing_df["Close"] * 1.085).round(2)
            swing_df["Stop Loss (-4.5%)"] = (swing_df["Close"] * 0.955).round(2)

            st.dataframe(
                swing_df[[
                    "Ticker",
                    "Close",
                    "Change %",
                    "Volume",
                    "Swing_Buy_Zone",
                    "Target (+8.5%)",
                    "Stop Loss (-4.5%)",
                    "Swing_Score",
                    "Swing_Reason",
                ]],
                use_container_width=True,
            )
        else:
            st.warning("No stocks currently meet Swing thresholds.")

# MODE 3: SINGLE STOCK LOOKUP
elif strategy_view == "🔍 Single Stock Search & Analysis":
    st.header("🔍 Individual Stock & Right Shares Lookup")

    search_input = st.text_input(
        "Enter ANY PSX Ticker (e.g., SGPLR, WAVESAPPR, CLVL, LEUL, ADMM):",
        "CLVL",
    )

    if search_input:
        clean_sym = search_input.strip().upper()
        if "scan_data" in st.session_state and not st.session_state["scan_data"].empty:
            match = df_raw[df_raw["Ticker"] == clean_sym]
            if not match.empty:
                res = match.iloc[0]
                c1, c2, c3 = st.columns(3)
                c1.metric(
                    "Current Price",
                    f"PKR {res['Close']}",
                    f"{res['Change %']}%",
                )
                c2.metric("BTST Score", f"{res['BTST_Score']} / 5.0")
                c3.metric("Swing Score", f"{res['Swing_Score']} / 5.0")

                st.divider()

                col_a, col_b = st.columns(2)
                with col_a:
                    st.subheader("⚡ BTST Strategy Setup")
                    st.write(f"**Optimal Buy Zone:** PKR {res['BTST_Buy_Zone']}")
                    st.write(
                        f"**Target (+3.0%):** PKR {round(res['Close'] * 1.03, 2)}"
                    )
                    st.write(
                        f"**Stop Loss (-1.8%):** PKR {round(res['Close'] * 0.982, 2)}"
                    )
                    st.info(f"**Reasoning:** {res['BTST_Reason']}")

                with col_b:
                    st.subheader("📈 Swing Strategy Setup")
                    st.write(f"**Optimal Buy Zone:** PKR {res['Swing_Buy_Zone']}")
                    st.write(
                        f"**Target (+8.5%):** PKR {round(res['Close'] * 1.085, 2)}"
                    )
                    st.write(
                        f"**Stop Loss (-4.5%):** PKR {round(res['Close'] * 0.955, 2)}"
                    )
                    st.info(f"**Reasoning:** {res['Swing_Reason']}")
            else:
                st.error(
                    f"Ticker '{clean_sym}' not found in current market scan."
                )
        else:
            st.info("Run the scan first using the sidebar button.")

# MASTER OVERVIEW TABLE
if "scan_data" in st.session_state and not st.session_state["scan_data"].empty:
    with st.expander("📋 View Complete Scanned PSX Market (All Tickers)"):
        st.dataframe(
            df_raw[[
                "Ticker",
                "Close",
                "Change %",
                "Volume",
                "BTST_Score",
                "BTST_Buy_Zone",
                "BTST_Reason",
                "Swing_Score",
                "Swing_Buy_Zone",
                "Swing_Reason",
            ]],
            use_container_width=True,
        )
        
