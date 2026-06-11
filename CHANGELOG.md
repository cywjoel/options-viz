# Changelog

## 0.1.1
- Add 0DTE intraday charts with 30-minute granularity during market hours (9:30am-4pm ET)
- Fix timezone bug: all date/time calculations now use Eastern Time, fixing DTE miscount for non-ET users
- Add saved contracts sidebar (collapsible) with persist-to-disk storage (recent.json)
- Auto-prune expired contracts on app load with toast notification
- Refactor data.py into data/ package (market.py, timeutils.py, storage.py)

## 0.1.0
- Theoretical options price decay and daily theta charts with interactive crosshair
- Mid-price anchoring: decay curves start at bid/ask midpoint (or last traded price) instead of pure Black-Scholes
- IV auto-populated from market data; falls back to numerical solve from last traded price when market is closed
- TradingView advanced chart widget embedded for each ticker
- Smart price detection: uses pre-market, post-market, or regular market price depending on session timing
- Date slider to inspect option price, theta, DTE, and moneyness at any point
- Option price vs. stock price sensitivity chart with IV-scaled default range
- Spot price lookup for exact option value at a selected date
- Profit target chart: required stock price over time to achieve a user-defined profit percentage
- Live data from yfinance (no API key required)
