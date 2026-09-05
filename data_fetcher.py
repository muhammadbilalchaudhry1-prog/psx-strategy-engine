"""Robust data fetching module for PSX stocks with multiple fallback strategies."""

import pandas as pd
import numpy as np
import yfinance as yf
import requests
from bs4 import BeautifulSoup
from typing import Tuple, Optional
import logging

from config import (
    YAHOO_FINANCE_SUFFIX,
    DATA_CACHE_TTL,
    FETCH_TIMEOUT,
    HISTORICAL_PERIOD,
    HISTORICAL_INTERVAL,
    MIN_DATA_POINTS,
)

logger = logging.getLogger(__name__)


class DataFetchError(Exception):
    """Custom exception for data fetching failures."""
    pass


def fetch_live_psx_data(symbol: str) -> Tuple[Optional[pd.DataFrame], str]:
    """
    Fetch live PSX data with intelligent fallback strategy.
    
    Priority order:
    1. Yahoo Finance (yfinance) with .KA suffix
    2. Direct PSX web scraping
    3. Fail gracefully with error message
    
    Args:
        symbol: PSX ticker symbol (e.g., 'SYS', 'ENGRO')
        
    Returns:
        Tuple of (DataFrame, source_label) or (None, error_message)
    """
    
    # Try Yahoo Finance first
    try:
        df = _fetch_from_yahoo_finance(symbol)
        if df is not None and len(df) >= MIN_DATA_POINTS:
            return df, "Yahoo Finance (.KA Feed)"
    except Exception as e:
        logger.warning(f"Yahoo Finance fetch failed for {symbol}: {str(e)}")
    
    # Try PSX web scraping
    try:
        df = _fetch_from_psx_portal(symbol)
        if df is not None and len(df) >= MIN_DATA_POINTS:
            return df, "PSX Data Portal"
    except Exception as e:
        logger.warning(f"PSX Portal scrape failed for {symbol}: {str(e)}")
    
    # All strategies failed
    error_msg = (
        f"Could not fetch live market data for symbol '{symbol}'. "
        f"Ensure the PSX ticker symbol is correct and data sources are accessible."
    )
    logger.error(error_msg)
    return None, error_msg


def _fetch_from_yahoo_finance(symbol: str) -> Optional[pd.DataFrame]:
    """
    Fetch historical data from Yahoo Finance using .KA suffix (Karachi).
    
    Args:
        symbol: PSX ticker symbol
        
    Returns:
        DataFrame with OHLC data or None if fetch fails
    """
    yf_ticker = f"{symbol}{YAHOO_FINANCE_SUFFIX}"
    logger.info(f"Fetching from Yahoo Finance: {yf_ticker}")
    
    try:
        df = yf.download(
            yf_ticker,
            period=HISTORICAL_PERIOD,
            interval=HISTORICAL_INTERVAL,
            progress=False,
            timeout=FETCH_TIMEOUT
        )
        
        if df.empty:
            logger.warning(f"Yahoo Finance returned empty data for {yf_ticker}")
            return None
        
        # Flatten MultiIndex columns if present (occurs with single ticker downloads)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        
        # Validate required columns
        required_cols = ['Open', 'High', 'Low', 'Close']
        if not all(col in df.columns for col in required_cols):
            logger.warning(f"Missing OHLC columns in Yahoo Finance data for {yf_ticker}")
            return None
        
        # Ensure data is sorted by date and has no NaN prices
        df = df.dropna(subset=['Close'])
        df = df.sort_index()
        
        logger.info(f"Successfully fetched {len(df)} rows from Yahoo Finance")
        return df
        
    except Exception as e:
        logger.error(f"Yahoo Finance error for {yf_ticker}: {str(e)}")
        return None


def _fetch_from_psx_portal(symbol: str) -> Optional[pd.DataFrame]:
    """
    Fetch data by scraping PSX official portal.
    
    IMPORTANT: This method scrapes the current price only.
    It does NOT generate synthetic historical data.
    Users must rely on Yahoo Finance or provide historical CSV.
    
    Args:
        symbol: PSX ticker symbol
        
    Returns:
        DataFrame with minimal OHLC data or None if scrape fails
    """
    url = f"https://dps.psx.com.pk/company/{symbol}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    logger.info(f"Attempting PSX Portal scrape: {url}")
    
    try:
        resp = requests.get(url, headers=headers, timeout=FETCH_TIMEOUT)
        resp.raise_for_status()  # Raise exception for non-200 status codes
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        price_div = soup.find("div", class_="quote__price")
        
        if not price_div:
            logger.warning(f"Could not find price element for {symbol} on PSX Portal")
            return None
        
        try:
            price_text = price_div.text.replace("PKR", "").replace(",", "").strip()
            price = float(price_text)
        except ValueError:
            logger.warning(f"Could not parse price text: {price_div.text}")
            return None
        
        logger.warning(
            f"PSX Portal scrape only provides current price (PKR {price:.2f}). "
            f"Insufficient for technical analysis. Consider using historical CSV upload."
        )
        return None  # Return None to trigger fallback or error message
        
    except requests.exceptions.RequestException as e:
        logger.error(f"PSX Portal request failed: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"PSX Portal scrape error: {str(e)}")
        return None


def load_csv_data(file_path: str) -> Optional[pd.DataFrame]:
    """
    Load historical OHLC data from CSV file.
    Expected columns: Date, Open, High, Low, Close
    
    Args:
        file_path: Path to CSV file
        
    Returns:
        DataFrame with OHLC data or None if load fails
    """
    try:
        df = pd.read_csv(file_path, parse_dates=['Date'], index_col='Date')
        df = df[['Open', 'High', 'Low', 'Close']].dropna()
        df = df.sort_index()
        logger.info(f"Loaded {len(df)} rows from CSV: {file_path}")
        return df
    except Exception as e:
        logger.error(f"CSV load error: {str(e)}")
        return None
