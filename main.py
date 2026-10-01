"""
CLI entry point for the Python stock backtester.

Usage examples:
    python main.py --ticker AAPL --start 2020-01-01 --end 2024-12-31 \\
        --strategy rsi_mean_reversion --initial-capital 100000

    python main.py --ticker MSFT --start 2019-01-01 --end 2024-12-31 \\
        --strategy sma_crossover --short-window 10 --long-window 30 \\
        --risk-per-trade 0.02 --stop-loss 0.05 --trailing-stop 0.03

    python main.py --ticker SPY --strategy macd --long-short \\
        --start 2018-01-01 --end 2024-12-31
"""

import argparse
import logging
import os
import sys

# Ensure the project root is on the path so sibling packages resolve
sys.path.insert(0, os.path.dirname(__file__))

from analysis.metrics import calculate_metrics
from analysis.report import generate_html_report
from data.fetcher import fetch_ohlcv
from engine.backtester import Backtester
from engine.risk import RiskManager
from strategies.bbands_strategy import BBandsStrategy
from strategies.dca_strategy import DCAStrategy
from strategies.donchian_breakout import DonchianBreakout
from strategies.macd_strategy import MACDStrategy
from strategies.rsi_bbands_combo import RSIBBandsCombo
from strategies.rsi_mean_reversion import RSIMeanReversion
from strategies.sma_crossover import SMACrossover
from strategies.volume_spike import VolumeSpikeReversal

STRATEGY_MAP = {
    "sma_crossover": "sma",
    "sma": "sma",
    "rsi_mean_reversion": "rsi",
    "rsi": "rsi",
    "macd_strategy": "macd",
    "macd": "macd",
    "bbands_strategy": "bbands",
    "bbands": "bbands",
    "bb": "bbands",
    "donchian": "donchian",
    "dc": "donchian",
    "rsi_bb": "rsi_bb",
    "combo": "rsi_bb",
    "volspike": "volspike",
    "vs": "volspike",
    "dca": "dca",
}


def build_strategy(args: argparse.Namespace):
    """Instantiate the chosen strategy from CLI arguments."""
    key = STRATEGY_MAP.get(args.strategy.lower())
    if key is None:
        raise ValueError(
            f"Unknown strategy '{args.strategy}'. "
            f"Available: sma, rsi, macd, bbands, donchian, rsi_bb, volspike"
        )

    if key == "sma":
        return SMACrossover(
            short_window=args.short_window,
            long_window=args.long_window,
        )
    if key == "rsi":
        return RSIMeanReversion(
            rsi_period=args.rsi_period,
            oversold=args.rsi_oversold,
            overbought=args.rsi_overbought,
        )
    if key == "macd":
        return MACDStrategy(
            fast=args.macd_fast,
            slow=args.macd_slow,
            signal=args.macd_signal,
        )
    if key == "bbands":
        return BBandsStrategy(
            period=args.bb_period,
            num_std=args.bb_std,
        )
    if key == "donchian":
        return DonchianBreakout(
            entry_period=args.dc_entry,
            exit_period=args.dc_exit,
        )
    if key == "rsi_bb":
        return RSIBBandsCombo(
            rsi_period=args.rsi_period,
            oversold=args.rsi_oversold,
            bb_period=args.bb_period,
            bb_std=args.bb_std,
        )
    if key == "volspike":
        return VolumeSpikeReversal(
            vol_period=args.vs_period,
            vol_multiplier=args.vs_multiplier,
            price_drop_pct=args.vs_drop,
        )
    if key == "dca":
        return DCAStrategy()


