import time
import pandas as pd
import requests
import streamlit as st
import yfinance as yf

# ==========================================
# 1. PAGE SETUP & STYLING
# ==========================================
st.set_page_config(
    page_title="PSX Whole Market Quant Scanner",
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
        ]
    )


# ==========================================
# 2. DYNAMIC FULL PSX UNIVERSE (DYNAMIC + FALLBACK)
# ==========================================
@st.cache_data(ttl=43200)
def get_full_psx_universe():
    """Fetches active PSX traded equities dynamically from DPS API + static master list."""
    master_list = [
        # Commercial Banks & Financials
        "MCB", "UBL", "MEBL", "HBL", "BAFL", "BOP", "FABL", "AKBL", "NBP", "BIPL", "SNBL", "JSBL", "SPL", "SILK",
        # Exploration, Marketing & Refineries
        "OGDC", "PPL", "MARI", "POL", "PSO", "SHEL", "SNGP", "SSGC", "APL", "HASCOL", "HTL", "ATRL", "NRL", "PRL", "CNERGY",
        # Fertilizer & Chemicals
        "EFERT", "FFC", "ENGRO", "FFBL", "FATIMA", "EPCL", "AGP", "SEARL", "ABOT", "GLAXO", "PAKOXY", "COLG", "ARCH", "ICI", "LOTCHEM", "GTYR", "BAPL", "DOL", "DYNO", "DAAG",
        # Cement & Materials
        "LUCK", "DGKC", "KOHC", "PIOC", "CHCC", "FCCL", "ACPL", "DCL", "POWER", "THCCL", "BWCL", "FLYNG", "SMC",
        # Tech, Telecom & Media
        "SYS", "TRG", "AIRLINK", "AVN", "OCTOPUS", "PTC", "WTL", "TELE", "HUMNL", "INBOX", "TPLP", "TPL", "NETSOL",
        # Power, Energy & Utilities
        "HUBC", "KAPCO", "KEL", "NCPL", "EPQL", "SPWL", "LPL", "ALTN", "SEL", "TRIBL",
        # Autos, Engineering & Steel
        "MUGHAL", "ASL", "GHNI", "PAEL", "MTL", "SAZEW", "PSMC", "LOADS", "GANI", "STPL", "CWSM", "ISL", "ASTL", "CSAP", "DFML",
        # Textiles & Apparel
        "ILP", "NML", "NCL", "GATM", "KTML", "TREET", "HAEL", "CRTM", "ANL", "BUXL", "KOHE", "MSOT",
        # Sugar, Food, Glass & Misc
        "TGL", "UNITY", "PNSC", "SCL", "MUREB", "STCL", "GHGL", "NESTLE", "NATF", "SHEZ", "SML", "JDWS", "TARC"
    ]

    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get("https://dps.psx.com.pk/data/summary", headers=headers, timeout=8)
        if res.status_code == 200:
            data = res.json()
            api_symbols = [
                str(item.get("code")).strip().upper() 
                for item in data 
                if item.get("code") and str(item.get("code")).isalnum() and len(str(item.get("code"))) <= 8
            ]
            master_list = list(set(master_list + api_symbols))
    except Exception:
        pass

    return sorted([f"{sym}.KA" for sym in set(master_list)])


