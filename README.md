# 🇵🇰 PSX Live Quantitative Strategy Engine

A production-ready Streamlit application for real-time technical analysis and trading signals on Pakistan Stock Exchange (PSX) stocks.

## 🎯 Features

✅ **Real-time Data Fetching**
- Multiple data sources with intelligent fallback (Yahoo Finance → PSX Portal)
- 60-second caching to prevent API rate limiting
- Graceful error handling with no synthetic data generation

✅ **Advanced Technical Analysis**
- **ATR 14:** Volatility-based position sizing
- **EMA 12/26:** Trend identification
- **Z-Score (20-day SMA):** Mean reversion signals
- **Regime Detection:** Adaptive strategy based on market conditions

✅ **Intelligent Signal Generation**
- Conviction score combining trend and mean reversion
- Volatility-aware regime switching
- Stop loss recommendations (2x ATR)
- Position size calculation based on risk tolerance

✅ **Professional UI**
- Clean, dark-themed dashboard
- Real-time metric cards
- Historical price charts with moving averages
- Confidence scoring (0-100%)

## 🚀 Quick Start

### Installation

```bash
git clone https://github.com/muhammadbilalchaudhry1-prog/psx-strategy-engine.git
cd psx-strategy-engine

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Run the App

```bash
streamlit run app.py
```

The app will open at `http://localhost:8501`

## 📊 How It Works

### Strategy Logic

1. **Data Acquisition**
   - Fetches 6 months of daily OHLC data from Yahoo Finance
   - Falls back to PSX web scraping if Yahoo Finance unavailable
   - Validates minimum 30 data points before analysis

2. **Indicator Calculation**
   ```
   ATR 14 (Volatility) → Trend Score
                      ↓
   EMA 12/26 (Momentum) → Conviction Score
                       ↓
   Z-Score (Mean Reversion) → Trading Signal
   ```

3. **Regime Detection**
   - **Low Volatility (ATR/Price < 3.5%):** Favor trend-following
     - Conviction = 0.7 × Trend Score - 0.3 × Z-Score
   - **High Volatility (ATR/Price ≥ 3.5%):** Favor mean reversion
     - Conviction = 0.3 × Trend Score - 1.2 × Z-Score

4. **Signal Generation**
   - **BUY:** Conviction > 1.0
   - **SELL:** Conviction < -1.0
   - **HOLD:** -1.0 ≤ Conviction ≤ 1.0

### Risk Management

- **Stop Loss:** 2 × ATR from entry price
- **Position Size:** Scaled by risk percentage and volatility
  - Formula: `min((risk_pct / vol_ratio) × 100, 100%)`
- **Adjustable Risk:** 0.5% - 5.0% per trade

## 📁 Project Structure

```
psx-strategy-engine/
├── app.py                 # Main Streamlit application
├── config.py              # Configurable parameters
├── data_fetcher.py        # Data acquisition with fallbacks
├── strategy.py            # Technical analysis & signal generation
├── requirements.txt       # Python dependencies
└── README.md              # This file
```

## ⚙️ Configuration

Edit `config.py` to customize:

- **Data Sources:** `PSX_API_ENDPOINTS`, `YAHOO_FINANCE_SUFFIX`
- **Indicators:** `ATR_PERIOD`, `EMA_FAST_PERIOD`, `EMA_SLOW_PERIOD`
- **Strategy:** `CONVICTION_BUY_THRESHOLD`, `CONVICTION_SELL_THRESHOLD`
- **Risk:** `DEFAULT_RISK_PERCENTAGE`, `STOP_LOSS_ATR_MULTIPLIER`
- **UI:** `PAGE_LAYOUT`, `UPDATE_INTERVAL`

### Adding PSX Symbols

Update `VALID_PSX_SYMBOLS` in `config.py`:

```python
VALID_PSX_SYMBOLS = [
    "SYS", "ENGRO", "LUCK", "OGDC", "TRG", "AIRLINK", "PPL",
    # Add more symbols here
]
```

