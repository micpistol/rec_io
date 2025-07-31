#!/usr/bin/env python3

import sqlite3
import os
import sys

# Add the backend directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from trade_manager import confirm_close_trade, get_accounts_data_dir, get_account_mode

def debug_close_trade():
    """Debug the confirm_close_trade function for trade 1330"""
    
    # Test the database connections
    mode = get_account_mode()
    POSITIONS_DB_PATH = os.path.join(get_accounts_data_dir(), "kalshi", mode, "positions.db")
    FILLS_DB_PATH = os.path.join(get_accounts_data_dir(), "kalshi", mode, "fills.db")
    
    print(f"Mode: {mode}")
    print(f"Positions DB: {POSITIONS_DB_PATH}")
    print(f"Fills DB: {FILLS_DB_PATH}")
    
    # Check if databases exist
    print(f"Positions DB exists: {os.path.exists(POSITIONS_DB_PATH)}")
    print(f"Fills DB exists: {os.path.exists(FILLS_DB_PATH)}")
    
    # Check position for the ticker
    ticker = 'KXBTCD-25JUL3020-T117749.99'
    
    try:
        conn_pos = sqlite3.connect(POSITIONS_DB_PATH, timeout=0.25)
        cursor_pos = conn_pos.cursor()
        cursor_pos.execute("SELECT position FROM positions WHERE ticker = ?", (ticker,))
        row = cursor_pos.fetchone()
        conn_pos.close()
        
        print(f"Position query result: {row}")
        
        if row and row[0] == 0:
            print("Position is zero - proceeding to check fills")
            
            # Check fills
            conn_fills = sqlite3.connect(FILLS_DB_PATH, timeout=0.25)
            cursor_fills = conn_fills.cursor()
            opposite_side = 'yes'  # Since original side is 'N'
            
            cursor_fills.execute("""
                SELECT yes_price, no_price, created_time, side 
                FROM fills 
                WHERE ticker = ? AND side = ? 
                ORDER BY created_time DESC 
                LIMIT 1
            """, (ticker, opposite_side))
            fill_row = cursor_fills.fetchone()
            conn_fills.close()
            
            print(f"Fill query result: {fill_row}")
            
            if fill_row:
                yes_price, no_price, fill_time, fill_side = fill_row
                print(f"Found fill: yes_price={yes_price}, no_price={no_price}, fill_time={fill_time}, fill_side={fill_side}")
                
                # Calculate sell price
                original_side = 'N'
                if original_side == 'N':  # Original was NO, so use YES price (we're buying YES to close)
                    sell_price = 1 - float(yes_price)  # Keep as decimal
                else:
                    sell_price = 1 - float(no_price)  # Keep as decimal
                
                print(f"Calculated sell_price: {sell_price}")
                
                # Test the update_trade_status function
                from trade_manager import update_trade_status
                
                try:
                    update_trade_status(1330, "closed", "19:18:49", sell_price, None, "L", -0.06, "manual")
                    print("✅ update_trade_status completed successfully")
                except Exception as e:
                    print(f"❌ Error in update_trade_status: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                print("❌ No fill found")
        else:
            print("❌ Position not zeroed out")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_close_trade() 