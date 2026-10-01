"""Performance metrics calculations."""

import logging
from typing import Any

import numpy as np
import pandas as pd

from config import DEFAULT_RISK_FREE_RATE, TRADING_DAYS_PER_YEAR

def _bars_per_year(equity: pd.Series) -> float:
    """Estimate annualisation factor from the median bar spacing."""
    if len(equity) < 2:
        return float(TRADING_DAYS_PER_YEAR)
    deltas = equity.index.to_series().diff().dropna()
    median_seconds = deltas.median().total_seconds()
    seconds_per_year = 365.25 * 24 * 3600
    return seconds_per_year / max(median_seconds, 1)
from engine.portfolio import Trade

logger = logging.getLogger(__name__)


def _safe_div(numerator: float, denominator: float, fallback: float = 0.0) -> float:
    """Division that returns fallback instead of raising on zero denominator."""
    if denominator == 0 or not np.isfinite(denominator):
        return fallback
    result = numerator / denominator
    return float(result) if np.isfinite(result) else fallback


def compute_max_drawdown(equity: pd.Series) -> tuple[float, int]:
    """
    Compute the maximum drawdown and its duration in calendar days.

    Args:
        equity: Time-series of portfolio equity values.

    Returns:
        Tuple of (max_drawdown_fraction, max_duration_days).
        max_drawdown_fraction is negative (e.g. -0.25 for a 25% drawdown).
    """
    if equity.empty or len(equity) < 2:
        return 0.0, 0

    rolling_max = equity.cummax()
    drawdown = (equity - rolling_max) / rolling_max

    max_dd = float(drawdown.min())

    # Duration: longest streak of being below the previous peak
    is_underwater = drawdown < 0
    max_duration = 0
    current_duration = 0
    dates = equity.index

    for i in range(len(is_underwater)):
        if is_underwater.iloc[i]:
            if i == 0:
                current_duration = 0
            else:
                current_duration = (dates[i] - dates[i - current_duration]).days if current_duration > 0 else 0
                current_duration += 1
            max_duration = max(max_duration, current_duration)
        else:
            current_duration = 0

    # Simpler recalculation using contiguous blocks
    durations = []
    start_idx = None
    for i, val in enumerate(is_underwater):
        if val and start_idx is None:
            start_idx = i
        elif not val and start_idx is not None:
            d = (dates[i - 1] - dates[start_idx]).days + 1
            durations.append(d)
            start_idx = None
    if start_idx is not None:
        d = (dates[-1] - dates[start_idx]).days + 1
        durations.append(d)

    max_duration_days = max(durations) if durations else 0

    return max_dd, max_duration_days


def compute_monthly_returns(equity: pd.Series) -> pd.DataFrame:
    """
    Compute month-by-month returns as a (year × month) pivot table.

    Args:
        equity: Daily equity curve.

    Returns:
        DataFrame with years as rows, months (1–12) as columns, values as
        decimal returns (e.g. 0.05 = 5%).
    """
    if equity.empty:
        return pd.DataFrame()

    monthly = equity.resample("ME").last()
    monthly_returns = monthly.pct_change().dropna()

    df = pd.DataFrame({
        "year": monthly_returns.index.year,
        "month": monthly_returns.index.month,
        "return": monthly_returns.values,
    })

    if df.empty:
        return pd.DataFrame()

    pivot = df.pivot(index="year", columns="month", values="return")
    pivot.columns.name = None
    return pivot


