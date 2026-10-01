"""Abstract base class for all trading strategies."""

from abc import ABC, abstractmethod

import pandas as pd


class BaseStrategy(ABC):
    """
    Every strategy must inherit from this class and implement generate_signals().

    The engine calls generate_signals(df) once before the simulation loop.
    The returned DataFrame must contain a 'signal' column with integer values:
        1  = buy / go long
       -1  = sell / go short (or close long)
        0  = no action
    """

    @abstractmethod
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute trading signals from price/volume data.

        Args:
            df: OHLCV DataFrame with DatetimeIndex.
                Columns: Open, High, Low, Close, Volume.

        Returns:
            The same DataFrame (or a copy) with a 'signal' column added.
            May also add indicator columns for use in the report.
        """

    @property
    def name(self) -> str:
        """Human-readable strategy name used in reports."""
        return self.__class__.__name__

    def __repr__(self) -> str:
        return f"{self.name}()"
