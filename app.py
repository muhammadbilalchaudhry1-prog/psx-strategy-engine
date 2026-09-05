import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from scipy.signal import find_peaks

st.set_page_config(page_title="PSX Advanced Quant Engine", layout="wide")

st.title("🇵🇰 PSX Advanced Pattern & Divergence Engine")

ticker = st.text_input("Enter PSX Stock Ticker Symbol:", value="SYS").upper().strip()

def calculate_technical_features(df):
    # --- 1. ATR (14) ---
    df['TR'] = np.maximum(
        df['High'] - df['Low'],
        np.maximum(
            abs(df['High'] - df['Close'].shift(1)),
            abs(df['Low'] - df['Close'].shift(1))
        )
    )
    df['ATR'] = df['TR'].rolling(window=14).mean()

    # --- 2. RSI (14) ---
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))

    # --- 3. MACD & Signal Line ---
    df['EMA_12'] = df['Close'].ewm(span=12, adjust=False).mean()
    df['EMA_26'] = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = df['EMA_12'] - df['EMA_26']
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']

    # --- 4. Divergence Detection (RSI & MACD) ---
    df['RSI_Divergence'] = "None"
    df['MACD_Divergence'] = "None"

    # Find local swing highs and lows in Close prices
    peaks, _ = find_peaks(df['Close'].values, distance=5)
    troughs, _ = find_peaks(-df['Close'].values, distance=5)

    if len(troughs) >= 2:
        t1, t2 = troughs[-2], troughs[-1]
        # Bullish RSI Divergence: Price lower low, RSI higher low
        if df['Close'].iloc[t2] < df['Close'].iloc[t1] and df['RSI'].iloc[t2] > df['RSI'].iloc[t1]:
            df.loc[df.index[t2:], 'RSI_Divergence'] = "Bullish"
        # Bullish MACD Divergence: Price lower low, MACD higher low
        if df['Close'].iloc[t2] < df['Close'].iloc[t1] and df['MACD'].iloc[t2] > df['MACD'].iloc[t1]:
            df.loc[df.index[t2:], 'MACD_Divergence'] = "Bullish"

    if len(peaks) >= 2:
        p1, p2 = peaks[-2], peaks[-1]
        # Bearish RSI Divergence: Price higher high, RSI lower high
        if df['Close'].iloc[p2] > df['Close'].iloc[p1] and df['RSI'].iloc[p2] < df['RSI'].iloc[p1]:
            df.loc[df.index[p2:], 'RSI_Divergence'] = "Bearish"
        # Bearish MACD Divergence: Price higher high, MACD lower high
        if df['Close'].iloc[p2] > df['Close'].iloc[p1] and df['MACD'].iloc[p2] < df['MACD'].iloc[p1]:
            df.loc[df.index[p2:], 'MACD_Divergence'] = "Bearish"

    # --- 5. ABC Harmonic Wave Pattern Detection ---
    df['ABC_Pattern'] = "None"
    if len(peaks) >= 2 and len(troughs) >= 1:
        # Check for Bullish ABC (Correction wave completed, setup for C expansion)
        a_price = df['Close'].iloc[peaks[-2]]
        b_price = df['Close'].iloc[troughs[-1]]
        c_price = df['Close'].iloc[-1]
        
        ab_retrace = (a_price - b_price) / a_price
        if 0.382 <= ab_retrace <= 0.618 and c_price > b_price:
            df.loc[df.index[-1], 'ABC_Pattern'] = "Bullish ABC Retracement"
        elif ab_retrace > 0.786:
            df.loc[df.index[-1], 'ABC_Pattern'] = "Bearish ABC Breakdown"

    return df

if ticker:
    with st.spinner(f"Processing live patterns for {ticker}.PSX..."):
        data = yf.download(f"{ticker}.KA", period="1y", interval="1d", progress=False)
        
        if not data.empty and len(data) >= 50:
            if hasattr(data.columns, 'get_level_values'):
                data.columns = data.columns.get_level_values(0)
            
            df = calculate_technical_features(data[['Open', 'High', 'Low', 'Close']].copy())
            latest = df.iloc[-1]

            # Weighted Conviction Scoring
            score = 0
            if latest['RSI_Divergence'] == "Bullish": score += 1.5
            elif latest['RSI_Divergence'] == "Bearish": score -= 1.5

            if latest['MACD_Divergence'] == "Bullish": score += 1.5
            elif latest['MACD_Divergence'] == "Bearish": score -= 1.5

            if latest['ABC_Pattern'] == "Bullish ABC Retracement": score += 2.0
            elif latest['ABC_Pattern'] == "Bearish ABC Breakdown": score -= 2.0

            if score >= 1.5: signal = "BUY"
            elif score <= -1.5: signal = "SELL"
            else: signal = "HOLD"

            st.metric("Live Price", f"PKR {latest['Close']:.2f}")
            st.metric("Signal", signal)

            col1, col2, col3 = st.columns(3)
            col1.metric("RSI Divergence", latest['RSI_Divergence'])
            col2.metric("MACD Divergence", latest['MACD_Divergence'])
            col3.metric("Pattern Status", latest['ABC_Pattern'])

            st.subheader("Price & Indicator Charts")
            st.line_chart(df[['Close', 'RSI', 'MACD']])
        else:
            st.error("Insufficient market history to generate pattern signals.")
          
