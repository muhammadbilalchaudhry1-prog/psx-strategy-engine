import streamlit as st
import pandas as pd
import numpy as np
from scipy.signal import find_peaks
import yfinance as yf
import psxdata
import requests
from bs4 import BeautifulSoup
import plotly.graph_objects as go
from concurrent.futures import ThreadPoolExecutor

st.set_page_config(page_title="PSX EOD Multi-Day Swing Screener", layout="wide")

st.title("🇵🇰 PSX EOD Swing Trading & Fundamental Scanner")
st.caption("Post-Market / Pre-Market Multi-Day Swing Analysis Engine (2–10 Day Swing Horizon)")

def fetch_psx_announcements(symbol):
    """Scrapes recent material disclosures directly from official PSX Data Portal."""
    try:
        url = f"https://dps.psx.com.pk/company/{symbol}"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=3)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            table = soup.find("table", class_="table")
            if table:
                rows = table.find_all("tr")[1:4]
                announcements = []
                for r in rows:
                    cols = r.find_all('td')
                    if len(cols) >= 2:
                        announcements.append(f"[{cols[0].text.strip()}] {cols[1].text.strip()}")
                return announcements if announcements else ["No recent announcements."]
    except Exception:
        pass
    return ["PSX portal temporarily unreachable."]

def analyze_swing_physics(symbol):
    """Evaluates multi-day price vector, volatility contraction, and kinetic swing absorption."""
    try:
        yf_ticker = f"{symbol}.KA"
        df = yf.download(yf_ticker, period="1y", interval="1d", progress=False)
        if df.empty or len(df) < 60:
            return None

        if hasattr(df.columns, 'get_level_values'):
            df.columns = df.columns.get_level_values(0)

        df = df[['Open', 'High', 'Low', 'Close', 'Volume']].dropna()

        # 1. Kinematics (Force = Vol_Norm * Acceleration)
        df['Price_Vel'] = df['Close'].diff()
        df['Price_Accel'] = df['Price_Vel'].diff()
        vol_norm = df['Volume'] / df['Volume'].rolling(20).mean()
        df['Kinetic_Force'] = vol_norm * df['Price_Accel']

        # 2. Volatility & Structural Levels
        df['TR'] = np.maximum(
            df['High'] - df['Low'],
            np.maximum(abs(df['High'] - df['Close'].shift(1)), abs(df['Low'] - df['Close'].shift(1)))
        )
        df['ATR'] = df['TR'].rolling(14).mean()
        df['SMA_20'] = df['Close'].rolling(20).mean()
        df['STD_20'] = df['Close'].rolling(20).std()
        df['BB_Upper'] = df['SMA_20'] + (2 * df['STD_20'])
        df['BB_Lower'] = df['SMA_20'] - (2 * df['STD_20'])

        # Swing Support & Resistance over 40 sessions
        supp_40 = float(df['Low'].tail(40).min())
        res_40 = float(df['High'].tail(40).max())

        # Harmonic Pivot Geometry
        peaks, _ = find_peaks(df['Close'].values, distance=5)
        troughs, _ = find_peaks(-df['Close'].values, distance=5)
        harmonic_setup = "None"
        if len(peaks) >= 2 and len(troughs) >= 2:
            A = df['Close'].iloc[peaks[-2]]
            B = df['Close'].iloc[troughs[-2]]
            retrace = (A - B) / A if A != 0 else 0
            if 0.382 <= abs(retrace) <= 0.618:
                harmonic_setup = "Bullish ABC Harmonic"

        latest = df.iloc[-1]
        close_p = float(latest['Close'])
        atr_p = float(latest['ATR'])

        # 3. Quantitative Swing Matrix Scoring
        score = 0.0
        # Absorbing liquidity at support with negative velocity & positive force
        if latest['Kinetic_Force'] > 0 and latest['Price_Vel'] < 0: score += 2.5
        if harmonic_setup != "None": score += 2.5
        if close_p <= df['BB_Lower'].iloc[-1]: score += 1.5
        if close_p <= supp_40 * 1.025: score += 2.0

        if score >= 4.5:
            signal = "HIGH CONFLUENCE SWING BUY"
            entry = close_p
            stop_loss = max(supp_40 - (1.2 * atr_p), 0.5)
            target = res_40
        elif score >= 3.0:
            signal = "SWING ACCUMULATE"
            entry = close_p
            stop_loss = max(supp_40 - (1.5 * atr_p), 0.5)
            target = close_p + (2.0 * (close_p - stop_loss))
        else:
            signal, entry, stop_loss, target = "NEUTRAL / HOLD", None, None, None

        return {
            "df": df, "Ticker": symbol, "Signal": signal,
            "Price": close_p, "Support": supp_40, "Resistance": res_40,
            "Entry": entry, "Target": target, "Stop Loss": stop_loss,
            "Harmonic Setup": harmonic_setup, "Score": round(score, 2)
        }
    except Exception:
        return None

# --- SECTION 1: SINGLE STOCK SEARCH & DEEP SWING DIAGNOSTIC ---
st.subheader("🔍 Single Stock Swing Analysis")
search_col1, search_col2 = st.columns([3, 1])

