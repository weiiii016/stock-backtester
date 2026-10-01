"""Bollinger Bands mean-reversion strategy."""

import logging

import pandas as pd

from strategies.base import BaseStrategy

logger = logging.getLogger(__name__)


class BBandsStrategy(BaseStrategy):
    """
    Bollinger Bands mean-reversion strategy.

    Entry:  Price crosses down to or below the lower band → buy signal.
    Exit:   Managed by the engine via stops.  The strategy publishes the
            upper band value in a 'trigger_price' column; the engine uses
            this as the level at which to activate a trailing stop.

    Args:
        period:  Look-back for the middle SMA and standard deviation.
        num_std: Number of standard deviations for the bands (default 2).
    """

    def __init__(self, period: int = 20, num_std: float = 2.0) -> None:
        if period < 2:
            raise ValueError("period must be >= 2")
        self.period = period
        self.num_std = num_std

    @property
    def name(self) -> str:
        return f"BBands({self.period}, {self.num_std}σ)"

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add bb_upper, bb_middle, bb_lower, trigger_price, and signal columns.

        signal = 1  when close crosses from above to at-or-below the lower band.
        signal = 0  all other bars (exits handled by stop/trailing).

        trigger_price = bb_upper at each bar — the engine activates the
        trailing stop when price reaches this level.
        """
        df = df.copy()

        min_bars = self.period + 1
        if len(df) < min_bars:
            logger.warning(
                "Insufficient data (%d bars) for BBands(%d); need at least %d.",
                len(df), self.period, min_bars,
            )
            for col in ("bb_upper", "bb_middle", "bb_lower", "trigger_price", "signal"):
                df[col] = float("nan") if col != "signal" else 0
            return df

        rolling = df["Close"].rolling(self.period)
        df["bb_middle"] = rolling.mean()
        df["bb_std"]    = rolling.std(ddof=1)
        df["bb_upper"]  = df["bb_middle"] + self.num_std * df["bb_std"]
        df["bb_lower"]  = df["bb_middle"] - self.num_std * df["bb_std"]

        # Engine reads this column to set the profit-trigger price at entry
        df["trigger_price"] = df["bb_upper"]

        # Buy when price crosses down into or below the lower band
        prev_close = df["Close"].shift(1)
        buy = (prev_close > df["bb_lower"]) & (df["Close"] <= df["bb_lower"])

        df["signal"] = 0
        df.loc[buy, "signal"] = 1
        df.drop(columns=["bb_std"], inplace=True)

        logger.debug("%s: %d buy signals", self.name, int(buy.sum()))
        return df