# ==========================================
# 3. QUANT ENGINE MODEL (PHYSICS & CONFLUENCE)
# ==========================================
def calculate_swing_score(df_daily):
    """Multi-Day Swing Strategy (Hold 2-10 Days): 40D Support Floor + Volume Absorption."""
    if df_daily is None or len(df_daily) < 40:
        return 0.0, "Insufficient history", "N/A"

    score = 0.0
    tags = []
    last_bar = df_daily.iloc[-1]
    close_p = float(last_bar["Close"])

    low_40d = float(df_daily["Low"].tail(40).min())
    if close_p <= low_40d * 1.05:
        score += 2.0
        tags.append("Near 40D Support Floor")

    vol_20d_avg = df_daily["Volume"].tail(20).mean()
    vol_today = float(last_bar["Volume"])
    atr14 = (df_daily["High"] - df_daily["Low"]).rolling(14).mean().iloc[-1]
    body_size = abs(close_p - float(last_bar["Open"]))

    if vol_today > (vol_20d_avg * 1.2) and body_size < atr14:
        score += 1.5
        tags.append("Kinetic Volume Absorption")

    sma20 = df_daily["Close"].rolling(20).mean().iloc[-1]
    std20 = df_daily["Close"].rolling(20).std().iloc[-1]
    lower_band = sma20 - (2 * std20)

    if close_p <= lower_band * 1.02:
        score += 1.5
        tags.append("Bollinger Lower Expansion Touch")

    buy_zone = f"{round(close_p * 0.98, 2)} - {round(close_p * 1.01, 2)}"
    reason = " + ".join(tags) if tags else "No swing confluence"

    return min(score, 5.0), reason, buy_zone


def calculate_btst_score(df_daily):
    """BTST Overnight Strategy (Physics Model: Momentum & HOD Close Pressure)."""
    if df_daily is None or len(df_daily) < 15:
        return 0.0, "Insufficient history", "N/A"

    score = 0.0
    tags = []
    last_bar = df_daily.iloc[-1]
    prev_close = float(df_daily["Close"].iloc[-2])

    close_p = float(last_bar["Close"])
    high_p = float(last_bar["High"])
    low_p = float(last_bar["Low"])
    vol_today = float(last_bar["Volume"])

    clr = (close_p - low_p) / (high_p - low_p) if (high_p - low_p) > 0 else 0
    if clr >= 0.85:
        score += 1.5
        tags.append("Close Near HOD")
    elif clr >= 0.70:
        score += 0.75
        tags.append("Strong Close Position")

    vol_10d_avg = df_daily["Volume"].iloc[-11:-1].mean()
    rvol = vol_today / vol_10d_avg if vol_10d_avg > 0 else 0

    if rvol >= 1.8:
        score += 1.5
        tags.append(f"Institutional Vol Surge ({rvol:.1f}x)")
    elif rvol >= 1.3:
        score += 0.75
        tags.append(f"Above Avg Vol ({rvol:.1f}x)")

    daily_pct = ((close_p - prev_close) / prev_close) * 100
    if 2.0 <= daily_pct <= 6.5:
        score += 1.0
        tags.append(f"+{daily_pct:.1f}% Momentum")

    ema20 = df_daily["Close"].ewm(span=20).mean().iloc[-1]
    if close_p > ema20:
        score += 1.0
        tags.append("Above 20-EMA")

    buy_zone = f"{round(close_p * 0.99, 2)} - {round(close_p, 2)}"
    reason = " + ".join(tags) if tags else "No BTST momentum"

    return min(score, 5.0), reason, buy_zone


# ==========================================
# 4. RESILIENT FULL MARKET SCANNER ENGINE
# ==========================================
def process_single_dataframe(df, clean_code, min_volume=25000):
    """Processes stock dataframe, applies liquidity filter, and calculates scores."""
    try:
        if df.empty or len(df) < 15:
            return None

        curr_close = float(df["Close"].iloc[-1])
        curr_vol = int(df["Volume"].iloc[-1])

        # Liquidity Safeguard for Small-Caps
        if curr_vol < min_volume:
            return None

        s_score, s_reason, s_buy = calculate_swing_score(df)
        b_score, b_reason, b_buy = calculate_btst_score(df)

        return {
            "Ticker": clean_code,
            "Close": round(curr_close, 2),
            "Volume": curr_vol,
            "Swing_Score": round(s_score, 1),
            "Swing_Buy_Zone": s_buy,
            "Swing_Reason": s_reason,
            "BTST_Score": round(b_score, 1),
            "BTST_Buy_Zone": b_buy,
            "BTST_Reason": b_reason,
        }
    except Exception:
        return None


