#!/usr/bin/env python3

import sys
import os
# Add the project root to the Python path
from backend.util.paths import get_project_root
if get_project_root() not in sys.path:
    sys.path.insert(0, get_project_root())

import psycopg2
from psycopg2.extras import RealDictCursor
import time
from datetime import datetime, timedelta
import pytz

EST = pytz.timezone("America/New_York")

# Database configuration
DB_CONFIG = {
    'host': os.getenv('POSTGRES_HOST', 'localhost'),
    'port': os.getenv('POSTGRES_PORT', '5432'),
    'database': os.getenv('POSTGRES_DB', 'rec_io_db'),
    'user': os.getenv('POSTGRES_USER', 'rec_io_user'),
    'password': os.getenv('POSTGRES_PASSWORD', 'rec_io_password')
}

def connect_database():
    """Connect to PostgreSQL database"""
    try:
        connection = psycopg2.connect(**DB_CONFIG)
        return connection
    except Exception as e:
        print(f"[{datetime.now(EST)}] ❌ Database connection failed: {e}")
        return None

def get_current_event_ticker():
    """Get the current active event ticker from the database"""
    try:
        connection = connect_database()
        if not connection:
            return None
            
        cursor = connection.cursor()
        cursor.execute("""
            SELECT event_ticker 
            FROM live_data.btc_live_strikes 
            ORDER BY created_at DESC 
            LIMIT 1
        """)
        result = cursor.fetchone()
        connection.close()
        
        if result:
            return result[0]
        return None
        
    except Exception as e:
        print(f"[{datetime.now(EST)}] ❌ Error getting current event ticker: {e}")
        return None

def calculate_ttc():
    """Calculate time to close (next hour)"""
    now = datetime.now(EST)
    next_hour = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    ttc_seconds = int((next_hour - now).total_seconds())
    return ttc_seconds

def get_live_probabilities(event_ticker):
    """Get live probabilities for the current strikes"""
    try:
        connection = connect_database()
        if not connection:
            return {}
            
        cursor = connection.cursor()
        
        # Get current price and momentum from header
        cursor.execute("""
            SELECT current_price, momentum_weighted_score 
            FROM live_data.btc_live_header 
            WHERE event_ticker = %s
        """, (event_ticker,))
        header_result = cursor.fetchone()
        
        if not header_result:
            print(f"[{datetime.now(EST)}] ⚠️ No header data found for {event_ticker}")
            connection.close()
            return {}
            
        current_price, momentum_score = header_result
        
        # Get TTC from header
        cursor.execute("""
            SELECT ttc_seconds 
            FROM live_data.btc_live_header 
            WHERE event_ticker = %s
        """, (event_ticker,))
        ttc_result = cursor.fetchone()
        ttc_seconds = ttc_result[0] if ttc_result and ttc_result[0] else calculate_ttc()
        
        # Convert to float for probability calculator
        current_price_float = float(current_price) if current_price else 114000.0
        momentum_float = float(momentum_score) if momentum_score else 0.0
        
        # Get actual strikes from the database (same as what Kalshi API provides)
        cursor.execute("""
            SELECT DISTINCT strike 
            FROM live_data.btc_live_strikes 
            WHERE event_ticker = %s 
            ORDER BY strike
        """, (event_ticker,))
        strike_results = cursor.fetchall()
        
        if not strike_results:
            print(f"[{datetime.now(EST)}] ⚠️ No strikes found in database for {event_ticker}")
            connection.close()
            return {}
        
        # Convert strike strings to float values
        strikes = []
        for (strike_str,) in strike_results:
            try:
                strike_value = float(strike_str.replace('$', '').replace(',', ''))
                strikes.append(strike_value)
            except Exception as e:
                print(f"[{datetime.now(EST)}] ⚠️ Error parsing strike '{strike_str}': {e}")
                continue
        
        print(f"[{datetime.now(EST)}] 📊 Using {len(strikes)} actual strikes from database")
        print(f"[{datetime.now(EST)}] 📊 Calculating probabilities: price={current_price_float}, momentum={momentum_float}, ttc={ttc_seconds}s, strikes={len(strikes)}")
        
        # Use the probability calculator exactly like the main system
        from backend.util.probability_calculator import get_probability_calculator
        
        calculator = get_probability_calculator()
        ttc_hours = ttc_seconds / 3600.0  # Convert to hours
        
        # Calculate probabilities for all strikes at once
        try:
            results = calculator.calculate_strike_probabilities(
                current_price=current_price_float,
                ttc_seconds=ttc_seconds,
                strikes=strikes,
                momentum_score=momentum_float
            )
            
            # Convert results to the expected format - use strike safety probability
            probabilities = {}
            for result in results:
                strike = result['strike']
                # The probability represents the probability of the strike NOT being hit
                # For strikes above current price: probability of staying below (safe)
                # For strikes below current price: probability of staying below (safe)
                if result['direction'] == 'above':
                    # For strikes above current price, use prob_within (probability of staying below)
                    prob = result['prob_within']
                else:
                    # For strikes below current price, use prob_within (probability of staying below)
                    prob = result['prob_within']
                probabilities[strike] = prob
                print(f"[{datetime.now(EST)}] 📊 Found probability for strike ${strike:,.0f}: {prob:.2f} (safety)")
                
        except Exception as e:
            print(f"[{datetime.now(EST)}] ⚠️ Error calculating probabilities: {e}")
            return {}
        
        connection.close()
        print(f"[{datetime.now(EST)}] ✅ Generated probabilities for {len(probabilities)} strikes")
        return probabilities
        
    except Exception as e:
        print(f"[{datetime.now(EST)}] ❌ Error getting live probabilities: {e}")
        if 'connection' in locals():
            connection.close()
        return {}

