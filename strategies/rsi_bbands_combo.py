"""RSI + Bollinger Bands combo strategy — double-confirmation mean reversion."""

import logging

import numpy as np
import pandas as pd

from strategies.base import BaseStrategy

logger = logging.getLogger(__name__)


def _compute_rsi(close: pd.Series, period: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


class RSIBBandsCombo(BaseStrategy):
    """
    Double-confirmation mean reversion: RSI oversold + price at BB lower band.

    Entry:  RSI < oversold AND close <= lower Bollinger Band → buy.
    Exit:   Managed by stops. trigger_price is set to BB upper for trailing
            stop activation (same as plain BBands strategy).

    The dual filter dramatically reduces false entries compared to either
    indicator alone — particularly useful on noisy hourly data.

    Args:
        rsi_period:  RSI look-back (default 7).
        oversold:    RSI oversold threshold (default 35).
        bb_period:   Bollinger Bands SMA period (default 20).
        bb_std:      Number of standard deviations (default 1.5).
    """

    def __init__(
        self,
        rsi_period: int = 7,
        oversold: float = 35,
        bb_period: int = 20,
        bb_std: float = 1.5,
    ) -> None:
        self.rsi_period = rsi_period
        self.oversold = oversold
        self.bb_period = bb_period
        self.bb_std = bb_std

    @property
    def name(self) -> str:
        return f"RSI_BB({self.rsi_period}<{self.oversold}, BB{self.bb_period}/{self.bb_std}σ)"

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        min_bars = max(self.rsi_period, self.bb_period) + 2
        if len(df) < min_bars:
            logger.warning("Insufficient data for %s", self.name)
            df["signal"] = 0
            return df

        # RSI
        df["rsi"] = _compute_rsi(df["Close"], self.rsi_period)

        # Bollinger Bands
        rolling = df["Close"].rolling(self.bb_period)
        df["bb_middle"] = rolling.mean()
        bb_std = rolling.std(ddof=1)
        df["bb_upper"] = df["bb_middle"] + self.bb_std * bb_std
        df["bb_lower"] = df["bb_middle"] - self.bb_std * bb_std

        # Trigger price for dynamic trailing stop activation
        df["trigger_price"] = df["bb_upper"]

        # Buy when BOTH conditions are met
        buy = (df["rsi"] < self.oversold) & (df["Close"] <= df["bb_lower"])

        df["signal"] = 0
        df.loc[buy, "signal"] = 1

        logger.debug("%s: %d buy signals", self.name, int(buy.sum()))
        return df
