from flask import Flask, jsonify, send_from_directory, request, render_template
from flask_cors import CORS
from fyers_apiv3 import fyersModel
import os
import time
import random
from datetime import datetime, timedelta
import math
import requests
from volatility_strategy import run_volatility_analysis  # Ensure this module exists
from arbitrage import check_arbitrage_opportunity
from login import read_file,read_auth
import json
api_key = os.getenv("API_KEY") ## for Production move

app = Flask(__name__)
CORS(app)  # Enable CORS
user = "XS06414"
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

def place_trade(user,option_strike,option_open):

    try:
        trade1 = fyers.place_order(
            data={
                "symbol": option_strike,
                "qty": 75,
                "type": 1,# Limit Order
                "side": -1,  # Sell side
                "productType": "INTRADAY",
                "limitPrice": option_open,
                "stopPrice": 0,
                "disclosedQty": 0,
                "validity": "DAY",
                "offlineOrder": False,  # True for AMO Order and False for Market Open
                "stopLoss": 0,
                "takeProfit": 0
            }
        )
        stat = trade1
        print(stat)

    except Exception as e:
        print("API error for ticker :", e)


@app.route('/trading-data', methods=['GET'])
def get_trading_data():
    global fyers
    access_token = read_file(user)
    client_id = read_auth(user)

    fyers = fyersModel.FyersModel(client_id=client_id, token=access_token, log_path=os.getcwd())
    symbol = request.args.get('symbol', 'NIFTY')  # Default symbol is 'NIFTY' if none is provided

    trading_data = {
        'previousClose': None,
        'currentOpen': None,
        'openPremium': None,
        'currentPremium': None,
        'highPremium':None,
        'optionType': None,
        'strikePrice': None,
        'position': None,
        'symbol':None
    }

    try:
        url = f'https://www.nseindia.com/api/option-chain-indices?symbol={symbol}'
        headers = {'User-Agent': 'Mozilla/5.0'}

        response = requests.get(url, headers=headers).json()
        print(response)
        #Step1: Extract Expiry and Spot price
        expiry = response['records']['expiryDates'][0]
        print(expiry)
        import datetime
        date_obj = datetime.datetime.strptime(expiry, "%d-%b-%Y")
        day = date_obj.strftime("%d")
        year_last_two = date_obj.strftime("%y")
        month = date_obj.strftime("%b").upper()

        spot_data = response['records']['data']
        spot_price = int(spot_data[0]['PE']['underlyingValue'])

        derivative_symbol = f"NSE:{symbol}{year_last_two}{month}FUT"
        data = {
            "symbols": derivative_symbol
        }
        response = fyers.quotes(data=data)
        print(response)
        biddata = response['d'][0]
        openprice = biddata['v']['open_price']
        prevClose = biddata['v']['prev_close_price']


        trading_data.update({
            'currentOpen': openprice,
            'previousClose': prevClose
        })

        # Step 2: Calculate strategy using futures data
        if trading_data['currentOpen'] and trading_data['previousClose']:
            difference = trading_data['currentOpen'] - trading_data['previousClose']
            position = 'CE' if difference < 0 else 'PE'

            # Calculate strike price (round to nearest 100)
            strike_base = trading_data['currentOpen']
            print(strike_base)
            #strike_base = spot_price
            strike_price = (math.floor(strike_base / 100) * 100)+100 if position == 'CE' \
                else (math.ceil(strike_base / 100) * 100)-100
            print(strike_price)
            trading_data.update({
                'optionType': position,
                'strikePrice': strike_price,
                'position': f'short {position}'
            })
        date_obj = datetime.datetime.strptime(expiry, "%d-%b-%Y")

        day = date_obj.strftime("%d")
        year_last_two = date_obj.strftime("%y")
        month_number = date_obj.strftime("%m").lstrip("0")

        def is_last_thursday(date):
            last_day = (date.replace(day=28) + datetime.timedelta(days=4)).replace(day=1) - datetime.timedelta(days=1)
            return date.weekday() == 3 and (last_day - date).days < 7

        # Determine if the expiry is the last Thursday of the month
        if is_last_thursday(date_obj) or symbol != "NIFTY":
            option_strike = f"NSE:{symbol}{year_last_two}{month}{strike_price}{position}"
        else:
            option_strike = f"NSE:{symbol}{year_last_two}{month_number}{day}{strike_price}{position}"

        print(option_strike)
        data = {
            "symbols": option_strike
        }
        response = fyers.quotes(data=data)
        #print(response)
        biddata = response['d'][0]
        option_open = biddata['v']['open_price']
        option_current = biddata['v']['lp']
        option_high = biddata['v']['high_price']
        trading_data['currentPremium'] = option_current
        trading_data['openPremium'] = option_open
        trading_data['symbol'] = option_strike
        trading_data['highPremium']=option_high
       # response = fyers.orderbook()
       # print(response)
        print (option_open)
        place_trade(user,option_strike,option_open)

    except requests.exceptions.RequestException as e:
        print(f"Request error: {e}")
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        print(f"General error: {e}")
        return jsonify({"error": str(e)}), 500
    print(trading_data)
    return jsonify(trading_data)

