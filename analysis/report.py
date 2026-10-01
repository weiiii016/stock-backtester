"""Generate a self-contained HTML backtest report with embedded charts."""

import base64
import io
import logging
from typing import Any, Optional

import matplotlib
matplotlib.use("Agg")  # non-interactive backend — must be set before pyplot import
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

from analysis.metrics import compute_monthly_returns
from engine.backtester import BacktestResult
from engine.portfolio import Trade

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Chart helpers
# ---------------------------------------------------------------------------

CHART_STYLE = {
    "figure.facecolor": "#1a1a2e",
    "axes.facecolor": "#16213e",
    "axes.edgecolor": "#444",
    "axes.labelcolor": "#ccc",
    "xtick.color": "#aaa",
    "ytick.color": "#aaa",
    "text.color": "#ddd",
    "grid.color": "#333",
    "grid.linestyle": "--",
    "grid.linewidth": 0.5,
    "lines.linewidth": 1.8,
}

STRATEGY_COLOR = "#00d4ff"
BH_COLOR = "#f0a500"
LOSS_COLOR = "#ff4757"
GAIN_COLOR = "#2ed573"


def _fig_to_base64(fig: plt.Figure) -> str:
    """Encode a matplotlib Figure as a base64 PNG string."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight", facecolor=fig.get_facecolor())
    buf.seek(0)
    encoded = base64.b64encode(buf.read()).decode("utf-8")
    plt.close(fig)
    return encoded


def _equity_chart(
    strategy_curve: pd.Series,
    bh_curve: pd.Series,
    strategy_name: str,
    ticker: str,
) -> str:
    """Return base64 PNG of the equity curve comparison."""
    with plt.rc_context(CHART_STYLE):
        fig, ax = plt.subplots(figsize=(12, 4.5))
        ax.plot(strategy_curve.index, strategy_curve.values,
                color=STRATEGY_COLOR, label=strategy_name, zorder=3)
        ax.plot(bh_curve.index, bh_curve.values,
                color=BH_COLOR, label=f"{ticker} Buy & Hold", alpha=0.8, zorder=2)
        ax.fill_between(strategy_curve.index, strategy_curve.values,
                        bh_curve.reindex(strategy_curve.index, method="ffill").values,
                        where=(strategy_curve.values >= bh_curve.reindex(strategy_curve.index, method="ffill").values),
                        alpha=0.08, color=GAIN_COLOR)
        ax.fill_between(strategy_curve.index, strategy_curve.values,
                        bh_curve.reindex(strategy_curve.index, method="ffill").values,
                        where=(strategy_curve.values < bh_curve.reindex(strategy_curve.index, method="ffill").values),
                        alpha=0.08, color=LOSS_COLOR)
        ax.set_title("Portfolio Equity Curve", fontsize=13, pad=10)
        ax.set_ylabel("Equity ($)")
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"${x:,.0f}"))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
        fig.autofmt_xdate()
        ax.legend(loc="upper left", framealpha=0.3)
        ax.grid(True)
    return _fig_to_base64(fig)


def _drawdown_chart(equity: pd.Series) -> str:
    """Return base64 PNG of the drawdown chart."""
    rolling_max = equity.cummax()
    dd = (equity - rolling_max) / rolling_max * 100  # in percent

    with plt.rc_context(CHART_STYLE):
        fig, ax = plt.subplots(figsize=(12, 3))
        ax.fill_between(dd.index, dd.values, 0, color=LOSS_COLOR, alpha=0.7)
        ax.plot(dd.index, dd.values, color=LOSS_COLOR, linewidth=1)
        ax.set_title("Drawdown (%)", fontsize=13, pad=10)
        ax.set_ylabel("Drawdown (%)")
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:.1f}%"))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
        fig.autofmt_xdate()
        ax.grid(True)
    return _fig_to_base64(fig)


def _monthly_heatmap(equity: pd.Series) -> Optional[str]:
    """Return base64 PNG of the monthly returns heatmap, or None if too little data."""
    monthly = compute_monthly_returns(equity)
    if monthly.empty or monthly.shape[0] < 1:
        return None

    month_labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    # Ensure all 12 months are columns
    for m in range(1, 13):
        if m not in monthly.columns:
            monthly[m] = np.nan
    monthly = monthly[[c for c in range(1, 13) if c in monthly.columns]]
    data = monthly.values * 100  # convert to pct

    with plt.rc_context(CHART_STYLE):
        fig, ax = plt.subplots(
            figsize=(max(10, monthly.shape[1] * 0.85), max(3, monthly.shape[0] * 0.5 + 1))
        )

        vmax = max(abs(np.nanmax(data)), abs(np.nanmin(data)), 1)
        im = ax.imshow(data, cmap="RdYlGn", aspect="auto", vmin=-vmax, vmax=vmax)

        ax.set_xticks(range(len(monthly.columns)))
        ax.set_xticklabels([month_labels[c - 1] for c in monthly.columns])
        ax.set_yticks(range(len(monthly.index)))
        ax.set_yticklabels(monthly.index.astype(str))
        ax.set_title("Monthly Returns (%)", fontsize=13, pad=10)

        for r in range(data.shape[0]):
            for c in range(data.shape[1]):
                val = data[r, c]
                if not np.isnan(val):
                    ax.text(c, r, f"{val:.1f}%", ha="center", va="center",
                            fontsize=8, color="black" if abs(val) < vmax * 0.6 else "white")

        plt.colorbar(im, ax=ax, fraction=0.02, pad=0.02,
                     format=mticker.FuncFormatter(lambda x, _: f"{x:.0f}%"))
        fig.tight_layout()
    return _fig_to_base64(fig)


# ---------------------------------------------------------------------------
# HTML template
# ---------------------------------------------------------------------------

_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Segoe UI', Arial, sans-serif; background: #0f0f23; color: #ccc; }
h1, h2, h3 { color: #e0e0ff; }
.container { max-width: 1200px; margin: 0 auto; padding: 24px 16px; }
.header { text-align: center; padding: 32px 0 24px; }
.header h1 { font-size: 2rem; color: #00d4ff; margin-bottom: 6px; }
.header .subtitle { color: #888; font-size: 0.95rem; }
.section { margin: 32px 0; }
.section h2 { font-size: 1.2rem; border-bottom: 1px solid #333; padding-bottom: 8px; margin-bottom: 18px; }
.metrics-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
    gap: 12px;
}
.metric-card {
    background: #1a1a2e;
    border: 1px solid #333;
    border-radius: 8px;
    padding: 14px 16px;
    text-align: center;
}
.metric-card .label { font-size: 0.75rem; color: #888; text-transform: uppercase; letter-spacing: 0.05em; }
.metric-card .value { font-size: 1.4rem; font-weight: 700; margin-top: 4px; }
.positive { color: #2ed573; }
.negative { color: #ff4757; }
.neutral  { color: #00d4ff; }
.chart-img { width: 100%; border-radius: 8px; border: 1px solid #333; margin-bottom: 16px; }
table { width: 100%; border-collapse: collapse; font-size: 0.82rem; }
thead th { background: #1a1a2e; color: #aaa; padding: 8px 10px; text-align: left;
           border-bottom: 2px solid #333; }
tbody tr:nth-child(even) { background: #141428; }
tbody td { padding: 7px 10px; border-bottom: 1px solid #282848; }
.win  { color: #2ed573; font-weight: 600; }
.loss { color: #ff4757; font-weight: 600; }
.tag  { display: inline-block; padding: 2px 7px; border-radius: 4px; font-size: 0.72rem; }
.tag-long  { background: #003d20; color: #2ed573; }
.tag-short { background: #3d0000; color: #ff4757; }
"""

