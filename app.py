import concurrent.futures
import time
import numpy as np
import pandas as pd
import requests
import streamlit as st
import yfinance as yf

# ==========================================
# 1. PAGE SETUP & CONFIGURATION
# ==========================================
st.set_page_config(
    page_title="PSX Dual-Strategy Quant Engine",
    page_icon="🇵🇰",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS Styling
st.markdown(
    """
    <style>
    .main { padding: 1.5rem; }
    .stMetric { background-color: #0f172a; border-radius: 8px; padding: 10px; border: 1px solid #1e293b; }
    </style>
""",
    unsafe_allow_html=True,
)

# Initialize Portfolio in Session State if not present
if "portfolio" not in st.session_state:
    st.session_state["portfolio"] = pd.DataFrame(
        [
            {"Symbol": "SYS", "Avg Price": 129.00, "Shares": 1000},
            {"Symbol": "ASL", "Avg Price": 16.95, "Shares": 5000},
        ]
    )


# ==========================================
# 2. TICKER LIST RETRIEVAL (FULL PSX MARKET)
# ==========================================
@st.cache_data(ttl=3600)
def get_psx_tickers():
    """Fetches ALL active symbols directly from PSX Data Portal."""
    url = "https://dps.psx.com.pk/data/summary"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            df = pd.DataFrame(response.json())
            symbols = df["code"].tolist()
            # Returns ALL valid symbols (Scans entire ~500+ stock universe)
            yf_symbols = [f"{sym}.KA" for sym in symbols if str(sym).isalnum()]
            return yf_symbols
    except Exception:
        pass

    # Fallback liquid universe if scraping network fails
    return [
        "SYS.KA",
        "ASL.KA",
        "GHNI.KA",
        "LUCK.KA",
        "TRG.KA",
        "OGDC.KA",
        "PPL.KA",
        "DGKC.KA",
        "ENGRO.KA",
        "MCB.KA",
        "UBL.KA",
        "MEBL.KA",
        "EFERT.KA",
        "PSO.KA",
        "SHEL.KA",
        "MUGHAL.KA",
        "INBOX.KA",
        "AGP.KA",
        "KAPCO.KA",
        "HUBC.KA",
    ]


# ==========================================
# 3. QUANTITATIVE SCORING ENGINES
# ==========================================


def calculate_swing_score(df_daily):
    """Multi-Day Swing Strategy (Physics Modeling: Kinetic Absorption & Support)."""
    if df_daily is None or len(df_daily) < 40:
        return 0.0, ["Insufficient Data (<40 bars)"]

    score = 0.0
    reasons = []

    last_bar = df_daily.iloc[-1]
    close_p = float(last_bar["Close"])

    # A. Structural Support Floor (40-day low proximity)
    low_40d = float(df_daily["Low"].tail(40).min())
    if close_p <= low_40d * 1.05:
        score += 2.0
        reasons.append("Holding Near 40-Day Structural Support Floor")

    # B. Kinetic Absorption Force (Volume & Volatility Compression)
    vol_20d_avg = df_daily["Volume"].tail(20).mean()
    vol_today = float(last_bar["Volume"])
    atr14 = (df_daily["High"] - df_daily["Low"]).rolling(14).mean().iloc[-1]
    body_size = abs(close_p - float(last_bar["Open"]))

    if vol_today > (vol_20d_avg * 1.2) and body_size < atr14:
        score += 1.5
        reasons.append("Kinetic Volume Absorption Detected")

    # C. Bollinger Band Lower Touch (Squeeze Reversal)
    sma20 = df_daily["Close"].rolling(20).mean().iloc[-1]
    std20 = df_daily["Close"].rolling(20).std().iloc[-1]
    lower_band = sma20 - (2 * std20)

    if close_p <= lower_band * 1.02:
        score += 1.5
        reasons.append("Bollinger Band Lower Expansion Touch")

    return min(score, 5.0), reasons


def calculate_btst_score(df_daily):
    """BTST Strategy (Overnight Late-Session Momentum & Volume Surge)."""
    if df_daily is None or len(df_daily) < 15:
        return 0.0, ["Insufficient Data (<15 bars)"]

    score = 0.0
    reasons = []

    last_bar = df_daily.iloc[-1]
    prev_close = float(df_daily["Close"].iloc[-2])

    close_p = float(last_bar["Close"])
    high_p = float(last_bar["High"])
    low_p = float(last_bar["Low"])
    vol_today = float(last_bar["Volume"])

    # 1. Close Location Ratio (CLR): Is stock closing near HOD?
    clr = (close_p - low_p) / (high_p - low_p) if (high_p - low_p) > 0 else 0
    if clr >= 0.85:
        score += 1.5
        reasons.append(f"Closing near HOD (CLR: {clr:.2f})")
    elif clr >= 0.70:
        score += 0.75
        reasons.append(f"Strong Close Location (CLR: {clr:.2f})")

    # 2. Relative Volume (RVOL) vs 10-day Average
    vol_10d_avg = df_daily["Volume"].iloc[-11:-1].mean()
    rvol = vol_today / vol_10d_avg if vol_10d_avg > 0 else 0

    if rvol >= 1.8:
        score += 1.5
        reasons.append(f"Institutional Volume Surge ({rvol:.2f}x)")
    elif rvol >= 1.3:
        score += 0.75
        reasons.append(f"Above Avg Volume ({rvol:.2f}x)")

    # 3. Daily Gain Check (Targeting +2.0% to +6.5%, avoiding upper lock traps)
    daily_pct = ((close_p - prev_close) / prev_close) * 100
    if 2.0 <= daily_pct <= 6.5:
        score += 1.0
        reasons.append(f"Healthy Intraday Momentum (+{daily_pct:.2f}%)")

    # 4. Moving Average Trend Alignment
    ema20 = df_daily["Close"].ewm(span=20).mean().iloc[-1]
    if close_p > ema20:
        score += 1.0
        reasons.append("Price Above 20-Day EMA")

    return min(score, 5.0), reasons


# ==========================================
# 4. PARALLEL THREADED DATA WORKER
# ==========================================


def process_single_ticker(symbol):
    """Worker function to fetch data and process both scoring engines."""
    clean_code = symbol.replace(".KA", "").upper()
    try:
        ticker_obj = yf.Ticker(symbol)
        df = ticker_obj.history(period="60d")

        if df.empty or len(df) < 15:
            return None

        curr_close = float(df["Close"].iloc[-1])
        curr_vol = int(df["Volume"].iloc[-1])

        # Execute Scoring Systems
        s_score, s_reasons = calculate_swing_score(df)
        b_score, b_reasons = calculate_btst_score(df)

        return {
            "Ticker": clean_code,
            "Close": round(curr_close, 2),
            "Volume": curr_vol,
            "Swing_Score": round(s_score, 1),
            "Swing_Reasons": ", ".join(s_reasons),
            "BTST_Score": round(b_score, 1),
            "BTST_Reasons": ", ".join(b_reasons),
        }
    except Exception:
        return None


def run_full_market_scan(tickers):
    """Executes multi-threaded processing across all PSX tickers."""
    results = []
    progress_bar = st.progress(0)
    status_text = st.empty()

    total = len(tickers)

    # Scans all ~500 stocks faster with 20 threads
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        future_to_ticker = {
            executor.submit(process_single_ticker, sym): sym for sym in tickers
        }

        for i, future in enumerate(
            concurrent.futures.as_completed(future_to_ticker)
        ):
            res = future.result()
            if res:
                results.append(res)

            percent = int(((i + 1) / total) * 100)
            progress_bar.progress(percent)
            status_text.text(f"Scanning Full PSX Universe: {i + 1}/{total} stocks")

    status_text.empty()
    progress_bar.empty()
    return pd.DataFrame(results)


# ==========================================
# 5. STREAMLIT USER INTERFACE & NAVIGATION
# ==========================================

# Sidebar Controls
st.sidebar.title("🇵🇰 PSX Quant Engine")
st.sidebar.caption("Free Data Pipeline • Multi-Strategy Scanner")

strategy_view = st.sidebar.radio(
    "Select Mode:",
    [
        "📈 Multi-Day Swing (EOD)",
        "⚡ BTST / Overnight (Free Feed)",
        "🔍 Single Stock Search & Analysis",
    ],
)

st.sidebar.divider()

# Editable Portfolio Module
st.sidebar.markdown("### 💼 My Portfolio Manager")
edited_pf = st.sidebar.data_editor(
    st.session_state["portfolio"],
    num_rows="dynamic",
    use_container_width=True,
    key="pf_editor",
)
st.session_state["portfolio"] = edited_pf

st.sidebar.divider()

if st.sidebar.button("🚀 Run Full Market Scan", type="primary"):
    ticker_list = get_psx_tickers()
    st.session_state["scan_data"] = run_full_market_scan(ticker_list)
    st.session_state["last_scan_time"] = time.strftime("%I:%M %p PKT")

# Main Dashboard View
st.title("PSX Quantitative Trading Dashboard")

if "last_scan_time" in st.session_state:
    st.caption(f"Last Scan Executed at: **{st.session_state['last_scan_time']}**")

# Portfolio Analysis Banner if Scan Data Exists
if "scan_data" in st.session_state and not st.session_state["scan_data"].empty:
    df_raw = st.session_state["scan_data"]

    # Check Portfolio Holdings against Market Scan
    user_symbols = [
        str(s).upper() for s in st.session_state["portfolio"]["Symbol"].dropna()
    ]
    pf_matches = df_raw[df_raw["Ticker"].isin(user_symbols)].copy()

    if not pf_matches.empty:
        with st.expander(
            "💼 Portfolio Analysis & Current Setup Status", expanded=True
        ):
            st.dataframe(
                pf_matches[
                    [
                        "Ticker",
                        "Close",
                        "Swing_Score",
                        "BTST_Score",
                        "Swing_Reasons",
                        "BTST_Reasons",
                    ]
                ],
                use_container_width=True,
            )

# ROUTE 1: MULTI-DAY SWING MODE
if strategy_view == "📈 Multi-Day Swing (EOD)":
    st.header("📈 Multi-Day Swing Setups (Hold 2–10 Days)")
    st.write(
        "Identifies structural support floors and kinetic volume absorption. **Threshold: Score ≥ 3.0**"
    )

    if (
        "scan_data" not in st.session_state
        or st.session_state["scan_data"].empty
    ):
        st.info("Click **'Run Full Market Scan'** in the sidebar to fetch data.")
    else:
        swing_df = df_raw[df_raw["Swing_Score"] >= 3.0].copy()

        if not swing_df.empty:
            swing_df["Target (+8.5%)"] = (swing_df["Close"] * 1.085).round(2)
            swing_df["Stop Loss (-4.5%)"] = (swing_df["Close"] * 0.955).round(2)

            col1, col2 = st.columns(2)
            col1.metric("Qualified Swing Setups", len(swing_df))
            col2.metric("Scan Universe", len(df_raw))

            st.dataframe(
                swing_df[
                    [
                        "Ticker",
                        "Swing_Score",
                        "Close",
                        "Target (+8.5%)",
                        "Stop Loss (-4.5%)",
                        "Volume",
                        "Swing_Reasons",
                    ]
                ],
                use_container_width=True,
            )
        else:
            st.warning("No stocks currently cross Swing Threshold (Score ≥ 3.0).")

# ROUTE 2: BTST OVERNIGHT MODE
elif strategy_view == "⚡ BTST / Overnight (Free Feed)":
    st.header("⚡ BTST Candidates (Buy Today 3:15 PM, Sell Tomorrow 10:00 AM)")
    st.caption(
        "Identifies late-session volume expansion and HOD closes. **Optimal window: 2:45 PM – 3:15 PM PKT**."
    )

    if (
        "scan_data" not in st.session_state
        or st.session_state["scan_data"].empty
    ):
        st.info("Click **'Run Full Market Scan'** in the sidebar to fetch data.")
    else:
        btst_df = df_raw[df_raw["BTST_Score"] >= 3.0].copy()

        if not btst_df.empty:
            btst_df["BTST Target (+3.0%)"] = (btst_df["Close"] * 1.03).round(2)
            btst_df["BTST Stop Loss (-1.8%)"] = (
                btst_df["Close"] * 0.982
            ).round(2)

            col1, col2 = st.columns(2)
            col1.metric("BTST Overnight Opportunities", len(btst_df))
            col2.metric("Scan Universe", len(df_raw))

            st.dataframe(
                btst_df[
                    [
                        "Ticker",
                        "BTST_Score",
                        "Close",
                        "BTST Target (+3.0%)",
                        "BTST Stop Loss (-1.8%)",
                        "Volume",
                        "BTST_Reasons",
                    ]
                ],
                use_container_width=True,
            )
        else:
            st.info(
                "No tickers meet the BTST confluence threshold (Score ≥ 3.0) right now."
            )

# ROUTE 3: SINGLE STOCK SEARCH & ANALYSIS
elif strategy_view == "🔍 Single Stock Search & Analysis":
    st.header("🔍 Individual Stock Technical Lookup")
    st.write(
        "Analyze any stock on the Pakistan Stock Exchange instantly without running a full market scan."
    )

    search_input = st.text_input(
        "Enter PSX Symbol (e.g., SYS, ASL, LUCK, TRG):", "SYS"
    )

    if search_input:
        symbol = f"{search_input.strip().upper()}.KA"
        with st.spinner(f"Analyzing {symbol}..."):
            stock_result = process_single_ticker(symbol)

        if stock_result:
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Current Price", f"PKR {stock_result['Close']}")
            col2.metric("Daily Volume", f"{stock_result['Volume']:,}")
            col3.metric("Swing Score", f"{stock_result['Swing_Score']} / 5.0")
            col4.metric("BTST Score", f"{stock_result['BTST_Score']} / 5.0")

            st.divider()

            c1, c2 = st.columns(2)
            with c1:
                st.subheader("📈 Swing Strategy Details")
                st.write(
                    f"**Target (+8.5%):** PKR {round(stock_result['Close'] * 1.085, 2)}"
                )
                st.write(
                    f"**Stop Loss (-4.5%):** PKR {round(stock_result['Close'] * 0.955, 2)}"
                )
                st.info(f"**Reasons:** {stock_result['Swing_Reasons']}")

            with c2:
                st.subheader("⚡ BTST Strategy Details")
                st.write(
                    f"**BTST Target (+3.0%):** PKR {round(stock_result['Close'] * 1.03, 2)}"
                )
                st.write(
                    f"**BTST Stop Loss (-1.8%):** PKR {round(stock_result['Close'] * 0.982, 2)}"
                )
                st.info(f"**Reasons:** {stock_result['BTST_Reasons']}")
        else:
            st.error(
                f"Could not fetch data for symbol '{search_input}'. Please check the symbol and try again."
            )

# Bottom Reference Table (if scan executed)
if "scan_data" in st.session_state and not st.session_state["scan_data"].empty:
    with st.expander("📋 View Complete Market Analysis (All Scanned Tickers)"):
        st.dataframe(
            df_raw[
                [
                    "Ticker",
                    "Close",
                    "Swing_Score",
                    "BTST_Score",
                    "Volume",
                    "Swing_Reasons",
                    "BTST_Reasons",
                ]
            ],
            use_container_width=True,
    )
        
