import os
import json
import requests

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