def print_metrics(metrics: dict, strategy_name: str, ticker: str) -> None:
    """Pretty-print key metrics to the terminal."""
    bar = "=" * 58
    print(f"\n{bar}")
    print(f"  BACKTEST RESULTS: {ticker} — {strategy_name}")
    print(bar)
    print(f"  {'Total Return':30s} {metrics.get('total_return_pct', 0):>10.2f}%")
    print(f"  {'Annualised Return':30s} {metrics.get('annualized_return_pct', 0):>10.2f}%")
    print(f"  {'Buy & Hold Return':30s} {metrics.get('buy_hold_return_pct', 0):>10.2f}%")
    print(f"  {'Alpha vs Buy & Hold':30s} {metrics.get('alpha_pct', 0):>10.2f}%")
    print(f"  {'Annualised Volatility':30s} {metrics.get('annualized_volatility_pct', 0):>10.2f}%")
    print(f"  {'Sharpe Ratio':30s} {metrics.get('sharpe_ratio', 0):>10.3f}")
    print(f"  {'Sortino Ratio':30s} {metrics.get('sortino_ratio', 0):>10.3f}")
    print(f"  {'Calmar Ratio':30s} {metrics.get('calmar_ratio', 0):>10.3f}")
    print(f"  {'Max Drawdown':30s} {metrics.get('max_drawdown_pct', 0):>10.2f}%")
    print(f"  {'Max DD Duration':30s} {metrics.get('max_drawdown_duration_days', 0):>9d}d")
    print(f"  {'-'*50}")
    print(f"  {'Total Trades':30s} {metrics.get('total_trades', 0):>10d}")
    print(f"  {'Win Rate':30s} {metrics.get('win_rate_pct', 0):>10.1f}%")
    print(f"  {'Avg Win':30s} ${metrics.get('avg_win', 0):>9.2f}")
    print(f"  {'Avg Loss':30s} ${metrics.get('avg_loss', 0):>9.2f}")
    print(f"  {'Profit Factor':30s} {metrics.get('profit_factor', 0):>10.3f}")
    print(f"  {'Expectancy / Trade':30s} ${metrics.get('expectancy_per_trade', 0):>9.2f}")
    print(f"  {'Avg Holding Period':30s} {metrics.get('avg_holding_days', 0):>9.1f}d")
    print(f"  {'Final Equity':30s} ${metrics.get('final_equity', 0):>9,.2f}")
    print(bar)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Python stock backtester using Yahoo Finance data.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # Data
    p.add_argument("--ticker", default="AAPL", help="Stock ticker symbol")
    p.add_argument("--start", default="2020-01-01", help="Start date YYYY-MM-DD")
    p.add_argument("--end", default="2024-12-31", help="End date YYYY-MM-DD")
    p.add_argument("--interval", default="1d",
                   choices=["1m","2m","5m","15m","30m","60m","1h","90m","1d","5d","1wk","1mo"],
                   help="Bar interval (1h limited to last 730 days by Yahoo Finance)")
    p.add_argument("--no-cache", action="store_true", help="Disable CSV caching")

    # Strategy
    p.add_argument(
        "--strategy",
        default="sma_crossover",
        choices=["sma_crossover", "sma", "rsi_mean_reversion", "rsi",
                 "macd_strategy", "macd", "bbands_strategy", "bbands", "bb",
                 "donchian", "dc", "rsi_bb", "combo", "volspike", "vs", "dca"],
        help="Strategy to backtest",
    )

    # SMA parameters
    p.add_argument("--short-window", type=int, default=20, help="SMA short window")
    p.add_argument("--long-window", type=int, default=50, help="SMA long window")

    # RSI parameters
    p.add_argument("--rsi-period", type=int, default=14, help="RSI look-back period")
    p.add_argument("--rsi-oversold", type=float, default=30.0, help="RSI oversold threshold")
    p.add_argument("--rsi-overbought", type=float, default=70.0, help="RSI overbought threshold")

    # MACD parameters
    p.add_argument("--macd-fast", type=int, default=12, help="MACD fast EMA period")
    p.add_argument("--macd-slow", type=int, default=26, help="MACD slow EMA period")
    p.add_argument("--macd-signal", type=int, default=9, help="MACD signal EMA period")

    # Bollinger Bands parameters
    p.add_argument("--bb-period", type=int, default=20, help="Bollinger Bands SMA period")
    p.add_argument("--bb-std", type=float, default=2.0, help="Bollinger Bands std deviation multiplier")

    # Donchian Channel parameters
    p.add_argument("--dc-entry", type=int, default=20, help="Donchian entry channel period")
    p.add_argument("--dc-exit", type=int, default=10, help="Donchian exit channel period")

    # Volume Spike parameters
    p.add_argument("--vs-period", type=int, default=20, help="Volume average look-back period")
    p.add_argument("--vs-multiplier", type=float, default=2.0, help="Volume spike multiplier threshold")
    p.add_argument("--vs-drop", type=float, default=0.01, help="Min bar drop to qualify (0.01=1%%)")

    # DCA parameters
    p.add_argument("--dca-amount", type=float, default=5000.0,
                   help="Fixed dollar amount to invest each month (DCA strategy)")

    # Portfolio
    p.add_argument("--initial-capital", type=float, default=100_000.0, help="Initial capital $")
    p.add_argument("--commission", type=float, default=0.0, help="Commission per trade $")
    p.add_argument("--slippage", type=float, default=0.001, help="Slippage fraction (0.001=0.1%)")
    p.add_argument("--long-short", action="store_true", help="Enable long/short trading")

    # Risk
    p.add_argument("--risk-per-trade", type=float, default=0.02, help="Fraction of equity per trade")
    p.add_argument("--stop-loss", type=float, default=None, help="Hard stop-loss % (e.g. 0.05=5%%)")
    p.add_argument("--trailing-stop", type=float, default=None, help="Trailing stop % (e.g. 0.03=3%%)")
    p.add_argument("--atr-stop", type=float, default=None, help="ATR stop multiplier (e.g. 2.0)")
    p.add_argument("--max-positions", type=int, default=10, help="Max simultaneous positions")
    p.add_argument("--position-fraction", type=float, default=None,
                   help="Deploy a fixed fraction of equity per trade (e.g. 0.20 = 20%%). "
                        "Overrides --risk-per-trade. Set --max-positions to 1/fraction "
                        "to cap concurrent exposure at 100%% (e.g. 5 for 20%%).")
    p.add_argument("--profit-trigger", type=float, default=None,
                   help="Unrealised profit %% that activates trailing stop (e.g. 0.10=10%%)")
    p.add_argument("--trailing-after-profit", type=float, default=None,
                   help="Trailing stop %% once profit trigger fires (e.g. 0.02=2%%)")

    # Output
    p.add_argument("--output", default="backtest_report.html", help="HTML report output path")
    p.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level",
    )

    return p.parse_args()


