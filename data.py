import yfinance as yf
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
MARKET_OPEN = time(9, 30)
MARKET_CLOSE = time(16, 0)


def now_et():
    return datetime.now(ET)


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
    """Calendar days until expiry, computed in Eastern Time."""
    expiry = datetime.strptime(expiry_str, "%Y-%m-%d").date()
    return max((expiry - now_et().date()).days, 0)


def market_hours_remaining(expiry_str):
    """For 0DTE: return list of hourly ET datetimes from now (or market open)
    through market close, at 30-minute intervals.

    Returns empty list if market has already closed or expiry isn't today.
    """
    expiry = datetime.strptime(expiry_str, "%Y-%m-%d").date()
    et_now = now_et()

    if expiry != et_now.date():
        return []

    close_dt = datetime.combine(expiry, MARKET_CLOSE, tzinfo=ET)
    open_dt = datetime.combine(expiry, MARKET_OPEN, tzinfo=ET)

    # Start from market open or current time, whichever is later
    start = max(open_dt, et_now)

    if start >= close_dt:
        return []

    # Generate 30-minute intervals from start to close (inclusive of close)
    times = []
    t = start.replace(minute=(start.minute // 30) * 30, second=0, microsecond=0)
    if t < start:
        t += timedelta(minutes=30)
    while t <= close_dt:
        times.append(t)
        t += timedelta(minutes=30)

    # Always include close if not already there
    if not times or times[-1] != close_dt:
        times.append(close_dt)

    return times
