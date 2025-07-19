"""
MARKET TITLE SERVICE
Dedicated service for serving market title data directly from Kalshi watchdog
"""

import os
import json
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import pytz

app = FastAPI(title="Market Title Service")

# Add CORS middleware to allow cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Use EST timezone
EST = pytz.timezone('US/Eastern')

@app.get("/market_title")
async def get_market_title():
    """Get current market title from Kalshi snapshot."""
    try:
        # Read from the latest market snapshot file
        snapshot_file = os.path.join("backend", "data", "kalshi", "latest_market_snapshot.json")
        
        if os.path.exists(snapshot_file):
            with open(snapshot_file, 'r') as f:
                snapshot_data = json.load(f)
                title = snapshot_data.get("title", "No Title Available")
                return {"title": title}
        else:
            print(f"Kalshi snapshot file not found: {snapshot_file}")
            return {"title": "No Title Available"}
    except Exception as e:
        print(f"Error getting market title: {e}")
        return {"title": "No Title Available"}

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "market_title", "timestamp": datetime.now(EST).isoformat()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8006) 