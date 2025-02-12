import json
import requests
import pyotp
from urllib import parse
import sys
from fyers_apiv3 import fyersModel
from datetime import date
from multiprocessing import Process
import os
myAccess = "access_token"
myAuth = "Auth_Data"
myAudit = "audit"
mycol2 = "access_token"
find = "https://ap-south-1.aws.data.mongodb-api.com/app/data-kpqgeul/endpoint/data/v1/action/findOne"
insert = "https://ap-south-1.aws.data.mongodb-api.com/app/data-kpqgeul/endpoint/data/v1/action/insertOne"
delete = "https://ap-south-1.aws.data.mongodb-api.com/app/data-kpqgeul/endpoint/data/v1/action/deleteOne"
update = "https://data.mongodb-api.com/app/myapp-abcde/endpoint/data/v1/action/updateOne"
delete_many = "https://data.mongodb-api.com/app/myapp-abcde/endpoint/data/v1/action/deleteMany"

# API endpoints
BASE_URL = "https://api-t2.fyers.in/vagator/v2"
BASE_URL_2 = "https://api-t1.fyers.in/api/v3"
URL_SEND_LOGIN_OTP = BASE_URL + "/send_login_otp"
URL_VERIFY_TOTP = BASE_URL + "/verify_otp"
URL_VERIFY_PIN = BASE_URL + "/verify_pin"
URL_TOKEN = BASE_URL_2 + "/token"
URL_VALIDATE_AUTH_CODE = BASE_URL_2 + "/validate-authcode"
api_key = os.getenv("API_KEY") ## for Production move

try:
    api = json.loads(open('api_key.json', 'r').read())
    api_key = api["API_KEY"]
except Exception as e:
    pass

headers = {
    'Content-Type': 'application/json',
    'Access-Control-Request-Headers': '*',
    'api-key': api_key,
}

SUCCESS = 1
ERROR = -1

today = date.today()
# dd/mm/YY
d1 = today.strftime("%d/%m/%Y")

def telegram(message1,message2):
    bot_token = '1720457948:AAF1VSmBzyhp70b4QGrLGDe23pKRhWP4iKw'  # paste bot_token
    #bot_chatID = '-579138108'  # paste your chatid where you want to send alert(group or channel or personal)
    bot_chatID = '-1001206209234'  # chatid of Telegram group Monitor Signal
    bot_message = str(message1) + str(message2)
    send_text = 'https://api.telegram.org/bot' + bot_token + '/sendMessage?chat_id=' + bot_chatID + '&parse_mode=Markdown&text=' + bot_message
    response = requests.get(send_text)
    return response.json()

def read_auth(user):
    payload = json.dumps({
        "collection": myAuth,
        "database": "myFirstDatabase",
        "dataSource": "Cluster0",
        "filter":{"userid":user},
        "projection": {
            "userid": 1,
            "app_id": 1,
            "app_type":1,
            "app_id_type":1,
            "app_id_hash":1,
            "totp":1,
            "pin":1,
            "redirect_uri":1
        }
    })

    response = requests.request("POST", find, headers=headers, data=payload)
    auth_data = response.json()
    print(auth_data)
    FY_ID = user
    APP_ID= auth_data['document']['app_id']
    APP_TYPE = auth_data['document']['app_type']
    APP_ID_TYPE = auth_data['document']['app_id_type']
    APP_ID_HASH = auth_data['document']['app_id_hash']
    TOTP_KEY = auth_data['document']['totp']
    PIN = auth_data['document']['pin']
    REDIRECT_URI = auth_data['document']['redirect_uri']
    return FY_ID,APP_ID,APP_TYPE,APP_ID_TYPE,APP_ID_HASH,TOTP_KEY,PIN,REDIRECT_URI

def send_login_otp(fy_id, app_id):
    try:
        payload = {
            "fy_id": fy_id,
            "app_id": app_id
        }

        result_string = requests.post(url=URL_SEND_LOGIN_OTP, json=payload)
        if result_string.status_code != 200:
            return [ERROR, result_string.text]

        result = json.loads(result_string.text)
        request_key = result["request_key"]

        return [SUCCESS, request_key]

    except Exception as e:
        return [ERROR, e]


def generate_totp(secret):
    try:
        generated_totp = pyotp.TOTP(secret).now()
        return [SUCCESS, generated_totp]

    except Exception as e:
        return [ERROR, e]


def verify_totp(request_key, totp):
    try:
        payload = {
            "request_key": request_key,
            "otp": totp
        }

        result_string = requests.post(url=URL_VERIFY_TOTP, json=payload)
        if result_string.status_code != 200:
            return [ERROR, result_string.text]

        result = json.loads(result_string.text)
        request_key = result["request_key"]

        return [SUCCESS, request_key]

    except Exception as e:
        return [ERROR, e]


def verify_PIN(request_key, pin):
    try:
        payload = {
            "request_key": request_key,
            "identity_type": "pin",
            "identifier": pin
        }

        result_string = requests.post(url=URL_VERIFY_PIN, json=payload)
        if result_string.status_code != 200:
            return [ERROR, result_string.text]

        result = json.loads(result_string.text)
        access_token = result["data"]["access_token"]

        return [SUCCESS, access_token]

    except Exception as e:
        return [ERROR, e]


