import numpy as np
from scipy.optimize import brentq
from scipy.stats import norm


def black_scholes_price(S, K, T, r, sigma, option_type="call"):
    """Compute Black-Scholes option price. T is in years."""
    if T <= 0:
        if option_type == "call":
            return max(S - K, 0.0)
        return max(K - S, 0.0)

    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)

    if option_type == "call":
        return S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
    return K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)


def theta(S, K, T, r, sigma, option_type="call"):
    """Daily theta (price change per calendar day)."""
    if T <= 0:
        return 0.0

    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)

    common = -(S * norm.pdf(d1) * sigma) / (2 * np.sqrt(T))

    if option_type == "call":
        annual_theta = common - r * K * np.exp(-r * T) * norm.cdf(d2)
    else:
        annual_theta = common + r * K * np.exp(-r * T) * norm.cdf(-d2)

    return annual_theta / 365


def implied_vol(price, S, K, T, r, option_type="call"):
    """Back-solve Black-Scholes for the implied volatility that produces `price`.

    Returns None if the solve fails (e.g. price is below intrinsic value).
    """
    if T <= 0 or price <= 0:
        return None

    def objective(sigma):
        return black_scholes_price(S, K, T, r, sigma, option_type) - price

    try:
        return brentq(objective, 0.001, 10.0)
    except ValueError:
        return None


def stock_price_for_target(target_price, K, T, r, sigma, option_type="call"):
    """Find the stock price that produces `target_price` for the option.

    Returns None if no solution exists (e.g. target is unreachable).
    """
    if target_price <= 0:
        return None

    def objective(S):
        return black_scholes_price(S, K, T, r, sigma, option_type) - target_price

    try:
        return brentq(objective, 0.01, K * 20)
    except ValueError:
        return None


def decay_curve(S, K, days_to_expiry, r, sigma, option_type="call"):
    """Return arrays of (days_remaining, price, daily_theta) from now to expiry."""
    days = np.arange(days_to_expiry, -1, -1)
    T_values = days / 365.0

    prices = np.array([black_scholes_price(S, K, t, r, sigma, option_type) for t in T_values])
    thetas = np.array([theta(S, K, t, r, sigma, option_type) for t in T_values])

    return days, prices, thetas
