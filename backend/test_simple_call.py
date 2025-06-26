import os
from dotenv import load_dotenv
import requests

# Load demo credentials
load_dotenv('backend/api/kalshi-api/kalshi-credentials/prod/.env')

api_key = os.getenv('KALSHI_API_KEY_ID')

print("Using API Key:", api_key)

# Minimal authenticated call — try "account balance" or similar
url = "https://api.elections.kalshi.com/trade-api/v2/portfolio/balance"

headers = {
    'Authorization': f'Bearer {api_key}'
}

response = requests.get(url, headers=headers)

print("Status code:", response.status_code)
print("Response text:", response.text)