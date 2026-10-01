"""Donchian Channel Breakout strategy — buy new highs, exit at channel low."""

import logging

import pandas as pd

from strategies.base import BaseStrategy

logger = logging.getLogger(__name__)


class DonchianBreakout(BaseStrategy):
    """
    Donchian Channel (turtle trading) breakout strategy.

    Entry:  Price closes above the upper channel (N-bar high) → buy.
    Exit:   Price closes below the exit channel (exit_period-bar low) → sell.

    This is a pure trend-following strategy — it catches big moves but
    gets whipsawed in sideways markets.

    Args:
        entry_period: Look-back for the breakout channel (default 20).
        exit_period:  Look-back for the exit channel (default 10).
    """

    def __init__(self, entry_period: int = 20, exit_period: int = 10) -> None:
        self.entry_period = entry_period
        self.exit_period = exit_period

    @property
    def name(self) -> str:
        return f"Donchian({self.entry_period}/{self.exit_period})"

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        min_bars = self.entry_period + 1
        if len(df) < min_bars:
            logger.warning(
                "Insufficient data (%d bars) for Donchian(%d); need %d.",
                len(df), self.entry_period, min_bars,
            )
            df["signal"] = 0
            return df

        # Upper channel = highest high over entry_period (shifted to avoid look-ahead)
        df["dc_upper"] = df["High"].shift(1).rolling(self.entry_period).max()
        # Lower exit channel = lowest low over exit_period (shifted)
        df["dc_lower"] = df["Low"].shift(1).rolling(self.exit_period).min()

        df["signal"] = 0

        # Buy when close breaks above the upper channel
        df.loc[df["Close"] > df["dc_upper"], "signal"] = 1
        # Sell when close breaks below the exit channel
        df.loc[df["Close"] < df["dc_lower"], "signal"] = -1

        # Only keep the first signal in each consecutive run
        df["signal"] = df["signal"].where(df["signal"] != df["signal"].shift(1), 0)

        buys = (df["signal"] == 1).sum()
        sells = (df["signal"] == -1).sum()
        logger.debug("%s: %d buy signals, %d sell signals", self.name, buys, sells)
        return df
