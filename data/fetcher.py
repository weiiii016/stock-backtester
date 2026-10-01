"""Yahoo Finance data downloader with local CSV caching."""

import logging
import os
from pathlib import Path
from typing import Optional

import pandas as pd
import yfinance as yf

from config import CACHE_DIR, DEFAULT_INTERVAL

logger = logging.getLogger(__name__)


def _cache_path(ticker: str, start: str, end: str, interval: str) -> Path:
    """Build a deterministic cache file path for a given query."""
    safe_ticker = ticker.upper().replace("/", "-")
    filename = f"{safe_ticker}_{start}_{end}_{interval}.csv"
    return Path(CACHE_DIR) / filename


def fetch_ohlcv(
    ticker: str,
    start: str,
    end: str,
    interval: str = DEFAULT_INTERVAL,
    use_cache: bool = True,
    cache_dir: str = CACHE_DIR,
) -> pd.DataFrame:
    """
    Download OHLCV data for a single ticker from Yahoo Finance.

    Uses adjusted close prices to account for splits and dividends.
    Downloaded data is cached as a CSV file to avoid redundant API calls.

    Args:
        ticker:    Stock ticker symbol (e.g. "AAPL").
        start:     Start date string "YYYY-MM-DD".
        end:       End date string "YYYY-MM-DD".
        interval:  Bar interval ("1d", "1wk", "1mo").
        use_cache: If True, read from cache when available and write new data.
        cache_dir: Directory for CSV cache files.

    Returns:
        DataFrame with columns: Open, High, Low, Close, Volume.
        Index is DatetimeIndex (UTC-normalised, timezone-naive).

    Raises:
        ValueError: If no data is returned for the ticker/date range.
    """
    os.makedirs(cache_dir, exist_ok=True)
    cache_file = _cache_path(ticker, start, end, interval)
    cache_file = Path(cache_dir) / cache_file.name

    if use_cache and cache_file.exists():
        logger.info("Loading %s from cache: %s", ticker, cache_file)
        df = pd.read_csv(cache_file, index_col=0, parse_dates=True)
        df.index = pd.to_datetime(df.index, utc=True).tz_localize(None)
        return df

    logger.info("Downloading %s from Yahoo Finance (%s → %s)…", ticker, start, end)
    raw = yf.download(
        ticker,
        start=start,
        end=end,
        interval=interval,
        auto_adjust=True,   # gives adjusted OHLCV — splits & dividends baked in
        progress=False,
    )

    if raw.empty:
        raise ValueError(
            f"No data returned for ticker '{ticker}' between {start} and {end}."
        )

    # yfinance may return multi-level columns when auto_adjust=True
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)

    df = raw[["Open", "High", "Low", "Close", "Volume"]].copy()
    df.index = pd.to_datetime(df.index).tz_localize(None)
    df.dropna(inplace=True)

    if use_cache:
        df.to_csv(cache_file)
        logger.info("Cached %s data to %s", ticker, cache_file)

    return df


def fetch_multiple(
    tickers: list[str],
    start: str,
    end: str,
    interval: str = DEFAULT_INTERVAL,
    use_cache: bool = True,
) -> dict[str, pd.DataFrame]:
    """
    Download OHLCV data for multiple tickers.

    Args:
        tickers:   List of ticker symbols.
        start:     Start date string "YYYY-MM-DD".
        end:       End date string "YYYY-MM-DD".
        interval:  Bar interval.
        use_cache: Whether to use CSV caching.

    Returns:
        Dict mapping ticker → DataFrame.
    """
    result: dict[str, pd.DataFrame] = {}
    for ticker in tickers:
        try:
            result[ticker] = fetch_ohlcv(ticker, start, end, interval, use_cache)
        except ValueError as exc:
            logger.warning("Skipping %s: %s", ticker, exc)
    return result
