"""Dollar-Cost Averaging strategy — buy a fixed amount on the first bar of each month."""

import logging

import pandas as pd

from strategies.base import BaseStrategy

logger = logging.getLogger(__name__)


class DCAStrategy(BaseStrategy):
    """
    Buy a fixed dollar amount on the first trading bar of each calendar month.
    Never sells — all positions are held until end of data.
    """

    @property
    def name(self) -> str:
        return "DCA(monthly)"

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["signal"] = 0

        seen_months: set[tuple[int, int]] = set()
        for i, dt in enumerate(df.index):
            key = (dt.year, dt.month)
            if key not in seen_months:
                seen_months.add(key)
                df.iloc[i, df.columns.get_loc("signal")] = 1

        logger.debug("DCA: %d monthly buy signals", int((df["signal"] == 1).sum()))
        return df
