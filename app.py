from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

import numpy as np

from data import (
    get_spot_price, get_options_chain, get_chain_for_expiry,
    days_until, market_hours_remaining, now_et, ET, MARKET_CLOSE,
)
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
is_0dte = dte == 0

# For 0DTE, check if market hours remain
if is_0dte:
    intraday_times = market_hours_remaining(expiry)
    if not intraday_times:
        st.warning("This contract has expired (market is closed).")
        st.stop()

# Compute T for IV fallback — use hours for 0DTE, days otherwise
if is_0dte:
    close_dt = datetime.combine(now_et().date(), MARKET_CLOSE, tzinfo=ET)
    hours_left = (close_dt - now_et()).total_seconds() / 3600
    T_now = max(hours_left / 8766, 1e-6)  # hours to years
else:
    T_now = dte / 365.0

market_iv = row.get("impliedVolatility", 0.0) or 0.0
if market_iv < 0.01:
    last_price = row.get("lastPrice", 0.0) or 0.0
    computed_iv = implied_vol(last_price, spot, strike, T_now, 0.045, option_type)
    market_iv = computed_iv if computed_iv is not None else 0.3

st.divider()
col_iv, col_r = st.columns(2)

with col_iv:
    iv = st.slider("Implied Volatility", 0.05, 2.0, float(market_iv), 0.01, format="%.2f")

with col_r:
    risk_free = st.slider("Risk-Free Rate", 0.0, 0.10, 0.045, 0.005, format="%.3f")

# --- Compute decay curve ---
# Build x-axis labels and T values depending on daily vs intraday mode
if is_0dte:
    close_dt = datetime.combine(now_et().date(), MARKET_CLOSE, tzinfo=ET)
    # T values in years for each intraday time point
    T_values = np.array([(close_dt - t).total_seconds() / (3600 * 8766) for t in intraday_times])
    T_values = np.maximum(T_values, 1e-6)

    prices = np.array([black_scholes_price(spot, strike, t, risk_free, iv, option_type) for t in T_values])
    # Theta per hour (annual theta / 8766)
    from pricing import theta as bs_theta
    thetas = np.array([bs_theta(spot, strike, t, risk_free, iv, option_type) * 365 / 8766 for t in T_values])

    x_axis = intraday_times
    x_labels = [t.strftime("%H:%M ET") for t in intraday_times]
    x_axis_title = "Time (ET)"
    x_tickformat = "%H:%M"
    theta_unit = "$/hr"
    time_label_header = "Time"
    slider_format = lambda t: t.strftime("%H:%M ET")
else:
    days_remaining, prices, thetas = decay_curve(spot, strike, dte, risk_free, iv, option_type)
    days_elapsed = dte - days_remaining
    today = now_et().date()
    x_axis = [today + timedelta(days=int(d)) for d in days_elapsed]
    x_labels = [d.strftime("%d-%m-%Y") for d in x_axis]
    x_axis_title = "Date"
    x_tickformat = "%d-%m-%Y"
    theta_unit = "$/day"
    time_label_header = "Date"
    slider_format = lambda d: d.strftime("%d-%m-%Y")

# Anchor to market price
bs_price_now = black_scholes_price(spot, strike, T_now, risk_free, iv, option_type)
if bs_price_now > 0 and anchor_price > 0:
    scale = anchor_price / bs_price_now
    prices = prices * scale
    thetas = thetas * scale
else:
    scale = 1.0

price_strs = [f"${p:.4f}" for p in prices]
theta_strs = [f"${t:.4f}" for t in thetas]

# --- Charts ---
fig = make_subplots(
    rows=2, cols=1,
    shared_xaxes=True,
    vertical_spacing=0.08,
    subplot_titles=(
        "Theoretical Price Decay (0DTE)" if is_0dte else "Theoretical Price Decay",
        "Hourly Theta" if is_0dte else "Daily Theta",
    ),
)

fig.add_trace(
    go.Scatter(
        x=x_axis, y=prices,
        mode="lines",
        name="Price",
        line=dict(color="#2196F3", width=2),
        customdata=list(zip(x_labels, price_strs)),
        hovertemplate=f"{time_label_header}: %{{customdata[0]}}<br>Option Price: %{{customdata[1]}}<extra></extra>",
    ),
    row=1, col=1,
)

fig.add_trace(
    go.Scatter(
        x=x_axis, y=thetas,
        mode="lines",
        name="Theta",
        line=dict(color="#FF5722", width=2),
        customdata=list(zip(x_labels, theta_strs)),
        hovertemplate=f"{time_label_header}: %{{customdata[0]}}<br>Theta: %{{customdata[1]}}/{theta_unit.split('/')[1]}<extra></extra>",
    ),
    row=2, col=1,
)

