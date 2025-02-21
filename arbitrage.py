import requests
from datetime import datetime
import math
from fyers_apiv3 import fyersModel
import os
import time
import random
from datetime import datetime, timedelta
import math
import requests
import json

global fyers
user = "XS06414"
try:
    api = json.loads(open('api_key.json', 'r').read())
    api_key = api["API_KEY"]
except Exception as e:
    api_key = os.getenv("API_KEY")  ## for Production move
    pass
# Add this at the top of your `arbitrage.py` file
LOT_SIZE_MAPPING = {
    "NIFTY": 75,       # NIFTY lot size is 50
    "BANKNIFTY": 30,   # BANKNIFTY lot size is 25
    "FINNIFTY": 40,    # FINNIFTY lot size is 40
    # Add more symbols and their lot sizes as needed
}
global fyers
find = "https://ap-south-1.aws.data.mongodb-api.com/app/data-kpqgeul/endpoint/data/v1/action/findOne"
insert = "https://ap-south-1.aws.data.mongodb-api.com/app/data-kpqgeul/endpoint/data/v1/action/insertOne"
insert_many="https://ap-south-1.aws.data.mongodb-api.com/app/data-kpqgeul/endpoint/data/v1/action/insertMany"
update = "https://ap-south-1.aws.data.mongodb-api.com/app/data-kpqgeul/endpoint/data/v1/action/updateOne"
update_many = "https://ap-south-1.aws.data.mongodb-api.com/app/data-kpqgeul/endpoint/data/v1/action/updateMany"
headers = {
    'Content-Type': 'application/json',
    'Access-Control-Request-Headers': '*',
    'api-key': api_key,
}


def read_auth(user):
    payload = json.dumps({
        "collection": "Auth_Data",
        "database": "myFirstDatabase",
        "dataSource": "Cluster0",
        "filter":{"userid":user},
        "projection": {
            "userid": 1,
            "app_id": 1,
            "app_id_type":1
        }
    })

    response = requests.request("POST", find, headers=headers, data=payload)
    token_data = response.json()
    print(token_data)
    client_id=token_data['document']['app_id']

    return client_id

def read_file(user):
    payload = json.dumps({
        "collection": "access_token",
        "database": "myFirstDatabase",
        "dataSource": "Cluster0",
        "filter":{"userid":user},
        "projection": {
            "userid": 1,
            "access_token": 1
        }
    })
    response = requests.request("POST", find, headers=headers, data=payload)
    token_data = response.json()
    token=token_data['document']['access_token']
    return token

def norm_cdf(x):
    """
    Calculate the cumulative distribution function (CDF) of the standard normal distribution.
    Uses the Abramowitz and Stegun approximation.
    """
    # Constants
    a1 = 0.254829592
    a2 = -0.284496736
    a3 = 1.421413741
    a4 = -1.453152027
    a5 = 1.061405429
    p = 0.3275911

    # Save the sign of x
    sign = 1 if x > 0 else -1
    x = abs(x) / math.sqrt(2.0)

    # Abramowitz and Stegun approximation
    t = 1.0 / (1.0 + p * x)
    y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * math.exp(-x * x)

    return 0.5 * (1.0 + sign * y)
def calculate_pop(futures_price, strike, implied_volatility, time_to_expiry, risk_free_rate=0.05):
    """
    Calculate the Probability of Profit (POP) for a put option using the Black-Scholes model.
    """
    try:
        # Calculate d1 and d2 for the Black-Scholes formula
        d1 = (math.log(futures_price / strike) + (risk_free_rate + (implied_volatility ** 2) / 2) * time_to_expiry) / (implied_volatility * math.sqrt(time_to_expiry))
        d2 = d1 - implied_volatility * math.sqrt(time_to_expiry)

        # Calculate the probability of the underlying price being below the strike (POP for put)
        pop = norm_cdf(-d2)  # Use custom norm_cdf function
        return pop
    except Exception as e:
        print(f"Error calculating POP: {e}")
        return 0
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

