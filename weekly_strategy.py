import requests
from datetime import datetime, timedelta
import math

# Function to fetch options chain data
def fetch_options_chain(symbol):
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

# Function to fetch historical data
def fetch_historical_data(symbol, from_date, to_date):
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

# Function to calculate volatility bands
def calculate_volatility_bands(historical_data, days_to_expiry):
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

# Main script
if __name__ == "__main__":
    symbol = "NIFTY"  # Change this to the desired symbol
    if symbol == "NIFTY":
        symbol1 = "NIFTY 50"

    # Define date range for historical data
    to_date = datetime.now().strftime("%d-%m-%Y")
    from_date = (datetime.now() - timedelta(days=365)).strftime("%d-%m-%Y")  # 1 year historical data

    # Fetch historical data
    historical_data = fetch_historical_data(symbol1, from_date, to_date)
    if not historical_data:
        print("No historical data fetched. Exiting.")
        exit()

    # Fetch options chain data
    options_data = fetch_options_chain(symbol)
    if not options_data:
        print("No options data fetched. Exiting.")
        exit()

    # Extract expiry dates
    if 'records' not in options_data or 'expiryDates' not in options_data['records']:
        print("Error: Expiry dates not found in options data.")
        exit()
    expiry_dates = options_data['records']['expiryDates']

    # Calculate days to expiry for each expiry date
    today = datetime.now()
    print(today)
    expiry_days = {}
    for expiry in expiry_dates:
        expiry_date = datetime.strptime(expiry, "%d-%b-%Y")
        days_to_expiry = (expiry_date - today).days+1
        expiry_days[expiry] = days_to_expiry

    # Calculate volatility bands for each expiry
    for expiry, days_to_expiry in expiry_days.items():
        print(f"\nExpiry Date: {expiry}, Days to Expiry: {days_to_expiry}")
        volatility_bands = calculate_volatility_bands(historical_data, days_to_expiry)

        print("Volatility Bands:")
        for key, value in volatility_bands.items():
            print(f"{key}: {value:.4f}")

        # Filter options data for the current expiry
        filtered_data = [record for record in options_data['records']['data'] if record['expiryDate'] == expiry]

        results = []
        for record in filtered_data:
            if 'CE' in record and record['CE']:
                ce_iv = record['CE']['impliedVolatility']
                if ce_iv / 100 > volatility_bands['sd_plus_2']:
                    results.append({
                        'expiry': expiry,
                        'strike': record['strikePrice'],
                        'type': 'CE',
                        'iv': ce_iv
                    })
            if 'PE' in record and record['PE']:
                pe_iv = record['PE']['impliedVolatility']
                if pe_iv / 100 > volatility_bands['sd_plus_2']:
                    results.append({
                        'expiry': expiry,
                        'strike': record['strikePrice'],
                        'type': 'PE',
                        'iv': pe_iv
                    })

        # Print results for the current expiry
        print(f"Options with Implied Volatility above SD+2 ({volatility_bands['sd_plus_2'] * 100:.2f}%):")
        for result in results:
            print(f"Expiry: {result['expiry']}, Strike: {result['strike']}, Type: {result['type']}, IV: {result['iv']}%")

        results = []
        for record in filtered_data:
            if 'CE' in record and record['CE']:
                ce_iv = record['CE']['impliedVolatility']
                if ce_iv / 100 < volatility_bands['sd_minus_2']:
                    results.append({
                        'expiry': expiry,
                        'strike': record['strikePrice'],
                        'type': 'CE',
                        'iv': ce_iv
                    })
            if 'PE' in record and record['PE']:
                pe_iv = record['PE']['impliedVolatility']
                if pe_iv / 100 < volatility_bands['sd_minus_2']:
                    results.append({
                        'expiry': expiry,
                        'strike': record['strikePrice'],
                        'type': 'PE',
                        'iv': pe_iv
                    })

        # Print results for the current expiry
        print(f"Options with Implied Volatility below SD-2 ({volatility_bands['sd_minus_2'] * 100:.2f}%):")
        for result in results:
            print(
                f"Expiry: {result['expiry']}, Strike: {result['strike']}, Type: {result['type']}, IV: {result['iv']}%")