## 📈 Supported Stocks

Current symbols include:

**Large Cap:** SYS, ENGRO, LUCK, OGDC, MARI, PPL, SNGP
**Oil & Gas:** EPCL, POL, PGAS, ATRL
**Financials:** GLAXO, BAFL, BAHL
**Technology:** BIPL, DCCI

## 🔍 Interpreting Signals

### Metrics Explained

| Metric | Meaning |
|--------|----------|
| **Trend Score** | Momentum normalized by volatility. +/- indicates direction. |
| **Z-Score** | Distance from 20-day average. ±2 signals extremes. |
| **Conviction** | Weighted signal strength. Larger magnitude = stronger signal. |
| **ATR** | Daily range expectation. Used for stop loss sizing. |
| **Confidence** | Signal reliability (0-100%). Higher = stronger conviction. |
| **Vol Ratio** | Volatility as % of price. Triggers regime switch at 3.5%. |

### Regime Example

**Trending Market (Low Vol)**
- ATR/Price = 1.5%
- Weights: 70% trend, 30% mean reversion
- Strategy: Follow momentum
- Example: Buy on bullish EMA crossover

**Choppy Market (High Vol)**
- ATR/Price = 4.2%
- Weights: 30% trend, 120% mean reversion
- Strategy: Fade extremes
- Example: Buy at oversold (-2 Z-Score)

## ⚠️ Disclaimer

**This tool is for educational and research purposes only.**

- **Not Financial Advice:** Do your own due diligence
- **Backtesting:** Strategy is not backtested on historical data
- **Risk:** Trading carries substantial risk of loss
- **Past Performance:** Does not guarantee future results
- **Use at Own Risk:** User responsible for trading decisions

## 🛠️ Troubleshooting

### "Could not fetch live market data"

1. Verify ticker symbol is correct (e.g., SYS, not SYS.KA)
2. Check internet connection
3. Yahoo Finance may be rate-limited; try again in a few minutes
4. Provide historical CSV with columns: Date, Open, High, Low, Close

### "Division by zero" in position sizing

- Occurs when ATR approaches 0 (extremely low volatility)
- App automatically defaults to 50% position size
- Monitor volatility and adjust risk percentage accordingly

### Streamlit cache warnings

- Normal with Streamlit. Restart app if experiencing stale data
- Manual refresh: Press `R` in browser or reload page

## 🔄 Data Sources

1. **Yahoo Finance (Primary)**
   - 6 months of daily OHLC data
   - Accessed via `.KA` suffix (Karachi Stock Exchange)
   - Reliable, high-volume source

2. **PSX Data Portal (Fallback)**
   - Current price only via web scraping
   - Used when Yahoo Finance unavailable
   - Limited to live price snapshot

3. **CSV Upload (Manual)**
   - Upload historical data as CSV
   - Required columns: Date, Open, High, Low, Close
   - Useful for testing or offline analysis

## 📝 License

MIT License - See LICENSE file for details

## 🤝 Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## 📧 Support

For issues or questions:
- Open an issue on GitHub
- Check existing issues for solutions
- Review the FAQ below

## ❓ FAQ

**Q: Why no synthetic data?**
A: Synthetic data is misleading and dangerous for trading. Better to fail gracefully than give false confidence.

**Q: Can I trade this directly?**
A: Not recommended without extensive backtesting and paper trading. Use as a research tool only.

**Q: How often should I check signals?**
A: Daily (market close) or intraday (multiple times). Up to your trading plan.

**Q: What's the minimum capital?**
A: No minimum, but position sizing requires meaningful account size. Adjust risk % accordingly.

**Q: Why Yahoo Finance, not PSX API?**
A: PSX doesn't have a public free API. Yahoo Finance is reliable and widely used.

---

**Built with ❤️ for the Pakistani trading community**
