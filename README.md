# Options Decay Visualizer

A Streamlit app for visualizing the theoretical time decay (theta) of options contracts, using live market data from yfinance.

## Setup

Requires Python 3.10+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone <repo-url> && cd options-viz
uv sync
```

## Run

```bash
uv run streamlit run app.py
```

Opens at `http://localhost:8501`.

## Features

- **Live pricing** — Automatically uses pre-market, post-market, or regular market price depending on session timing (via yfinance).
- **TradingView chart** — Embedded advanced chart widget for the selected ticker, with full drawing/indicator tools.
- **Contract selection** — Pick any available expiry, strike, and call/put from the live options chain.
- **IV from market data** — Implied volatility defaults to the contract's market IV, with a slider to override.
- **Mid-price anchoring** — Decay curves start at the actual bid/ask midpoint rather than pure Black-Scholes, then apply theoretical decay from there.
- **Price decay chart** — Theoretical option price from today through expiration.
- **Theta chart** — Daily theta over the same period, showing acceleration near expiry. Both charts share a crosshair on hover.
- **Date slider** — Select any date to see option price, theta, DTE, and moneyness at that point.
- **Price sensitivity chart** — Option price across a range of stock prices at the selected date. Default range is spot +/- 2 standard deviations (IV-scaled), adjustable via slider.
- **Price lookup** — Enter any stock price to get the exact theoretical option value at the selected date.

## Project structure

```
app.py        Streamlit UI, charts, and layout
pricing.py    Black-Scholes pricing, theta, and decay curve generation
data.py       yfinance wrapper for spot price, options chains, and expiry dates
```

## Data sources

- **yfinance** — Stock prices, options chains, implied volatility. No API key needed.
- **TradingView** — Embedded chart widget (client-side, no API key).