with search_col1:
    search_ticker = st.text_input("Enter PSX Symbol (e.g. TPLP, NCPL, SILK, GGL, SYS):", value="SYS").upper().strip()

with search_col2:
    trigger_search = st.button("🔎 Analyze Swing Vector")

if search_ticker and (trigger_search or search_ticker):
    with st.spinner(f"Retrieving EOD multi-day vector metrics for {search_ticker}.PSX..."):
        res = analyze_swing_physics(search_ticker)
        if res:
            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("Ticker", res['Ticker'])
            m2.metric("EOD Closing Price", f"PKR {res['Price']:.2f}")
            m3.metric("Swing Signal", res['Signal'])
            m4.metric("Ideal Entry", f"PKR {res['Entry']:.2f}" if res['Entry'] else "-")
            m5.metric("Target (Multi-Day)", f"PKR {res['Target']:.2f}" if res['Target'] else "-")

            m6, m7, m8 = st.columns(3)
            m6.metric("Structural Support Floor", f"PKR {res['Support']:.2f}")
            m7.metric("Resistance Target Cap", f"PKR {res['Resistance']:.2f}")
            m8.metric("Hard Stop Loss", f"PKR {res['Stop Loss']:.2f}" if res['Stop Loss'] else "-")

            # Candlestick Charting for Swing Outlook
            df_plot = res['df']
            fig = go.Figure(data=[go.Candlestick(
                x=df_plot.index[-120:], open=df_plot['Open'][-120:], high=df_plot['High'][-120:],
                low=df_plot['Low'][-120:], close=df_plot['Close'][-120:], name=res['Ticker']
            )])
            fig.add_trace(go.Scatter(x=df_plot.index[-120:], y=df_plot['BB_Upper'][-120:], line=dict(color='orange', width=1), name='Upper Band'))
            fig.add_trace(go.Scatter(x=df_plot.index[-120:], y=df_plot['BB_Lower'][-120:], line=dict(color='blue', width=1), name='Lower Band'))
            fig.update_layout(title=f"{res['Ticker']} - 120-Day Daily EOD Chart", template="plotly_dark", height=430)
            st.plotly_chart(fig, use_container_width=True)

            # PSX Official Announcements Parsing
            with st.expander(f"📰 Official PSX Data Portal Filings for {search_ticker}"):
                announcements = fetch_psx_announcements(search_ticker)
                for item in announcements:
                    st.write(f"- {item}")
        else:
            st.error(f"Could not load data for '{search_ticker}'. Check the ticker symbol.")

st.markdown("---")

# --- SECTION 2: MARKET-WIDE AUTOMATED SWING SCANNER ---
st.subheader("🌐 Whole-Market EOD Swing Scanner")
scan_mode = st.radio("Select Universe:", ["KSE-100 Actives", "Full PSX Market (500+ Equities)"], horizontal=True)

if st.button("🚀 Run Whole-Market EOD Scan"):
    with st.spinner("Executing post-market scanner across PSX directory..."):
        if scan_mode == "KSE-100 Actives":
            tickers_to_scan = ["SYS", "ENGRO", "LUCK", "OGDC", "PPL", "TRG", "AIRLINK", "HUBC", "MEBL", "EFERT", "SAZEW", "PSO", "MARI", "DGKC", "FCCL", "TPLP", "NCPL", "GGL"]
        else:
            try:
                tickers_to_scan = psxdata.tickers() # Fetch all 500+ PSX stocks
            except Exception:
                tickers_to_scan = ["SYS", "ENGRO", "LUCK", "OGDC", "PPL", "TRG", "AIRLINK", "HUBC", "MEBL", "EFERT"]

        scan_results = []
        progress_bar = st.progress(0)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(analyze_swing_physics, sym): sym for sym in tickers_to_scan}
            for idx, future in enumerate(futures):
                r = future.result()
                if r:
                    scan_results.append({
                        "Ticker": r['Ticker'], "Signal": r['Signal'], "Price": f"PKR {r['Price']:.2f}",
                        "Entry": f"PKR {r['Entry']:.2f}" if r['Entry'] else "-",
                        "Target": f"PKR {r['Target']:.2f}" if r['Target'] else "-",
                        "Stop Loss": f"PKR {r['Stop Loss']:.2f}" if r['Stop Loss'] else "-",
                        "Support": f"PKR {r['Support']:.2f}", "Resistance": f"PKR {r['Resistance']:.2f}",
                        "Score": r['Score']
                    })
                progress_bar.progress((idx + 1) / len(tickers_to_scan))

        if scan_results:
            results_df = pd.DataFrame(scan_results)
            st.subheader("🎯 Primary Multi-Day Swing Recommendations")
            swing_buys = results_df[results_df['Signal'].isin(["HIGH CONFLUENCE SWING BUY", "SWING ACCUMULATE"])]
            
            if not swing_buys.empty:
                st.dataframe(swing_buys.sort_values(by="Score", ascending=False), use_container_width=True)
            else:
                st.info("No stocks currently satisfy the strict multi-day swing threshold today.")

            st.subheader("📋 Complete Market Scan Breakdown")
            st.dataframe(results_df, use_container_width=True)
        