def fetch_futures_price(symbol, expiry):
    """
    Fetch the futures price for the given symbol and expiry.
    """
    global fyers
    access_token = read_file(user)
    client_id = read_auth(user)

    fyers = fyersModel.FyersModel(client_id=client_id, token=access_token, log_path=os.getcwd())

    try:
        # Construct the futures symbol (e.g., NIFTY24MAYFUT)
        expiry_date = datetime.strptime(expiry, "%d-%b-%Y")
        year_last_two = expiry_date.strftime("%y")
        month = expiry_date.strftime("%b").upper()
        futures_symbol = f"{symbol}{year_last_two}{month}FUT"

        # Fetch futures data from Fyers API
        data = {
            "symbols": f"NSE:{futures_symbol}"
        }
        response = fyers.quotes(data=data)
        if response and 'd' in response and len(response['d']) > 0:
            futures_price = response['d'][0]['v']['ask']  # Last traded price
            return futures_price
        else:
            print(f"Failed to fetch futures price for {futures_symbol}")
            return None
    except Exception as e:
        print(f"Error fetching futures price: {e}")
        return None

def check_arbitrage_opportunity(symbol):
    try:
        # Get lot size for the symbol
        lot_size = LOT_SIZE_MAPPING.get(symbol.upper(), 1)  # Default to 1 if symbol not found
        print(f"Lot size for {symbol}: {lot_size}")

        # Fetch options chain data
        options_data = fetch_options_chain(symbol)
        if not options_data:
            return {"error": "Failed to fetch options chain data."}

        # Extract expiry dates
        expiry_dates = options_data['records']['expiryDates']
        today = datetime.now()
        expiry_days = {expiry: (datetime.strptime(expiry, "%d-%b-%Y") - today).days + 1 for expiry in expiry_dates}

        # Filter to get only the last expiry for each month
        monthly_expiries = {}
        for expiry in expiry_dates:
            expiry_date = datetime.strptime(expiry, "%d-%b-%Y")
            month_key = expiry_date.strftime("%Y-%m")
            if month_key not in monthly_expiries or expiry_date > datetime.strptime(monthly_expiries[month_key], "%d-%b-%Y"):
                monthly_expiries[month_key] = expiry

        sorted_expiry_dates = sorted(monthly_expiries.values(), key=lambda x: expiry_days[x])

        # List to store all arbitrage opportunities
        arbitrage_opportunities = []

        # Iterate through each expiry and strike price
        for expiry in sorted_expiry_dates:
            # Fetch futures price for this expiry
            futures_price = fetch_futures_price(symbol, expiry)
            if not futures_price:
                continue  # Skip this expiry if futures price is not available

            filtered_data = [record for record in options_data['records']['data'] if record['expiryDate'] == expiry]

            for record in filtered_data:
                strike = record['strikePrice']
                if 'CE' in record and 'PE' in record:
                    # Fetch CE bid price and PE ask price from Fyers
                    ce_bid_price = record['CE'].get('bidPrice', record['CE'].get('lastPrice', 0))
                    pe_ask_price = record['PE'].get('askPrice', record['PE'].get('lastPrice', 0))
                    implied_volatility_ce = record['CE'].get('impliedVolatility', 0)
                    implied_volatility_pe = record['PE'].get('impliedVolatility', 0)

                    risk_free_rate = 0.05  # Assume 5% risk-free rate
                    time_to_expiry = expiry_days[expiry] / 365  # Convert days to years

                    # Calculate theoretical put price using Put-Call Parity
                    discount_factor = math.exp(-risk_free_rate * time_to_expiry)
                    theoretical_put_price = ce_bid_price - futures_price + (strike * discount_factor)

                    # Check for arbitrage opportunity
                    if pe_ask_price < theoretical_put_price:
                        profit = theoretical_put_price - pe_ask_price
                        total_profit = profit * lot_size
                        max_profit = profit
                        max_loss = 0

                        # Calculate Probability of Profit (POP)
                        pop = calculate_pop(futures_price, strike, implied_volatility_pe, time_to_expiry, risk_free_rate)

                        ce_payoff = max(futures_price - strike, 0)
                        pe_payoff = max(strike - futures_price, 0)
                        print(f'Expiry:{expiry} | Underlying Price:{futures_price} | Strike:{strike} | CE Payoff:{ce_payoff} | PE Payoff:{pe_payoff} | POP:{pop:.2f}')

                        arbitrage_opportunities.append({
                            "expiry": expiry,
                            "strike": strike,
                            "futures_price": futures_price,
                            "ce_bid_price": ce_bid_price,
                            "pe_ask_price": pe_ask_price,
                            "implied_volatility_ce": implied_volatility_ce,
                            "implied_volatility_pe": implied_volatility_pe,
                            "profit": total_profit,
                            "pop": pop  # Add POP to the result
                        })


        # Return all opportunities
        return arbitrage_opportunities
    except Exception as e:
        return {"error": f"Error checking arbitrage: {str(e)}"}