from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
MARKET_OPEN = time(9, 30)
MARKET_CLOSE = time(16, 0)


def now_et():
    return datetime.now(ET)


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
