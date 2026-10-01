"""Core event-driven backtesting engine."""

import logging
from typing import Optional

import pandas as pd

from engine.portfolio import Portfolio
from engine.risk import RiskManager, compute_atr
from strategies.base import BaseStrategy

logger = logging.getLogger(__name__)


class BacktestResult:
    """Container for all outputs produced by a backtest run."""

    def __init__(
        self,
        ticker: str,
        strategy_name: str,
        equity_curve: pd.Series,
        trades: list,
        signals_df: pd.DataFrame,
        buy_hold_curve: pd.Series,
        initial_capital: float,
    ) -> None:
        self.ticker = ticker
        self.strategy_name = strategy_name
        self.equity_curve = equity_curve         # pd.Series  date → equity
        self.trades = trades                      # list[Trade]
        self.signals_df = signals_df              # full bar DF with indicators
        self.buy_hold_curve = buy_hold_curve      # pd.Series  date → equity
        self.initial_capital = initial_capital


class Backtester:
    """
    Event-driven backtesting engine.

    Iterates bar-by-bar through historical price data, applying a strategy's
    signals and executing orders through the Portfolio, subject to RiskManager
    constraints.

    Args:
        strategy:        A strategy instance (inherits BaseStrategy).
        risk_manager:    A RiskManager instance.
        initial_capital: Starting cash.
        commission:      Flat dollar commission per order.
        slippage:        Slippage fraction of price per order.
        long_only:       If True, short signals simply close any long position.
                         If False, short signals open a short position.
    """

    def __init__(
        self,
        strategy: BaseStrategy,
        risk_manager: RiskManager,
        initial_capital: float = 100_000.0,
        commission: float = 0.0,
        slippage: float = 0.001,
        long_only: bool = True,
    ) -> None:
        self.strategy = strategy
        self.risk_manager = risk_manager
        self.initial_capital = initial_capital
        self.commission = commission
        self.slippage = slippage
        self.long_only = long_only

    def run(
        self,
        df: pd.DataFrame,
        ticker: str = "ASSET",
    ) -> BacktestResult:
        """
        Execute the backtest on a single-asset OHLCV DataFrame.

        Args:
            df:     OHLCV DataFrame (DatetimeIndex, ascending).
                    Must have columns: Open, High, Low, Close, Volume.
            ticker: Ticker label used in trade records and reports.

        Returns:
            BacktestResult with equity curve, trades, and signals DataFrame.
        """
        logger.info("Running backtest for %s using %s", ticker, self.strategy.name)

        df = df.sort_index()
        signals_df = self.strategy.generate_signals(df)

        # Pre-compute ATR if needed by risk manager
        if (
            self.risk_manager.atr_stop_multiplier is not None
            or self.risk_manager.trailing_stop_pct is None
            and self.risk_manager.atr_stop_multiplier is not None
        ):
            atr_series = compute_atr(signals_df, self.risk_manager.atr_period)
        else:
            atr_series = pd.Series(index=signals_df.index, dtype=float)

        portfolio = Portfolio(
            initial_capital=self.initial_capital,
            commission=self.commission,
            slippage=self.slippage,
        )

        previous_date: Optional[pd.Timestamp] = None

        for date, row in signals_df.iterrows():
            price = float(row["Close"])
            if price <= 0 or pd.isna(price):
                continue

            current_equity = portfolio.equity({ticker: price})
            prices = {ticker: price}

            # ----- Day boundary -----
            if previous_date is None or date.date() != previous_date.date():
                self.risk_manager.start_of_day(current_equity)

            previous_date = date

            atr_val: Optional[float] = (
                float(atr_series.loc[date])
                if date in atr_series.index and not pd.isna(atr_series.loc[date])
                else None
            )

            # ----- Stop-loss / trailing-stop checks on ALL open slots -----
            slots_to_close: list[tuple[str, float, str]] = []  # (slot_id, fill, reason)
            for slot_id, pos in list(portfolio.open_positions.items()):
                if pos.ticker != ticker:
                    continue

                # Dynamic profit-trigger: upgrade hard stop → trailing stop
                self.risk_manager.update_dynamic_stop(pos, price)

                # Update trailing stop (standard, non-dynamic)
                if self.risk_manager.trailing_stop_pct is not None or (
                    self.risk_manager.atr_stop_multiplier is not None
                    and self.risk_manager.trailing_stop_pct is None
                ):
                    new_ts = self.risk_manager.trailing_stop(
                        current_price=price,
                        previous_stop=pos.trailing_stop_price,
                        direction=pos.direction,
                        atr=atr_val,
                    )
                    if new_ts is not None:
                        pos.trailing_stop_price = new_ts

                # Check hard stop
                hard_stop = pos.stop_price
                if hard_stop is not None:
                    if pos.direction == 1 and row["Low"] <= hard_stop:
                        fill = min(hard_stop, float(row["Open"]))
                        slots_to_close.append((slot_id, fill, "stop_loss"))
                        continue
                    elif pos.direction == -1 and row["High"] >= hard_stop:
                        fill = max(hard_stop, float(row["Open"]))
                        slots_to_close.append((slot_id, fill, "stop_loss"))
                        continue

                # Check trailing stop
                ts_price = pos.trailing_stop_price
                if ts_price is not None:
                    if pos.direction == 1 and row["Low"] <= ts_price:
                        fill = min(ts_price, float(row["Open"]))
                        slots_to_close.append((slot_id, fill, "trailing_stop"))
                        continue
                    elif pos.direction == -1 and row["High"] >= ts_price:
                        fill = max(ts_price, float(row["Open"]))
                        slots_to_close.append((slot_id, fill, "trailing_stop"))
                        continue

            # Execute stop exits
            for slot_id, fill, reason in slots_to_close:
                portfolio.exit(slot_id, date, fill, reason=reason)

            # ----- Signal processing -----
            signal = int(row.get("signal", 0))

            if signal == -1:
                # Close ALL open longs in this ticker
                for slot_id, pos in portfolio.positions_for_ticker(ticker):
                    if pos.direction == 1:
                        portfolio.exit(slot_id, date, price, reason="signal")

                # Open short only in long/short mode
                if not self.long_only and not portfolio.is_invested(ticker):
                    stop = self.risk_manager.initial_stop(price, -1, atr_val)
                    qty = self.risk_manager.size_position(
                        equity=current_equity,
                        entry_price=price,
                        stop_price=stop,
                        direction=-1,
                    )
                    if qty > 0 and not self.risk_manager.check_daily_loss(current_equity):
                        open_val = portfolio.open_position_value({ticker: price})
                        if self.risk_manager.can_enter(
                            portfolio.num_open_positions(), current_equity,
                            abs(open_val), price * qty,
                        ):
                            ts = self.risk_manager.trailing_stop(
                                price, None, -1, atr_val
                            ) if self.risk_manager.trailing_stop_pct else None
                            portfolio.enter(
                                ticker, date, price, qty, direction=-1,
                                stop_price=stop, trailing_stop_price=ts,
                            )

            elif signal == 1:
                # Allow new entry even if other slots are open (multi-position)
                if self.risk_manager.check_daily_loss(current_equity):
                    logger.debug("Daily loss limit active — skipping entry on %s.", date)
                else:
                    stop = self.risk_manager.initial_stop(price, 1, atr_val)
                    qty = self.risk_manager.size_position(
                        equity=current_equity,
                        entry_price=price,
                        stop_price=stop,
                        direction=1,
                    )
                    if qty > 0:
                        open_val = portfolio.open_position_value({ticker: price})
                        if self.risk_manager.can_enter(
                            portfolio.num_open_positions(), current_equity,
                            abs(open_val), price * qty,
                        ):
                            ts = self.risk_manager.trailing_stop(
                                price, None, 1, atr_val
                            ) if self.risk_manager.trailing_stop_pct else None
                            trigger_price: Optional[float] = None
                            if "trigger_price" in signals_df.columns:
                                raw_tp = row.get("trigger_price")
                                if raw_tp is not None and not pd.isna(raw_tp):
                                    trigger_price = float(raw_tp)
                            portfolio.enter(
                                ticker, date, price, qty, direction=1,
                                stop_price=stop, trailing_stop_price=ts,
                                profit_trigger_price=trigger_price,
                            )

            portfolio.snapshot_equity(date, {ticker: price})

        # Close any remaining open positions at the last available price
        last_date = signals_df.index[-1]
        last_price = float(signals_df["Close"].iloc[-1])
        for slot_id in list(portfolio.open_positions.keys()):
            portfolio.exit(slot_id, last_date, last_price, reason="end_of_data")

        equity_series = pd.Series(portfolio.equity_curve).sort_index()

        # Buy-and-hold benchmark
        first_price = float(signals_df["Close"].iloc[0])
        shares_bh = self.initial_capital / first_price
        bh_curve = (signals_df["Close"] / first_price) * self.initial_capital
        bh_curve.name = "buy_and_hold"

        logger.info(
            "Backtest complete. Trades: %d  Final equity: $%.2f",
            len(portfolio.trades), equity_series.iloc[-1] if not equity_series.empty else self.initial_capital,
        )

        return BacktestResult(
            ticker=ticker,
            strategy_name=self.strategy.name,
            equity_curve=equity_series,
            trades=portfolio.trades,
            signals_df=signals_df,
            buy_hold_curve=bh_curve,
            initial_capital=self.initial_capital,
        )