def update_header_with_ttc(event_ticker):
    """Update header with current TTC"""
    try:
        connection = connect_database()
        if not connection:
            return False
            
        ttc_seconds = calculate_ttc()
        cursor = connection.cursor()
        
        cursor.execute("""
            UPDATE live_data.btc_live_header 
            SET ttc_seconds = %s, updated_at = NOW()
            WHERE event_ticker = %s
        """, (ttc_seconds, event_ticker))
        
        connection.commit()
        connection.close()
        print(f"[{datetime.now(EST)}] ✅ Updated header with TTC: {ttc_seconds}s")
        return True
        
    except Exception as e:
        print(f"[{datetime.now(EST)}] ❌ Error updating header TTC: {e}")
        if 'connection' in locals():
            connection.rollback()
            connection.close()
        return False

def calculate_active_side_and_diffs(strike_price, current_price, yes_ask, no_ask, probability):
    """Calculate active side and price differentials using the same logic as main system"""
    try:
        strike_value = float(strike_price.replace('$', '').replace(',', ''))
        
        # Determine active side based on position relative to current price
        active_side = "NO" if strike_value > current_price else "YES"
        
        # Calculate diffs using the exact same logic as main system
        if strike_value < current_price:
            # Strike is BELOW current price (money line)
            yes_diff = int(probability - yes_ask) if yes_ask else 0
            no_diff = int(100 - probability - no_ask) if no_ask else 0
        else:
            # Strike is ABOVE current price (money line)
            yes_diff = int(100 - probability - yes_ask) if yes_ask else 0
            no_diff = int(probability - no_ask) if no_ask else 0
        
        return active_side, yes_diff, no_diff
        
    except Exception as e:
        print(f"[{datetime.now(EST)}] ❌ Error calculating active side and diffs: {e}")
        return "UNKNOWN", 0, 0

def update_strikes_with_probabilities_and_diffs(event_ticker, probabilities):
    """Update strikes with probabilities and differentials"""
    try:
        connection = connect_database()
        if not connection:
            return False
            
        cursor = connection.cursor()
        
        # Get all strikes for this event
        cursor.execute("""
            SELECT market_ticker, strike, yes_ask, no_ask 
            FROM live_data.btc_live_strikes 
            WHERE event_ticker = %s
        """, (event_ticker,))
        strikes = cursor.fetchall()
        
        updated_count = 0
        for market_ticker, strike_price, yes_ask, no_ask in strikes:
            try:
                # Convert strike to float for lookup
                strike_float = float(strike_price.replace('$', '').replace(',', ''))
                
                if strike_float in probabilities:
                    probability = probabilities[strike_float]
                    
                    # Get current price from header
                    cursor.execute("""
                        SELECT current_price FROM live_data.btc_live_header 
                        WHERE event_ticker = %s ORDER BY updated_at DESC LIMIT 1
                    """, (event_ticker,))
                    current_price_result = cursor.fetchone()
                    current_price = current_price_result[0] if current_price_result else 114000.0
                    
                    # Calculate active side and diffs
                    active_side, yes_diff, no_diff = calculate_active_side_and_diffs(
                        strike_price, current_price, yes_ask, no_ask, probability
                    )
                    
                    # Update the strike record
                    cursor.execute("""
                        UPDATE live_data.btc_live_strikes 
                        SET probability = %s, active_side = %s, yes_diff = %s, no_diff = %s, updated_at = NOW()
                        WHERE event_ticker = %s AND market_ticker = %s
                    """, (probability, active_side, yes_diff, no_diff, event_ticker, market_ticker))
                    
                    updated_count += 1
                    
            except Exception as e:
                print(f"[{datetime.now(EST)}] ⚠️ Error updating strike {market_ticker}: {e}")
                continue
        
        connection.commit()
        connection.close()
        print(f"[{datetime.now(EST)}] ✅ Updated {updated_count} strikes with probabilities and diffs")
        return True
        
    except Exception as e:
        print(f"[{datetime.now(EST)}] ❌ Error updating strikes: {e}")
        if 'connection' in locals():
            connection.rollback()
            connection.close()
        return False

