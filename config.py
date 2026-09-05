"""Configuration parameters for PSX Strategy Engine."""

# ============================================================================
# DATA SOURCES
# ============================================================================
PSX_API_ENDPOINTS = {
    "primary": "https://api.mstock.com/stocks/{symbol}",
    "fallback_yfinance": True,
    "fallback_scrape": True,
}

YAHOO_FINANCE_SUFFIX = ".KA"  # Karachi Stock Exchange suffix
DATA_CACHE_TTL = 60  # seconds
FETCH_TIMEOUT = 10  # seconds

# ============================================================================
# TECHNICAL INDICATORS
# ============================================================================
ATR_PERIOD = 14
EMA_FAST_PERIOD = 12
EMA_SLOW_PERIOD = 26
SMA_PERIOD = 20
Z_SCORE_PERIOD = 20

# Historical data period
HISTORICAL_PERIOD = "6mo"
HISTORICAL_INTERVAL = "1d"
MIN_DATA_POINTS = 30

# ============================================================================
# STRATEGY PARAMETERS
# ============================================================================
# Volatility regime threshold
VOL_RATIO_THRESHOLD = 0.035

# Conviction score thresholds for signals
CONVICTION_BUY_THRESHOLD = 1.0
CONVICTION_SELL_THRESHOLD = -1.0

# Regime weights: (trend_weight, mean_reversion_weight)
HIGH_VOL_REGIME_WEIGHTS = (0.3, -1.2)  # Favor mean reversion
LOW_VOL_REGIME_WEIGHTS = (0.7, -0.3)   # Favor trend following

# Stop loss multiplier (ATR units)
STOP_LOSS_ATR_MULTIPLIER = 2.0

# ============================================================================
# RISK MANAGEMENT
# ============================================================================
DEFAULT_RISK_PERCENTAGE = 2.0  # % of account per trade
MIN_RISK_PERCENTAGE = 0.5
MAX_RISK_PERCENTAGE = 5.0
MAX_POSITION_SIZE = 100.0  # % of portfolio

# ============================================================================
# UI/UX
# ============================================================================
PAGE_LAYOUT = "wide"
PAGE_TITLE = "PSX Live Strategy Engine"
UPDATE_INTERVAL = 60  # seconds for auto-refresh

# ============================================================================
# VALID PSX SYMBOLS (Sample)
# ============================================================================
VALID_PSX_SYMBOLS = [
    "SYS", "ENGRO", "LUCK", "OGDC", "TRG", "AIRLINK", "PPL",
    "HUBC", "MARI", "POL", "PGAS", "SNGP", "SSGC", "ATRL",
    "BAFL", "BAHL", "BIPL", "BOP", "DAWH", "DCCI", "DGKC",
    "EPCL", "FCCL", "FIMM", "FFC", "FLYH", "GATM", "GHCC",
    "GLAXO", "GNDF", "GOPL", "GRDH", "GRPH", "GTYR", "HBPL"
]