_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>{css}</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>{ticker} — {strategy}</h1>
    <div class="subtitle">{date_range} &nbsp;|&nbsp; Initial capital: {initial_capital}</div>
  </div>

  <div class="section">
    <h2>Performance Summary</h2>
    <div class="metrics-grid">{metric_cards}</div>
  </div>

  <div class="section">
    <h2>Equity Curve</h2>
    <img class="chart-img" src="data:image/png;base64,{equity_chart}" alt="Equity Curve">
  </div>

  <div class="section">
    <h2>Drawdown</h2>
    <img class="chart-img" src="data:image/png;base64,{drawdown_chart}" alt="Drawdown">
  </div>

  {monthly_section}

  <div class="section">
    <h2>Trade List ({trade_count} trades)</h2>
    <div style="overflow-x:auto">
    <table>
      <thead>
        <tr>
          <th>#</th><th>Direction</th><th>Entry Date</th><th>Entry Price</th>
          <th>Exit Date</th><th>Exit Price</th><th>Qty</th>
          <th>Net P&amp;L</th><th>Return %</th><th>Days</th>
        </tr>
      </thead>
      <tbody>{trade_rows}</tbody>
    </table>
    </div>
  </div>

  <div style="text-align:center;color:#555;font-size:0.75rem;padding:24px 0;">
    Generated by Python Backtester &nbsp;|&nbsp; Data: Yahoo Finance
  </div>
