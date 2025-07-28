import sqlite3
import threading
import time
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import re
import requests
from backend.core.config.settings import config
# APScheduler imports
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

# Import the universal centralized port system
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from backend.core.port_config import get_port, get_port_info

# Import centralized path utilities
from backend.util.paths import get_project_root, get_trade_history_dir, get_logs_dir, get_host, get_data_dir
from backend.account_mode import get_account_mode
from backend.util.paths import get_accounts_data_dir

# Get port from centralized system
TRADE_MANAGER_PORT = get_port("trade_manager")
print(f"[TRADE_MANAGER] 🚀 Using centralized port: {TRADE_MANAGER_PORT}")

def get_executor_port():
    return get_port("trade_executor")

# ---------- CORE HELPERS ----------------------------------------------------
def create_pending_trade(trade: dict) -> int:
    """Insert a new ticket immediately with status='pending' and return DB id."""
    # Ensure the trade is created with 'pending' status
    trade['status'] = 'pending'
    trade_id = insert_trade(trade)
    log_event(trade["ticket_id"], "MANAGER: TICKET RECEIVED — CONFIRMED")
    log_event(trade["ticket_id"], "MANAGER: TRADE LOGGED PENDING — CONFIRMED")
    return trade_id


def _wait_for_fill(ticker: str, timeout: int = 10) -> tuple[int | None, float | None]:
    """
    Poll /api/db/positions (no hard‑wired port) until ticker appears with
    non‑zero position, or timeout seconds elapse.
    Returns (abs_position, buy_price) or (None, None) if not seen in time.
    """
    deadline = time.time() + timeout
    # Use the main agent port for positions API
    port = get_port("main_app")
    url = f"http://{get_host()}:{port}/api/db/positions"          # host‑relative; no port hard‑coding
    while time.time() < deadline:
        try:
            r = requests.get(url, timeout=2)
            if r.status_code == 200:
                payload = r.json()
                positions = (
                    payload.get("positions")
                    or payload.get("market_positions")
                    or []
                )
                for p in positions:
                    # Return the first position with pos > 0 and exposure > 0 regardless of ticker
                    pos = abs(p.get("position", 0))
                    exposure = abs(p.get("market_exposure", 0))
                    if pos > 0 and exposure > 0:
                        price = round(float(exposure) / float(pos) / 100, 2)
                        return int(pos), price
                # print(f"[FILL POLL] No position data yet for any position, retrying...")
        except Exception:
            pass
        time.sleep(1)
    return None, None


def confirm_open_trade(id: int, ticket_id: str) -> None:
    """
    Confirms a PENDING trade has been opened in the market account.
    Polls positions.db for matching ticker with non-zero position.
    Updates trade status to 'open' and fills in actual buy price and fees.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT ticker FROM trades WHERE id = ?", (id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        log_event(ticket_id, f"MANAGER: No trade found for ID {id}")
        return
    
    expected_ticker = row[0]
    
    # Use centralized paths for positions database
    mode = get_account_mode()
    POSITIONS_DB_PATH = os.path.join(get_accounts_data_dir(), "kalshi", mode, "positions.db")
    
    if not os.path.exists(POSITIONS_DB_PATH):
        log_event(ticket_id, f"MANAGER: Positions DB path not found: {POSITIONS_DB_PATH}")
        return
    
    conn_pos = sqlite3.connect(POSITIONS_DB_PATH, timeout=0.25)
    cursor_pos = conn_pos.cursor()
    deadline = time.time() + 15  # 15 second timeout
    
    while time.time() < deadline:
        try:
            cursor_pos.execute("SELECT position, market_exposure, fees_paid FROM positions WHERE ticker = ?", (expected_ticker,))
            row = cursor_pos.fetchone()
            
            if row and row[0] is not None and row[1] is not None:
                pos = abs(row[0])
                exposure = abs(row[1])
                fees_paid = float(row[2]) if row[2] is not None else 0.0
                
                # Calculate actual buy price and fees
                price = round(float(exposure) / float(pos) / 100, 2) if pos > 0 else 0.0
                fees = round(fees_paid / 100, 2)
                
                # Check if trade is still pending and position has appeared
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT status FROM trades WHERE id = ?", (id,))
                status_row = cursor.fetchone()
                current_status = status_row[0] if status_row else None
                conn.close()
                
                if current_status == "pending" and pos > 0 and exposure > 0:
                    # Calculate DIFF: PROB - BUY (formatted as whole integer)
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("SELECT prob FROM trades WHERE id = ?", (id,))
                    prob_row = cursor.fetchone()
                    conn.close()
                    
                    prob_value = prob_row[0] if prob_row and prob_row[0] is not None else None
                    diff_value = None
                    
                    if prob_value is not None:
                        # Convert prob from percentage to decimal (96.7 -> 0.967)
                        prob_decimal = float(prob_value) / 100
                        # Calculate diff: prob_decimal - buy_price
                        diff_decimal = prob_decimal - price
                        # Convert to whole integer (0.02 -> +2, -0.03 -> -3)
                        diff_value = int(round(diff_decimal * 100))
                        # Format as string with sign
                        diff_formatted = f"+{diff_value}" if diff_value >= 0 else f"{diff_value}"
                    else:
                        diff_formatted = None
                    
                    # Update trade to OPEN status with actual data
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE trades
                        SET status = 'open',
                            position = ?,
                            buy_price = ?,
                            fees = ?,
                            diff = ?
                        WHERE id = ?
                    """, (pos, price, round(fees_paid, 2), diff_formatted, id))
                    conn.commit()
                    conn.close()
                    
                    log_event(ticket_id, f"MANAGER: OPEN TRADE CONFIRMED — pos={pos}, price={price}, fees={fees}, diff={diff_formatted}")
                    
                    # Notify active trade supervisor about new open trade
                    notify_active_trade_supervisor(id, ticket_id, "open")
                    
                    # Notify frontend about trade database change
                    notify_frontend_trade_change()
                    
                    break
                    
        except Exception as e:
            log_event(ticket_id, f"MANAGER: OPEN TRADE WATCH DB read error: {e}")
        
        time.sleep(1)
    
    conn_pos.close()
    log_event(ticket_id, f"MANAGER: OPEN TRADE polling complete for ticker: {expected_ticker}")