def calculate_metrics(
    equity: pd.Series,
    trades: list[Trade],
    buy_hold_curve: pd.Series,
    initial_capital: float,
    risk_free_rate: float = DEFAULT_RISK_FREE_RATE,
) -> dict[str, Any]:
    """
    Calculate a comprehensive set of backtest performance metrics.

    Args:
        equity:          Daily equity curve of the strategy.
        trades:          List of completed Trade objects.
        buy_hold_curve:  Daily equity curve of the buy-and-hold benchmark.
        initial_capital: Starting capital.
        risk_free_rate:  Annualised risk-free rate (default 4.5%).

    Returns:
        Dict with all metrics (see docstring body for keys).
    """
    metrics: dict[str, Any] = {}

    if equity.empty or len(equity) < 2:
        logger.warning("Equity curve is empty or too short — returning empty metrics.")
        return metrics

    equity = equity.sort_index()
    daily_returns = equity.pct_change().dropna()

    bars_per_year = _bars_per_year(equity)

    # ---- Basic returns ----
    final_equity = float(equity.iloc[-1])
    total_return = _safe_div(final_equity - initial_capital, initial_capital)
    metrics["total_return_pct"] = round(total_return * 100, 2)
    metrics["final_equity"] = round(final_equity, 2)

    num_days = (equity.index[-1] - equity.index[0]).days
    num_years = max(num_days / 365.25, 1e-9)
    ann_return = (1 + total_return) ** (1 / num_years) - 1
    metrics["annualized_return_pct"] = round(ann_return * 100, 2)

    # ---- Risk metrics ----
    daily_rf = (1 + risk_free_rate) ** (1 / bars_per_year) - 1
    excess_returns = daily_returns - daily_rf

    ann_vol = float(daily_returns.std()) * np.sqrt(bars_per_year)
    metrics["annualized_volatility_pct"] = round(ann_vol * 100, 2)

    sharpe = _safe_div(
        float(excess_returns.mean()) * bars_per_year,
        float(daily_returns.std()) * np.sqrt(bars_per_year),
        fallback=0.0,
    )
    metrics["sharpe_ratio"] = round(sharpe, 3)

    downside = daily_returns[daily_returns < daily_rf].std()
    ann_downside = float(downside) * np.sqrt(bars_per_year) if not np.isnan(downside) else 0.0
    sortino = _safe_div(ann_return - risk_free_rate, ann_downside)
    metrics["sortino_ratio"] = round(sortino, 3)

    max_dd, max_dd_days = compute_max_drawdown(equity)
    metrics["max_drawdown_pct"] = round(max_dd * 100, 2)
    metrics["max_drawdown_duration_days"] = max_dd_days

    calmar = _safe_div(ann_return, abs(max_dd))
    metrics["calmar_ratio"] = round(calmar, 3)

    # ---- Trade statistics ----
    metrics["total_trades"] = len(trades)

    if trades:
        net_pnls = [t.net_pnl for t in trades]
        winners = [p for p in net_pnls if p > 0]
        losers = [p for p in net_pnls if p <= 0]

        win_rate = _safe_div(len(winners), len(trades))
        metrics["win_rate_pct"] = round(win_rate * 100, 2)

        avg_win = float(np.mean(winners)) if winners else 0.0
        avg_loss = float(np.mean(losers)) if losers else 0.0
        metrics["avg_win"] = round(avg_win, 2)
        metrics["avg_loss"] = round(avg_loss, 2)

        gross_profit = sum(winners)
        gross_loss = abs(sum(losers))
        metrics["profit_factor"] = round(_safe_div(gross_profit, gross_loss, fallback=0.0), 3)

        holding_days = [t.holding_days for t in trades]
        metrics["avg_holding_days"] = round(float(np.mean(holding_days)), 1)

        # Expectancy = (win_rate × avg_win) + (loss_rate × avg_loss)
        loss_rate = 1 - win_rate
        expectancy = win_rate * avg_win + loss_rate * avg_loss
        metrics["expectancy_per_trade"] = round(expectancy, 2)
    else:
        metrics.update({
            "win_rate_pct": 0.0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "profit_factor": 0.0,
            "avg_holding_days": 0.0,
            "expectancy_per_trade": 0.0,
        })

    # ---- Buy-and-hold comparison ----
    if not buy_hold_curve.empty:
        bh_return = _safe_div(
            float(buy_hold_curve.iloc[-1]) - initial_capital, initial_capital
        )
        metrics["buy_hold_return_pct"] = round(bh_return * 100, 2)
        metrics["alpha_pct"] = round(
            metrics["total_return_pct"] - metrics["buy_hold_return_pct"], 2
        )
    else:
        metrics["buy_hold_return_pct"] = 0.0
        metrics["alpha_pct"] = 0.0

    metrics["risk_free_rate_pct"] = round(risk_free_rate * 100, 2)
    return metrics
