import os
import math
import numpy as np
import pandas as pd
import requests
import streamlit as st

# Streamlit Page Configuration
st.set_page_config(
    page_title="PSX Quant Engine — Econophysics",
    page_icon="⚛️",
    layout="wide",
)

st.title("⚛️ PSX Econophysics & Quantitative Strategy Engine")
st.caption(
    "Damped Harmonic Oscillator Mechanics & Thermodynamic Entropy Scanner for PSX Equities"
)


# ------------------------------------------------------------------
# 1. DATA LOADING ENGINE
# ------------------------------------------------------------------
@st.cache_data(ttl=300)
def fetch_live_psx_summary():
    """Attempts direct client-side stream pull from PSX DPS API endpoint."""
    url = "https://dps.psx.com.pk/data/market-summary"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
    }
    try:
        res = requests.get(url, headers=headers, timeout=8)
        if res.status_code == 200:
            data = res.json()
            if isinstance(data, list) and len(data) > 0:
                return pd.DataFrame(data)
            elif isinstance(data, dict):
                records = data.get("stocks", data.get("data", []))
                if records:
                    return pd.DataFrame(records)
    except Exception:
        pass
    return None


def load_market_data(uploaded_file=None):
    if uploaded_file is not None:
        return pd.read_csv(uploaded_file)

    # Try Live Feed
    live_df = fetch_live_psx_summary()
    if live_df is not None and not live_df.empty:
        return live_df

    # Fallback to local snapshot
    if os.path.exists("psx_market_data.csv"):
        return pd.read_csv("psx_market_data.csv")

    return None


# ------------------------------------------------------------------
# 2. ECONOPHYSICS CORE ENGINE
# ------------------------------------------------------------------
def calculate_thermodynamic_entropy(prices, bins=8):
    """Calculates Shannon/Thermodynamic Entropy (H) over price distribution."""
    if len(prices) < 3:
        return 0.0
    counts, _ = np.histogram(prices, bins=bins)
    probs = counts / float(len(prices))
    probs = probs[probs > 0]
    return -float(np.sum(probs * np.log2(probs)))


def run_physics_algo(df):
    """Applies Damped Driven Harmonic Oscillator Model and Entropy Filters."""
    # Standardize column headers
    col_map = {
        "Symbol": "Ticker",
        "code": "Ticker",
        "symbol": "Ticker",
        "Close": "Close",
        "close": "Close",
        "current": "Close",
        "Volume": "Volume",
        "volume": "Volume",
        "vol": "Volume",
        "High": "High",
        "high": "High",
        "Low": "Low",
        "low": "Low",
        "Open": "Open",
        "open": "Open",
        "ldcp": "LDCP",
        "LDCP": "LDCP",
    }
    df = df.rename(columns=col_map)

    # Required columns check
    for c in ["Close", "High", "Low", "Volume", "LDCP"]:
        if c not in df.columns:
            if c == "LDCP" and "Close" in df.columns:
                df["LDCP"] = df["Close"]
            elif c in ["High", "Low"] and "Close" in df.columns:
                df[c] = df["Close"]
            else:
                df[c] = 0.0

        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)

    results = []

    for _, row in df.iterrows():
        ticker = str(row.get("Ticker", "UNKNOWN")).strip().upper()
        close_p = float(row.get("Close", 0.0))
        high_p = float(row.get("High", close_p))
        low_p = float(row.get("Low", close_p))
        ldcp = float(row.get("LDCP", close_p))
        vol = float(row.get("Volume", 0))

        if close_p <= 0 or vol <= 0:
            continue

        # Physical Kinematics
        # Displacement (x) from moving equilibrium (LDCP)
        x = close_p - ldcp
        # Velocity (v) = Price Momentum
        v = x
        # Mass (m) = Log-scaled volume (Inertia)
        m = math.log(vol + 1.0)

        # Hooke's Elasticity Spring Constant (k)
        day_range = max(high_p - low_p, 0.01)
        k = 1.0 / day_range

        # Energy Dynamics
        potential_energy = 0.5 * k * (x**2)  # U = 1/2 k x^2
        kinetic_energy = 0.5 * m * (v**2)  # K = 1/2 m v^2
        total_energy = potential_energy + kinetic_energy

        # Thermodynamic Disorder State (Entropy Approximation)
        # Higher range volatility under low inertia = High Entropy State
        entropy = (day_range / close_p) * 100.0

        # Close Location Ratio (CLR): Measures pressure distribution
        clr = (close_p - low_p) / day_range if day_range > 0 else 0.5

        # Strategy Trigger Rules
        btst_score = 0.0
        swing_score = 0.0
        signal = "NEUTRAL"
        reasons = []

        # 1. BTST Signal (Kinetic Expansion & Low Entropy)
        if kinetic_energy > 2.0 and clr >= 0.70 and v > 0:
            btst_score += 3.0
            reasons.append("High Kinetic Momentum Expansion")

        if entropy < 3.5:
            btst_score += 2.0
            reasons.append("Low Entropy (Ordered Outflow/Inflow)")

        # 2. Swing Signal (Max Elastic Potential Energy / Hooke Rebound)
        if x < 0 and potential_energy > 0.5:
            swing_score += 2.5
            reasons.append("Stretched Elastic Potential (Compressed Spring)")

        if vol >= 50000:
            swing_score += 1.5
            reasons.append("Sufficient Mass / Liquidity Floor")

        if close_p < 25.0 or ticker.endswith("R"):
            swing_score += 1.0
            reasons.append("Low Float / High Velocity Setup")

        # Consolidated Signal Determination
        if btst_score >= 3.5 and v > 0:
            signal = "⚡ BTST KINETIC BUY"
        elif swing_score >= 3.0 and x <= 0:
            signal = "📈 SWING ELASTIC BUY"
        elif x > 0 and potential_energy > 3.0:
            signal = "⚠️ OVEREXTENDED (EXIT)"

        results.append({
            "Ticker": ticker,
            "Close": close_p,
            "Change (%)": round(
                ((close_p - ldcp) / ldcp * 100) if ldcp > 0 else 0.0, 2
            ),
            "Volume": int(vol),
            "Displacement (x)": round(x, 2),
            "Kinetic Energy (K)": round(kinetic_energy, 2),
            "Potential Energy (U)": round(potential_energy, 2),
            "Total Energy": round(total_energy, 2),
            "Entropy Index": round(entropy, 2),
            "Signal": signal,
            "Physics State": (
                " | ".join(reasons) if reasons else "Equilibrium"
            ),
        })

    return pd.DataFrame(results)


