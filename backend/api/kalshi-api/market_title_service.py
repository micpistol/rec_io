"""
MARKET TITLE SERVICE
Dedicated service for serving market title data directly from Kalshi watchdog
"""

import sys
import os
# Add the project root to the Python path
from backend.util.paths import get_project_root
if get_project_root() not in sys.path:
    sys.path.insert(0, get_project_root())

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
        # Read from the latest market snapshot file using centralized paths
        from backend.util.paths import get_kalshi_data_dir
        snapshot_file = os.path.join(get_kalshi_data_dir(), "latest_market_snapshot.json")
        
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
    from backend.core.port_config import get_port
    
    # Get port from centralized system
    MARKET_TITLE_PORT = get_port("market_title_service")
    print(f"[MARKET_TITLE_SERVICE] 🚀 Using centralized port: {MARKET_TITLE_PORT}")
    
    uvicorn.run(app, host="0.0.0.0", port=MARKET_TITLE_PORT) 