import json
from pathlib import Path

MAX_SAVED = 20
STORAGE_PATH = Path(__file__).resolve().parent.parent / "recent.json"


def _read_all():
    if not STORAGE_PATH.exists():
        return []
    try:
        return json.loads(STORAGE_PATH.read_text())
    except (json.JSONDecodeError, ValueError):
        return []


def _write_all(contracts):
    STORAGE_PATH.write_text(json.dumps(contracts, indent=2))


def save_contract(ticker, expiry, option_type, strike):
    """Save a contract to the recent list. Deduplicates and caps at MAX_SAVED."""
    entry = {
        "ticker": ticker,
        "expiry": expiry,
        "type": option_type,
        "strike": strike,
    }
    contracts = _read_all()

    # Remove duplicate if it already exists
    contracts = [c for c in contracts if c != entry]

    # Insert at the front (most recent first)
    contracts.insert(0, entry)

    # Cap at MAX_SAVED
    contracts = contracts[:MAX_SAVED]

    _write_all(contracts)


def load_contracts():
    """Return the list of saved contracts, most recent first."""
    return _read_all()


def prune_expired():
    """Remove contracts whose expiry has passed. 0DTE contracts are kept
    until market close, then pruned on the next app load."""
    from data.timeutils import days_until, market_hours_remaining

    contracts = _read_all()
    kept = []
    for c in contracts:
        dte = days_until(c["expiry"])
        if dte > 0:
            kept.append(c)
        elif dte == 0 and market_hours_remaining(c["expiry"]):
            # 0DTE but market still open — keep it
            kept.append(c)
        # else: expired, drop it

    if len(kept) != len(contracts):
        _write_all(kept)

    return len(contracts) - len(kept)


def remove_contract(index):
    """Remove a contract by index."""
    contracts = _read_all()
    if 0 <= index < len(contracts):
        contracts.pop(index)
        _write_all(contracts)
