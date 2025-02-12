import requests
from datetime import datetime
import math  # Import the math module for exponential calculation
from fyers_apiv3 import fyersModel
import os
import time
import random
from datetime import datetime, timedelta
import math
import requests
import json

global fyers
user = "XD01606"
try:
    api = json.loads(open('api_key.json', 'r').read())
    api_key = api["API_KEY"]
except Exception as e:
    api_key = os.getenv("API_KEY")  ## for Production move
    pass


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
    #token_data = json.loads(response.text)
    token=token_data['document']['access_token']
    return token

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
    #print(response.json())
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

        # Fetch futures data from your data source (e.g., Fyers API or NSE)
        # Example using Fyers API (replace with your actual API call)
        data = {
            "symbols": f"NSE:{futures_symbol}"
        }
        response = fyers.quotes(data=data)  # Replace with your API call
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
        # Fetch options chain data
        options_data = fetch_options_chain(symbol)
        if not options_data:
            return {"error": "Failed to fetch options chain data."}

        # Extract expiry dates
        expiry_dates = options_data['records']['expiryDates']
        today = datetime.now()
        expiry_days = {expiry: (datetime.strptime(expiry, "%d-%b-%Y") - today).days + 1 for expiry in expiry_dates}
        sorted_expiry_dates = sorted(expiry_dates, key=lambda x: expiry_days[x])

        # List to store all arbitrage opportunities
        arbitrage_opportunities = []

        # Iterate through each expiry and strike price
        for expiry in sorted_expiry_dates:
            # Fetch futures price for this expiry
#            futures_price = fetch_futures_price(symbol, expiry)
 #           if not futures_price:
 #               continue  # Skip this expiry if futures price is not available

            filtered_data = [record for record in options_data['records']['data'] if record['expiryDate'] == expiry]
            for record in filtered_data:
                strike = record['strikePrice']
                if 'CE' in record and 'PE' in record:
                    call_price = record['CE'].get('bidPrice', 0)
                    put_price = record['PE'].get('askPrice', 0)
                    futures_price = options_data['records']['underlyingValue']
                    risk_free_rate = 0.05  # Assume 5% risk-free rate
                    time_to_expiry = expiry_days[expiry]

                    # Calculate theoretical put price using Put-Call Parity
                    discount_factor = math.exp(-risk_free_rate * (time_to_expiry / 365))
                    theoretical_put_price = call_price - futures_price + (strike * discount_factor)

                    # Check for arbitrage opportunity
                    if put_price < theoretical_put_price:
                        profit = theoretical_put_price - put_price
                        arbitrage_opportunities.append({
                            "expiry": expiry,
                            "strike": strike,
                            "futures_price": futures_price,
                            "call_price": call_price,
                            "put_price": put_price,
                            "theoretical_put_price": theoretical_put_price,
                            "profit": profit
                        })

        # Return all opportunities (not just top 3)
        return arbitrage_opportunities
    except Exception as e:
        return {"error": f"Error checking arbitrage: {str(e)}"}

def check_arbitrage_opportunity1(symbol):
    """
        Check for arbitrage opportunities using Underlying price for the respective symbol.
        """
    try:
        options_data = fetch_options_chain(symbol)
        if not options_data:
            return {"error": "Failed to fetch options chain data."}

        expiry_dates = options_data['records']['expiryDates']
        today = datetime.now()
        expiry_days = {expiry: (datetime.strptime(expiry, "%d-%b-%Y") - today).days + 1 for expiry in expiry_dates}
        sorted_expiry_dates = sorted(expiry_dates, key=lambda x: expiry_days[x])

        arbitrage_opportunities = []

        for expiry in sorted_expiry_dates:
            filtered_data = [rec for rec in options_data['records']['data'] if rec['expiryDate'] == expiry]
            for record in filtered_data:
                strike = record['strikePrice']
                if 'CE' in record and 'PE' in record:
                    call_price = record['CE'].get('lastPrice', 0)
                    put_price = record['PE'].get('lastPrice', 0)
                    underlying_price = options_data['records']['underlyingValue']
                    risk_free_rate = 0.05
                    time_to_expiry = expiry_days[expiry]

                    discount_factor = math.exp(-risk_free_rate * (time_to_expiry / 365))
                    theoretical_put_price = call_price - underlying_price + (strike * discount_factor)

                    if put_price < theoretical_put_price:
                        profit = theoretical_put_price - put_price
                        arbitrage_opportunities.append({
                            "expiry": expiry,
                            "strike": strike,
                            "underlying_price": underlying_price,
                            "call_price": call_price,
                            "put_price": put_price,
                            "theoretical_put_price": theoretical_put_price,
                            "profit": profit * 75
                        })

        # Return top 3 opportunities sorted by profit
        sorted_opportunities = sorted(arbitrage_opportunities, key=lambda x: x['profit'], reverse=True)
        return sorted_opportunities
    except Exception as e:
        return {"error": f"Error checking arbitrage: {str(e)}"}