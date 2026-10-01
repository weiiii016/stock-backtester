"""SMA Crossover strategy — buy when fast SMA crosses above slow SMA."""

import logging

import pandas as pd

from config import SMA_LONG_WINDOW, SMA_SHORT_WINDOW
from strategies.base import BaseStrategy

logger = logging.getLogger(__name__)


class SMACrossover(BaseStrategy):
    """
    Simple Moving Average (SMA) crossover strategy.

    Generates a buy signal when the short-period SMA crosses above the
    long-period SMA, and a sell signal on the reverse crossover.

    Args:
        short_window: Look-back period for the fast SMA.
        long_window:  Look-back period for the slow SMA.
    """

    def __init__(
        self,
        short_window: int = SMA_SHORT_WINDOW,
        long_window: int = SMA_LONG_WINDOW,
    ) -> None:
        if short_window >= long_window:
            raise ValueError(
                f"short_window ({short_window}) must be less than long_window ({long_window})"
            )
        self.short_window = short_window
        self.long_window = long_window

    @property
    def name(self) -> str:
        return f"SMA({self.short_window}/{self.long_window})"

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add 'sma_short', 'sma_long', and 'signal' columns to df.

        Signal transitions only — 1 on the crossover bar, -1 on crossunder,
        0 everywhere else.
        """
        df = df.copy()

        min_bars = self.long_window + 1
        if len(df) < min_bars:
            logger.warning(
                "Insufficient data (%d bars) for SMA(%d/%d); need at least %d bars.",
                len(df), self.short_window, self.long_window, min_bars,
            )
            df["sma_short"] = float("nan")
            df["sma_long"] = float("nan")
            df["signal"] = 0
            return df

        df["sma_short"] = df["Close"].rolling(self.short_window).mean()
        df["sma_long"] = df["Close"].rolling(self.long_window).mean()

        # Position: 1 when short is above long, 0 otherwise
        df["_position"] = (df["sma_short"] > df["sma_long"]).astype(int)

        # Crossover/crossunder = change in position
        df["signal"] = df["_position"].diff().fillna(0).astype(int)
        df.drop(columns=["_position"], inplace=True)

        buys = (df["signal"] == 1).sum()
        sells = (df["signal"] == -1).sum()
        logger.debug("%s: %d buy signals, %d sell signals", self.name, buys, sells)

        return df
