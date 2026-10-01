"""Default configuration settings for the backtester."""

# Data
CACHE_DIR = "cache"
DEFAULT_INTERVAL = "1d"

# Portfolio
DEFAULT_INITIAL_CAPITAL = 100_000.0
DEFAULT_COMMISSION = 0.0          # $ per trade (modern brokers = $0)
DEFAULT_SLIPPAGE = 0.001          # 0.1% of price

# Risk management
DEFAULT_RISK_PER_TRADE = 0.02     # 2% of portfolio per trade
DEFAULT_MAX_POSITIONS = 10
DEFAULT_MAX_EXPOSURE = 1.0        # 100% of portfolio
DEFAULT_DAILY_LOSS_LIMIT = 0.05   # 5% of portfolio

# Stop loss defaults (None = disabled)
DEFAULT_STOP_LOSS_PCT = None
DEFAULT_TRAILING_STOP_PCT = None
DEFAULT_ATR_MULTIPLIER = 2.0
DEFAULT_ATR_PERIOD = 14

# Performance
DEFAULT_RISK_FREE_RATE = 0.045    # 4.5% annualised
TRADING_DAYS_PER_YEAR = 252

# Strategy defaults — SMA Crossover
SMA_SHORT_WINDOW = 20
SMA_LONG_WINDOW = 50

# Strategy defaults — RSI Mean Reversion
RSI_PERIOD = 14
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70

# Strategy defaults — MACD
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