def add_probability_column():
    """Add probability columns to the strikes table if they don't exist"""
    try:
        connection = connect_database()
        if not connection:
            return False
            
        cursor = connection.cursor()
        
        # Check if columns exist
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_schema = 'live_data' 
            AND table_name = 'btc_live_strikes' 
            AND column_name IN ('probability', 'active_side', 'yes_diff', 'no_diff', 'ttc_seconds')
        """)
        existing_columns = [row[0] for row in cursor.fetchall()]
        
        # Add missing columns
        if 'probability' not in existing_columns:
            cursor.execute("ALTER TABLE live_data.btc_live_strikes ADD COLUMN probability DECIMAL(5,2)")
        if 'active_side' not in existing_columns:
            cursor.execute("ALTER TABLE live_data.btc_live_strikes ADD COLUMN active_side VARCHAR(10)")
        if 'yes_diff' not in existing_columns:
            cursor.execute("ALTER TABLE live_data.btc_live_strikes ADD COLUMN yes_diff INTEGER")
        if 'no_diff' not in existing_columns:
            cursor.execute("ALTER TABLE live_data.btc_live_strikes ADD COLUMN no_diff INTEGER")
        if 'ttc_seconds' not in existing_columns:
            cursor.execute("ALTER TABLE live_data.btc_live_strikes ADD COLUMN ttc_seconds INTEGER")
        
        connection.commit()
        connection.close()
        print(f"[{datetime.now(EST)}] ✅ Probability columns ready")
        return True
        
    except Exception as e:
        print(f"[{datetime.now(EST)}] ❌ Error adding probability columns: {e}")
        if 'connection' in locals():
            connection.rollback()
            connection.close()
        return False

def add_ttc_column_to_header():
    """Add TTC column to header table if it doesn't exist"""
    try:
        connection = connect_database()
        if not connection:
            return False
            
        cursor = connection.cursor()
        
        # Check if column exists
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_schema = 'live_data' 
            AND table_name = 'btc_live_header' 
            AND column_name = 'ttc_seconds'
        """)
        result = cursor.fetchone()
        
        if not result:
            cursor.execute("ALTER TABLE live_data.btc_live_header ADD COLUMN ttc_seconds INTEGER")
            connection.commit()
            print(f"[{datetime.now(EST)}] ✅ Added ttc_seconds column to header")
        
        connection.close()
        return True
        
    except Exception as e:
        print(f"[{datetime.now(EST)}] ❌ Error adding TTC column: {e}")
        if 'connection' in locals():
            connection.rollback()
            connection.close()
        return False

def main():
    print(f"[{datetime.now(EST)}] 🚀 Starting Strike Table Analysis")
    
    # Initialize database schema
    add_probability_column()
    add_ttc_column_to_header()
    
    while True:
        try:
            # Get current event ticker
            event_ticker = get_current_event_ticker()
            
            if event_ticker:
                print(f"[{datetime.now(EST)}] 📊 Analyzing event: {event_ticker}")
                
                # Update header with TTC
                update_header_with_ttc(event_ticker)
                
                # Get live probabilities
                probabilities = get_live_probabilities(event_ticker)
                
                if probabilities:
                    print(f"[{datetime.now(EST)}] ✅ Got {len(probabilities)} probabilities, updating strikes...")
                    update_strikes_with_probabilities_and_diffs(event_ticker, probabilities)
                else:
                    print(f"[{datetime.now(EST)}] ⚠️ No probabilities available")
            else:
                print(f"[{datetime.now(EST)}] ⚠️ No active event found")
            
            time.sleep(1)  # Run every second
            
        except KeyboardInterrupt:
            print(f"\n[{datetime.now(EST)}] 🛑 Strike Table Analysis stopped")
            break
        except Exception as e:
            print(f"[{datetime.now(EST)}] ❌ Unexpected error: {e}")
            time.sleep(1)

if __name__ == "__main__":
    main() 