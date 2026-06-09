from datetime import datetime, timedelta

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

import numpy as np

from data import get_spot_price, get_options_chain, get_chain_for_expiry, days_until
from pricing import black_scholes_price, decay_curve, implied_vol, stock_price_for_target

st.set_page_config(page_title="Options Decay Visualizer", layout="wide")
st.title("Options Decay Visualizer")

# --- Ticker input and data fetch ---
ticker = st.text_input("Ticker", value="AAPL").upper().strip()

if not ticker:
    st.stop()

try:
    spot, price_label = get_spot_price(ticker)
    st.metric(price_label, f"${spot:.2f}")
except Exception as e:
    st.error(f"Could not fetch data for {ticker}: {e}")
    st.stop()

# --- TradingView chart ---
tv_widget = f"""
<div class="tradingview-widget-container" style="height:500px;width:100%">
  <div id="tradingview_chart" style="height:100%;width:100%"></div>
  <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
  <script type="text/javascript">
    new TradingView.widget({{
      "autosize": true,
      "symbol": "{ticker}",
      "interval": "D",
      "timezone": "Etc/UTC",
      "theme": "dark",
      "style": "1",
      "locale": "en",
      "allow_symbol_change": false,
      "hide_side_toolbar": false,
      "container_id": "tradingview_chart"
    }});
  </script>
</div>
"""
st.components.v1.html(tv_widget, height=500)

ticker_obj, expiries = get_options_chain(ticker)

if not expiries:
    st.warning("No options data available for this ticker.")
    st.stop()

# --- Expiry and strike selection ---
col1, col2, col3 = st.columns(3)

with col1:
    expiry = st.selectbox("Expiry", expiries)

with col2:
    option_type = st.selectbox("Type", ["call", "put"])

calls_df, puts_df = get_chain_for_expiry(ticker_obj, expiry)
chain_df = calls_df if option_type == "call" else puts_df

strikes = chain_df["strike"].tolist()
# Default to the strike closest to spot
default_idx = min(range(len(strikes)), key=lambda i: abs(strikes[i] - spot))

with col3:
    strike = st.selectbox("Strike", strikes, index=default_idx)

# --- IV and parameters ---
row = chain_df[chain_df["strike"] == strike].iloc[0]

bid = row.get("bid", 0.0) or 0.0
ask = row.get("ask", 0.0) or 0.0

if bid > 0 and ask > 0:
    anchor_price = (bid + ask) / 2.0
else:
    anchor_price = row.get("lastPrice", 0.0) or 0.0

dte = days_until(expiry)
if dte == 0:
    st.warning("This contract expires today.")
    st.stop()

market_iv = row.get("impliedVolatility", 0.0) or 0.0
if market_iv < 0.01:
    last_price = row.get("lastPrice", 0.0) or 0.0
    computed_iv = implied_vol(last_price, spot, strike, dte / 365.0, 0.045, option_type)
    market_iv = computed_iv if computed_iv is not None else 0.3

st.divider()
col_iv, col_r = st.columns(2)

with col_iv:
    iv = st.slider("Implied Volatility", 0.05, 2.0, float(market_iv), 0.01, format="%.2f")

with col_r:
    risk_free = st.slider("Risk-Free Rate", 0.0, 0.10, 0.045, 0.005, format="%.3f")

days_remaining, prices, thetas = decay_curve(spot, strike, dte, risk_free, iv, option_type)
days_elapsed = dte - days_remaining

# Anchor the decay curve to the market mid price instead of pure BS
bs_price_now = black_scholes_price(spot, strike, dte / 365.0, risk_free, iv, option_type)
if bs_price_now > 0 and anchor_price > 0:
    scale = anchor_price / bs_price_now
    prices = prices * scale
    thetas = thetas * scale

today = datetime.now().date()
dates = [today + timedelta(days=int(d)) for d in days_elapsed]
date_strs = [d.strftime("%d-%m-%Y") for d in dates]
price_strs = [f"${p:.4f}" for p in prices]
theta_strs = [f"${t:.4f}" for t in thetas]

# --- Charts ---
fig = make_subplots(
    rows=2, cols=1,
    shared_xaxes=True,
    vertical_spacing=0.08,
    subplot_titles=("Theoretical Price Decay", "Daily Theta"),
)

fig.add_trace(
    go.Scatter(
        x=dates, y=prices,
        mode="lines",
        name="Price",
        line=dict(color="#2196F3", width=2),
        customdata=list(zip(date_strs, price_strs)),
        hovertemplate="Date: %{customdata[0]}<br>Option Price: %{customdata[1]}<extra></extra>",
    ),
    row=1, col=1,
)

fig.add_trace(
    go.Scatter(
        x=dates, y=thetas,
        mode="lines",
        name="Theta",
        line=dict(color="#FF5722", width=2),
        customdata=list(zip(date_strs, theta_strs)),
        hovertemplate="Date: %{customdata[0]}<br>Theta: %{customdata[1]}/day<extra></extra>",
    ),
    row=2, col=1,
)

fig.update_xaxes(title_text="Date", row=2, col=1, tickformat="%d-%m-%Y")
fig.update_xaxes(tickformat="%d-%m-%Y", row=1, col=1)
fig.update_yaxes(title_text="Option Price ($)", row=1, col=1)
fig.update_yaxes(title_text="Theta ($/day)", row=2, col=1)

fig.update_layout(
    height=700,
    showlegend=False,
    hovermode="x unified",
    spikedistance=-1,
)
fig.update_xaxes(
    showspikes=True,
    spikemode="across",
    spikethickness=1,
    spikedash="dot",
    spikecolor="grey",
)

