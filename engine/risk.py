"""Risk management: position sizing, stop-loss calculation, portfolio guards."""

import logging
from typing import Optional

import numpy as np
import pandas as pd

from config import (
    DEFAULT_ATR_MULTIPLIER,
    DEFAULT_ATR_PERIOD,
    DEFAULT_DAILY_LOSS_LIMIT,
    DEFAULT_MAX_EXPOSURE,
    DEFAULT_MAX_POSITIONS,
    DEFAULT_RISK_PER_TRADE,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ATR helper
# ---------------------------------------------------------------------------

def compute_atr(df: pd.DataFrame, period: int = DEFAULT_ATR_PERIOD) -> pd.Series:
    """
    Compute the Average True Range (ATR) for a given bar DataFrame.

    Args:
        df:     OHLCV DataFrame.
        period: Rolling look-back in bars.

    Returns:
        Series of ATR values (same index as df).
    """
    high = df["High"]
    low = df["Low"]
    prev_close = df["Close"].shift(1)

    tr = pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)

    return tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()


# ---------------------------------------------------------------------------
# Position sizing
# ---------------------------------------------------------------------------

class RiskManager:
    """
    Centralises position sizing, stop-loss placement, and portfolio-level rules.

    Args:
        risk_per_trade:     Fraction of current equity to risk on each trade.
        stop_loss_pct:      Hard stop loss as a fraction of entry price.
                            None = no hard stop.
        trailing_stop_pct:  Trailing stop as a fraction below the highest price
                            seen since entry. None = no trailing stop.
        atr_stop_multiplier: If set, derive the stop from ATR × multiplier
                            (overrides stop_loss_pct for initial placement).
        atr_period:         Period used for ATR calculation.
        max_positions:      Maximum number of simultaneous open positions.
        max_exposure:       Maximum fraction of equity allowed in open positions.
        daily_loss_limit:   If daily P&L drops by this fraction of starting
                            equity, no new trades are opened for the rest of
                            the day.
    """

    def __init__(
        self,
        risk_per_trade: float = DEFAULT_RISK_PER_TRADE,
        stop_loss_pct: Optional[float] = None,
        trailing_stop_pct: Optional[float] = None,
        atr_stop_multiplier: Optional[float] = None,
        atr_period: int = DEFAULT_ATR_PERIOD,
        max_positions: int = DEFAULT_MAX_POSITIONS,
        max_exposure: float = DEFAULT_MAX_EXPOSURE,
        daily_loss_limit: float = DEFAULT_DAILY_LOSS_LIMIT,
        profit_trigger_pct: Optional[float] = None,
        trailing_after_profit_pct: Optional[float] = None,
        position_fraction: Optional[float] = None,
    ) -> None:
        self.risk_per_trade = risk_per_trade
        self.stop_loss_pct = stop_loss_pct
        self.trailing_stop_pct = trailing_stop_pct
        self.atr_stop_multiplier = atr_stop_multiplier
        self.atr_period = atr_period
        self.max_positions = max_positions
        self.max_exposure = max_exposure
        self.daily_loss_limit = daily_loss_limit
        self.profit_trigger_pct = profit_trigger_pct
        self.trailing_after_profit_pct = trailing_after_profit_pct
        # When set, each trade receives exactly this fraction of current equity
        # (e.g. 0.20 = 20%), ignoring the risk-per-trade calculation.
        # max_positions caps how many can run simultaneously (default 5 for 20%).
        self.position_fraction = position_fraction
        self.dca_amount: Optional[float] = None

        # State
        self._day_start_equity: float = 0.0
        self._daily_loss_breached: bool = False

    # ------------------------------------------------------------------
    # Session helpers called by the engine
    # ------------------------------------------------------------------

    def start_of_day(self, equity: float) -> None:
        """Record starting equity for the day and reset the loss-limit flag."""
        self._day_start_equity = equity
        self._daily_loss_breached = False

    def check_daily_loss(self, current_equity: float) -> bool:
        """
        Return True if the daily loss limit has been breached.

        Once breached, no new entries are allowed for the rest of the day.
        """
        if self._day_start_equity <= 0:
            return False
        daily_return = (current_equity - self._day_start_equity) / self._day_start_equity
        if daily_return <= -self.daily_loss_limit:
            if not self._daily_loss_breached:
                logger.debug("Daily loss limit hit (%.1f%%).", daily_return * 100)
                self._daily_loss_breached = True
        return self._daily_loss_breached

    # ------------------------------------------------------------------
    # Position sizing
    # ------------------------------------------------------------------

    def size_position(
        self,
        equity: float,
        entry_price: float,
        stop_price: Optional[float],
        direction: int = 1,
    ) -> float:
        """
        Calculate the number of shares to buy/sell.

        Uses the risk-per-trade approach:
            shares = (equity × risk_per_trade) / |entry_price - stop_price|

        If no stop is given, sizes by a fixed fraction of equity instead.

        Args:
            equity:       Current total portfolio equity.
            entry_price:  Projected fill price.
            stop_price:   Stop-loss level (or None).
            direction:    1 = long, -1 = short.

        Returns:
            Quantity of shares (float, allowing fractional shares).
        """
        if entry_price <= 0:
            return 0.0

        if self.dca_amount is not None:
            return max(self.dca_amount / entry_price, 0.0)

        if self.position_fraction is not None:
            quantity = (equity * self.position_fraction) / entry_price
            return max(quantity, 0.0)

        risk_dollars = equity * self.risk_per_trade

        if stop_price is not None and abs(entry_price - stop_price) > 1e-9:
            risk_per_share = abs(entry_price - stop_price)
            quantity = risk_dollars / risk_per_share
        else:
            # Fallback: risk_per_trade fraction of equity at entry price
            quantity = risk_dollars / entry_price

        # Cap at max_exposure fraction of equity
        max_qty = (equity * self.max_exposure) / entry_price
        quantity = min(quantity, max_qty)

        return max(quantity, 0.0)

    # ------------------------------------------------------------------
    # Stop-loss helpers
    # ------------------------------------------------------------------

    def initial_stop(
        self,
        entry_price: float,
        direction: int,
        atr: Optional[float] = None,
    ) -> Optional[float]:
        """
        Compute the initial hard stop-loss price.

        ATR-based stop takes priority over percentage-based stop when both
        are configured.

        Args:
            entry_price: Fill price.
            direction:   1 = long, -1 = short.
            atr:         Current ATR value (required for ATR-based stops).

        Returns:
            Stop price level, or None if no stop is configured.
        """
        if self.atr_stop_multiplier is not None and atr is not None and atr > 0:
            return entry_price - direction * self.atr_stop_multiplier * atr

        if self.stop_loss_pct is not None:
            return entry_price * (1 - direction * self.stop_loss_pct)

        return None

    def trailing_stop(
        self,
        current_price: float,
        previous_stop: Optional[float],
        direction: int,
        atr: Optional[float] = None,
    ) -> Optional[float]:
        """
        Update a trailing stop price.

        The stop only moves in the favourable direction — it never gives
        back profit.

        Args:
            current_price:  Latest price of the asset.
            previous_stop:  Existing trailing stop level.
            direction:      1 = long, -1 = short.
            atr:            Current ATR (for ATR trailing stops).

        Returns:
            New trailing stop price, or None if trailing stops are disabled.
        """
        if self.trailing_stop_pct is None and self.atr_stop_multiplier is None:
            return None

        if self.trailing_stop_pct is not None:
            new_stop = current_price * (1 - direction * self.trailing_stop_pct)
        elif atr is not None and atr > 0:
            new_stop = current_price - direction * self.atr_stop_multiplier * atr
        else:
            return previous_stop

        if previous_stop is None:
            return new_stop

        # Ratchet: only move the stop in the direction of the trade
        if direction == 1:
            return max(new_stop, previous_stop)
        else:
            return min(new_stop, previous_stop)

    def update_dynamic_stop(
        self,
        pos,                    # OpenPosition — avoid circular import with string type
        current_price: float,
    ) -> None:
        """
        Implement the profit-trigger trailing stop.

        Once unrealised profit exceeds `profit_trigger_pct`:
          - Disable the hard stop (set to None)
          - Activate a `trailing_after_profit_pct` trailing stop anchored to
            the highest (long) / lowest (short) price seen since entry.

        Updates pos in-place. No-op if profit_trigger_pct is not configured.
        """
        if self.profit_trigger_pct is None or self.trailing_after_profit_pct is None:
            return

        # Track peak price for the trailing calculation
        if pos.direction == 1:
            pos.peak_price = max(pos.peak_price or current_price, current_price)
        else:
            pos.peak_price = min(pos.peak_price or current_price, current_price)

        if pos.trailing_activated:
            # Already in trailing mode — ratchet the stop from the new peak
            new_ts = pos.peak_price * (1 - pos.direction * self.trailing_after_profit_pct)
            if pos.trailing_stop_price is None:
                pos.trailing_stop_price = new_ts
            elif pos.direction == 1:
                pos.trailing_stop_price = max(pos.trailing_stop_price, new_ts)
            else:
                pos.trailing_stop_price = min(pos.trailing_stop_price, new_ts)
            return

        # Check price-level trigger (e.g. BB upper band stored in pos.profit_trigger_price)
        price_trigger_hit = (
            pos.profit_trigger_price is not None
            and (
                (pos.direction == 1 and current_price >= pos.profit_trigger_price)
                or (pos.direction == -1 and current_price <= pos.profit_trigger_price)
            )
        )

        # Check percentage-based trigger
        pct_trigger_hit = False
        if self.profit_trigger_pct is not None:
            unrealised_pct = pos.direction * (current_price - pos.entry_price) / pos.entry_price
            pct_trigger_hit = unrealised_pct >= self.profit_trigger_pct

        if price_trigger_hit or pct_trigger_hit:
            pos.trailing_activated = True
            pos.stop_price = None   # cancel the hard stop
            pos.trailing_stop_price = pos.peak_price * (
                1 - pos.direction * self.trailing_after_profit_pct
            )
            trigger_desc = "BB upper" if price_trigger_hit else f"{self.profit_trigger_pct*100:.0f}% profit"
            logger.debug(
                "Trigger hit on %s (%s) — switching to %.0f%% trailing stop @ %.2f",
                pos.ticker, trigger_desc,
                self.trailing_after_profit_pct * 100, pos.trailing_stop_price,
            )

    # ------------------------------------------------------------------
    # Portfolio guards
    # ------------------------------------------------------------------

    def can_enter(
        self,
        num_open: int,
        equity: float,
        current_exposure: float,
        trade_cost: float,
    ) -> bool:
        """
        Check portfolio-level rules before opening a new position.

        Args:
            num_open:         Number of currently open positions.
            equity:           Current total equity.
            current_exposure: Dollar value of all open positions.
            trade_cost:       Dollar cost of the proposed new trade.

        Returns:
            True if the trade is allowed.
        """
        if num_open >= self.max_positions:
            logger.debug("Max positions (%d) reached.", self.max_positions)
            return False

        if equity > 0:
            projected_exposure = (current_exposure + trade_cost) / equity
            if projected_exposure > self.max_exposure:
                logger.debug(
                    "Max exposure (%.0f%%) would be breached.", self.max_exposure * 100
                )
                return False

        return True
