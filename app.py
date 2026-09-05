import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from scipy.signal import find_peaks

st.set_page_config(page_title="PSX Full Quant Reversal Engine", layout="wide")

st.title("🇵🇰 PSX Multi-Factor Reversal & Early-Signal Scanner")

DEFAULT_TICKERS = [
    "SYS", "ENGRO", "LUCK", "OGDC", "PPL", "TRG", "AIRLINK", 
    "HUBC", "MEBL", "MCB", "FEROZ", "EFERT", "SAZEW", "PSO", "MARI"
]

selected_tickers = st.multiselect("Select Tickers to Scan:", DEFAULT_TICKERS, default=DEFAULT_TICKERS)
rr_ratio = st.slider("Target Risk-to-Reward Ratio:", 1.5, 4.0, 2.0, 0.5)

def analyze_full_technicals(symbol):
    df = yf.download(f"{symbol}.KA", period="1y", interval="1d", progress=False)
    if df.empty or len(df) < 50:
        return None

    if hasattr(df.columns, 'get_level_values'):
        df.columns = df.columns.get_level_values(0)

    df = df[['Open', 'High', 'Low', 'Close', 'Volume']].dropna()

    # --- 1. Moving Averages & Trend Filters ---
    df['EMA_12'] = df['Close'].ewm(span=12, adjust=False).mean()
    df['EMA_26'] = df['Close'].ewm(span=26, adjust=False).mean()
    df['SMA_50'] = df['Close'].rolling(50).mean()
    df['SMA_200'] = df['Close'].rolling(200).mean()

    # --- 2. Volatility & Bollinger Bands ---
    df['SMA_20'] = df['Close'].rolling(20).mean()
    df['STD_20'] = df['Close'].rolling(20).std()
    df['BB_Upper'] = df['SMA_20'] + (2 * df['STD_20'])
    df['BB_Lower'] = df['SMA_20'] - (2 * df['STD_20'])

    # --- 3. Momentum (RSI & MACD) ---
    df['TR'] = np.maximum(df['High'] - df['Low'], np.maximum(abs(df['High'] - df['Close'].shift(1)), abs(df['Low'] - df['Close'].shift(1))))
    df['ATR'] = df['TR'].rolling(14).mean()

    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain / loss)))

    df['MACD'] = df['EMA_12'] - df['EMA_26']
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()

    # --- 4. Candlestick Pattern Recognition ---
    O, H, L, C = df['Open'].iloc[-1], df['High'].iloc[-1], df['Low'].iloc[-1], df['Close'].iloc[-1]
    O_prev, C_prev = df['Open'].iloc[-2], df['Close'].iloc[-2]
    body = abs(C - O)
    range_total = H - L if (H - L) > 0 else 1.0

    candle_pattern = "None"
    # Bullish Engulfing
    if C_prev < O_prev and C > O and C > O_prev and O < C_prev:
        candle_pattern = "Bullish Engulfing"
    # Hammer / Pinbar
    elif (min(O, C) - L) > (2 * body) and (H - max(O, C)) < (0.2 * range_total):
        candle_pattern = "Bullish Hammer / Pinbar"

    # --- 5. Support & Resistance (Rolling 20-Day Pivots) ---
    recent = df.tail(20)
    support = float(recent['Low'].min())
    resistance = float(recent['High'].max())

    # --- 6. Divergences & Harmonic Wave Pivots ---
    peaks, _ = find_peaks(df['Close'].values, distance=5)
    troughs, _ = find_peaks(-df['Close'].values, distance=5)

    rsi_div = "Neutral"
    macd_div = "Neutral"
    if len(troughs) >= 2:
        t1, t2 = troughs[-2], troughs[-1]
        if df['Close'].iloc[t2] < df['Close'].iloc[t1] and df['RSI'].iloc[t2] > df['RSI'].iloc[t1]:
            rsi_div = "Bullish RSI Div"
        if df['Close'].iloc[t2] < df['Close'].iloc[t1] and df['MACD'].iloc[t2] > df['MACD'].iloc[t1]:
            macd_div = "Bullish MACD Div"

    harmonic_setup = "None"
    if len(peaks) >= 2 and len(troughs) >= 2:
        a = df['Close'].iloc[peaks[-2]]
        b = df['Close'].iloc[troughs[-2]]
        retrace = (a - b) / a if a != 0 else 0
        if 0.382 <= abs(retrace) <= 0.618:
            harmonic_setup = "Bullish ABC Setup"

    # --- 7. Weighted Composite Score ---
    score = 0
    if rsi_div == "Bullish RSI Div": score += 2.0
    if macd_div == "Bullish MACD Div": score += 2.0
    if candle_pattern != "None": score += 1.5
    if harmonic_setup != "None": score += 2.0
    if C <= df['BB_Lower'].iloc[-1]: score += 1.5  # Oversold on Bollinger Lower Band
    if C >= df['SMA_50'].iloc[-1]: score += 1.0     # Trend confirmation

    latest_close = float(C)
    atr = float(df['ATR'].iloc[-1])

    if score >= 4.0:
        signal = "EARLY BUY CALL"
        entry_price = latest_close
        stop_loss = max(support - (1.0 * atr), 0.5)
        target = entry_price + (rr_ratio * (entry_price - stop_loss))
    else:
        signal = "NEUTRAL / WAIT"
        entry_price, stop_loss, target = None, None, None

    return {
        "Ticker": symbol,
        "Signal": signal,
        "Price": f"PKR {latest_close:.2f}",
        "Support": f"PKR {support:.2f}",
        "Resistance": f"PKR {resistance:.2f}",
        "Entry": f"PKR {entry_price:.2f}" if entry_price else "-",
        "Target": f"PKR {target:.2f}" if target else "-",
        "Stop Loss": f"PKR {stop_loss:.2f}" if stop_loss else "-",
        "Candle Pattern": candle_pattern,
        "RSI Div": rsi_div,
        "Harmonic Wave": harmonic_setup,
        "Score": score
    }

if st.button("🚀 Scan Full Market for Reversals"):
    results = []
    bar = st.progress(0)
    for idx, sym in enumerate(selected_tickers):
        res = analyze_full_technicals(sym)
        if res: results.append(res)
        bar.progress((idx + 1) / len(selected_tickers))

    if results:
        scan_df = pd.DataFrame(results)
        st.subheader("🎯 High-Probability Reversal Signals")
        buys = scan_df[scan_df['Signal'] == "EARLY BUY CALL"]
        if not buys.empty:
            st.dataframe(buys, use_container_width=True)
        else:
            st.info("No tickers met the minimum confluence score threshold (4.0+) today.")

        st.subheader("📋 Complete Technical Matrix")
        st.dataframe(scan_df, use_container_width=True)
        