</div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _metric_card(label: str, value: str, css_class: str = "neutral") -> str:
    return (
        f'<div class="metric-card">'
        f'<div class="label">{label}</div>'
        f'<div class="value {css_class}">{value}</div>'
        f"</div>"
    )


def _classify(value: float) -> str:
    if value > 0:
        return "positive"
    if value < 0:
        return "negative"
    return "neutral"


def generate_html_report(
    result: BacktestResult,
    metrics: dict[str, Any],
    output_path: str = "backtest_report.html",
) -> str:
    """
    Create a self-contained HTML report and write it to disk.

    Args:
        result:      BacktestResult from the engine.
        metrics:     Metrics dict from analysis.metrics.calculate_metrics.
        output_path: File path for the output HTML.

    Returns:
        The output path (same as input).
    """
    logger.info("Generating HTML report → %s", output_path)

    # --- Charts ---
    equity_b64 = _equity_chart(
        result.equity_curve, result.buy_hold_curve,
        result.strategy_name, result.ticker,
    )
    dd_b64 = _drawdown_chart(result.equity_curve)
    monthly_b64 = _monthly_heatmap(result.equity_curve)

    # --- Metric cards ---
    m = metrics
    cards = [
        _metric_card("Total Return", f"{m.get('total_return_pct', 0):.2f}%",
                     _classify(m.get("total_return_pct", 0))),
        _metric_card("Ann. Return", f"{m.get('annualized_return_pct', 0):.2f}%",
                     _classify(m.get("annualized_return_pct", 0))),
        _metric_card("Sharpe Ratio", f"{m.get('sharpe_ratio', 0):.3f}",
                     "positive" if m.get("sharpe_ratio", 0) >= 1 else
                     "negative" if m.get("sharpe_ratio", 0) < 0 else "neutral"),
        _metric_card("Sortino Ratio", f"{m.get('sortino_ratio', 0):.3f}",
                     "positive" if m.get("sortino_ratio", 0) >= 1 else "neutral"),
        _metric_card("Max Drawdown", f"{m.get('max_drawdown_pct', 0):.2f}%",
                     _classify(m.get("max_drawdown_pct", 0))),
        _metric_card("DD Duration", f"{m.get('max_drawdown_duration_days', 0)} days", "neutral"),
        _metric_card("Calmar Ratio", f"{m.get('calmar_ratio', 0):.3f}",
                     "positive" if m.get("calmar_ratio", 0) >= 0.5 else "neutral"),
        _metric_card("Win Rate", f"{m.get('win_rate_pct', 0):.1f}%",
                     "positive" if m.get("win_rate_pct", 0) >= 50 else "negative"),
        _metric_card("Profit Factor", f"{m.get('profit_factor', 0):.3f}",
                     "positive" if m.get("profit_factor", 0) >= 1 else "negative"),
        _metric_card("Avg Win", f"${m.get('avg_win', 0):,.2f}", "positive"),
        _metric_card("Avg Loss", f"${m.get('avg_loss', 0):,.2f}", "negative"),
        _metric_card("Expectancy", f"${m.get('expectancy_per_trade', 0):,.2f}",
                     _classify(m.get("expectancy_per_trade", 0))),
        _metric_card("Total Trades", str(m.get("total_trades", 0)), "neutral"),
        _metric_card("Avg Hold", f"{m.get('avg_holding_days', 0):.1f} days", "neutral"),
        _metric_card("Ann. Vol", f"{m.get('annualized_volatility_pct', 0):.2f}%", "neutral"),
        _metric_card("B&H Return", f"{m.get('buy_hold_return_pct', 0):.2f}%",
                     _classify(m.get("buy_hold_return_pct", 0))),
        _metric_card("Alpha vs B&H", f"{m.get('alpha_pct', 0):.2f}%",
                     _classify(m.get("alpha_pct", 0))),
        _metric_card("Risk-Free Rate", f"{m.get('risk_free_rate_pct', 4.5):.1f}%", "neutral"),
    ]

    # --- Trade rows ---
    trade_rows = ""
    for i, t in enumerate(result.trades, 1):
        pnl_class = "win" if t.net_pnl >= 0 else "loss"
        dir_tag = (
            '<span class="tag tag-long">LONG</span>'
            if t.direction == 1
            else '<span class="tag tag-short">SHORT</span>'
        )
        ret_pct = t.return_pct * 100
        trade_rows += (
            f"<tr>"
            f"<td>{i}</td>"
            f"<td>{dir_tag}</td>"
            f"<td>{t.entry_date.strftime('%Y-%m-%d')}</td>"
            f"<td>${t.entry_price:,.2f}</td>"
            f"<td>{t.exit_date.strftime('%Y-%m-%d')}</td>"
            f"<td>${t.exit_price:,.2f}</td>"
            f"<td>{t.quantity:.2f}</td>"
            f'<td class="{pnl_class}">${t.net_pnl:,.2f}</td>'
            f'<td class="{pnl_class}">{ret_pct:+.2f}%</td>'
            f"<td>{t.holding_days}</td>"
            f"</tr>\n"
        )

    if not trade_rows:
        trade_rows = '<tr><td colspan="10" style="text-align:center;color:#666">No trades executed</td></tr>'

    # --- Monthly section ---
    if monthly_b64:
        monthly_section = (
            '<div class="section">'
            '<h2>Monthly Returns Heatmap</h2>'
            f'<img class="chart-img" src="data:image/png;base64,{monthly_b64}" alt="Monthly Returns">'
            "</div>"
        )
    else:
        monthly_section = ""

    # --- Date range ---
    if not result.equity_curve.empty:
        date_range = (
            f"{result.equity_curve.index[0].strftime('%Y-%m-%d')} → "
            f"{result.equity_curve.index[-1].strftime('%Y-%m-%d')}"
        )
    else:
        date_range = "N/A"

    html = _HTML_TEMPLATE.format(
        title=f"{result.ticker} Backtest — {result.strategy_name}",
        css=_CSS,
        ticker=result.ticker,
        strategy=result.strategy_name,
        date_range=date_range,
        initial_capital=f"${result.initial_capital:,.0f}",
        metric_cards="\n".join(cards),
        equity_chart=equity_b64,
        drawdown_chart=dd_b64,
        monthly_section=monthly_section,
        trade_count=len(result.trades),
        trade_rows=trade_rows,
    )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    logger.info("Report saved to %s", output_path)
    return output_path
