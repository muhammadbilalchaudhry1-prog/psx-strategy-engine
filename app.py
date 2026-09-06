import time
import pandas as pd
import requests
import streamlit as st
import yfinance as yf

# ==========================================
# 1. PAGE SETUP & STYLING
# ==========================================
st.set_page_config(
    page_title="PSX KSE-100 Quant Engine",
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
# 2. EXACT KSE-100 CONSTITUENTS UNIVERSE
# ==========================================
@st.cache_data(ttl=86400)
def get_kse100_tickers():
    """Returns the benchmark KSE-100 Index constituents."""
    kse100_symbols = [
        "SYS", "TRG", "AVN", "AIRLINK", "OCTOPUS", "PTC", "WTL", "TELE", "HUMNL",
        "OGDC", "PPL", "MARI", "POL", "PSO", "SHEL", "SNGP", "SSGC", "APL", "HTL",
        "MCB", "UBL", "MEBL", "HBL", "BAFL", "BOP", "FABL", "AKBL", "NBP", "SNBL", "JSBL",
        "EFERT", "FFC", "ENGRO", "FFBL", "FATIMA",
        "LUCK", "DGKC", "KOHC", "PIOC", "CHCC", "FCCL", "ACPL", "BWCL", "THCCL",
        "HUBC", "KAPCO", "KEL", "NCPL", "EPQL", "SPWL", "LPL",
        "ATRL", "NRL", "PRL", "CNERGY",
        "EPCL", "AGP", "SEARL", "ABOT", "GLAXO", "COLG", "ARCH", "ICI", "LOTCHEM", "GTYR",
        "MUGHAL", "ASL", "GHNI", "PAEL", "MTL", "SAZEW", "ISL", "ASTL", "CSAP",
        "ILP", "NML", "NCL", "GATM", "KTML", "TREET",
        "TGL", "UNITY", "PNSC", "SCL", "MUREB", "STCL", "GHGL", "NESTLE", "NATF", "SHEZ"
    ]
    return sorted([f"{sym}.KA" for sym in set(kse100_symbols)])


# ==========================================
# 3. QUANT ENGINES (PHYSICS & CONFLUENCE)
# ==========================================
def calculate_swing_score(df_daily):
    """Multi-Day Swing Strategy (Hold 2-10 Days): Support Floor + Volume Absorption."""
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
        tags.append("Volume Absorption")

    sma20 = df_daily["Close"].rolling(20).mean().iloc[-1]
    std20 = df_daily["Close"].rolling(20).std().iloc[-1]
    lower_band = sma20 - (2 * std20)

    if close_p <= lower_band * 1.02:
        score += 1.5
        tags.append("Lower BB Expansion")

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
# 4. KSE-100 SCANNER ENGINE
# ==========================================
def process_dataframe(df, ticker_code):
    try:
        if df.empty or len(df) < 15:
            return None

        curr_close = float(df["Close"].iloc[-1])
        curr_vol = int(df["Volume"].iloc[-1])

        s_score, s_reason, s_buy = calculate_swing_score(df)
        b_score, b_reason, b_buy = calculate_btst_score(df)

        return {
            "Ticker": ticker_code,
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


def run_kse100_scan(tickers):
    results = []
    progress_bar = st.progress(0)
    status_text = st.empty()

    batch_size = 25
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

                    res = process_dataframe(df, clean_code)
                    if res:
                        results.append(res)
                except Exception:
                    try:
                        single_df = yf.Ticker(sym).history(period="60d")
                        res = process_dataframe(single_df, clean_code)
                        if res:
                            results.append(res)
                    except Exception:
                        continue
        except Exception:
            pass

        percent = min(int(((i + batch_size) / total) * 100), 100)
        progress_bar.progress(percent)
        status_text.text(f"Scanning KSE-100 Benchmark Universe: {min(i + batch_size, total)}/{total} stocks processed")

    status_text.empty()
    progress_bar.empty()
    return pd.DataFrame(results)


# ==========================================
# 5. STREAMLIT INTERFACE
# ==========================================
st.sidebar.title("🇵🇰 PSX KSE-100 Engine")

strategy_view = st.sidebar.radio(
    "Select Mode:",
    [
        "⚡ BTST / Overnight (Free Feed)",
        "📈 Multi-Day Swing (EOD)",
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

if st.sidebar.button("🚀 Scan KSE-100 Index", type="primary"):
    ticker_list = get_kse100_tickers()
    st.session_state["scan_data"] = run_kse100_scan(ticker_list)
    st.session_state["scanned_count"] = len(st.session_state["scan_data"])
    st.session_state["last_scan_time"] = time.strftime("%I:%M %p PKT")

st.title("PSX KSE-100 Quantitative Scanner")

if "last_scan_time" in st.session_state:
    st.caption(
        f"Last Scan Executed: **{st.session_state['last_scan_time']}** | Scanned KSE-100 Tickers: **{st.session_state.get('scanned_count', 0)}**"
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
                        "BTST_Score",
                        "BTST_Buy_Zone",
                        "Swing_Score",
                        "Swing_Buy_Zone",
                    ]
                ],
                use_container_width=True,
            )

# MODE 1: BTST STRATEGY
if strategy_view == "⚡ BTST / Overnight (Free Feed)":
    st.header("⚡ BTST Overnight Candidates (Buy Today 3:15 PM)")
    st.caption("Filters for late-session volume spikes and high CLR close pressure. **Threshold: Score ≥ 3.0**")

    if "scan_data" not in st.session_state or st.session_state["scan_data"].empty:
        st.info("Click **'Scan KSE-100 Index'** in the sidebar to initiate.")
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
            st.info("No KSE-100 stocks currently cross the BTST Threshold (Score ≥ 3.0).")

# MODE 2: SWING STRATEGY (2-10 DAYS)
elif strategy_view == "📈 Multi-Day Swing (EOD)":
    st.header("📈 Swing Trade Setups (2–10 Days Holding)")
    st.caption("Filters for 40-day support floors and volume absorption. **Threshold: Score ≥ 3.0**")

    if "scan_data" not in st.session_state or st.session_state["scan_data"].empty:
        st.info("Click **'Scan KSE-100 Index'** in the sidebar to initiate.")
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
            st.warning("No KSE-100 stocks currently cross the Swing Threshold (Score ≥ 3.0).")

# MODE 3: INDIVIDUAL SEARCH
elif strategy_view == "🔍 Single Stock Search & Analysis":
    st.header("🔍 Individual Stock Lookup")

    search_input = st.text_input("Enter PSX Symbol (e.g., SYS, ASL, LUCK, TRG):", "SYS")

    if search_input:
        symbol = f"{search_input.strip().upper()}.KA"
        with st.spinner(f"Analyzing {symbol}..."):
            try:
                single_df = yf.Ticker(symbol).history(period="60d")
                res = process_dataframe(single_df, search_input.strip().upper())

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
                    st.error(f"Could not retrieve historical data for '{search_input}'.")
            except Exception as e:
                st.error(f"Error executing lookup: {str(e)}")

# Complete Overview
if "scan_data" in st.session_state and not st.session_state["scan_data"].empty:
    with st.expander("📋 View Complete KSE-100 Market Analysis"):
        st.dataframe(
            df_raw[
                [
                    "Ticker",
                    "Close",
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
        