def main() -> None:
    args = parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    # 1. Fetch data
    print(f"Fetching data for {args.ticker} ({args.start} → {args.end})…")
    df = fetch_ohlcv(
        ticker=args.ticker,
        start=args.start,
        end=args.end,
        interval=args.interval,
        use_cache=not args.no_cache,
    )
    print(f"  {len(df)} bars loaded.")

    # 2. Build strategy
    strategy = build_strategy(args)
    print(f"Strategy: {strategy.name}")

    # 3. Build risk manager
    risk_mgr = RiskManager(
        risk_per_trade=args.risk_per_trade,
        stop_loss_pct=args.stop_loss,
        trailing_stop_pct=args.trailing_stop,
        atr_stop_multiplier=args.atr_stop,
        max_positions=args.max_positions,
        profit_trigger_pct=args.profit_trigger,
        trailing_after_profit_pct=args.trailing_after_profit,
        position_fraction=args.position_fraction,
    )

    # Wire DCA fixed-dollar sizing
    if STRATEGY_MAP.get(args.strategy.lower()) == "dca":
        risk_mgr.dca_amount = args.dca_amount

    # 4. Run backtest
    engine = Backtester(
        strategy=strategy,
        risk_manager=risk_mgr,
        initial_capital=args.initial_capital,
        commission=args.commission,
        slippage=args.slippage,
        long_only=not args.long_short,
    )
    result = engine.run(df, ticker=args.ticker)

    # 5. Calculate metrics
    from config import DEFAULT_RISK_FREE_RATE
    metrics = calculate_metrics(
        equity=result.equity_curve,
        trades=result.trades,
        buy_hold_curve=result.buy_hold_curve,
        initial_capital=args.initial_capital,
        risk_free_rate=DEFAULT_RISK_FREE_RATE,
    )

    # 6. Print to terminal
    print_metrics(metrics, strategy_name=result.strategy_name, ticker=args.ticker)

    # 7. Generate HTML report
    report_path = generate_html_report(result, metrics, output_path=args.output)
    print(f"\nHTML report saved → {os.path.abspath(report_path)}")


if __name__ == "__main__":
    main()
