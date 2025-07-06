import sqlite3
import math
import os
from flask import Flask, jsonify
import numpy as np

app = Flask(__name__)

def get_btc_price_history():
    """Get the last 1500 BTC prices from the database (more than enough for calculations)"""
    db_path = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'price_history', 'btc_price_history.db')
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get the last 1500 prices (more than enough for 60 log-returns + 1440 volatilities)
        cursor.execute("""
            SELECT price, timestamp 
            FROM price_log 
            ORDER BY timestamp DESC 
            LIMIT 1500
        """)
        
        results = cursor.fetchall()
        conn.close()
        
        # Return prices in chronological order (oldest first)
        prices = [float(row[0]) for row in reversed(results)]
        return prices
        
    except Exception as e:
        print(f"Error reading BTC price history: {e}")
        return []

def compute_log_returns(prices):
    """Compute log-returns from price series"""
    if len(prices) < 2:
        return []
    
    log_returns = []
    for i in range(1, len(prices)):
        if prices[i-1] > 0 and prices[i] > 0:
            log_return = math.log(prices[i] / prices[i-1])
            log_returns.append(log_return)
    
    return log_returns

def compute_realized_volatility(log_returns, window_size=60):
    """Compute realized volatility as sample standard deviation of log-returns"""
    if len(log_returns) < window_size:
        return None
    
    # Use the last 'window_size' log-returns
    recent_returns = log_returns[-window_size:]
    
    if len(recent_returns) < 2:
        return None
    
    # Compute sample standard deviation
    mean = sum(recent_returns) / len(recent_returns)
    variance = sum((x - mean) ** 2 for x in recent_returns) / (len(recent_returns) - 1)
    return math.sqrt(variance)

def compute_percentile_rank(value, sorted_array):
    """Compute percentile rank of a value in a sorted array"""
    if len(sorted_array) == 0:
        return 0
    
    # Find the index where value would be inserted to maintain sort order
    index = 0
    for i, x in enumerate(sorted_array):
        if x > value:
            index = i
            break
        index = i + 1
    
    return index / len(sorted_array)

def calculate_absolute_volatility_score():
    """Calculate the absolute volatility score using historical data"""
    prices = get_btc_price_history()
    
    if len(prices) < 61:  # Need at least 61 prices for 60 log-returns
        return {"score": 0.00, "error": "Insufficient historical data"}
    
    # Compute all log-returns
    log_returns = compute_log_returns(prices)
    
    if len(log_returns) < 60:
        return {"score": 0.00, "error": "Insufficient log-returns"}
    
    # Compute realized volatilities using rolling windows
    volatilities = []
    for i in range(60, len(log_returns) + 1):
        vol = compute_realized_volatility(log_returns[:i])
        if vol is not None:
            volatilities.append(vol)
    
    if len(volatilities) < 10:  # Need at least 10 volatilities for percentile rank
        return {"score": 0.00, "error": "Insufficient volatility data"}
    
    # Get the most recent volatility
    current_volatility = volatilities[-1]
    
    # Compute percentile rank against the last 1440 volatilities (or all available)
    historical_volatilities = volatilities[-1440:] if len(volatilities) >= 1440 else volatilities
    sorted_volatilities = sorted(historical_volatilities)
    
    percentile_rank = compute_percentile_rank(current_volatility, sorted_volatilities)
    score = percentile_rank * 100  # Convert to 0-100 scale
    
    return {
        "score": round(score, 2),
        "current_volatility": round(current_volatility, 6),
        "volatility_count": len(volatilities),
        "price_count": len(prices)
    }

@app.route('/api/volatility_score', methods=['GET'])
def get_volatility_score():
    """API endpoint to get the absolute volatility score"""
    try:
        result = calculate_absolute_volatility_score()
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e), "score": 0.00}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5001) 