def run_full_psx_scan(tickers, min_volume):
    results = []
    progress_bar = st.progress(0)
    status_text = st.empty()

    batch_size = 20
    total = len(tickers)

    for i in range(0, total, batch_size):
        batch = tickers[i : i + batch_size]
        batch_str = " ".join(batch)

        try:
            data = yf.download(
                batch_str, period="60d", group_by="ticker", progress=False, threads=True
            )

            for sym in batch:
                clean_code = sym.replace(".KA", "").upper()
                try:
                    if len(batch) == 1:
                        df = data.copy()
                    else:
                        df = data[sym].dropna()

                    res = process_single_dataframe(df, clean_code, min_volume)
                    if res:
                        results.append(res)
                except Exception:
                    # Single-ticker fallback isolation loop
                    try:
                        single_df = yf.Ticker(sym).history(period="60d")
                        res = process_single_dataframe(single_df, clean_code, min_volume)
                        if res:
                            results.append(res)
                    except Exception:
                        continue
        except Exception:
            pass

        percent = min(int(((i + batch_size) / total) * 100), 100)
        progress_bar.progress(percent)
        status_text.text(f"Scanning Full PSX Market Universe: {min(i + batch_size, total)}/{total} stocks processed")

    status_text.empty()
    progress_bar.empty()
    return pd.DataFrame(results)


# ==========================================
# 5. STREAMLIT INTERFACE & ROUTING
# ==========================================
st.sidebar.title("🇵🇰 PSX Full Quant Engine")

strategy_view = st.sidebar.radio(
    "Select Mode:",
    [
        "⚡ BTST / Overnight Setups",
        "📈 Multi-Day Swing Setups (2–10 Days)",
        "🔍 Single Stock Search & Analysis",
    ],
)

st.sidebar.divider()

