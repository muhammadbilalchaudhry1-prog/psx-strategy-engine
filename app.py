import concurrent.futures
import time
import pandas as pd
import requests
import streamlit as st
import yfinance as yf

# ==========================================
# 1. PAGE SETUP & STYLING
# ==========================================
st.set_page_config(
    page_title="PSX Quant Engine",
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

# Portfolio Session State
if "portfolio" not in st.session_state:
    st.session_state["portfolio"] = pd.DataFrame(
        [
            {"Symbol": "SYS", "Avg Price": 129.00, "Shares": 1000},
            {"Symbol": "ASL", "Avg Price": 16.95, "Shares": 5000},
        ]
    )

# ==========================================
# 2. TICKER LIST (BROAD PSX LIQUID UNIVERSE)
# ==========================================
@st.cache_data(ttl=86400)
def get_psx_tickers():
    """Returns top 100+ active PSX stocks for dependable scanning."""
    raw_tickers = [
        "SYS", "ASL", "GHNI", "LUCK", "TRG", "OGDC", "PPL", "DGKC", "ENGRO", "MCB",
        "UBL", "MEBL", "EFERT", "PSO", "SHEL", "MUGHAL", "AGP", "HUBC", "KEL", "PRL",
        "CNERGY", "PAEL", "EPCL", "GTYR", "AIRLINK", "TGL", "FFC", "HBL", "ABOT",
        "KOHC", "PIOC", "CHCC", "FCCL", "DCL", "ATRL", "NRL", "SEARL", "SAZEW",
        "MTL", "INBOX", "PSMC", "GHGL", "TPLP", "TREET", "BOP", "FABL", "BAFL",
        "AKBL", "NBP", "AVN", "OCTOPUS", "NCPL", "EPQL", "KAPCO", "SNGP", "SSGC",
        "MARI", "POL", "HUMNL", "TELE", "WTL", "LOADS", "GATM", "NML", "NCL",
        "ILP", "KTML", "PAKOXY", "BIPL", "SCL", "COLG", "UNITY", "HASCOL",
        "BYCO", "FLYNG", "PNSC", "STCL", "GANI", "STPL", "CWSM", "TGL", "MUREB"
    ]
    return [f"{sym}.KA" for sym in raw_tickers]


# ==========================================
# 3. QUANT ENGINES WITH BUY ZONES
# ==========================================
def calculate_swing_score(df_daily):
    if df_daily is None or len(df_daily) < 40:
        return 0.0, "Insufficient history", "N/A"

    score = 0.0
    tags = []
    last_bar = df_daily.iloc[-1]
    close_p = float(last_bar["Close"])

    low_40d = float(df_daily["Low"].tail(40).min())
    if close_p <= low_40d * 1.05:
        score += 2.0
        tags.append("Near 40D Support")

    vol_20d_avg = df_daily["Volume"].tail(20).mean()
    vol_today = float(last_bar["Volume"])
    atr14 = (df_daily["High"] - df_daily["Low"]).rolling(14).mean().iloc[-1]
    body_size = abs(close_p - float(last_bar["Open"]))

    if vol_today > (vol_20d_avg * 1.2) and body_size < atr14:
        score += 1.5
        tags.append("Volume Absorption")

    sma20 = df_daily["Close"].rolling(20).mean().iloc[-1]
    std20 = df_daily["Close"].rolling(20).std().iloc[-1]
    lower_band = sma20 - (2 * std20)

    if close_p <= lower_band * 1.02:
        score += 1.5
        tags.append("Lower BB Touch")

    buy_zone = f"{round(close_p * 0.98, 2)} - {round(close_p * 1.01, 2)}"
    reason = " + ".join(tags) if tags else "No clear swing confluence"

    return min(score, 5.0), reason, buy_zone


def calculate_btst_score(df_daily):
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
        tags.append("Near HOD Close")
    elif clr >= 0.70:
        score += 0.75
        tags.append("Strong Close")

    vol_10d_avg = df_daily["Volume"].iloc[-11:-1].mean()
    rvol = vol_today / vol_10d_avg if vol_10d_avg > 0 else 0

    if rvol >= 1.8:
        score += 1.5
        tags.append(f"Vol Spike ({rvol:.1f}x)")
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
# 4. WORKER THREADS
# ==========================================
def process_single_ticker(symbol):
    clean_code = symbol.replace(".KA", "").upper()
    try:
        ticker_obj = yf.Ticker(symbol)
        df = ticker_obj.history(period="60d")

        if df.empty or len(df) < 15:
            return None

        curr_close = float(df["Close"].iloc[-1])
        curr_vol = int(df["Volume"].iloc[-1])

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


def run_full_market_scan(tickers):
    results = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    total = len(tickers)

    with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
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
            status_text.text(f"Scanning PSX Universe: {i + 1}/{total} stocks")

    status_text.empty()
    progress_bar.empty()
    return pd.DataFrame(results)


# ==========================================
# 5. STREAMLIT INTERFACE & ROUTING
# ==========================================
st.sidebar.title("🇵🇰 PSX Quant Engine")

strategy_view = st.sidebar.radio(
    "Select Mode:",
    [
        "📈 Multi-Day Swing (EOD)",
        "⚡ BTST / Overnight (Free Feed)",
        "🔍 Single Stock Search & Analysis",
    ],
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

if st.sidebar.button("🚀 Run Full Market Scan", type="primary"):
    ticker_list = get_psx_tickers()
    st.session_state["scan_data"] = run_full_market_scan(ticker_list)
    st.session_state["scanned_count"] = len(ticker_list)
    st.session_state["last_scan_time"] = time.strftime("%I:%M %p PKT")

st.title("PSX Quantitative Trading Dashboard")

if "last_scan_time" in st.session_state:
    st.caption(
        f"Last Scan: **{st.session_state['last_scan_time']}** | Scanned Tickers: **{st.session_state.get('scanned_count', 0)}**"
    )

# Portfolio Technical Overlay
if "scan_data" in st.session_state and not st.session_state["scan_data"].empty:
    df_raw = st.session_state["scan_data"]
    user_symbols = [
        str(s).upper() for s in st.session_state["portfolio"]["Symbol"].dropna()
    ]
    pf_matches = df_raw[df_raw["Ticker"].isin(user_symbols)].copy()

    if not pf_matches.empty:
        with st.expander("💼 My Portfolio Technical Status", expanded=True):
            st.dataframe(
                pf_matches[
                    [
                        "Ticker",
                        "Close",
                        "Swing_Score",
                        "Swing_Buy_Zone",
                        "BTST_Score",
                        "BTST_Buy_Zone",
                    ]
                ],
                use_container_width=True,
            )

# MODE 1: SWING STRATEGY
if strategy_view == "📈 Multi-Day Swing (EOD)":
    st.header("📈 Swing Trade Setups (Score ≥ 3.0)")

    if "scan_data" not in st.session_state or st.session_state["scan_data"].empty:
        st.info("Click **'Run Full Market Scan'** in the sidebar to run.")
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
            st.warning("No stocks currently meet Swing criteria (Score ≥ 3.0).")

# MODE 2: BTST STRATEGY
elif strategy_view == "⚡ BTST / Overnight (Free Feed)":
    st.header("⚡ BTST Overnight Candidates (Score ≥ 3.0)")

    if "scan_data" not in st.session_state or st.session_state["scan_data"].empty:
        st.info("Click **'Run Full Market Scan'** in the sidebar to run.")
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
            st.info("No stocks currently meet BTST criteria (Score ≥ 3.0).")

# MODE 3: INDIVIDUAL SEARCH
elif strategy_view == "🔍 Single Stock Search & Analysis":
    st.header("🔍 Stock Lookup & Buy Zone")

    search_input = st.text_input("Enter PSX Symbol (e.g., SYS, ASL, LUCK, TRG):", "SYS")

    if search_input:
        symbol = f"{search_input.strip().upper()}.KA"
        with st.spinner(f"Analyzing {symbol}..."):
            res = process_single_ticker(symbol)

        if res:
            c1, c2, c3 = st.columns(3)
            c1.metric("Current Price", f"PKR {res['Close']}")
            c2.metric("Swing Score", f"{res['Swing_Score']} / 5.0")
            c3.metric("BTST Score", f"{res['BTST_Score']} / 5.0")

            st.divider()

            col_a, col_b = st.columns(2)
            with col_a:
                st.subheader("📈 Swing Strategy")
                st.write(f"**Optimal Buy Zone:** PKR {res['Swing_Buy_Zone']}")
                st.write(f"**Target (+8.5%):** PKR {round(res['Close'] * 1.085, 2)}")
                st.write(f"**Stop Loss (-4.5%):** PKR {round(res['Close'] * 0.955, 2)}")
                st.info(f"**Summary:** {res['Swing_Reason']}")

            with col_b:
                st.subheader("⚡ BTST Strategy")
                st.write(f"**Optimal Buy Zone:** PKR {res['BTST_Buy_Zone']}")
                st.write(f"**Target (+3.0%):** PKR {round(res['Close'] * 1.03, 2)}")
                st.write(f"**Stop Loss (-1.8%):** PKR {round(res['Close'] * 0.982, 2)}")
                st.info(f"**Summary:** {res['BTST_Reason']}")
        else:
            st.error(f"Symbol '{search_input}' not found on Yahoo Finance PSX feed.")

# Complete Market Table
if "scan_data" in st.session_state and not st.session_state["scan_data"].empty:
    with st.expander("📋 View Complete Market Analysis"):
        st.dataframe(
            df_raw[
                [
                    "Ticker",
                    "Close",
                    "Swing_Score",
                    "Swing_Buy_Zone",
                    "Swing_Reason",
                    "BTST_Score",
                    "BTST_Buy_Zone",
                    "BTST_Reason",
                ]
            ],
            use_container_width=True,
    )
    
