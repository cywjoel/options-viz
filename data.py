import yfinance as yf
from datetime import datetime


def get_spot_price(ticker):
    """Return (price, label) using the most recent available price.

    Uses pre-market or post-market price when available, otherwise regular market.
    """
    t = yf.Ticker(ticker)

    try:
        info = t.info
    except Exception:
        info = {}

    state = info.get("marketState", "")

    if state == "PRE" and info.get("preMarketPrice"):
        return info["preMarketPrice"], "Pre-Market Price"
    if state in ("POST", "POSTPOST", "CLOSED") and info.get("postMarketPrice"):
        return info["postMarketPrice"], "Post-Market Price"
    if info.get("regularMarketPrice"):
        return info["regularMarketPrice"], "Spot Price"

    # Fallback for tickers where .info is incomplete
    return t.fast_info.last_price, "Spot Price"


def get_options_chain(ticker):
    """Return available expiry dates and the full options chain for each."""
    t = yf.Ticker(ticker)
    expiries = t.options
    return t, expiries


def get_chain_for_expiry(ticker_obj, expiry_str):
    """Return (calls_df, puts_df) for a given expiry date string."""
    chain = ticker_obj.option_chain(expiry_str)
    return chain.calls, chain.puts


def days_until(expiry_str):
    expiry = datetime.strptime(expiry_str, "%Y-%m-%d")
    return max((expiry - datetime.now()).days, 0)