def confirm_close_trade(id: int, ticket_id: str) -> None:
    """
    Confirms a CLOSING trade has been closed in the market account.
    Polls positions.db for matching ticker with zero position.
    Updates trade status to 'closed' and fills in actual sell price and PnL.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT ticker FROM trades WHERE id = ?", (id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        log_event(ticket_id, f"MANAGER: No trade found for ID {id}")
        return
    
    expected_ticker = row[0]
    
    # Use centralized paths for positions database
    mode = get_account_mode()
    POSITIONS_DB_PATH = os.path.join(get_accounts_data_dir(), "kalshi", mode, "positions.db")
    
    if not os.path.exists(POSITIONS_DB_PATH):
        log_event(ticket_id, f"MANAGER: positions.db not found at {POSITIONS_DB_PATH}")
        return
    
    # Poll for position to be zeroed out
    max_attempts = 15  # 15 seconds
    attempt = 0
    
    while attempt < max_attempts:
        try:
            conn_pos = sqlite3.connect(POSITIONS_DB_PATH, timeout=0.25)
            cursor_pos = conn_pos.cursor()
            cursor_pos.execute("SELECT position FROM positions WHERE ticker = ?", (expected_ticker,))
            row = cursor_pos.fetchone()
            conn_pos.close()
            
            if row and row[0] == 0:
                # Position has been zeroed out - confirm the close
                log_event(ticket_id, f"MANAGER: POSITION ZEROED OUT for {expected_ticker}")
                
                # Get current time for closed_at
                now_est = datetime.now(ZoneInfo("America/New_York"))
                closed_at = now_est.strftime("%H:%M:%S")
                
                # Get fees_paid from positions.db for this ticker
                conn_pos = sqlite3.connect(POSITIONS_DB_PATH, timeout=0.25)
                cursor_pos = conn_pos.cursor()
                cursor_pos.execute("SELECT fees_paid FROM positions WHERE ticker = ?", (expected_ticker,))
                fees_row = cursor_pos.fetchone()
                conn_pos.close()
                
                # Get the total fees_paid from positions.db
                total_fees_paid = float(fees_row[0]) if fees_row and fees_row[0] is not None else 0.0
                
                # Get the original trade side to determine which price to use
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT side FROM trades WHERE id = ?", (id,))
                side_row = cursor.fetchone()
                conn.close()
                
                original_side = side_row[0] if side_row else None
                
                # Get the actual sell price from fills.db using centralized paths
                FILLS_DB_PATH = os.path.join(get_accounts_data_dir(), "kalshi", mode, "fills.db")
                
                sell_price = 999  # Default fallback
                
                if os.path.exists(FILLS_DB_PATH):
                    conn_fills = sqlite3.connect(FILLS_DB_PATH, timeout=0.25)
                    cursor_fills = conn_fills.cursor()
                    
                    # Look for fills with the OPPOSITE side of the original trade
                    # YES trade closes by buying NO, NO trade closes by buying YES
                    opposite_side = 'no' if original_side == 'Y' else 'yes'
                    
                    # Get fills for this ticker with the opposite side, ordered by most recent
                    cursor_fills.execute("""
                        SELECT yes_price, no_price, created_time, side 
                        FROM fills 
                        WHERE ticker = ? AND side = ? 
                        ORDER BY created_time DESC 
                        LIMIT 1
                    """, (expected_ticker, opposite_side))
                    fill_row = cursor_fills.fetchone()
                    conn_fills.close()
                    
                    if fill_row and original_side:
                        yes_price, no_price, fill_time, fill_side = fill_row
                        
                        # Use the price for the opposite side (the side we're buying to close)
                        # Sell price should be 1 - the price we're paying to close
                        if original_side == 'Y':  # Original was YES, so use NO price (we're buying NO to close)
                            sell_price = 1 - float(no_price)
                        elif original_side == 'N':  # Original was NO, so use YES price (we're buying YES to close)
                            sell_price = 1 - float(yes_price)
                        
                        log_event(ticket_id, f"MANAGER: Found closing fill at {fill_time} - side={fill_side}, yes_price={yes_price}, no_price={no_price}, using sell_price={sell_price}")
                    else:
                        # If no opposite-side fill found, wait and retry
                        log_event(ticket_id, f"MANAGER: No closing fill found for {opposite_side} side yet, waiting...")
                        conn_fills.close()
                        time.sleep(1)  # Wait 1 second before next check
                        continue
                
                # Get current symbol price from API for symbol_close
                symbol_close = None
                try:
                    # Get current BTC price from the API
                    from active_trade_supervisor import get_current_btc_price
                    symbol_close = get_current_btc_price()
                    log_event(ticket_id, f"MANAGER: Retrieved current symbol price for close: {symbol_close}")
                except Exception as e:
                    log_event(ticket_id, f"MANAGER: Failed to get current symbol price: {e}")
                    symbol_close = None
                
                # Calculate PnL with fees included
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT buy_price, position FROM trades WHERE id = ?", (id,))
                trade_data = cursor.fetchone()
                conn.close()
                
                if trade_data:
                    buy_price, position = trade_data
                    # Calculate PnL with fees: (sell_price - buy_price) * position - fees
                    buy_value = buy_price * position
                    sell_value = sell_price * position
                    fees = total_fees_paid if total_fees_paid is not None else 0.0
                    pnl = round(sell_value - buy_value - fees, 2)
                    
                    # Determine win/loss
                    win_loss = "W" if pnl > 0 else "L" if pnl < 0 else "D"
                    
                    # Get the close_method from the trade record
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("SELECT close_method FROM trades WHERE id = ?", (id,))
                    close_method_row = cursor.fetchone()
                    close_method = close_method_row[0] if close_method_row else "manual"
                    conn.close()
                    
                    # Update trade status to closed with correct PnL calculation
                    update_trade_status(id, "closed", closed_at, sell_price, symbol_close, win_loss, pnl, close_method)
                    
                    # Update the FEES column in trades.db with total_fees_paid
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute("UPDATE trades SET fees = ? WHERE id = ?", (total_fees_paid, id))
                    conn.commit()
                    conn.close()
                    
                    log_event(ticket_id, f"MANAGER: CLOSE TRADE CONFIRMED - PnL: {pnl}, W/L: {win_loss}, Fees: {total_fees_paid}")
                    log(f"[✅ CLOSE TRADE CONFIRMED] id={id}, ticker={expected_ticker}, PnL={pnl}, W/L={win_loss}, Fees={total_fees_paid}")
                    notify_active_trade_supervisor(id, ticket_id, "closed")
                    return
                else:
                    log_event(ticket_id, f"MANAGER: Could not get trade data for PnL calculation")
                    return
            else:
                position_value = row[0] if row else "None"
                log_event(ticket_id, f"MANAGER: Waiting for position to zero out... Current: {position_value}")
                
        except Exception as e:
            log_event(ticket_id, f"MANAGER: Error checking position: {e}")
        
        attempt += 1
        time.sleep(1)  # Wait 1 second before next check
    
    # If we get here, position was never zeroed out
    log_event(ticket_id, f"MANAGER: TIMEOUT - Position never zeroed out for {expected_ticker}")
    log(f"[❌ CLOSE TRADE TIMEOUT] id={id}, ticker={expected_ticker}")


def finalize_trade(id: int, ticket_id: str) -> None:
    """
    Called only after executor says 'accepted'.
    Immediately sets status to 'open', no fill checking.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    # Removed immediate status='open' update; will update after fill is confirmed.
    conn.commit()
    conn.close()

    # Begin polling positions.db for matching ticker
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT ticker FROM trades WHERE id = ?", (id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        log_event(ticket_id, f"MANAGER: No trade found for ID {id}")
        return
    expected_ticker = row[0]
    
    # Use centralized paths for positions database
    mode = get_account_mode()
    POSITIONS_DB_PATH = os.path.join(get_accounts_data_dir(), "kalshi", mode, "positions.db")
    
    if not os.path.exists(POSITIONS_DB_PATH):
        log_event(ticket_id, f"MANAGER: Positions DB path not found: {POSITIONS_DB_PATH}")
        return
    conn_pos = sqlite3.connect(POSITIONS_DB_PATH, timeout=0.25)
    cursor_pos = conn_pos.cursor()
    deadline = time.time() + 15
    while time.time() < deadline:
        try:
            cursor_pos.execute("SELECT position, market_exposure, fees_paid FROM positions WHERE ticker = ?", (expected_ticker,))
            row = cursor_pos.fetchone()
            pos = abs(row[0]) if row else 0
            exposure = abs(row[1]) if row else 0
            fees_paid = float(row[2]) if row and row[2] is not None else 0.0
            price = round(float(exposure) / float(pos) / 100, 2) if pos > 0 else 0.0
            fees = round(fees_paid / 100, 2)

            # ------------------------------------------------------------------
            # Decide what to do based on the latest trade status
            # ------------------------------------------------------------------
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT status FROM trades WHERE id=?", (id,))
            status_row = cursor.fetchone()
            current_status = status_row[0] if status_row else None
            conn.close()

            # ❶ If trade is still pending, finalize once position appears
            if current_status == "pending" and pos > 0 and exposure > 0:
                # Calculate DIFF: PROB - BUY (formatted as whole integer)
                # Get the prob value from the trade
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT prob FROM trades WHERE id = ?", (id,))
                prob_row = cursor.fetchone()
                conn.close()
                
                prob_value = prob_row[0] if prob_row and prob_row[0] is not None else None
                diff_value = None
                
                if prob_value is not None:
                    # Convert prob from percentage to decimal (96.7 -> 0.967)
                    prob_decimal = float(prob_value) / 100
                    # Calculate diff: prob_decimal - buy_price
                    diff_decimal = prob_decimal - price
                    # Convert to whole integer (0.02 -> +2, -0.03 -> -3)
                    diff_value = int(round(diff_decimal * 100))
                    # Format as string with sign
                    diff_formatted = f"+{diff_value}" if diff_value >= 0 else f"{diff_value}"
                else:
                    diff_formatted = None
                
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE trades
                    SET status = 'open',
                        position = ?,
                        buy_price = ?,
                        fees      = ?,
                        diff      = ?
                    WHERE id = ?
                """, (pos, price, round(fees_paid, 2), diff_formatted, id))
                conn.commit()
                conn.close()
                log_event(ticket_id, f"MANAGER: FILL CONFIRMED — pos={pos}, price={price}, fees={fees}, diff={diff_formatted}")
                
                # Notify active trade supervisor about new open trade
                notify_active_trade_supervisor(id, ticket_id, "open")
                
                break

            # ❷ If trade is closing, wait until position is zero (row missing or pos == 0)
            elif current_status == "closing" and (row is None or pos == 0):
                conn = get_db_connection()
                cursor = conn.cursor()
                closed_at = datetime.now(ZoneInfo("America/New_York")).strftime("%H:%M:%S")
                
                # Get trade data for PnL and win_loss calculation
                cursor.execute("SELECT buy_price, position, side, ticket_id FROM trades WHERE ticker = ? AND status = 'closing'", (expected_ticker,))
                trade_row = cursor.fetchone()
                if trade_row:
                    buy_price, position, side, ticket_id = trade_row
                    
                    # Calculate actual sell price from fills.db
                    actual_sell_price = None
                    try:
                        # fills.db is in the prod directory
                        FILLS_DB_PATH = os.path.join(get_accounts_data_dir(), "kalshi", mode, "fills.db")
                        
                        if os.path.exists(FILLS_DB_PATH):
                            conn_fills = sqlite3.connect(FILLS_DB_PATH, timeout=0.25)
                            cursor_fills = conn_fills.cursor()
                            
                            # For closing trades: match by ticker and opposite side
                            # YES trade closes by buying NO, NO trade closes by buying YES
                            opposite_side = 'no' if side == 'Y' else 'yes'
                            
                            # Get fills in reverse chronological order (latest first)
                            cursor_fills.execute("SELECT yes_price, no_price, count FROM fills WHERE ticker = ? AND side = ? AND action = 'buy' ORDER BY rowid DESC", (expected_ticker, opposite_side))
                            fills = cursor_fills.fetchall()
                            
                            if fills:
                                total_value = 0
                                total_count = 0
                                fills_used = []
                                
                                # Work backwards through fills until we have enough to match the original position
                                for fill in fills:
                                    yes_price, no_price, count = fill
                                    # Use the opposite side's price
                                    price = no_price if side == 'Y' else yes_price
                                    
                                    # Add this fill to our calculation
                                    fills_used.append((price, count))
                                    total_value += price * count
                                    total_count += count
                                    
                                    # Stop when we have enough fills to match the original position
                                    if total_count >= position:
                                        break
                                
                                if total_count > 0:
                                    actual_sell_price = total_value / total_count
                                    log_event(ticket_id, f"MANAGER: Found {len(fills_used)} fills for closing trade (position={position}), calculated weighted average sell price: {actual_sell_price}")
                                else:
                                    log_event(ticket_id, f"MANAGER: No valid fills found for closing trade")
                            else:
                                log_event(ticket_id, f"MANAGER: No fills found for ticker={expected_ticker}, side={opposite_side}, action=buy")
                            
                            conn_fills.close()
                        else:
                            log_event(ticket_id, f"MANAGER: fills.db not found at {FILLS_DB_PATH}")
                    except Exception as e:
                        log_event(ticket_id, f"MANAGER: Error querying fills.db: {str(e)}")
                    
                    # Use actual sell price from fills if available, otherwise write NULL
                    final_sell_price = actual_sell_price
                    
                    # Calculate PnL only if we have a valid sell price
                    pnl = None
                    win_loss = None
                    if buy_price is not None and final_sell_price is not None and position is not None:
                        buy_value = buy_price * position
                        sell_value = final_sell_price * position
                        fees = round(fees_paid, 2) if fees_paid is not None else 0.0
                        pnl = round(sell_value - buy_value - fees, 2)
                        win_loss = 'W' if final_sell_price > buy_price else 'L'
                        
                        if actual_sell_price is not None:
                            log_event(ticket_id, f"MANAGER: Using fills-derived sell price {final_sell_price} for PnL calculation")
                        else:
                            log_event(ticket_id, f"MANAGER: No valid sell price from fills, PnL will be NULL")
                    else:
                        log_event(ticket_id, f"MANAGER: Missing required data for PnL calculation")
                    
                    # Use NULL for sell_price if no valid price found
                    sell_price_for_db = final_sell_price if final_sell_price is not None else None
                    
                    cursor.execute("""
                        UPDATE trades
                        SET status    = 'closed',
                            closed_at = ?,
                            sell_price = ?,
                            fees      = COALESCE(fees, 0) + ?,
                            pnl       = ?,
                            win_loss  = ?
                        WHERE ticker = ? AND status = 'closing'
                    """, (closed_at, sell_price_for_db, round(fees_paid, 2), pnl, win_loss, expected_ticker))
                    
                    conn.commit()
                    conn.close()
                    
                    log_event(ticket_id, f"MANAGER: Trade finalized with sell_price={sell_price_for_db}, pnl={pnl}, win_loss={win_loss}")
                    notify_active_trade_supervisor(id, ticket_id, "closed")
                else:
                    log_event(ticket_id, f"MANAGER: No trade found for ticker {expected_ticker}")
        except Exception as e:
            log_event(ticket_id, f"MANAGER: FILL WATCH DB read error: {e}")
        time.sleep(1)
    conn_pos.close()
    log_event(ticket_id, f"MANAGER: FILL WATCH polling complete for ticker: {expected_ticker}")

from fastapi import APIRouter, HTTPException, status, Request
router = APIRouter()

# Port information endpoint
@router.get("/api/ports")
async def get_ports():
    """Get all port assignments from centralized system."""
    return get_port_info()


@router.post("/api/ping_fill_watch")
async def ping_fill_watch():
    """
    Trigger a re-check of open trades that may be missing fill data.
    This is a lightweight endpoint for account_sync to notify us of possible changes.
    """
    log("[PING] Received ping from account_sync — checking for missing fills")
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, ticket_id, position, buy_price FROM trades WHERE status IN ('open', 'pending')")
    rows = cursor.fetchall()
    conn.close()

    for row in rows:
        id, ticket_id, pos, price = row
        if not pos or not price:
            log(f"[PING] Found unfilled trade — id={id}, ticket_id={ticket_id}")
            threading.Thread(target=finalize_trade, args=(id, ticket_id), daemon=True).start()

    return {"message": "Ping received, checking unfilled trades"}


# New endpoint: ping_settlement_watch
@router.post("/api/ping_settlement_watch")
async def ping_settlement_watch():
    """
    Called when account_sync confirms new entries in settlements.db.
    If any expired trades are still unfinalized, finalize them now.
    """
    log("[PING] Received ping from account_sync — checking for expired trades")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, ticket_id FROM trades WHERE status = 'expired'")
    expired_trades = cursor.fetchall()
    conn.close()

    for id, ticket_id in expired_trades:
        log(f"[PING] Triggering finalize_trade for expired trade id={id}")
        threading.Thread(target=finalize_trade, args=(id, ticket_id), daemon=True).start()

    return {"message": f"Triggered finalize_trade for {len(expired_trades)} expired trades"}

@router.post("/api/manual_expiration_check")
async def manual_expiration_check():
    """
    Manually trigger the expiration check - marks all open trades as expired
    """
    log("[MANUAL] Manual expiration check triggered")
    
    # Run the expiration check in a separate thread to avoid blocking
    threading.Thread(target=check_expired_trades, daemon=True).start()
    
    return {"message": "Manual expiration check triggered"}

def log(msg):
    """Log messages with timestamp"""
    timestamp = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[TRADE_MANAGER {timestamp}] {msg}")
    
    # Also write to a dedicated log file for easy tailing
    try:
        log_path = os.path.join(get_logs_dir(), "trade_manager.out.log")
        with open(log_path, "a") as f:
            f.write(f"{datetime.now().isoformat()} | {msg}\n")
    except Exception as e:
        print(f"Error writing to log file: {e}")

def log_event(ticket_id, message):
    try:
        trade_suffix = ticket_id[-5:] if len(ticket_id) >= 5 else ticket_id
        log_path = os.path.join(get_trade_history_dir(), "tickets", f"trade_flow_{trade_suffix}.log")
        timestamp = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M:%S")
        log_line = f"[{timestamp}] Ticket {ticket_id[-5:]}: {message}\n"
        with open(log_path, "a") as f:
            f.write(log_line)
    except Exception as e:
        print(f"[LOG ERROR] Failed to write log: {message} — {e}")

def notify_active_trade_supervisor(trade_id: int, ticket_id: str, status: str) -> None:
    """
    Notify the active trade supervisor about a trade status change.
    Calls the active trade supervisor to add or remove the trade as needed.
    """
    try:
        from active_trade_supervisor import add_new_active_trade, remove_closed_trade, update_trade_status_to_closing
        if status == "open":
            success = add_new_active_trade(trade_id, ticket_id)
            if success:
                log(f"✅ Notified active trade supervisor about new open trade: id={trade_id}, ticket_id={ticket_id}")
            else:
                log(f"⚠️ Failed to notify active trade supervisor about trade: id={trade_id}, ticket_id={ticket_id}")
        elif status == "closing":
            success = update_trade_status_to_closing(trade_id)
            if success:
                log(f"✅ Notified active trade supervisor to update trade status to closing: id={trade_id}, ticket_id={ticket_id}")
            else:
                log(f"⚠️ Failed to notify active trade supervisor to update trade status: id={trade_id}, ticket_id={ticket_id}")
        elif status in ("closed", "expired"):
            success = remove_closed_trade(trade_id)
            if success:
                log(f"✅ Notified active trade supervisor to remove closed/expired trade: id={trade_id}, ticket_id={ticket_id}")
            else:
                log(f"⚠️ Failed to notify active trade supervisor to remove trade: id={trade_id}, ticket_id={ticket_id}")
    except ImportError:
        log(f"⚠️ Active trade supervisor not available - skipping notification for trade: id={trade_id}")
    except Exception as e:
        log(f"❌ Error notifying active trade supervisor: {e}")

def notify_frontend_trade_change() -> None:
    """
    Send notification to frontend when trades.db is updated.
    This triggers the trade history page to refresh.
    """
    try:
        import aiohttp
        import asyncio
        import threading
        
        def send_notification_sync():
            """Send notification in a separate thread to avoid event loop conflicts"""
            try:
                import requests
                from backend.util.paths import get_host
                notification_url = f"http://{get_host()}:{config.get('main_app_port', 3000)}/api/notify_db_change"
                payload = {
                    "db_name": "trades",
                    "timestamp": time.time(),
                    "change_data": {"trades": 1}
                }
                
                response = requests.post(notification_url, json=payload, timeout=2)
                if response.status_code == 200:
                    log("✅ Notified frontend about trade database change")
                else:
                    log(f"⚠️ Failed to notify frontend about trade change: {response.status_code}")
            except Exception as e:
                log(f"❌ Error sending trade change notification: {e}")
        
        # Run the notification in a separate thread to avoid event loop conflicts
        thread = threading.Thread(target=send_notification_sync)
        thread.daemon = True
        thread.start()
            
    except ImportError:
        log("⚠️ requests not available - skipping frontend notification")
    except Exception as e:
        log(f"❌ Error in trade change notification: {e}")

def is_trade_expired(trade):
    contract = trade.get('contract', '')
    if not contract:
        return False
    match = re.search(r'BTC\s+(\d{1,2})(am|pm)', contract, re.IGNORECASE)
    if not match:
        return False
    hour = int(match.group(1))
    ampm = match.group(2).lower()
    if ampm == 'pm' and hour != 12:
        hour += 12
    elif ampm == 'am' and hour == 12:
        hour = 0
    now = datetime.now(ZoneInfo('America/New_York'))
    expiration = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    return now >= expiration


# Define path for the trades database file using centralized paths
DB_TRADES_PATH = os.path.join(get_trade_history_dir(), "trades.db")

# Initialize trades DB and table
def init_trades_db():
    # Ensure the parent directory exists
    os.makedirs(os.path.dirname(DB_TRADES_PATH), exist_ok=True)
    
    conn = sqlite3.connect(DB_TRADES_PATH)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        time TEXT NOT NULL,
        strike TEXT NOT NULL,
        side TEXT NOT NULL,
        buy_price REAL NOT NULL,
        position INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'open',
        closed_at TEXT DEFAULT NULL,
        contract TEXT DEFAULT NULL,
        sell_price REAL DEFAULT NULL,
        pnl REAL DEFAULT NULL,
        symbol TEXT DEFAULT NULL,
        market TEXT DEFAULT NULL,
        trade_strategy TEXT DEFAULT NULL,
        symbol_open REAL DEFAULT NULL,
        momentum REAL DEFAULT NULL,
        prob REAL DEFAULT NULL,
        volatility REAL DEFAULT NULL,
        symbol_close REAL DEFAULT NULL,
        win_loss TEXT DEFAULT NULL,
        ticker TEXT DEFAULT NULL,
        fees REAL DEFAULT NULL,
        entry_method TEXT DEFAULT 'manual',
        close_method TEXT DEFAULT NULL
    )
    """)
    conn.commit()
    conn.close()