def token(fy_id, app_id, redirect_uri, app_type, access_token):
    try:
        payload = {
            "fyers_id": fy_id,
            "app_id": app_id,
            "redirect_uri": redirect_uri,
            "appType": app_type,
            "code_challenge": "",
            "state": "sample_state",
            "scope": "",
            "nonce": "",
            "response_type": "code",
            "create_cookie": True
        }
        headers = {'Authorization': f'Bearer {access_token}'}

        result_string = requests.post(
            url=URL_TOKEN, json=payload, headers=headers
        )

        if result_string.status_code != 308:
            return [ERROR, result_string.text]

        result = json.loads(result_string.text)
        url = result["Url"]
        auth_code = parse.parse_qs(parse.urlparse(url).query)['auth_code'][0]

        return [SUCCESS, auth_code]

    except Exception as e:
        return [ERROR, e]


def validate_authcode(app_id_hash, auth_code):
    try:
        payload = {
            "grant_type": "authorization_code",
            "appIdHash": app_id_hash,
            "code": auth_code,
        }

        result_string = requests.post(url=URL_VALIDATE_AUTH_CODE, json=payload)
        if result_string.status_code != 200:
            return [ERROR, result_string.text]

        result = json.loads(result_string.text)
        access_token = result["access_token"]

        return [SUCCESS, access_token]

    except Exception as e:
        return [ERROR, e]

def del_record(user):
    payload = json.dumps({
        "collection": "access_token",
        "database": "myFirstDatabase",
        "dataSource": "Cluster0",
        "filter": {"userid": user}
    }
    )
    checkToken = requests.request("POST", delete, headers=headers, data=payload)
    #print(checkToken.json())

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

def main(user):
    FY_ID = str(read_auth(user)[0])
    APP_ID = str(read_auth(user)[1])
    APP_TYPE = str(read_auth(user)[2])
    APP_ID_TYPE = str(read_auth(user)[3])
    APP_ID_HASH = str(read_auth(user)[4])
    TOTP_KEY = str(read_auth(user)[5])
    PIN = str(read_auth(user)[6])
    REDIRECT_URI = str(read_auth(user)[7])


    # Step 1 - Retrieve request_key from send_login_otp API
    send_otp_result = send_login_otp(fy_id=FY_ID, app_id=APP_ID_TYPE)
    if send_otp_result[0] != SUCCESS:
        print(f"send_login_otp failure - {send_otp_result[1]}")
        sys.exit()
    else:
        print("send_login_otp success")

    # Step 2 - Generate totp
    generate_totp_result = generate_totp(secret=TOTP_KEY)
    if generate_totp_result[0] != SUCCESS:
        print(f"generate_totp failure - {generate_totp_result[1]}")
        sys.exit()
    else:
        print("generate_totp success")

    # Step 3 - Verify totp and get request key from verify_otp API
    request_key = send_otp_result[1]
    totp = generate_totp_result[1]
    verify_totp_result = verify_totp(request_key=request_key, totp=totp)
    if verify_totp_result[0] != SUCCESS:
        print(f"verify_totp_result failure - {verify_totp_result[1]}")
        sys.exit()
    else:
        print("verify_totp_result success")

    # Step 4 - Verify pin and send back access token
    request_key_2 = verify_totp_result[1]
    verify_pin_result = verify_PIN(request_key=request_key_2, pin=PIN)
    if verify_pin_result[0] != SUCCESS:
        print(f"verify_pin_result failure - {verify_pin_result[1]}")
##        telegram(user,":Verify Pin failure")
        sys.exit()
    else:
        print("verify_pin_result success")

    # Step 5 - Get auth code for API V2 App from trade access token
    token_result = token(
        fy_id=FY_ID, app_id=APP_ID, redirect_uri=REDIRECT_URI, app_type=APP_TYPE,
        access_token=verify_pin_result[1]
    )
    if token_result[0] != SUCCESS:
        print(f"token_result failure - {token_result[1]}")
        sys.exit()
    else:
        print("token_result success")

    # Step 6 - Get API V2 access token from validating auth code
    auth_code = token_result[1]
    validate_authcode_result = validate_authcode(
        app_id_hash=APP_ID_HASH, auth_code=auth_code
    )
    if token_result[0] != SUCCESS:
        print(f"validate_authcode failure - {validate_authcode_result[1]}")
        sys.exit()
    else:
        print("validate_authcode success")

    access_token = APP_ID + "-" + APP_TYPE + ":" + validate_authcode_result[1]

    #print(f"access_token - {access_token}")
    parts = access_token.split(":")
    del_record(user)
    if len(parts) > 1:
        a_token = parts[1]
     #   print(d1,user,a_token)
        access_data = {"Date": d1, "userid":user, "access_token": a_token}
        payload1 = json.dumps({
            "collection": "access_token",
            "database": "myFirstDatabase",
            "dataSource": "Cluster0",
            "document":{"Date": d1, "userid":user, "access_token": a_token}
        })
        response = requests.request("POST", insert, headers=headers, data=payload1)
        token_data = response.json()
      #  print(token_data)
        #telegram(FY_ID,":Token generated successfully")
        #     print(f"Extracted letters: {a_token}")
    else:
        print("No delimiter found in the output string.")

    # Initialize the FyersModel instance with your client_id, access_token, and enable async mode
    client_id = APP_ID+"-"+APP_TYPE

    access_token = read_file(user)

    fyers = fyersModel.FyersModel(client_id=client_id, is_async=False, token=access_token, log_path="")

    # Make a request to get the user profile information
    response = fyers.get_profile()
    telegram(FY_ID,":- Logged into Fyers")
    print (response)
    fund_available = fyers.funds()
    print(fund_available)

    fund = fund_available["fund_limit"][9]
    capital = fund["equityAmount"]
    print("Funds Available: ", capital)
    msg1="-->Funds Available: "+str(capital)
    telegram(user,msg1)


if __name__ == "__main__":
    #telegram("FYERS Login Started", "")

    myProcess3 = Process(target=main, args=('XD01606',))

    myProcess3.start()