min_vol_input = st.sidebar.number_input(
    "Minimum Daily Volume Filter:",
    value=25000,
    step=10000,
    help="Filters out illiquid penny or non-traded stocks to prevent high slippage.",
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

if st.sidebar.button("🚀 Scan Entire PSX Market", type="primary"):
    ticker_list = get_full_psx_universe()
    st.session_state["scan_data"] = run_full_psx_scan(ticker_list, min_vol_input)
    st.session_state["scanned_count"] = len(st.session_state["scan_data"])
    st.session_state["last_scan_time"] = time.strftime("%I:%M %p PKT")

st.title("PSX Whole Market Quantitative Scanner")

if "last_scan_time" in st.session_state:
    st.caption(
        f"Last Scan Executed: **{st.session_state['last_scan_time']}** | Scanned Active Stocks: **{st.session_state.get('scanned_count', 0)}**"
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
                pf_matches[
                    [
                        "Ticker",
                        "Close",
                        "Volume",
                        "BTST_Score",
                        "BTST_Buy_Zone",
                        "Swing_Score",
                        "Swing_Buy_Zone",
                    ]
                ],
                use_container_width=True,
            )

# MODE 1: BTST STRATEGY
if strategy_view == "⚡ BTST / Overnight Setups":
    st.header("⚡ BTST Candidates (Buy Today 3:15 PM, Sell Tomorrow)")
    st.caption("Filters all PSX stocks for late-session volume spikes and close pressure. **Threshold: Score ≥ 3.0**")

    if "scan_data" not in st.session_state or st.session_state["scan_data"].empty:
        st.info("Click **'Scan Entire PSX Market'** in the sidebar to initiate the scan.")
    else:
        btst_df = df_raw[df_raw["BTST_Score"] >= 3.0].copy()

        if not btst_df.empty:
            btst_df["Target (+3.0%)"] = (btst_df["Close"] * 1.03).round(2)
            btst_df["Stop Loss (-1.8%)"] = (btst_df["Close"] * 0.982).round(2)

            st.dataframe(
                btst_df[
                    [
                        "Ticker",
                        "Close",
                        "Volume",
                        "BTST_Buy_Zone",
                        "Target (+3.0%)",
                        "Stop Loss (-1.8%)",
                        "BTST_Score",
                        "BTST_Reason",
                    ]
                ],
                use_container_width=True,
            )
        else:
            st.info("No PSX stocks currently cross the BTST Threshold (Score ≥ 3.0).")

# MODE 2: MULTI-DAY SWING STRATEGY
elif strategy_view == "📈 Multi-Day Swing Setups (2–10 Days)":
    st.header("📈 Swing Trade Setups (2–10 Days Holding Horizon)")
    st.caption("Scans whole PSX market for 40-day support floors and volume absorption. **Threshold: Score ≥ 3.0**")

    if "scan_data" not in st.session_state or st.session_state["scan_data"].empty:
        st.info("Click **'Scan Entire PSX Market'** in the sidebar to initiate the scan.")
    else:
        swing_df = df_raw[df_raw["Swing_Score"] >= 3.0].copy()

        if not swing_df.empty:
            swing_df["Target (+8.5%)"] = (swing_df["Close"] * 1.085).round(2)
            swing_df["Stop Loss (-4.5%)"] = (swing_df["Close"] * 0.955).round(2)

            st.dataframe(
                swing_df[
                    [
                        "Ticker",
                        "Close",
                        "Volume",
                        "Swing_Buy_Zone",
                        "Target (+8.5%)",
                        "Stop Loss (-4.5%)",
                        "Swing_Score",
                        "Swing_Reason",
                    ]
                ],
                use_container_width=True,
            )
        else:
            st.warning("No PSX stocks currently cross the Swing Threshold (Score ≥ 3.0).")

# MODE 3: SINGLE STOCK SEARCH
elif strategy_view == "🔍 Single Stock Search & Analysis":
    st.header("🔍 Individual PSX Stock Analysis")

    search_input = st.text_input("Enter ANY PSX Ticker (e.g., BUXL, PAEL, SYS, ASL, ARCH):", "BUXL")

    if search_input:
        symbol = f"{search_input.strip().upper()}.KA"
        with st.spinner(f"Analyzing {symbol}..."):
            try:
                single_df = yf.Ticker(symbol).history(period="60d")
                res = process_single_dataframe(single_df, search_input.strip().upper(), min_volume=0)

                if res:
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Current Price", f"PKR {res['Close']}")
                    c2.metric("BTST Score", f"{res['BTST_Score']} / 5.0")
                    c3.metric("Swing Score", f"{res['Swing_Score']} / 5.0")

                    st.divider()

                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.subheader("⚡ BTST Strategy Setup")
                        st.write(f"**Optimal Buy Zone:** PKR {res['BTST_Buy_Zone']}")
                        st.write(f"**Target (+3.0%):** PKR {round(res['Close'] * 1.03, 2)}")
                        st.write(f"**Stop Loss (-1.8%):** PKR {round(res['Close'] * 0.982, 2)}")
                        st.info(f"**Reasoning:** {res['BTST_Reason']}")

                    with col_b:
                        st.subheader("📈 Swing Strategy Setup")
                        st.write(f"**Optimal Buy Zone:** PKR {res['Swing_Buy_Zone']}")
                        st.write(f"**Target (+8.5%):** PKR {round(res['Close'] * 1.085, 2)}")
                        st.write(f"**Stop Loss (-4.5%):** PKR {round(res['Close'] * 0.955, 2)}")
                        st.info(f"**Reasoning:** {res['Swing_Reason']}")
                else:
                    st.error(f"Could not fetch historical data for '{search_input}'.")
            except Exception as e:
                st.error(f"Error executing lookup: {str(e)}")

# Master Overview
if "scan_data" in st.session_state and not st.session_state["scan_data"].empty:
    with st.expander("📋 View Complete Scanned PSX Universe (All Tickers)"):
        st.dataframe(
            df_raw[
                [
                    "Ticker",
                    "Close",
                    "Volume",
                    "BTST_Score",
                    "BTST_Buy_Zone",
                    "BTST_Reason",
                    "Swing_Score",
                    "Swing_Buy_Zone",
                    "Swing_Reason",
                ]
            ],
            use_container_width=True,
        )