init_trades_db()

# Short timeout so UI requests don't hang if the DB is locked.
def get_db_connection():
    # check_same_thread=False lets each thread safely open its *own* connection.
    return sqlite3.connect(DB_TRADES_PATH, timeout=0.25, check_same_thread=False)

# Very small, read‑only query used by the background monitor so it
# doesn't contend with the UI's full SELECT call.
def fetch_open_trades_light():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, contract FROM trades WHERE status = 'open'")
    rows = cursor.fetchall()
    conn.close()
    return [{"id": row[0], "contract": row[1]} for row in rows]

def fetch_open_trades():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, date, time, strike, side, buy_price, position, status, contract FROM trades WHERE status = 'open'")
    rows = cursor.fetchall()
    conn.close()
    return [dict(zip(["id","date","time","strike","side","buy_price","position","status","contract"], row)) for row in rows]

def fetch_all_trades():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM trades ORDER BY id DESC")
    rows = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]
    conn.close()
    return [dict(zip(columns, row)) for row in rows]

def truncate_contract_name(contract_name):
    """Truncate contract name to short form like 'BTC 5pm'"""
    if not contract_name:
        return contract_name
    
    # If it's already in short form (like "BTC 5pm"), return as-is
    if contract_name.startswith("BTC ") and len(contract_name) < 20:
        return contract_name
    
    # Extract time from full title like "Bitcoin price on Jul 24, 2025 at 5pm EDT?"
    # Look for patterns like "at 5pm", "at 4pm", etc.
    import re
    time_match = re.search(r'at (\d+)(am|pm)', contract_name, re.IGNORECASE)
    if time_match:
        hour = time_match.group(1)
        ampm = time_match.group(2).lower()
        return f"BTC {hour}{ampm}"
    
    # Fallback: return as-is if we can't parse it
    return contract_name

