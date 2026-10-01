"""Portfolio and position tracking."""

import logging
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class Trade:
    """Record of a completed round-trip trade."""
    ticker: str
    entry_date: pd.Timestamp
    entry_price: float
    exit_date: pd.Timestamp
    exit_price: float
    quantity: float                  # shares (may be fractional)
    direction: int                   # 1 = long, -1 = short
    commission: float = 0.0
    slippage_cost: float = 0.0

    @property
    def gross_pnl(self) -> float:
        return self.direction * (self.exit_price - self.entry_price) * self.quantity

    @property
    def net_pnl(self) -> float:
        return self.gross_pnl - self.commission - self.slippage_cost

    @property
    def holding_days(self) -> int:
        return (self.exit_date - self.entry_date).days

    @property
    def return_pct(self) -> float:
        cost_basis = self.entry_price * self.quantity
        if cost_basis == 0:
            return 0.0
        return self.net_pnl / cost_basis


@dataclass
class OpenPosition:
    """A currently held position."""
    ticker: str
    entry_date: pd.Timestamp
    entry_price: float
    quantity: float
    direction: int                   # 1 = long, -1 = short
    stop_price: Optional[float] = None
    trailing_stop_price: Optional[float] = None
    cost_basis: float = 0.0          # total cash spent (entry_price * qty + costs)
    trailing_activated: bool = False         # True once profit-trigger threshold is crossed
    peak_price: float = 0.0                  # highest (long) or lowest (short) price seen since entry
    profit_trigger_price: Optional[float] = None  # price level (e.g. BB upper) that activates trailing


class Portfolio:
    """
    Tracks cash, open positions, and closed trades.

    Args:
        initial_capital: Starting cash balance.
        commission:      Flat commission per trade in dollars.
        slippage:        Slippage as a fraction of price (e.g. 0.001 = 0.1%).
    """

    def __init__(
        self,
        initial_capital: float,
        commission: float = 0.0,
        slippage: float = 0.001,
    ) -> None:
        self.initial_capital = initial_capital
        self.commission = commission
        self.slippage = slippage

        self.cash: float = initial_capital
        self.open_positions: dict[str, OpenPosition] = {}  # slot_id → position
        self.trades: list[Trade] = []
        self._next_slot: int = 0

        # Daily equity snapshots — {date: equity}
        self.equity_curve: dict[pd.Timestamp, float] = {}

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    def open_position_value(self, prices: dict[str, float]) -> float:
        """Mark-to-market value of all open positions."""
        total = 0.0
        for slot_id, pos in self.open_positions.items():
            price = prices.get(pos.ticker, pos.entry_price)
            total += price * pos.quantity * pos.direction
        return total

    def equity(self, prices: dict[str, float]) -> float:
        """Total portfolio equity = cash + open position value."""
        return self.cash + self.open_position_value(prices)

    def num_open_positions(self) -> int:
        return len(self.open_positions)

    def positions_for_ticker(self, ticker: str) -> list[tuple[str, 'OpenPosition']]:
        """Return list of (slot_id, position) for all open positions in a ticker."""
        return [(k, v) for k, v in self.open_positions.items() if v.ticker == ticker]

    def num_positions_for_ticker(self, ticker: str) -> int:
        return sum(1 for v in self.open_positions.values() if v.ticker == ticker)

    def is_invested(self, ticker: str) -> bool:
        return any(v.ticker == ticker for v in self.open_positions.values())

    # ------------------------------------------------------------------
    # Order execution
    # ------------------------------------------------------------------

    def _apply_slippage(self, price: float, direction: int) -> float:
        """Widen the fill price by the slippage fraction."""
        return price * (1 + direction * self.slippage)

    def enter(
        self,
        ticker: str,
        date: pd.Timestamp,
        price: float,
        quantity: float,
        direction: int = 1,
        stop_price: Optional[float] = None,
        trailing_stop_price: Optional[float] = None,
        profit_trigger_price: Optional[float] = None,
    ) -> bool:
        """
        Open a new position.

        Args:
            ticker:               Stock symbol.
            date:                 Bar date (entry date).
            price:                Raw bar price (slippage applied internally).
            quantity:             Number of shares (may be fractional).
            direction:            1 = long, -1 = short.
            stop_price:           Hard stop-loss price level.
            trailing_stop_price:  Initial trailing stop price level.

        Returns:
            True if the order was filled, False if rejected (insufficient cash).
        """
        fill_price = self._apply_slippage(price, direction)
        cost = fill_price * quantity + self.commission

        if cost > self.cash:
            logger.debug(
                "Insufficient cash ($%.2f) to enter %s × %.2f @ $%.2f",
                self.cash, ticker, quantity, fill_price,
            )
            return False

        # Generate a unique slot ID so multiple positions in the same ticker can coexist
        slot_id = f"{ticker}_{self._next_slot}"
        self._next_slot += 1

        self.cash -= cost
        self.open_positions[slot_id] = OpenPosition(
            ticker=ticker,
            entry_date=date,
            entry_price=fill_price,
            quantity=quantity,
            direction=direction,
            stop_price=stop_price,
            trailing_stop_price=trailing_stop_price,
            cost_basis=cost,
            trailing_activated=False,
            peak_price=fill_price,
            profit_trigger_price=profit_trigger_price,
        )
        logger.debug(
            "ENTER %s %s × %.2f @ $%.2f  cash=$%.2f",
            "LONG" if direction == 1 else "SHORT",
            ticker, quantity, fill_price, self.cash,
        )
        return True

    def exit(
        self,
        slot_id: str,
        date: pd.Timestamp,
        price: float,
        reason: str = "signal",
    ) -> Optional[Trade]:
        """
        Close an open position by slot ID.

        Args:
            slot_id: Unique slot identifier (e.g. "AAPL_0").
            date:    Bar date (exit date).
            price:   Raw bar price (slippage applied internally).
            reason:  Description of why the trade was closed (for logging).

        Returns:
            Completed Trade object, or None if no position was open.
        """
        pos = self.open_positions.pop(slot_id, None)
        if pos is None:
            logger.debug("No open position for slot %s to exit.", slot_id)
            return None

        fill_price = self._apply_slippage(price, -pos.direction)
        proceeds = fill_price * pos.quantity * pos.direction
        slippage_cost = abs(fill_price - price) * pos.quantity
        total_commission = self.commission * 2   # entry + exit

        self.cash += proceeds - self.commission

        trade = Trade(
            ticker=pos.ticker,
            entry_date=pos.entry_date,
            entry_price=pos.entry_price,
            exit_date=date,
            exit_price=fill_price,
            quantity=pos.quantity,
            direction=pos.direction,
            commission=total_commission,
            slippage_cost=slippage_cost,
        )
        self.trades.append(trade)

        logger.debug(
            "EXIT %s [%s] (%s) × %.2f @ $%.2f  P&L=$%.2f  cash=$%.2f",
            pos.ticker, slot_id, reason, pos.quantity, fill_price, trade.net_pnl, self.cash,
        )
        return trade

    def snapshot_equity(self, date: pd.Timestamp, prices: dict[str, float]) -> float:
        """Record and return today's equity value."""
        eq = self.equity(prices)
        self.equity_curve[date] = eq
        return eq