# ------------------------------------------------------------------
# 3. STREAMLIT INTERFACE
# ------------------------------------------------------------------
st.sidebar.header("🕹️ Controls & Data Portal")
uploaded_csv = st.sidebar.file_uploader(
    "Upload PSX CSV (Optional)", type=["csv"]
)

if st.sidebar.button("🔄 Force Refresh Feed"):
    st.cache_data.clear()
    st.rerun()

df_raw = load_market_data(uploaded_csv)

if df_raw is not None and not df_raw.empty:
    st.sidebar.success(f"Loaded {len(df_raw)} records successfully.")

    # Process Physics Pipeline
    df_quant = run_physics_algo(df_raw)

    # Metrics Summary
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Tickers Scanned", len(df_quant))
    col2.metric(
        "⚡ BTST Kinetic Signals",
        len(df_quant[df_quant["Signal"] == "⚡ BTST KINETIC BUY"]),
    )
    col3.metric(
        "📈 Swing Elastic Signals",
        len(df_quant[df_quant["Signal"] == "📈 SWING ELASTIC BUY"]),
    )
    col4.metric(
        "⚠️ Overextended Tickers",
        len(df_quant[df_quant["Signal"] == "⚠️ OVEREXTENDED (EXIT)"]),
    )

    st.markdown("---")

    # Display Strategy Tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "⚡ BTST Setups (Kinetic)",
        "📈 Swing Setups (Elastic Rebound)",
        "⚛️ Full Physics Engine Universe",
        "📊 Raw Data Stream",
    ])

    with tab1:
        st.subheader("⚡ BTST Setups (High Kinetic Energy & Low Entropy)")
        btst_df = df_quant[
            df_quant["Signal"] == "⚡ BTST KINETIC BUY"
        ].sort_values(by="Kinetic Energy (K)", ascending=False)
        st.dataframe(btst_df, use_container_width=True)

    with tab2:
        st.subheader(
            "📈 Multi-Day Swing Setups (Elastic Potential Energy Rebound)"
        )
        swing_df = df_quant[
            df_quant["Signal"] == "📈 SWING ELASTIC BUY"
        ].sort_values(by="Potential Energy (U)", ascending=False)
        st.dataframe(swing_df, use_container_width=True)

    with tab3:
        st.subheader("⚛️ Full Market Quant Matrix")
        st.dataframe(df_quant, use_container_width=True)

    with tab4:
        st.subheader("📋 Ingested Dataset")
        st.dataframe(df_raw, use_container_width=True)

else:
    st.error(
        "No market data available. Please upload a `psx_market_data.csv` file in the sidebar or run during active market hours."
    )
    
