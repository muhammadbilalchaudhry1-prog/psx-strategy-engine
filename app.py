"""Main Streamlit application for PSX Strategy Engine."""

import streamlit as st
import pandas as pd
import logging
from datetime import datetime

from config import (
    PAGE_TITLE,
    PAGE_LAYOUT,
    VALID_PSX_SYMBOLS,
    DEFAULT_RISK_PERCENTAGE,
    MIN_RISK_PERCENTAGE,
    MAX_RISK_PERCENTAGE,
    DATA_CACHE_TTL,
)
from data_fetcher import fetch_live_psx_data
from strategy import StrategyEngine

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Streamlit config
st.set_page_config(
    page_title=PAGE_TITLE,
    layout=PAGE_LAYOUT,
    initial_sidebar_state="expanded"
)

# Initialize session state
if 'strategy_engine' not in st.session_state:
    st.session_state.strategy_engine = StrategyEngine()


def render_signal_display(signal_obj, source: str):
    """Render the main signal display card."""
    
    # Color mapping
    signal_color_map = {
        "BUY": "#10b981",   # Green
        "SELL": "#ef4444",  # Red
        "HOLD": "#f59e0b"   # Orange
    }
    
    signal_color = signal_color_map.get(signal_obj.signal, "#6b7280")
    
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); 
                padding: 30px; border-radius: 15px; border: 3px solid {signal_color}; 
                text-align: center; margin-bottom: 20px;">
        <h2 style="margin: 0; color: #94a3b8; font-size: 16px;">PSX Strategy Signal</h2>
        <h1 style="margin: 15px 0 0 0; color: #ffffff; font-size: 28px;">{signal_obj.price:.2f} PKR</h1>
        <h1 style="margin: 15px 0; color: {signal_color}; font-size: 56px; font-weight: bold;">{signal_obj.signal}</h1>
        <p style="margin: 10px 0 0 0; color: #cbd5e1; font-size: 13px;">
            <strong>Data Source:</strong> {source} | <strong>Last Updated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        </p>
        <p style="margin: 5px 0 0 0; color: #94a3b8; font-size: 12px;">
            Confidence: {signal_obj.confidence*100:.0f}% | Regime: {signal_obj.regime}
        </p>
    </div>
    """, unsafe_allow_html=True)


def render_metrics(signal_obj):
    """Render metric cards."""
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="Trend Score",
            value=f"{signal_obj.trend_score:+.2f}",
            help="EMA momentum normalized by volatility. >0 = uptrend, <0 = downtrend"
        )
    
    with col2:
        st.metric(
            label="Z-Score (Mean Reversion)",
            value=f"{signal_obj.z_score:+.2f}",
            help="Standard deviations from 20-day SMA. >2 = overbought, <-2 = oversold"
        )
    
    with col3:
        st.metric(
            label="Conviction Score",
            value=f"{signal_obj.conviction:+.2f}",
            help="Weighted signal strength. Buy threshold: >1.0, Sell threshold: <-1.0"
        )
    
    with col4:
        st.metric(
            label="Market Regime",
            value="High Vol" if signal_obj.vol_ratio > 0.035 else "Low Vol",
            delta=f"Volatility: {signal_obj.vol_ratio*100:.2f}%",
            help="Volatility ratio (ATR/Price). Determines signal weighting strategy."
        )
    
    col5, col6, col7, col8 = st.columns(4)
    
    with col5:
        st.metric(
            label="ATR 14 (Daily Range)",
            value=f"PKR {signal_obj.atr:.2f}",
            help="Average True Range over 14 days. Measures volatility."
        )
    
    with col6:
        stop_loss_text = f"PKR {signal_obj.stop_loss:.2f}" if signal_obj.stop_loss else "N/A"
        st.metric(
            label="Suggested Stop Loss",
            value=stop_loss_text,
            help="2x ATR away from entry price. Adjust based on risk tolerance."
        )
    
    with col7:
        st.metric(
            label="Position Size",
            value=f"{signal_obj.position_size:.1f}%",
            help="Suggested position size as % of portfolio. Capped at 100%."
        )
    
    with col8:
        st.metric(
            label="Confidence",
            value=f"{signal_obj.confidence*100:.0f}%",
            help="Signal strength based on conviction score magnitude."
        )


def main():
    """Main application flow."""
    
    st.title("🇵🇰 PSX Live Quantitative Strategy Engine")
    st.markdown(
        "Real-time trading signals powered by technical analysis. "
        "**Disclaimer:** This is for educational purposes only. Not financial advice."
    )
    
    # Sidebar controls
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        ticker_input = st.selectbox(
            label="Select PSX Stock Ticker",
            options=VALID_PSX_SYMBOLS,
            help="Choose from validated PSX stock symbols"
        )
        
        risk_pct = st.slider(
            label="Target Risk per Trade (%)",
            min_value=MIN_RISK_PERCENTAGE,
            max_value=MAX_RISK_PERCENTAGE,
            value=DEFAULT_RISK_PERCENTAGE,
            step=0.5,
            help="Percentage of account to risk on a single trade"
        )
        
        st.divider()
        st.subheader("📚 Strategy Info")
        st.info(
            "This engine combines:\n"
            "- **Trend Following:** EMA-based momentum (12/26 period)\n"
            "- **Mean Reversion:** Z-score analysis (20-day SMA)\n"
            "- **Volatility Regime:** Adaptive weighting based on ATR\n\n"
            "Regime switches strategy when volatility (ATR/Price) > 3.5%"
        )
        
        st.divider()
        st.subheader("⚠️ Risk Disclaimer")
        st.warning(
            "This tool is for educational and research purposes. "
            "Always conduct your own due diligence. Past performance ≠ future results."
        )
    
    # Main content
    if ticker_input:
        with st.spinner(f"🔄 Fetching live data for {ticker_input}.PSX..."):
            df, source = fetch_live_psx_data(ticker_input)
        
        if df is None or len(df) < 30:
            st.error(
                f"❌ Could not fetch sufficient data for '{ticker_input}'.\n\n"
                f"Details: {source}\n\n"
                f"**Troubleshooting:**\n"
                f"- Verify the ticker symbol is correct (e.g., SYS, ENGRO, OGDC)\n"
                f"- Check your internet connection\n"
                f"- Data sources may be temporarily unavailable\n\n"
                f"**Alternative:** Upload a CSV file with historical OHLC data"
            )
            return
        
        # Ensure we have required columns
        df = df[['Open', 'High', 'Low', 'Close']].dropna()
        
        try:
            # Run strategy analysis
            signal = st.session_state.strategy_engine.analyze(df, risk_pct)
            
            # Render UI
            render_signal_display(signal, source)
            render_metrics(signal)
            
            # Historical chart
            st.subheader("📊 Historical Price & Moving Averages")
            
            # Calculate EMAs for chart
            df_plot = df.copy()
            df_plot['EMA_12'] = df_plot['Close'].ewm(span=12, adjust=False).mean()
            df_plot['EMA_26'] = df_plot['Close'].ewm(span=26, adjust=False).mean()
            
            chart_df = df_plot[['Close', 'EMA_12', 'EMA_26']].iloc[-100:]  # Last 100 days
            st.line_chart(
                chart_df,
                use_container_width=True,
                height=400
            )
            
            # Raw data table
            st.subheader("📋 Recent Data")
            display_df = df[['Open', 'High', 'Low', 'Close']].tail(10).copy()
            display_df = display_df.applymap(lambda x: f"{x:.2f}" if isinstance(x, (int, float)) else x)
            st.dataframe(display_df, use_container_width=True)
            
        except Exception as e:
            st.error(f"❌ Strategy analysis failed: {str(e)}")
            logger.exception(f"Analysis error: {str(e)}")


if __name__ == "__main__":
    main()