def insert_trade(trade):
    log(f"[DEBUG] TRADES DB PATH (insert_trade): {DB_TRADES_PATH}")
    print("[DEBUG] Inserting trade data:", trade)
    
    # ALWAYS get current BTC price for symbol_open
    try:
        btc_price_log = os.path.join(get_data_dir(), "coinbase", "btc_price_log.txt")
        if os.path.exists(btc_price_log):
            with open(btc_price_log, 'r') as f:
                lines = f.readlines()
                if lines:
                    last_line = lines[-1].strip()
                    # Extract price from format: "2025-07-24T15:45:12 | $119,098.68"
                    if " | $" in last_line:
                        price_str = last_line.split(" | $")[1]
                        symbol_open = float(price_str.replace(",", ""))
                        print(f"[TRADE_MANAGER] Got symbol_open from log: {symbol_open}")
                    else:
                        print(f"[TRADE_MANAGER] Warning: Could not parse price from log line: {last_line}")
                        symbol_open = None
                else:
                    print(f"[TRADE_MANAGER] Warning: BTC price log is empty")
                    symbol_open = None
        else:
            print(f"[TRADE_MANAGER] Warning: BTC price log not found: {btc_price_log}")
            symbol_open = None
    except Exception as e:
        print(f"[TRADE_MANAGER] Error getting BTC price: {e}")
        symbol_open = None
    
    # Get current momentum from API and format it correctly for database
    momentum_for_db = None
    try:
        # Get momentum from live_data_analysis API
        from live_data_analysis import get_momentum_data
        momentum_data = get_momentum_data()
        momentum_score = momentum_data.get('weighted_momentum_score', 0)
        
        # Format as whole number with +/- sign (e.g., 0.0621 becomes "+6", -0.0501 becomes "-5")
        if momentum_score != 0:
            momentum_whole = round(momentum_score * 100)
            momentum_for_db = f"{'+' if momentum_whole > 0 else ''}{momentum_whole}"
        else:
            momentum_for_db = "0"
            
        print(f"[MOMENTUM] Raw: {momentum_score}, Formatted for DB: {momentum_for_db}")
    except Exception as e:
        print(f"[MOMENTUM] Error getting momentum: {e}")
        momentum_for_db = "0"
    
    conn = get_db_connection()
    cursor = conn.cursor()
    # Truncate contract name to short form
    contract_name = truncate_contract_name(trade.get('contract'))
    
    cursor.execute(
        """INSERT INTO trades (
            date, time, strike, side, buy_price, position, status,
            contract, ticker, symbol, market, trade_strategy, symbol_open,
            momentum, prob, volatility, ticket_id, entry_method
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            trade['date'], trade['time'], trade['strike'], trade['side'], trade['buy_price'],
            trade['position'], trade.get('status', 'open'), contract_name,
            trade.get('ticker'), trade.get('symbol'), trade.get('market'), trade.get('trade_strategy'),
            symbol_open, momentum_for_db, trade.get('prob'),
            trade.get('volatility'), trade.get('ticket_id'), trade.get('entry_method', 'manual')
        )
    )
    conn.commit()
    last_id = cursor.lastrowid
    conn.close()
    
    # Notify frontend about trade database change
    notify_frontend_trade_change()
    
    return last_id

def update_trade_status(trade_id, status, closed_at=None, sell_price=None, symbol_close=None, win_loss=None, pnl=None, close_method=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    if status == 'closed':
        if closed_at is None:
            utc_now = datetime.utcnow().replace(tzinfo=ZoneInfo("UTC"))
            est_now = utc_now.astimezone(ZoneInfo("America/New_York"))
            closed_at = est_now.isoformat()

        # If PnL is already calculated and passed in, use it
        if pnl is not None:
            calculated_pnl = pnl
        else:
            # Fetch trade data for PnL calculation
            cursor.execute("SELECT buy_price, position, fees FROM trades WHERE id = ?", (trade_id,))
            row = cursor.fetchone()
            buy_price = row[0] if row else None
            position = row[1] if row else None
            fees_paid = row[2] if row else 0.0

            # Calculate win/loss
            if buy_price is not None and sell_price is not None:
                win_loss = 'W' if sell_price > buy_price else 'L'
            else:
                win_loss = None

            # Calculate PnL with fees included
            calculated_pnl = None
            if buy_price is not None and sell_price is not None and position is not None:
                buy_value = buy_price * position
                sell_value = sell_price * position
                fees = fees_paid if fees_paid is not None else 0.0
                calculated_pnl = round(sell_value - buy_value - fees, 2)

        cursor.execute(
            "UPDATE trades SET status = ?, closed_at = ?, sell_price = ?, symbol_close = ?, win_loss = ?, pnl = ?, close_method = ? WHERE id = ?",
            (status, closed_at, sell_price, symbol_close, win_loss, calculated_pnl, close_method, trade_id)
        )
    else:
        cursor.execute("UPDATE trades SET status = ? WHERE id = ?", (status, trade_id))
    conn.commit()
    conn.close()
    
    # Notify frontend about trade database change
    notify_frontend_trade_change()

def delete_trade(trade_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM trades WHERE id = ?", (trade_id,))
    conn.commit()
    conn.close()
    
    # Notify frontend about trade database change
    notify_frontend_trade_change()

def fetch_recent_closed_trades(hours=24):
    conn = get_db_connection()
    cursor = conn.cursor()
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    cutoff_iso = cutoff.isoformat()
    cursor.execute("""
        SELECT id, date, time, strike, side, buy_price, position, status, closed_at, contract, sell_price, pnl, win_loss
        FROM trades
        WHERE status = 'closed' AND closed_at >= ?
        ORDER BY closed_at DESC
    """, (cutoff_iso,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(zip(["id","date","time","strike","side","buy_price","position","status","closed_at","contract","sell_price","pnl","win_loss"], row)) for row in rows]

# API routes for trade management

@router.get("/trades")
def get_trades(status: str = None, recent_hours: int = None):
    import time
    start_time = time.time()
    if status == "open":
        result = fetch_open_trades()
        print(f"[DEBUG] /trades?status={status} responded in {time.time() - start_time:.3f} sec")
        return result
    elif status == "closed" and recent_hours:
        result = fetch_recent_closed_trades(recent_hours)
        print(f"[DEBUG] /trades?status={status}&recent_hours={recent_hours} responded in {time.time() - start_time:.3f} sec")
        return result
    elif status == "closed":
        result = [t for t in fetch_all_trades() if t["status"] == "closed"]
        print(f"[DEBUG] /trades?status={status} responded in {time.time() - start_time:.3f} sec")
        return result
    result = fetch_all_trades()
    print(f"[DEBUG] /trades?status={status} responded in {time.time() - start_time:.3f} sec")
    return result

@router.post("/trades", status_code=status.HTTP_201_CREATED)
async def add_trade(request: Request):
    data = await request.json()
    intent = data.get("intent", "open").lower()
    if intent == "close":
        print("[TRADE_MANAGER] 🔴 CLOSE TICKET RECEIVED")
        print("[TRADE_MANAGER] Close Payload:", data)
        log(f"[TRADE_MANAGER] 🔴 CLOSE TICKET RECEIVED — Payload: {data}")
        ticker = data.get("ticker")
        if ticker:
            conn = get_db_connection()
            cursor = conn.cursor()
            sell_price = data.get("buy_price")
            symbol_close = data.get("symbol_close")
            close_method = data.get("close_method", "manual")
            cursor.execute("UPDATE trades SET status = 'closing', symbol_close = ?, close_method = ? WHERE ticker = ?", (symbol_close, close_method, ticker))
            conn.commit()
            conn.close()
            log(f"[DEBUG] Trade status set to 'closing' for ticker: {ticker}")
            
            # Notify frontend about trade database change
            notify_frontend_trade_change()
            
            # Notify active trade supervisor about the closing status
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM trades WHERE ticker = ?", (ticker,))
            row = cursor.fetchone()
            conn.close()
            
            if row:
                trade_id = row[0]
                notify_active_trade_supervisor(trade_id, data.get('ticket_id'), "closing")
            
            # Confirm close match in positions.db
            try:
                # Use centralized paths for positions database
                mode = get_account_mode()
                POSITIONS_DB_PATH = os.path.join(get_accounts_data_dir(), "kalshi", mode, "positions.db")

                if os.path.exists(POSITIONS_DB_PATH):
                    conn_pos = sqlite3.connect(POSITIONS_DB_PATH, timeout=0.25)
                    cursor_pos = conn_pos.cursor()
                    cursor_pos.execute("SELECT position FROM positions WHERE ticker = ?", (ticker,))
                    row = cursor_pos.fetchone()
                    conn_pos.close()

                    if row:
                        pos_db = abs(row[0])
                        conn = get_db_connection()
                        cursor = conn.cursor()
                        cursor.execute("SELECT position FROM trades WHERE ticker = ?", (ticker,))
                        trade_row = cursor.fetchone()
                        conn.close()

                        if trade_row and abs(trade_row[0]) == pos_db:
                            log(f"[CLOSE CHECK] ✅ Confirmed matching position for {ticker} — abs(pos) = {pos_db}")
                        else:
                            log(f"[CLOSE CHECK] ❌ Mismatch for {ticker}: trades.db = {abs(trade_row[0]) if trade_row else 'None'}, positions.db = {pos_db}")
                    else:
                        log(f"[CLOSE CHECK] ⚠️ No matching entry in positions.db for ticker: {ticker}")
                else:
                    log(f"[CLOSE CHECK] ❌ positions.db not found: {POSITIONS_DB_PATH}")
            except Exception as e:
                log(f"[CLOSE CHECK ERROR] Exception while checking close match for {ticker}: {e}")

            # --- Send close ticket to executor and handle response ---
            try:
                executor_port = get_executor_port()
                log(f"[CLOSE EXECUTOR] Sending close trade to executor on port {executor_port}")
                close_payload = {
                    "ticker": ticker,
                    "side": data.get("side"),
                    "count": data.get("count"),
                    "action": "close",
                    "type": "market",
                    "time_in_force": "IOC",
                    "buy_price": sell_price,
                    "symbol_close": symbol_close,
                    "intent": "close"
                }
                response = requests.post(f"http://{get_host()}:{executor_port}/trigger_trade", json=close_payload, timeout=5)
                log(f"[CLOSE EXECUTOR] Executor responded with {response.status_code}: {response.text}")
            except Exception as e:
                log(f"[CLOSE EXECUTOR ERROR] Failed to send close trade to executor: {e}")

            # --- Ensure confirm_close_trade runs after close ticket is sent ---
            ticker = data.get("ticker")
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM trades WHERE ticker = ?", (ticker,))
            row = cursor.fetchone()
            conn.close()

            if row:
                trade_id = row[0]
                log(f"[🧵 STARTING CONFIRM CLOSE TRADE THREAD] id={trade_id}, ticket_id={data.get('ticket_id')}")
                threading.Thread(target=confirm_close_trade, args=(trade_id, data.get("ticket_id")), daemon=True).start()
            else:
                log(f"[CONFIRM CLOSE THREAD ERROR] Could not find trade id for ticker: {ticker}")

        return {"message": "Close ticket received and processed"}
    log("✅ /trades POST route triggered successfully")
    print("✅ TRADE MANAGER received POST")
    required_fields = {"date", "time", "strike", "side", "buy_price", "position"}
    if not required_fields.issubset(data.keys()):
        raise HTTPException(status_code=400, detail="Missing required trade fields")

    # Ensure the "time" field is recorded in EST in HH:MM:SS format
    now_est = datetime.now(ZoneInfo("America/New_York"))
    data["time"] = now_est.strftime("%H:%M:%S")

    trade_id = create_pending_trade(data)
    log_event(data["ticket_id"], "MANAGER: SENT TO EXECUTOR — CONFIRMED")

    try:
        executor_port = get_executor_port()
        log(f"📤 SENDING TO EXECUTOR on port {executor_port}")
        log(f"📤 FULL URL: http://{get_host()}:{executor_port}/trigger_trade")
        response = requests.post(f"http://{get_host()}:{executor_port}/trigger_trade", json=data, timeout=5)
        print(f"[EXECUTOR RESPONSE] {response.status_code} — {response.text}")
        # Do not mark as open or error here; status update will come from executor via /api/update_trade_status
    except Exception as e:
        log(f"[❌ EXECUTOR ERROR] Failed to send trade to executor: {e}")
        log_event(data["ticket_id"], f"❌ EXECUTOR ERROR: {e}")

    return {"id": trade_id}

# Route to fetch an individual trade by ID
@router.get("/trades/{trade_id}")
def get_trade(trade_id: int):
    conn = sqlite3.connect(DB_TRADES_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM trades WHERE id = ?", (trade_id,))
    row = cursor.fetchone()
    if row is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Trade not found")
    columns = [desc[0] for desc in cursor.description]
    conn.close()
    return dict(zip(columns, row))

@router.put("/trades/{trade_id}")
async def update_trade(trade_id: int, request: Request):
    data = await request.json()
    if "status" not in data:
        raise HTTPException(status_code=400, detail="Missing 'status' field for update")
    closed_at = data.get("closed_at")
    sell_price = data.get("sell_price")
    symbol_close = data.get("symbol_close")
    win_loss = data.get("win_loss")
    # Update update_trade_status to accept symbol_close and win_loss
    update_trade_status(trade_id, data["status"], closed_at, sell_price, symbol_close, win_loss)
    return {"id": trade_id, "status": data["status"]}


@router.delete("/trades/{trade_id}")
def remove_trade(trade_id: int):
    delete_trade(trade_id)
    return {"id": trade_id, "deleted": True}

# Route to handle incoming fill data messages from the executor

@router.post("/api/update_trade_status")
async def update_trade_status_api(request: Request):
    log(f"📩 RECEIVED STATUS UPDATE PAYLOAD: {await request.body()}")
    data = await request.json()
    id = data.get("id")
    ticket_id = data.get("ticket_id")
    new_status = data.get("status", "").strip().lower()
    print(f"[🔥 STATUS UPDATE API HIT] ticket_id={ticket_id} | id={id} | new_status={new_status}")

    if not new_status or (not id and not ticket_id):
        raise HTTPException(status_code=400, detail="Missing id or ticket_id or status")

    # If id is not provided, try to fetch it via ticket_id
    if not id and ticket_id:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM trades WHERE ticket_id = ?", (ticket_id,))
        row = cursor.fetchone()
        conn.close()
        if not row:
            raise HTTPException(status_code=404, detail="Trade with provided ticket_id not found")
        id = row[0]

    # If ticket_id is not provided, try to fetch it via id
    if not ticket_id:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT ticket_id FROM trades WHERE id = ?", (id,))
        row = cursor.fetchone()
        conn.close()
        ticket_id = row[0] if row else None

    if new_status == "accepted":
        # Trade accepted by executor - just log it, confirmation will come from db_poller
        log(f"[✅ TRADE ACCEPTED BY EXECUTOR] id={id}, ticket_id={ticket_id}")
        log(f"[⏳ WAITING FOR POSITION CONFIRMATION FROM DB_POLLER]")
        return {"message": "Trade accepted – waiting for position confirmation", "id": id}

    elif new_status == "error":
        update_trade_status(id, "error")
        if ticket_id:
            log_event(ticket_id, "MANAGER: STATUS UPDATED — SET TO 'ERROR'")
        return {"message": "Trade marked error", "id": id}

    else:
        raise HTTPException(status_code=400, detail=f"Unrecognized status value: '{new_status}'")

@router.post("/api/positions_change")
async def positions_change_api(request: Request):
    """Endpoint for db_poller to notify about positions.db changes"""
    try:
        data = await request.json()
        db_name = data.get("database")
        log(f"[🔔 POSITIONS CHANGE] Database: {db_name} - checking for pending/closing trades")
        
        # Check for pending trades that might need confirmation (opening)
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, ticket_id FROM trades WHERE status = 'pending'")
        pending_trades = cursor.fetchall()
        conn.close()
        
        if pending_trades:
            log(f"[🔔 POSITIONS CHANGE] Found {len(pending_trades)} pending trades to confirm")
            for id, ticket_id in pending_trades:
                threading.Thread(target=confirm_open_trade, args=(id, ticket_id), daemon=True).start()
        
        # Check for closing trades that might need confirmation (closing)
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, ticket_id FROM trades WHERE status = 'closing'")
        closing_trades = cursor.fetchall()
        conn.close()
        
        if closing_trades:
            log(f"[🔔 POSITIONS CHANGE] Found {len(closing_trades)} closing trades to confirm")
            # Track which trades we've already started confirmation for
            for id, ticket_id in closing_trades:
                # Check if this trade is already being confirmed
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT status FROM trades WHERE id = ?", (id,))
                current_status = cursor.fetchone()
                conn.close()
                
                # Only start confirmation if still in 'closing' status
                if current_status and current_status[0] == 'closing':
                    threading.Thread(target=confirm_close_trade, args=(id, ticket_id), daemon=True).start()
        
        return {"message": "positions_change received"}
    except Exception as e:
        log(f"[ERROR /api/positions_change] {e}")
        return {"error": str(e)}

# Background trade monitoring thread

def check_stop_trigger(trade):
    # TODO: Implement your stop trigger logic here
    # For now, never triggers
    return False

_monitor_thread = None

def start_trade_monitor():
    # REMOVED: No longer needed since APScheduler handles expiration
    # The APScheduler is started in the FastAPI startup event
    pass

# ------------------------------------------------------------------------------
# SIMPLE HOURLY EXPIRATION CHECK
# ------------------------------------------------------------------------------
def check_expired_trades():
    """
    TRIGGER: Called at top of every hour (minute=0, second=0)
    
    LOGIC:
    1. Check for OPEN trades
    2. Mark them as EXPIRED with current time and BTC price
    3. Poll settlements.db every 2 seconds
    4. When settlements.db updates, check for matching tickers
    5. Mark matching trades as CLOSED with sell_price and W/L
    6. Stop polling when all expired trades are closed
    """
    try:
        # Step 1: Get all OPEN trades
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, ticker FROM trades WHERE status = 'open'")
        open_trades = cursor.fetchall()
        conn.close()
        
        if not open_trades:
            print("[EXPIRATION] No open trades to check")
            return
            
        print(f"[EXPIRATION] Found {len(open_trades)} open trades to expire")
        
        # Step 2: Mark all OPEN trades as EXPIRED
        now_est = datetime.now(ZoneInfo("America/New_York"))
        closed_at = now_est.strftime("%H:%M:%S")
        
        # Get current BTC price from watchdog
        try:
            import requests
            main_port = get_port("main_app")
            response = requests.get(f"http://{get_host()}:{main_port}/core", timeout=5)
            if response.ok:
                core_data = response.json()
                symbol_close = core_data.get('btc_price')
            else:
                symbol_close = None
        except Exception as e:
            print(f"[EXPIRATION] Failed to get BTC price: {e}")
            symbol_close = None
        
        # Mark trades as expired
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE trades 
            SET status = 'expired', 
                closed_at = ?, 
                symbol_close = ?,
                close_method = 'expired'
            WHERE status = 'open'
        """, (closed_at, symbol_close))
        conn.commit()
        conn.close()
        
        print(f"[EXPIRATION] Marked {len(open_trades)} trades as expired")
        
        # Notify frontend about trade database change
        notify_frontend_trade_change()
        
        # Notify active_trade_supervisor for each expired trade
        for id, ticker in open_trades:
            notify_active_trade_supervisor(id, str(ticker), "expired")
        
        # Step 3: Poll settlements.db for matches
        expired_tickers = [trade[1] for trade in open_trades]
        poll_settlements_for_matches(expired_tickers)
        
    except Exception as e:
        print(f"[EXPIRATION] Error: {e}")


