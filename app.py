import os
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="PSX Quant Engine",
    page_icon="🇵🇰",
    layout="wide",
)

st.title("🇵🇰 PSX Quantitative Market Scanner")


# Load CSV Data
def load_data(uploaded_file=None):
    if uploaded_file is not None:
        return pd.read_csv(uploaded_file)
    elif os.path.exists("psx_market_data.csv"):
        return pd.read_csv("psx_market_data.csv")
    return None


# Sidebar Configuration
st.sidebar.header("📁 Data Source & Controls")
uploaded_csv = st.sidebar.file_uploader(
    "Upload PSX Market Summary CSV", type=["csv"]
)

df_raw = load_data(uploaded_csv)

if df_raw is not None:
    st.sidebar.success(f"Loaded {len(df_raw)} ticker rows successfully.")

    # Column Normalization
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
        "High Price": "High",
        "Low": "Low",
        "Low Price": "Low",
    }
    df_raw.rename(columns=col_map, inplace=True)

    # Clean numeric columns
    for col in ["Close", "High", "Low", "Volume"]:
        if col in df_raw.columns:
            df_raw[col] = pd.to_numeric(df_raw[col], errors="coerce").fillna(
                0.0
            )

    # Apply Calculations
    processed = []
    for _, row in df_raw.iterrows():
        symbol = str(row.get("Ticker", "UNKNOWN")).strip().upper()
        close_p = float(row.get("Close", 0.0))
        high_p = float(row.get("High", close_p))
        low_p = float(row.get("Low", close_p))
        vol = int(row.get("Volume", 0))

        if close_p <= 0:
            continue

        # Strategy Logic
        btst_eligible = close_p > 5.0 and vol > 10000
        swing_eligible = close_p > 10.0 and vol > 50000

        processed.append({
            "Ticker": symbol,
            "Close": close_p,
            "High": high_p,
            "Low": low_p,
            "Volume": vol,
            "BTST Setup": "⚡ Ready" if btst_eligible else "—",
            "Swing Setup": "📈 Ready" if swing_eligible else "—",
        })

    df_final = pd.DataFrame(processed)

    # Strategy Tabs
    tab1, tab2, tab3 = st.tabs(
        ["⚡ BTST Setups", "📈 Swing Setups", "📋 All Market Data"]
    )

    with tab1:
        st.subheader("Buy Today, Sell Tomorrow (BTST) Candidates")
        btst_df = df_final[df_final["BTST Setup"] == "⚡ Ready"]
        st.dataframe(btst_df, use_container_width=True)

    with tab2:
        st.subheader("Multi-Day Swing Trade Candidates")
        swing_df = df_final[df_final["Swing Setup"] == "📈 Ready"]
        st.dataframe(swing_df, use_container_width=True)

    with tab3:
        st.subheader("Complete Stock Universe")
        st.dataframe(df_final, use_container_width=True)

else:
    st.warning(
        "No market data found! Please upload `psx_market_data.csv` in the sidebar or save it in your repository root."
    )
    
