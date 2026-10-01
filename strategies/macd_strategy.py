"""MACD strategy — buy when MACD line crosses above its signal line."""

import logging

import pandas as pd

from config import MACD_FAST, MACD_SIGNAL, MACD_SLOW
from strategies.base import BaseStrategy

logger = logging.getLogger(__name__)


class MACDStrategy(BaseStrategy):
    """
    Moving Average Convergence/Divergence (MACD) strategy.

    Generates a buy signal when the MACD line crosses above its signal line
    and a sell signal when it crosses below.

    Args:
        fast:   EMA period for the fast line.
        slow:   EMA period for the slow line.
        signal: EMA period smoothing the MACD histogram.
    """

    def __init__(
        self,
        fast: int = MACD_FAST,
        slow: int = MACD_SLOW,
        signal: int = MACD_SIGNAL,
    ) -> None:
        if fast >= slow:
            raise ValueError(f"fast ({fast}) must be less than slow ({slow})")
        self.fast = fast
        self.slow = slow
        self.signal = signal

    @property
    def name(self) -> str:
        return f"MACD({self.fast}/{self.slow}/{self.signal})"

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add 'macd', 'macd_signal', 'macd_hist', and 'signal' columns.

        Buy signal (1):  MACD crosses above signal line.
        Sell signal (-1): MACD crosses below signal line.
        """
        df = df.copy()

        min_bars = self.slow + self.signal
        if len(df) < min_bars:
            logger.warning(
                "Insufficient data (%d bars) for MACD(%d/%d/%d); need at least %d bars.",
                len(df), self.fast, self.slow, self.signal, min_bars,
            )
            df["macd"] = float("nan")
            df["macd_signal"] = float("nan")
            df["macd_hist"] = float("nan")
            df["signal"] = 0
            return df

        ema_fast = df["Close"].ewm(span=self.fast, adjust=False).mean()
        ema_slow = df["Close"].ewm(span=self.slow, adjust=False).mean()

        df["macd"] = ema_fast - ema_slow
        df["macd_signal"] = df["macd"].ewm(span=self.signal, adjust=False).mean()
        df["macd_hist"] = df["macd"] - df["macd_signal"]

        prev_macd = df["macd"].shift(1)
        prev_sig = df["macd_signal"].shift(1)

        buy_signal = (prev_macd <= prev_sig) & (df["macd"] > df["macd_signal"])
        sell_signal = (prev_macd >= prev_sig) & (df["macd"] < df["macd_signal"])

        df["signal"] = 0
        df.loc[buy_signal, "signal"] = 1
        df.loc[sell_signal, "signal"] = -1

        buys = buy_signal.sum()
        sells = sell_signal.sum()
        logger.debug("%s: %d buy signals, %d sell signals", self.name, buys, sells)

        return df