def get_analysis():
    """
    Generate market analysis, including arbitrage opportunities.
    """
    # Check for arbitrage opportunity
    #arbitrage_result = check_arbitrage_opportunity()

    # Include arbitrage results in the analysis
    analysis = {
        "market_condition": "Volatile",
        "recommended_strategy": "Iron Fly",
        "confidence_score": 85
 #       "arbitrage_opportunity": arbitrage_result.get("arbitrage_opportunity", False),
#   "arbitrage_details": arbitrage_result if arbitrage_result.get("arbitrage_opportunity") else None,
    }

    return analysis


# Mock data for running strategies
running_strategies = []


# Home page
@app.route('/')
def home():
    return send_from_directory('static', 'menu.html')


# API for analysis and recommendations
@app.route('/api/analysis', methods=['GET'])
def analysis():
    return jsonify(get_analysis())


# API to start a strategy
@app.route('/api/start_strategy', methods=['POST'])
def start_strategy():
    data = request.json
    strategy_name = data.get('strategy_name')

    if not strategy_name:
        return jsonify({"error": "Strategy name is required"}), 400

    strategy_id = f"strategy_{len(running_strategies) + 1}"

    # Add to running strategies
    running_strategies.append({
        "id": strategy_id,
        "name": strategy_name,
        "start_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "status": "Running",
        "pnl": 0,
    })

    # Handle different strategies
    if strategy_name == "Volatility Cone":
        try:
            # Execute and get analysis results
            result = execute_volatility_cone_strategy()
            return jsonify({
                "message": f"Strategy '{strategy_name}' started",
                "strategy_id": strategy_id,
                "analysis": result
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    elif strategy_name == "Conversion Arbitrage":
        try:
            # Execute and get analysis results
            result = execute_conversion_arbitrage_strategy()
            return jsonify({
                "message": f"Strategy '{strategy_name}' started",
                "strategy_id": strategy_id,
                "analysis": result
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    else:
        return jsonify({"message": f"Strategy '{strategy_name}' started", "strategy_id": strategy_id})


# Volatility analysis page
@app.route('/volatility')
def volatility():
    try:
        # Fetch volatility data or pass necessary context
        return render_template('voltas.html')
    except Exception as e:
        return str(e), 500


# Volatility analysis page
# Correct the route to handle both GET and POST requests
@app.route('/check_arbitrage', methods=['GET', 'POST'])
def handle_arbitrage():
    try:
        if request.method == 'GET':
            # Render the arbitrage.html template for GET requests
            return render_template("arbitrage.html")
        else:
            # Handle POST request for arbitrage checking
            data = request.get_json()
            symbol = data.get('symbol', 'NIFTY')
            result = check_arbitrage_opportunity(symbol)
            return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
# Weekly Expiry analysis page
@app.route('/weekly_expiry')
def weekly_expiry():
    try:
        # Fetch volatility data or pass necessary context
        return render_template('index_updated.html')
    except Exception as e:
        return str(e), 500


# API endpoint to get data
@app.route('/get_data')
def get_data():
    symbol = "NIFTY"  # Change this to the desired symbol
    if symbol == "NIFTY":
        symbol1 = "NIFTY 50"

    # Define date range for historical data
    to_date = datetime.now().strftime("%d-%m-%Y")
    from_date = (datetime.now() - timedelta(days=365)).strftime("%d-%m-%Y")  # 1 year historical data

    # Fetch historical data
    historical_data = fetch_historical_data(symbol1, from_date, to_date)
    if not historical_data:
        return jsonify({"error": "No historical data fetched."})

    # Fetch options chain data
    options_data = fetch_options_chain(symbol)
    if not options_data:
        return jsonify({"error": "No options data fetched."})

    # Extract expiry dates
    if 'records' not in options_data or 'expiryDates' not in options_data['records']:
        return jsonify({"error": "Expiry dates not found in options data."})
    expiry_dates = options_data['records']['expiryDates']

    # Calculate days to expiry for each expiry date
    today = datetime.now()
    expiry_days = {}
    for expiry in expiry_dates:
        expiry_date = datetime.strptime(expiry, "%d-%b-%Y")
        days_to_expiry = (expiry_date - today).days + 1
        expiry_days[expiry] = days_to_expiry

    # Sort expiry dates by days to expiry (nearest to farthest)
    sorted_expiry_dates = sorted(expiry_dates, key=lambda x: expiry_days[x])

    # Group options by expiry and strike price
    results = {}
    for expiry in sorted_expiry_dates:
        filtered_data = [record for record in options_data['records']['data'] if record['expiryDate'] == expiry]
        strike_data = {}

        for record in filtered_data:
            strike = record['strikePrice']
            if strike not in strike_data:
                strike_data[strike] = {'CE': None, 'PE': None}

            if 'CE' in record and record['CE']:
                strike_data[strike]['CE'] = {
                    'iv': record['CE']['impliedVolatility'],
                    'last_price': record['CE']['lastPrice'],
                  #  'greeks': calculate_greeks(
                  #      spot_price=options_data['records']['underlyingValue'],
                  #      strike_price=strike,
                  #      time_to_expiry=expiry_days[expiry] / 365,
                  #      volatility=record['CE']['impliedVolatility'] / 100,
                  #      risk_free_rate=0.05,  # Assume 5% risk-free rate
                  #      option_type='CE'
                  #  )
                }
            if 'PE' in record and record['PE']:
                strike_data[strike]['PE'] = {
                    'iv': record['PE']['impliedVolatility'],
                    'last_price': record['PE']['lastPrice'],
                 #   'greeks': calculate_greeks(
                 #       spot_price=options_data['records']['underlyingValue'],
                 #       strike_price=strike,
                 #       time_to_expiry=expiry_days[expiry] / 365,
                 #       volatility=record['PE']['impliedVolatility'] / 100,
                 #       risk_free_rate=0.05,  # Assume 5% risk-free rate
                 #       option_type='PE'
                 #   )
                }

        # Filter strikes with both CE and PE
        valid_strikes = []
        for strike, data in strike_data.items():
            if data['CE'] and data['PE']:
                # Check for arbitrage opportunity
                arbitrage_result = calculate_arbitrage(
                    underlying_price=options_data['records']['underlyingValue'],
                    call_price=data['CE']['last_price'],
                    put_price=data['PE']['last_price'],
                    strike_price=strike,
                    risk_free_rate=0.05,  # Assume 5% risk-free rate
                    time_to_expiry=expiry_days[expiry]
                )
                valid_strikes.append({
                    'strike': strike,
                    'CE': data['CE'],
                    'PE': data['PE'],
                    'arbitrage_opportunity': arbitrage_result['arbitrage_opportunity'],
                    'theoretical_value': arbitrage_result['theoretical_value'],
                    'actual_value': arbitrage_result['actual_value'],
                    'difference': arbitrage_result['difference']
                })

        results[expiry] = {
            'days_to_expiry': expiry_days[expiry],
            'strikes': valid_strikes,
            'volatility_bands': calculate_volatility_bands(historical_data, expiry_days[expiry]),
            'spot_price': options_data['records']['underlyingValue']
        }

    return jsonify(results)
def calculate_arbitrage(underlying_price, call_price, put_price, strike_price, risk_free_rate, time_to_expiry):
    """
    Calculate arbitrage opportunity using the Conversion Arbitrage formula.
    """
    try:
        # Conversion Arbitrage Formula:
        # Arbitrage exists if: Call Price - Put Price != Underlying Price - Strike Price * e^(-rT)
        discount_factor = math.exp(-risk_free_rate * (time_to_expiry / 365))
        theoretical_value = underlying_price - strike_price * discount_factor
        actual_value = call_price - put_price

        if abs(actual_value - theoretical_value) > 0.01:  # Tolerance for floating-point errors
            return {
                "arbitrage_opportunity": True,
                "theoretical_value": theoretical_value,
                "actual_value": actual_value,
                "difference": actual_value - theoretical_value
            }
        else:
            return {
                "arbitrage_opportunity": False,
                "theoretical_value": theoretical_value,
                "actual_value": actual_value,
                "difference": actual_value - theoretical_value
            }
    except Exception as e:
        return {"error": f"Error in arbitrage calculation: {str(e)}"}
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
# API to stop a strategy
@app.route('/api/stop_strategy', methods=['POST'])
def stop_strategy():
    data = request.json
    strategy_id = data.get('strategy_id')
    if not strategy_id:
        return jsonify({"error": "Strategy ID is required"}), 400

    # Find and update the strategy status
    for strategy in running_strategies:
        if strategy["id"] == strategy_id:
            strategy["status"] = "Stopped"
            strategy["pnl"] = random.uniform(-100, 100)  # Mock P&L
            return jsonify({"message": f"Strategy '{strategy['name']}' stopped", "pnl": strategy["pnl"]})
    return jsonify({"error": "Strategy not found"}), 404


# API to get running strategies
@app.route('/api/running_strategies', methods=['GET'])
def get_running_strategies():
    return jsonify(running_strategies)


def execute_volatility_cone_strategy():
    try:
        print("Executing Volatility Cone Strategy")
        analysis_results = run_volatility_analysis()
        # Ensure results are in a JSON-serializable format
        if isinstance(analysis_results, dict):
            return analysis_results
        else:
            return {"error": "Unexpected result from volatility analysis"}
    except Exception as e:
        return {"error": f"Error executing strategy: {str(e)}"}


def execute_conversion_arbitrage_strategy():
    try:
        data = fetch_options_chain("NIFTY")
        print(data)
        # Mock data for the underlying asset, call option, and put option
        underlying_price = 100  # Current price of the underlying asset
        call_price = 5  # Price of the Call option
        put_price = 4  # Price of the Put option
        strike_price = 100  # Strike price of the options
        risk_free_rate = 0.05  # Risk-free interest rate
        time_to_expiry = 30  # Time to expiry in days

        # Calculate the theoretical price of the Put option using Put-Call Parity
        theoretical_put_price = call_price - underlying_price + (strike_price / (1 + risk_free_rate) ** (time_to_expiry / 365))

        # Check for arbitrage opportunity
        if put_price < theoretical_put_price:
            # Execute Conversion Arbitrage
            profit = theoretical_put_price - put_price
            return {
                "status": "Arbitrage Opportunity Found",
                "strategy": "Conversion Arbitrage",
                "profit": profit,
                "details": {
                    "underlying_price": underlying_price,
                    "call_price": call_price,
                    "put_price": put_price,
                    "strike_price": strike_price,
                    "theoretical_put_price": theoretical_put_price,
                }
            }
        else:
            return {
                "status": "No Arbitrage Opportunity",
                "strategy": "Conversion Arbitrage",
                "profit": 0,
                "details": {
                    "underlying_price": underlying_price,
                    "call_price": call_price,
                    "put_price": put_price,
                    "strike_price": strike_price,
                    "theoretical_put_price": theoretical_put_price,
                }
            }
    except Exception as e:
        return {"error": f"Error executing strategy: {str(e)}"}


if __name__ == '__main__':
    app.run(debug=True)