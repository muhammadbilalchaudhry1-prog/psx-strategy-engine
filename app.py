import time
import pandas as pd
import requests
import streamlit as st
import yfinance as yf

# ==========================================
# 1. PAGE SETUP & STYLING
# ==========================================
st.set_page_config(
    page_title="PSX Ultimate Whole-Market Scanner",
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
# 2. COMPLETE PSX ALL-SHARE SCRAPER (DPS API)
# ==========================================
@st.cache_data(ttl=21600)
def get_complete_psx_universe():
    """Dynamically fetches EVERY listed security (Equities, Rights Shares, Small Caps) directly from the official PSX Data Portal."""
    symbols = set()
    
    # 1. Official PSX DPS Live Summary API
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        res = requests.get("https://dps.psx.com.pk/data/summary", headers=headers, timeout=10)
        if res.status_code == 200:
            data = res.json()
            for item in data:
                code = item.get("code")
                if code:
                    symbols.add(str(code).strip().upper())
    except Exception:
        pass

    # 2. Comprehensive Static Master List (Includes Right Shares, Restructured & Micro-Caps)
    master_fallback = [
        # Micro-caps, Rights & Specific Request Stocks
        "SGPL", "SGPLR", "WAVES", "WAVESAPP", "WAVESAPPR", "CLVL", "LEUL", "ADMM", "BUXL", "KOHE", "MSOT", "DAAG", "DYNO",
        # Standard PSX Universe
        "SYS", "TRG", "AVN", "AIRLINK", "OCTOPUS", "PTC", "WTL", "TELE", "HUMNL", "INBOX", "TPLP", "TPL", "NETSOL",
        "OGDC", "PPL", "MARI", "POL", "PSO", "SHEL", "SNGP", "SSGC", "APL", "HASCOL", "HTL", "ATRL", "NRL", "PRL", "CNERGY",
        "MCB", "UBL", "MEBL", "HBL", "BAFL", "BOP", "FABL", "AKBL", "NBP", "BIPL", "SNBL", "JSBL", "SPL", "SILK",
        "EFERT", "FFC", "ENGRO", "FFBL", "FATIMA", "EPCL", "AGP", "SEARL", "ABOT", "GLAXO", "PAKOXY", "COLG", "ARCH", "ICI", "LOTCHEM", "GTYR",
        "LUCK", "DGKC", "KOHC", "PIOC", "CHCC", "FCCL", "ACPL", "DCL", "POWER", "THCCL", "BWCL", "FLYNG",
        "HUBC", "KAPCO", "KEL", "NCPL", "EPQL", "SPWL", "LPL", "ALTN", "SEL",
        "MUGHAL", "ASL", "GHNI", "PAEL", "MTL", "SAZEW", "PSMC", "LOADS", "ISL", "ASTL", "CSAP", "DFML",
        "ILP", "NML", "NCL", "GATM", "KTML", "TREET", "HAEL", "CRTM", "ANL",
        "TGL", "UNITY", "PNSC", "SCL", "MUREB", "STCL", "GHGL", "NESTLE", "NATF", "SHEZ", "SML", "JDWS", "TARC"
    ]
    
    symbols.update(master_fallback)
    return sorted(list(symbols))


# ==========================================
# 3. HYBRID DUAL DATA FETCHER (DPS API + YFINANCE)
# ==========================================
def fetch_stock_dataframe(symbol: str) -> pd.DataFrame:
    """Fetches stock data directly from PSX DPS API first, falling back to yfinance."""
    clean_symbol = symbol.strip().upper()
    
    # --- Primary Source: PSX DPS Official API ---
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        url = f"https://dps.psx.com.pk/data/timeseries/eod/{clean_symbol}"
        res = requests.get(url, headers=headers, timeout=4)
        if res.status_code == 200:
            raw = res.json().get("data", [])
            if raw and len(raw) >= 5:
                df = pd.DataFrame(raw, columns=["Epoch", "Close", "Volume"])
                df["Close"] = pd.to_numeric(df["Close"], errors="coerce")
                df["Volume"] = pd.to_numeric(df["Volume"], errors="coerce")
                
                # Approximate High, Low, Open if missing from basic API payload
                df["High"] = df["Close"]
                df["Low"] = df["Close"]
                df["Open"] = df["Close"]
                df = df.dropna().reset_index(drop=True)
                if len(df) >= 5:
                    return df
    except Exception:
        pass

    # --- Secondary Fallback: Yahoo Finance ---
    yf_symbol = f"{clean_symbol}.KA"
    try:
        df = yf.Ticker(yf_symbol).history(period="60d")
        if not df.empty and len(df) >= 5:
            return df
    except Exception:
        pass

    return pd.DataFrame()


# ==========================================
# 4. QUANT ENGINE MODEL (PHYSICS & CONFLUENCE)
# ==========================================
def calculate_swing_score(df_daily):
    """Multi-Day Swing Strategy: Support Floor + Volume Absorption."""
    hist_len = len(df_daily)
    if hist_len < 10:
        return 0.0, "Insufficient history for swing scan", "N/A"

    score = 0.0
    tags = []
    last_bar = df_daily.iloc[-1]
    close_p = float(last_bar["Close"])

    lookback = min(40, hist_len)
    low_floor = float(df_daily["Low"].tail(lookback).min())
    if close_p <= low_floor * 1.05:
        score += 2.0
        tags.append(f"Near {lookback}D Support Floor")

    vol_avg = df_daily["Volume"].tail(min(20, hist_len)).mean()
    vol_today = float(last_bar["Volume"])
    
    if vol_today > (vol_avg * 1.2):
        score += 1.5
        tags.append("Volume Absorption")

    sma_len = min(20, hist_len)
    sma20 = df_daily["Close"].rolling(sma_len).mean().iloc[-1]
    std20 = df_daily["Close"].rolling(sma_len).std().iloc[-1]
    
    if pd.notnull(std20) and std20 > 0:
        lower_band = sma20 - (2 * std20)
        if close_p <= lower_band * 1.02:
            score += 1.5
            tags.append("Lower BB Touch")

    buy_zone = f"{round(close_p * 0.98, 2)} - {round(close_p * 1.01, 2)}"
    reason = " + ".join(tags) if tags else "No swing confluence"

    return min(score, 5.0), reason, buy_zone


def calculate_btst_score(df_daily):
    """BTST Overnight Strategy: Momentum & Close Pressure."""
    hist_len = len(df_daily)
    if hist_len < 5:
        return 0.0, "Insufficient history for BTST", "N/A"

    score = 0.0
    tags = []
    last_bar = df_daily.iloc[-1]
    prev_close = float(df_daily["Close"].iloc[-2]) if hist_len >= 2 else float(last_bar["Open"])

    close_p = float(last_bar["Close"])
    high_p = float(last_bar["High"])
    low_p = float(last_bar["Low"])
    vol_today = float(last_bar["Volume"])

    clr = (close_p - low_p) / (high_p - low_p) if (high_p - low_p) > 0 else 0.8
    if clr >= 0.80:
        score += 1.5
        tags.append("Strong High Close")

    vol_avg = df_daily["Volume"].tail(min(10, hist_len)).mean()
    rvol = vol_today / vol_avg if vol_avg > 0 else 1.0

    if rvol >= 1.5:
        score += 1.5
        tags.append(f"Volume Surge ({rvol:.1f}x)")

    daily_pct = ((close_p - prev_close) / prev_close) * 100 if prev_close > 0 else 0
    if 1.5 <= daily_pct <= 10.0:
        score += 1.0
        tags.append(f"+{daily_pct:.1f}% Momentum")

    ema20 = df_daily["Close"].ewm(span=min(20, hist_len)).mean().iloc[-1]
    if close_p >= ema20:
        score += 1.0
        tags.append("Above EMA")

    buy_zone = f"{round(close_p * 0.99, 2)} - {round(close_p, 2)}"
    reason = " + ".join(tags) if tags else "No BTST momentum"

    return min(score, 5.0), reason, buy_zone


def process_single_stock(df, clean_code, min_volume):
    try:
        if df.empty or len(df) < 3:
            return None

        curr_close = float(df["Close"].iloc[-1])
        curr_vol = int(df["Volume"].iloc[-1])

        # Apply volume filter, bypass if stock is a Right Share (ends with R)
        if curr_vol < min_volume and not clean_code.endswith("R"):
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


# ==========================================
# 5. ALL-SHARE BULK SCANNER PIPELINE
# ==========================================
def run_all_psx_scan(tickers, min_volume):
    results = []
    progress_bar = st.progress(0)
    status_text = st.empty()

    total = len(tickers)

    for idx, sym in enumerate(tickers):
        df = fetch_stock_dataframe(sym)
        res = process_single_stock(df, sym, min_volume)
        if res:
            results.append(res)

        percent = min(int(((idx + 1) / total) * 100), 100)
        progress_bar.progress(percent)
        status_text.text(f"Scanning Complete PSX Universe: {idx + 1}/{total} stocks processed ({sym})")

    status_text.empty()
    progress_bar.empty()
    return pd.DataFrame(results)


# ==========================================
# 6. STREAMLIT INTERFACE & ROUTING
# ==========================================
st.sidebar.title("🇵🇰 PSX Complete Engine")

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
    help="Set to 0 to catch micro-caps like ADMM, LEUL, or Right Shares (SGPLR, WAVESAPPR).",
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

if st.sidebar.button("🚀 Scan ALL PSX Equities & Rights", type="primary"):
    all_tickers = get_complete_psx_universe()
    st.session_state["scan_data"] = run_all_psx_scan(all_tickers, min_vol_input)
    st.session_state["scanned_count"] = len(st.session_state["scan_data"])
    st.session_state["last_scan_time"] = time.strftime("%I:%M %p PKT")

st.title("PSX All-Share & Right Shares Quant Scanner")

if "last_scan_time" in st.session_state:
    st.caption(
        f"Last Scan Executed: **{st.session_state['last_scan_time']}** | Total Active Securities Returned: **{st.session_state.get('scanned_count', 0)}**"
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
    st.caption("Includes all mainboard stocks, micro-caps, and right shares. **Threshold: Score ≥ 2.5**")

    if "scan_data" not in st.session_state or st.session_state["scan_data"].empty:
        st.info("Click **'Scan ALL PSX Equities & Rights'** in the sidebar to run full scan.")
    else:
        btst_df = df_raw[df_raw["BTST_Score"] >= 2.5].copy()

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
            st.info("No PSX stocks currently cross the BTST Threshold (Score ≥ 2.5).")

# MODE 2: MULTI-DAY SWING STRATEGY
elif strategy_view == "📈 Multi-Day Swing Setups":
    st.header("📈 Swing Trade Setups (2–10 Days Holding Horizon)")
    st.caption("Filters complete market for support floors and volume absorption. **Threshold: Score ≥ 2.5**")

    if "scan_data" not in st.session_state or st.session_state["scan_data"].empty:
        st.info("Click **'Scan ALL PSX Equities & Rights'** in the sidebar to run full scan.")
    else:
        swing_df = df_raw[df_raw["Swing_Score"] >= 2.5].copy()

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
            st.warning("No PSX stocks currently cross the Swing Threshold (Score ≥ 2.5).")

# MODE 3: SINGLE STOCK SEARCH
elif strategy_view == "🔍 Single Stock Search & Analysis":
    st.header("🔍 Individual Stock & Rights Lookup")

    search_input = st.text_input("Enter ANY PSX Ticker (e.g., SGPLR, WAVESAPPR, CLVL, LEUL, ADMM):", "SGPLR")

    if search_input:
        clean_sym = search_input.strip().upper()
        with st.spinner(f"Analyzing {clean_sym} via PSX Data Portal..."):
            df = fetch_stock_dataframe(clean_sym)
            res = process_single_stock(df, clean_sym, min_volume=0)

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
                st.error(f"Could not fetch data for '{clean_sym}'. It may be currently inactive or suspended.")

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
