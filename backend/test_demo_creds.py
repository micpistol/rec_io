import os
from dotenv import load_dotenv
import requests

load_dotenv('backend/api/kalshi-api/kalshi-credentials/demo/.env')

print("API Key:", os.getenv('KALSHI_API_KEY_ID'))
print("Key Path:", os.getenv('KALSHI_PRIVATE_KEY_PATH'))

try:
    resp = requests.get(
        "https://api.elections.kalshi.com/trade-api/v2/portfolio/balance",
        headers={'Authorization': f"Bearer {os.getenv('KALSHI_API_KEY_ID')}"}
    )
    print("Status code:", resp.status_code)
    print("Response text:", resp.text)
except Exception as e:
    print("Request failed:", e)