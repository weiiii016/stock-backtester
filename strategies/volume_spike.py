"""Volume Spike Reversal strategy — buy capitulation events."""

import logging

import pandas as pd

from strategies.base import BaseStrategy

logger = logging.getLogger(__name__)


class VolumeSpikeReversal(BaseStrategy):
    """
    Volume spike + price drop reversal strategy.

    Detects capitulation: a bar where volume is significantly above its
    rolling average AND the bar closes red (down). The next bar gets a
    buy signal on the assumption that panic selling is exhausted.

    Works best on volatile assets with occasional sharp sell-offs followed
    by mean reversion (e.g. COIN, high-beta tech).

    Args:
        vol_period:     Rolling period for volume average (default 20).
        vol_multiplier: Volume must exceed average × multiplier (default 2.0).
        price_drop_pct: Minimum intra-bar drop (close vs open) to qualify
                        as a down bar (default 0.01 = 1%).
    """

    def __init__(
        self,
        vol_period: int = 20,
        vol_multiplier: float = 2.0,
        price_drop_pct: float = 0.01,
    ) -> None:
        self.vol_period = vol_period
        self.vol_multiplier = vol_multiplier
        self.price_drop_pct = price_drop_pct

    @property
    def name(self) -> str:
        return f"VolSpike({self.vol_period}, {self.vol_multiplier}x, {self.price_drop_pct*100:.0f}%)"

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        min_bars = self.vol_period + 2
        if len(df) < min_bars:
            logger.warning("Insufficient data for %s", self.name)
            df["signal"] = 0
            return df

        # Rolling average volume
        df["vol_avg"] = df["Volume"].rolling(self.vol_period).mean()
        df["vol_ratio"] = df["Volume"] / df["vol_avg"]

        # Detect capitulation bars: high volume + red candle with significant drop
        bar_return = (df["Close"] - df["Open"]) / df["Open"]
        capitulation = (
            (df["vol_ratio"] >= self.vol_multiplier)
            & (bar_return <= -self.price_drop_pct)
        )

        # Buy on the bar AFTER capitulation (shift forward)
        df["signal"] = 0
        df.loc[capitulation.shift(1).fillna(False).astype(bool), "signal"] = 1

        logger.debug("%s: %d buy signals", self.name, int((df["signal"] == 1).sum()))
        return df
