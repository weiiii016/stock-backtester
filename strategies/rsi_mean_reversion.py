"""RSI Mean Reversion strategy — buy oversold, sell overbought."""

import logging

import numpy as np
import pandas as pd

from config import RSI_OVERBOUGHT, RSI_OVERSOLD, RSI_PERIOD
from strategies.base import BaseStrategy

logger = logging.getLogger(__name__)


def _compute_rsi(close: pd.Series, period: int) -> pd.Series:
    """
    Compute Wilder's Relative Strength Index.

    Args:
        close:  Series of closing prices.
        period: Look-back period (typically 14).

    Returns:
        RSI series (0–100), same index as close.
    """
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    # Use exponential moving average (Wilder's smoothing = alpha 1/period)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi


class RSIMeanReversion(BaseStrategy):
    """
    RSI Mean Reversion strategy.

    Buys when the RSI crosses *up* through the oversold threshold (momentum
    returning from oversold territory) and sells when RSI crosses *down*
    through the overbought threshold.

    Args:
        rsi_period:  Look-back period for RSI calculation.
        oversold:    RSI level below which a stock is considered oversold.
        overbought:  RSI level above which a stock is considered overbought.
    """

    def __init__(
        self,
        rsi_period: int = RSI_PERIOD,
        oversold: float = RSI_OVERSOLD,
        overbought: float = RSI_OVERBOUGHT,
    ) -> None:
        if oversold >= overbought:
            raise ValueError(
                f"oversold ({oversold}) must be less than overbought ({overbought})"
            )
        self.rsi_period = rsi_period
        self.oversold = oversold
        self.overbought = overbought

    @property
    def name(self) -> str:
        return f"RSI({self.rsi_period}, OB={self.overbought}, OS={self.oversold})"

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add 'rsi' and 'signal' columns.

        Buy signal (1):  RSI was below oversold on previous bar, now >= oversold.
        Sell signal (-1): RSI was above overbought on previous bar, now <= overbought.
        """
        df = df.copy()

        min_bars = self.rsi_period + 2
        if len(df) < min_bars:
            logger.warning(
                "Insufficient data (%d bars) for RSI(%d); need at least %d bars.",
                len(df), self.rsi_period, min_bars,
            )
            df["rsi"] = float("nan")
            df["signal"] = 0
            return df

        df["rsi"] = _compute_rsi(df["Close"], self.rsi_period)

        prev_rsi = df["rsi"].shift(1)

        buy_signal = (prev_rsi < self.oversold) & (df["rsi"] >= self.oversold)
        sell_signal = (prev_rsi > self.overbought) & (df["rsi"] <= self.overbought)

        df["signal"] = 0
        df.loc[buy_signal, "signal"] = 1
        df.loc[sell_signal, "signal"] = -1

        buys = buy_signal.sum()
        sells = sell_signal.sum()
        logger.debug("%s: %d buy signals, %d sell signals", self.name, buys, sells)

        return df