st.plotly_chart(fig, use_container_width=True)

# --- Date slider and summary stats ---
st.divider()

selected_date = st.select_slider(
    "Select date",
    options=dates,
    value=dates[0],
    format_func=lambda d: d.strftime("%d-%m-%Y"),
)

idx = dates.index(selected_date)
selected_dte = dte - int(days_elapsed[idx])
moneyness = "ITM" if (spot > strike and option_type == "call") or (spot < strike and option_type == "put") else "OTM"
if abs(spot - strike) / spot < 0.02:
    moneyness = "ATM"

st.markdown(f"### At {selected_date.strftime('%d-%m-%Y')}")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Option Price", f"${prices[idx]:.4f}")
c2.metric("Theta", f"${thetas[idx]:.4f}/day")
c3.metric("Days to Expiry", selected_dte)
c4.metric("Moneyness", moneyness)

# --- Price sensitivity chart ---
st.divider()
st.subheader("Option Price vs. Stock Price")

T_selected = selected_dte / 365.0
expected_move = spot * iv * np.sqrt(T_selected) if T_selected > 0 else spot * iv * np.sqrt(dte / 365.0)
default_low = max(spot - 2 * expected_move, 0.01)
default_high = spot + 2 * expected_move

price_range = st.slider(
    "Stock price range",
    min_value=0.01,
    max_value=round(spot * 5, 2),
    value=(round(default_low, 2), round(default_high, 2)),
    step=0.01,
    format="$%.2f",
)

stock_prices = np.linspace(price_range[0], price_range[1], 200)
option_prices_at_date = np.array([
    black_scholes_price(s, strike, T_selected, risk_free, iv, option_type)
    for s in stock_prices
])

if bs_price_now > 0 and anchor_price > 0:
    option_prices_at_date = option_prices_at_date * scale

price_fig = go.Figure()
price_fig.add_trace(
    go.Scatter(
        x=stock_prices,
        y=option_prices_at_date,
        mode="lines",
        line=dict(color="#2196F3", width=2),
        customdata=list(zip(
            [f"${s:.2f}" for s in stock_prices],
            [f"${p:.4f}" for p in option_prices_at_date],
        )),
        hovertemplate="Stock Price: %{customdata[0]}<br>Option Price: %{customdata[1]}<extra></extra>",
    )
)

price_fig.add_vline(x=spot, line_dash="dot", line_color="grey", annotation_text="Spot")
price_fig.add_vline(x=strike, line_dash="dot", line_color="orange", annotation_text="Strike")

price_fig.update_layout(
    xaxis_title="Stock Price ($)",
    yaxis_title="Option Price ($)",
    height=450,
    hovermode="x unified",
    title=f"Option price at {selected_date.strftime('%d-%m-%Y')} ({selected_dte} DTE)",
)

st.plotly_chart(price_fig, use_container_width=True)

# --- Price lookup ---
col_input, col_result = st.columns(2)
with col_input:
    lookup_price = st.number_input("Spot Price", min_value=0.01, value=round(spot, 2), step=0.01, format="%.2f")
with col_result:
    lookup_option = black_scholes_price(lookup_price, strike, T_selected, risk_free, iv, option_type)
    if bs_price_now > 0 and anchor_price > 0:
        lookup_option *= scale
    st.metric("Option Value", f"${lookup_option:.4f}")

# --- Profit target chart ---
st.divider()
st.subheader("Stock Price for Target Profit")

profit_multiplier = st.number_input(
    "Profit multiplier (n)",
    min_value=0.01,
    value=1.50,
    step=0.01,
    format="%.2f",
    help="1.50 = 50% profit, 2.00 = 100% profit, etc.",
)

target_option_price = profit_multiplier * anchor_price

# For each date, solve for the stock price that produces the target option price
# Use unscaled BS target if we're using mid-price scaling
if bs_price_now > 0 and anchor_price > 0:
    bs_target = target_option_price / scale
else:
    bs_target = target_option_price

profit_dates = []
profit_stock_prices = []
for i, d in enumerate(dates):
    T_rem = (dte - int(days_elapsed[i])) / 365.0
    result = stock_price_for_target(bs_target, strike, T_rem, risk_free, iv, option_type)
    if result is not None:
        profit_dates.append(d)
        profit_stock_prices.append(result)

if profit_dates:
    profit_date_strs = [d.strftime("%d-%m-%Y") for d in profit_dates]
    profit_price_strs = [f"${p:.2f}" for p in profit_stock_prices]

    profit_fig = go.Figure()
    profit_fig.add_trace(
        go.Scatter(
            x=profit_dates,
            y=profit_stock_prices,
            mode="lines",
            line=dict(color="#4CAF50", width=2),
            customdata=list(zip(profit_date_strs, profit_price_strs)),
            hovertemplate="Date: %{customdata[0]}<br>Required Stock Price: %{customdata[1]}<extra></extra>",
        )
    )

    profit_fig.add_hline(y=spot, line_dash="dot", line_color="grey", annotation_text="Current Spot")
    profit_fig.add_hline(y=strike, line_dash="dot", line_color="orange", annotation_text="Strike")

    profit_fig.update_layout(
        xaxis_title="Date",
        yaxis_title="Required Stock Price ($)",
        height=450,
        hovermode="x unified",
        xaxis_tickformat="%d-%m-%Y",
        title=f"Stock price needed for {(profit_multiplier - 1) * 100:.0f}% profit (option target: ${target_option_price:.4f})",
    )

    st.plotly_chart(profit_fig, use_container_width=True)
else:
    st.warning("No solution found — the target profit may be unreachable for this contract.")