fig.update_xaxes(title_text=x_axis_title, row=2, col=1, tickformat=x_tickformat)
fig.update_xaxes(tickformat=x_tickformat, row=1, col=1)
fig.update_yaxes(title_text="Option Price ($)", row=1, col=1)
fig.update_yaxes(title_text=f"Theta ({theta_unit})", row=2, col=1)

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

# --- Slider and summary stats ---
st.divider()

selected_point = st.select_slider(
    "Select time" if is_0dte else "Select date",
    options=x_axis,
    value=x_axis[0],
    format_func=slider_format,
)

idx = x_axis.index(selected_point)

if is_0dte:
    close_dt = datetime.combine(now_et().date(), MARKET_CLOSE, tzinfo=ET)
    T_selected = max((close_dt - selected_point).total_seconds() / (3600 * 8766), 1e-6)
    time_remaining_str = f"{(close_dt - selected_point).total_seconds() / 3600:.1f} hrs"
else:
    selected_dte = dte - int(days_elapsed[idx])
    T_selected = selected_dte / 365.0
    time_remaining_str = f"{selected_dte} days"

moneyness = "ITM" if (spot > strike and option_type == "call") or (spot < strike and option_type == "put") else "OTM"
if abs(spot - strike) / spot < 0.02:
    moneyness = "ATM"

header_text = f"At {slider_format(selected_point)}"
st.markdown(f"### {header_text}")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Option Price", f"${prices[idx]:.4f}")
c2.metric("Theta", f"${thetas[idx]:.4f}/{theta_unit.split('/')[1]}")
c3.metric("Time to Expiry", time_remaining_str)
c4.metric("Moneyness", moneyness)

# --- Price sensitivity chart ---
st.divider()
st.subheader("Option Price vs. Stock Price")

expected_move = spot * iv * np.sqrt(T_selected) if T_selected > 0 else spot * iv * np.sqrt(T_now)
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

sensitivity_title = (
    f"Option price at {slider_format(selected_point)} ({time_remaining_str} to expiry)"
    if is_0dte else
    f"Option price at {slider_format(selected_point)} ({selected_dte} DTE)"
)
price_fig.update_layout(
    xaxis_title="Stock Price ($)",
    yaxis_title="Option Price ($)",
    height=450,
    hovermode="x unified",
    title=sensitivity_title,
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

if bs_price_now > 0 and anchor_price > 0:
    bs_target = target_option_price / scale
else:
    bs_target = target_option_price

profit_x = []
profit_stock_prices = []

if is_0dte:
    close_dt = datetime.combine(now_et().date(), MARKET_CLOSE, tzinfo=ET)
    for i, t_point in enumerate(intraday_times):
        T_rem = max((close_dt - t_point).total_seconds() / (3600 * 8766), 1e-6)
        result = stock_price_for_target(bs_target, strike, T_rem, risk_free, iv, option_type)
        if result is not None:
            profit_x.append(t_point)
            profit_stock_prices.append(result)
else:
    for i, d in enumerate(x_axis):
        T_rem = (dte - int(days_elapsed[i])) / 365.0
        result = stock_price_for_target(bs_target, strike, T_rem, risk_free, iv, option_type)
        if result is not None:
            profit_x.append(d)
            profit_stock_prices.append(result)

if profit_x:
    if is_0dte:
        profit_labels = [t.strftime("%H:%M ET") for t in profit_x]
    else:
        profit_labels = [d.strftime("%d-%m-%Y") for d in profit_x]
    profit_price_strs = [f"${p:.2f}" for p in profit_stock_prices]

    profit_fig = go.Figure()
    profit_fig.add_trace(
        go.Scatter(
            x=profit_x,
            y=profit_stock_prices,
            mode="lines",
            line=dict(color="#4CAF50", width=2),
            customdata=list(zip(profit_labels, profit_price_strs)),
            hovertemplate=f"{time_label_header}: %{{customdata[0]}}<br>Required Stock Price: %{{customdata[1]}}<extra></extra>",
        )
    )

    profit_fig.add_hline(y=spot, line_dash="dot", line_color="grey", annotation_text="Current Spot")
    profit_fig.add_hline(y=strike, line_dash="dot", line_color="orange", annotation_text="Strike")

    profit_fig.update_layout(
        xaxis_title=x_axis_title,
        yaxis_title="Required Stock Price ($)",
        height=450,
        hovermode="x unified",
        xaxis_tickformat=x_tickformat,
        title=f"Stock price needed for {(profit_multiplier - 1) * 100:.0f}% profit (option target: ${target_option_price:.4f})",
    )

    st.plotly_chart(profit_fig, use_container_width=True)
else:
    st.warning("No solution found — the target profit may be unreachable for this contract.")