def poll_settlements_for_matches(expired_tickers):
    """
    Poll settlements.db for matches to expired trades.
    Updates expired trades to closed with sell_price and PnL.
    """
    # Use centralized paths for settlements database
    mode = get_account_mode()
    SETTLEMENTS_DB_PATH = os.path.join(get_accounts_data_dir(), "kalshi", mode, "settlements.db")
    
    if not os.path.exists(SETTLEMENTS_DB_PATH):
        print(f"[SETTLEMENTS] Settlements DB not found: {SETTLEMENTS_DB_PATH}")
        return
    
    # Track which tickers we've found settlements for
    found_tickers = set()
    
    # Add timeout to prevent infinite polling (30 minutes max)
    start_time = time.time()
    timeout_seconds = 30 * 60  # 30 minutes
    
    while len(found_tickers) < len(expired_tickers):
        # Check timeout
        if time.time() - start_time > timeout_seconds:
            print(f"[SETTLEMENTS] Timeout reached after {timeout_seconds/60:.1f} minutes. Found {len(found_tickers)}/{len(expired_tickers)} settlements.")
            print(f"[SETTLEMENTS] Remaining tickers: {set(expired_tickers) - found_tickers}")
            break
            
        try:
            conn = sqlite3.connect(SETTLEMENTS_DB_PATH, timeout=0.25)
            cursor = conn.cursor()
            
            # Check for new settlements matching our expired tickers
            for ticker in expired_tickers:
                if ticker in found_tickers:
                    continue
                    
                cursor.execute("SELECT revenue FROM settlements WHERE ticker = ? ORDER BY settled_time DESC LIMIT 1", (ticker,))
                row = cursor.fetchone()
                
                if row:
                    revenue = row[0]
                    sell_price = 1.00 if revenue > 0 else 0.00
                    
                    # Get fees from positions.db for this ticker using centralized paths
                    POSITIONS_DB_PATH = os.path.join(get_accounts_data_dir(), "kalshi", mode, "positions.db")
                    
                    total_fees_paid = 0.0
                    if os.path.exists(POSITIONS_DB_PATH):
                        conn_pos = sqlite3.connect(POSITIONS_DB_PATH, timeout=0.25)
                        cursor_pos = conn_pos.cursor()
                        cursor_pos.execute("SELECT fees_paid FROM positions WHERE ticker = ?", (ticker,))
                        fees_row = cursor_pos.fetchone()
                        conn_pos.close()
                        total_fees_paid = float(fees_row[0]) if fees_row and fees_row[0] is not None else 0.0
                    
                    # Update the expired trade to closed with PnL calculation
                    conn_trades = get_db_connection()
                    cursor_trades = conn_trades.cursor()
                    
                    # Get trade data for PnL calculation
                    cursor_trades.execute("SELECT buy_price, position, fees FROM trades WHERE ticker = ? AND status = 'expired'", (ticker,))
                    trade_row = cursor_trades.fetchone()
                    if trade_row:
                        buy_price, position, fees = trade_row
                        # Calculate PnL with fees included
                        pnl = None
                        if buy_price is not None and sell_price is not None and position is not None:
                            buy_value = buy_price * position
                            sell_value = sell_price * position
                            fees = fees if fees is not None else 0.0
                            pnl = round(sell_value - buy_value - fees, 2)
                    
                    cursor_trades.execute("""
                        UPDATE trades 
                        SET status = 'closed',
                            sell_price = ?,
                            win_loss = ?,
                            pnl = ?
                        WHERE ticker = ? AND status = 'expired'
                    """, (sell_price, 'W' if sell_price > 0 else 'L', pnl, ticker))
                    conn_trades.commit()
                    conn_trades.close()
                    
                    # Notify frontend about trade database change
                    notify_frontend_trade_change()
                    
                    found_tickers.add(ticker)
                    print(f"[SETTLEMENTS] Closed trade for {ticker} with sell_price={sell_price}")
            
            conn.close()
            
            if len(found_tickers) < len(expired_tickers):
                print(f"[SETTLEMENTS] Found {len(found_tickers)}/{len(expired_tickers)} settlements, continuing to poll...")
                time.sleep(2)  # Poll every 2 seconds
            else:
                print(f"[SETTLEMENTS] All {len(expired_tickers)} expired trades have been closed")
                break
                
        except Exception as e:
            print(f"[SETTLEMENTS] Error polling settlements: {e}")
            time.sleep(2)


# ------------------------------------------------------------------------------
# APScheduler Setup for Hourly Expiration Checks
# ------------------------------------------------------------------------------
_scheduler = BackgroundScheduler(timezone=ZoneInfo("America/New_York"))
_scheduler.add_job(check_expired_trades, CronTrigger(minute=0, second=0), max_instances=1, coalesce=True)

from fastapi import FastAPI

app = FastAPI()

@app.on_event("startup")
async def startup_event():
    """Start APScheduler when FastAPI app starts"""
    try:
        _scheduler.start()
        print("[SCHEDULER] APScheduler started successfully")
        print(f"[TRADE_MANAGER] 🚀 Trade manager started on centralized port {get_port('trade_manager')}")
    except Exception as e:
        print(f"[SCHEDULER ERROR] Failed to start APScheduler: {e}")

app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    import os

    port = get_port("trade_manager")
    print(f"[INFO] Trade Manager running on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)