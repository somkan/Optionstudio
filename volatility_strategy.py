import requests
from datetime import datetime, timedelta
import math
#from scipy.stats import norm


def calculate_greeks(spot_price, strike_price, time_to_expiry, volatility, risk_free_rate, option_type):
    # (Keep the same calculate_greeks implementation from your original code)
    print(spot_price, strike_price)
    d1 = (math.log(spot_price / strike_price) + (risk_free_rate + 0.5 * volatility ** 2) * time_to_expiry) / (
                volatility * math.sqrt(time_to_expiry))
    d2 = d1 - volatility * math.sqrt(time_to_expiry)

    if option_type == 'CE':
        delta = norm.cdf(d1)
        gamma = norm.pdf(d1) / (spot_price * volatility * math.sqrt(time_to_expiry))
        vega = spot_price * norm.pdf(d1) * math.sqrt(time_to_expiry) / 100
        theta = (-spot_price * norm.pdf(d1) * volatility / (
                    2 * math.sqrt(time_to_expiry)) - risk_free_rate * strike_price * math.exp(
            -risk_free_rate * time_to_expiry) * norm.cdf(d2)) / 365
    else:
        delta = -norm.cdf(-d1)
        gamma = norm.pdf(d1) / (spot_price * volatility * math.sqrt(time_to_expiry))
        vega = spot_price * norm.pdf(d1) * math.sqrt(time_to_expiry) / 100
        theta = (-spot_price * norm.pdf(d1) * volatility / (
                    2 * math.sqrt(time_to_expiry)) + risk_free_rate * strike_price * math.exp(
            -risk_free_rate * time_to_expiry) * norm.cdf(-d2)) / 365

    return {
        'delta': delta,
        'gamma': gamma,
        'vega': vega,
        'theta': theta
    }

def fetch_options_chain(symbol):
    # (Keep the same fetch_options_chain implementation from your original code)
    url = f"https://www.nseindia.com/api/option-chain-indices?symbol={symbol.upper()}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 Edg/123.0.0.0",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.nseindia.com/get-quotes/derivatives",
    }
    session = requests.Session()
    session.get("https://www.nseindia.com", headers=headers)  # Generate cookies
    response = session.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Failed to fetch options chain data. Status code: {response.status_code}")
        return None

def fetch_historical_data(symbol, from_date, to_date):
    # (Keep the same fetch_historical_data implementation from your original code)
    api_url = "https://www.nseindia.com/api/historical/indicesHistory"
    params = {
        "indexType": symbol.upper(),
        "from": from_date,
        "to": to_date
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 Edg/123.0.0.0",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.nseindia.com/get-quotes/derivatives",
    }
    session = requests.Session()
    session.get("https://www.nseindia.com", headers=headers)  # Generate cookies
    response = session.get(api_url, params=params, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Failed to fetch historical data. Status code: {response.status_code}")
        return None

def calculate_volatility_bands(historical_data, days_to_expiry):
    # (Keep the same calculate_volatility_bands implementation from your original code)
    records = historical_data['data']['indexCloseOnlineRecords']
    close_prices = [float(record['EOD_CLOSE_INDEX_VAL']) for record in records]
    log_returns = [math.log(close_prices[i] / close_prices[i - 1]) for i in range(1, len(close_prices))]

    # Calculate mean daily return and daily volatility
    mean_daily_return = sum(log_returns) / len(log_returns)
    daily_volatility = math.sqrt(sum((x - mean_daily_return) ** 2 for x in log_returns) / len(log_returns))

    # Calculate current day volatility
    current_day_volatility = (daily_volatility / math.sqrt(days_to_expiry)) * math.sqrt(252)

    # Calculate volatility bands
    sd_plus_2 = mean_daily_return + 2 * current_day_volatility
    sd_plus_1 = mean_daily_return + 1 * current_day_volatility
    mean = mean_daily_return
    sd_minus_1 = mean_daily_return - 1 * current_day_volatility
    sd_minus_2 = mean_daily_return - 2 * current_day_volatility
    max_volatility = mean_daily_return + 3 * current_day_volatility  # Max band (SD+3)
    min_volatility = mean_daily_return - 3 * current_day_volatility  # Min band (SD-3)

    return {
        'sd_plus_2': sd_plus_2,
        'sd_plus_1': sd_plus_1,
        'mean': mean,
        'sd_minus_1': sd_minus_1,
        'sd_minus_2': sd_minus_2,
        'max': max_volatility,
        'min': min_volatility,
        'current_day_volatility': current_day_volatility
    }

def run_volatility_analysis():
    symbol = "NIFTY"
    symbol1 = "NIFTY 50" if symbol == "NIFTY" else symbol

    # Date calculations
    to_date = datetime.now().strftime("%d-%m-%Y")
    from_date = (datetime.now() - timedelta(days=365)).strftime("%d-%m-%Y")

    # Fetch data
    historical_data = fetch_historical_data(symbol1, from_date, to_date)
    options_data = fetch_options_chain(symbol)

    # (Keep the same processing logic from your original '/get_data' route)

    return {
        'expiry_dates': processed_expiry_dates,
        'volatility_bands': volatility_bands,
        'spot_price': spot_price,
        'strike_data': valid_strikes
    }
