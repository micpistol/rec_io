"""
MAIN APPLICATION - UNIVERSAL CENTRALIZED PORT SYSTEM
Uses the single centralized port configuration system.
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
import json
import asyncio
import time
from datetime import datetime, timedelta
import pytz
import requests
import sqlite3
import psycopg2
from typing import List, Optional, Dict
import fcntl
from datetime import datetime, timezone
from typing import Optional, Dict, Any
import hashlib
import secrets
import hmac

# Import the universal centralized port system
import sys
import os
from backend.util.paths import get_project_root
sys.path.append(get_project_root())

# Use relative imports to avoid ModuleNotFoundError
from backend.core.port_config import get_port, get_port_info

# Get port from centralized system
MAIN_APP_PORT = get_port("main_app")
ACTIVE_TRADE_SUPERVISOR_PORT = get_port("active_trade_supervisor")
print(f"[MAIN] 🚀 Using centralized port: {MAIN_APP_PORT}")
print(f"[MAIN] 🚀 Active Trade Supervisor port: {ACTIVE_TRADE_SUPERVISOR_PORT}")

# Import centralized path utilities
from backend.util.paths import get_data_dir, get_trade_history_dir, get_accounts_data_dir
from backend.account_mode import get_account_mode

# Global set of connected websocket clients for preferences
connected_clients = set()

# Global set of connected websocket clients for database changes
db_change_clients = set()

# Legacy preference path removed - all data now in PostgreSQL

# Global preferences cache
_preferences_cache = None
_cache_timestamp = 0
CACHE_TTL = 1.0  # 1 second cache TTL

# PostgreSQL helper functions for auto trade settings
def update_auto_trade_settings_postgresql(**kwargs):
    """Update auto trade settings in PostgreSQL using UPDATE"""
    try:
        import psycopg2
        conn = psycopg2.connect(
            host="localhost",
            database="rec_io_db",
            user="rec_io_user",
            password="rec_io_password"
        )
        with conn.cursor() as cursor:
            # First, ensure we only have one row
            cursor.execute("DELETE FROM users.auto_trade_settings_0001 WHERE id > 1")
            
            # Check if row exists
            cursor.execute("SELECT COUNT(*) FROM users.auto_trade_settings_0001 WHERE id = 1")
            row_exists = cursor.fetchone()[0] > 0
            
            if row_exists:
                # UPDATE existing row
                set_clauses = []
                values = []
                for key, value in kwargs.items():
                    set_clauses.append(f"{key} = %s")
                    values.append(value)
                
                if set_clauses:
                    query = f"UPDATE users.auto_trade_settings_0001 SET {', '.join(set_clauses)}, updated_at = CURRENT_TIMESTAMP WHERE id = 1"
                    cursor.execute(query, values)
            else:
                # INSERT new row with defaults
                columns = list(kwargs.keys())
                values = list(kwargs.values())
                placeholders = ['%s'] * len(values)
                
                # Add default values for missing columns
                default_columns = ['id', 'auto_entry', 'auto_stop', 'min_probability', 'min_differential', 'min_time', 'max_time', 'allow_re_entry', 'spike_alert_enabled', 'spike_alert_momentum_threshold', 'spike_alert_cooldown_threshold', 'spike_alert_cooldown_minutes', 'current_probability', 'min_ttc_seconds', 'momentum_spike_enabled', 'momentum_spike_threshold', 'auto_entry_status', 'user_id', 'cooldown_timer']
                default_values = [1, False, False, 95, 0.25, 120, 900, False, True, 36, 30, 15, 40, 60, True, 36, 'disabled', '0001', 0]
                
                # Merge provided values with defaults
                for col, val in zip(columns, values):
                    if col in default_columns:
                        idx = default_columns.index(col)
                        default_values[idx] = val
                
                query = f"INSERT INTO users.auto_trade_settings_0001 ({', '.join(default_columns)}) VALUES ({', '.join(['%s'] * len(default_values))})"
                cursor.execute(query, default_values)
            
            conn.commit()
            print(f"[PostgreSQL] Updated auto trade settings: {kwargs}")
        
        conn.close()
    except Exception as e:
        print(f"[PostgreSQL Error] Failed to update auto trade settings: {e}")

def get_auto_trade_settings_postgresql():
    """Get auto trade settings from PostgreSQL"""
    try:
        import psycopg2
        conn = psycopg2.connect(
            host="localhost",
            database="rec_io_db",
            user="rec_io_user",
            password="rec_io_password"
        )
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT auto_entry, auto_stop, 
                       min_probability, min_differential, min_time, max_time, allow_re_entry,
                       spike_alert_enabled, spike_alert_momentum_threshold, spike_alert_cooldown_threshold, spike_alert_cooldown_minutes,
                       current_probability, min_ttc_seconds, momentum_spike_enabled, momentum_spike_threshold
                FROM users.auto_trade_settings_0001 WHERE id = 1
            """)
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return {
                    "auto_entry": result[0],
                    "auto_stop": result[1],
                    "min_probability": result[2],
                    "min_differential": float(result[3]) if result[3] else 0.25,
                    "min_time": result[4],
                    "max_time": result[5],
                    "allow_re_entry": result[6],
                    "spike_alert_enabled": result[7],
                    "spike_alert_momentum_threshold": result[8],
                    "spike_alert_cooldown_threshold": result[9],
                    "spike_alert_cooldown_minutes": result[10],
                    "current_probability": result[11],
                    "min_ttc_seconds": result[12],
                    "momentum_spike_enabled": result[13],
                    "momentum_spike_threshold": result[14]
                }
            else:
                return {
                    "auto_entry": False, "auto_stop": False,
                    "min_probability": 95, "min_differential": 0.25, "min_time": 120, "max_time": 900, "allow_re_entry": False,
                    "spike_alert_enabled": True, "spike_alert_momentum_threshold": 36, "spike_alert_cooldown_threshold": 30, "spike_alert_cooldown_minutes": 15,
                    "current_probability": 40, "min_ttc_seconds": 60, "momentum_spike_enabled": True, "momentum_spike_threshold": 36
                }
    except Exception as e:
        print(f"[PostgreSQL Error] Failed to get auto trade settings: {e}")
        return {
            "auto_entry": False, "auto_stop": False,
            "min_probability": 95, "min_differential": 0.25, "min_time": 120, "max_time": 900, "allow_re_entry": False,
            "spike_alert_enabled": True, "spike_alert_momentum_threshold": 36, "spike_alert_cooldown_threshold": 30, "spike_alert_cooldown_minutes": 15,
            "current_probability": 40, "min_ttc_seconds": 60, "momentum_spike_enabled": True, "momentum_spike_threshold": 36
        }

def get_auto_stop_settings_postgresql():
    """Get auto stop settings from PostgreSQL"""
    try:
        import psycopg2
        conn = psycopg2.connect(
            host="localhost",
            database="rec_io_db",
            user="rec_io_user",
            password="rec_io_password"
        )
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT current_probability, min_ttc_seconds, momentum_spike_enabled, momentum_spike_threshold
                FROM users.auto_trade_settings_0001 WHERE id = 1
            """)
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return {
                    "current_probability": result[0],
                    "min_ttc_seconds": result[1],
                    "momentum_spike_enabled": result[2],
                    "momentum_spike_threshold": result[3]
                }
            else:
                return {
                    "current_probability": 40,
                    "min_ttc_seconds": 60,
                    "momentum_spike_enabled": True,
                    "momentum_spike_threshold": 36
                }
    except Exception as e:
        print(f"[PostgreSQL Error] Failed to get auto stop settings: {e}")
        return {
            "current_probability": 40,
            "min_ttc_seconds": 60,
            "momentum_spike_enabled": True,
            "momentum_spike_threshold": 36
        }

# PostgreSQL helper functions for trade preferences
def update_trade_preferences_postgresql(**kwargs):
    """Update trade preferences in PostgreSQL using UPSERT"""
    try:
        import psycopg2
        conn = psycopg2.connect(
            host="localhost",
            database="rec_io_db",
            user="rec_io_user",
            password="rec_io_password"
        )
        with conn.cursor() as cursor:
            # First, ensure we only have one row
            cursor.execute("DELETE FROM users.trade_preferences_0001 WHERE id > 1")
            
            # Build dynamic UPSERT query
            columns = list(kwargs.keys())
            values = list(kwargs.values())
            placeholders = ['%s'] * len(values)
            
            # Add updated_at to the columns
            columns.append('updated_at')
            placeholders.append('CURRENT_TIMESTAMP')
            
            query = f"""
                INSERT INTO users.trade_preferences_0001 (id, {', '.join(columns)})
                VALUES (1, {', '.join(placeholders)})
                ON CONFLICT (id) DO UPDATE SET
                {', '.join([f"{col} = EXCLUDED.{col}" for col in columns])}
            """
            
            cursor.execute(query, values)
            conn.commit()
            print(f"[PostgreSQL] Updated trade preferences: {kwargs}")
        
        conn.close()
    except Exception as e:
        print(f"[PostgreSQL Error] Failed to update trade preferences: {e}")

def get_trade_preferences_postgresql():
    """Get trade preferences from PostgreSQL"""
    try:
        import psycopg2
        conn = psycopg2.connect(
            host="localhost",
            database="rec_io_db",
            user="rec_io_user",
            password="rec_io_password"
        )
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT trade_strategy, position_size, multiplier
                FROM users.trade_preferences_0001 WHERE id = 1
            """)
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return {
                    "trade_strategy": result[0],
                    "position_size": result[1],
                    "multiplier": result[2]
                }
            else:
                return {
                    "trade_strategy": "Hourly HTC",
                    "position_size": 1,
                    "multiplier": 1
                }
    except Exception as e:
        print(f"[PostgreSQL Error] Failed to get trade preferences: {e}")
        return {
            "trade_strategy": "Hourly HTC",
            "position_size": 1,
            "multiplier": 1
        }

def get_all_preferences_postgresql():
    """Get all preferences from PostgreSQL (combines auto_trade_settings and trade_preferences)"""
    try:
        import psycopg2
        conn = psycopg2.connect(
            host="localhost",
            database="rec_io_db",
            user="rec_io_user",
            password="rec_io_password"
        )
        with conn.cursor() as cursor:
            # Get auto trade settings
            cursor.execute("""
                SELECT auto_entry, auto_stop
                FROM users.auto_trade_settings_0001 WHERE id = 1
            """)
            auto_settings = cursor.fetchone()
            
            # Get trade preferences
            cursor.execute("""
                SELECT trade_strategy, position_size, multiplier
                FROM users.trade_preferences_0001 WHERE id = 1
            """)
            trade_prefs = cursor.fetchone()
            
            conn.close()
            
            # Combine the results
            preferences = {
                "auto_stop": auto_settings[1] if auto_settings else True,  # auto_stop is second column
                "auto_entry": auto_settings[0] if auto_settings else False,  # auto_entry is first column
                "position_size": trade_prefs[1] if trade_prefs else 1,
                "multiplier": trade_prefs[2] if trade_prefs else 1
            }
            
            return preferences
    except Exception as e:
        print(f"[PostgreSQL Error] Failed to get all preferences: {e}")
        return {
            "auto_stop": True,
            "auto_entry": False,
            "diff_mode": False,
            "position_size": 1,
            "multiplier": 1
        }

def get_trade_history_preferences_postgresql():
    """Get trade history preferences from PostgreSQL"""
    try:
        import psycopg2
        conn = psycopg2.connect(
            host="localhost",
            database="rec_io_db",
            user="rec_io_user",
            password="rec_io_password"
        )
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT date_filter, custom_date_start, custom_date_end, win_filter, loss_filter,
                       sort_key, sort_asc, page_size, last_search_timestamp
                FROM users.trade_history_preferences_0001 WHERE id = 1
            """)
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return {
                    "date_filter": result[0],
                    "custom_date_start": result[1].isoformat() if result[1] else None,
                    "custom_date_end": result[2].isoformat() if result[2] else None,
                    "win_filter": result[3],
                    "loss_filter": result[4],
                    "sort_key": result[5],
                    "sort_asc": result[6],
                    "page_size": result[7],
                    "last_search_timestamp": result[8]
                }
            else:
                return {
                    "date_filter": "TODAY",
                    "custom_date_start": None,
                    "custom_date_end": None,
                    "win_filter": True,
                    "loss_filter": True,
                    "sort_key": None,
                    "sort_asc": True,
                    "page_size": 50,
                    "last_search_timestamp": int(time.time())
                }
    except Exception as e:
        print(f"[PostgreSQL Error] Failed to get trade history preferences: {e}")
        return {
            "date_filter": "TODAY",
            "custom_date_start": None,
            "custom_date_end": None,
            "win_filter": True,
            "loss_filter": True,
            "sort_key": None,
            "sort_asc": True,
            "page_size": 50,
            "last_search_timestamp": int(time.time())
        }

def update_trade_history_preferences_postgresql(**kwargs):
    """Update trade history preferences in PostgreSQL using UPSERT"""
    try:
        import psycopg2
        conn = psycopg2.connect(
            host="localhost",
            database="rec_io_db",
            user="rec_io_user",
            password="rec_io_password"
        )
        with conn.cursor() as cursor:
            # First, ensure we only have one row
            cursor.execute("DELETE FROM users.trade_history_preferences_0001 WHERE id > 1")
            
            # Build dynamic UPSERT query
            columns = list(kwargs.keys())
            values = list(kwargs.values())
            placeholders = ['%s'] * len(values)
            
            # Add updated_at to the columns
            columns.append('updated_at')
            placeholders.append('CURRENT_TIMESTAMP')
            
            query = f"""
                INSERT INTO users.trade_history_preferences_0001 (id, {', '.join(columns)})
                VALUES (1, {', '.join(placeholders)})
                ON CONFLICT (id) DO UPDATE SET
                {', '.join([f"{col} = EXCLUDED.{col}" for col in columns])}
            """
            
            cursor.execute(query, values)
            conn.commit()
            print(f"[PostgreSQL] Updated trade history preferences: {kwargs}")
        
        conn.close()
    except Exception as e:
        print(f"[PostgreSQL Error] Failed to update trade history preferences: {e}")

# Authentication system
AUTH_TOKENS_FILE = os.path.join(get_data_dir(), "users", "user_0001", "auth_tokens.json")
DEVICE_TOKENS_FILE = os.path.join(get_data_dir(), "users", "user_0001", "device_tokens.json")

# Authentication settings - can be overridden for local development
AUTH_ENABLED = os.environ.get("AUTH_ENABLED", "false").lower() == "true"

def load_auth_tokens():
    """Load authentication tokens from file"""
    try:
        if os.path.exists(AUTH_TOKENS_FILE):
            with open(AUTH_TOKENS_FILE, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def save_auth_tokens(tokens):
    """Save authentication tokens to file"""
    try:
        os.makedirs(os.path.dirname(AUTH_TOKENS_FILE), exist_ok=True)
        with open(AUTH_TOKENS_FILE, "w") as f:
            json.dump(tokens, f, indent=2)
    except Exception as e:
        print(f"[AUTH] Error saving auth tokens: {e}")

def load_device_tokens():
    """Load device tokens from file"""
    try:
        if os.path.exists(DEVICE_TOKENS_FILE):
            with open(DEVICE_TOKENS_FILE, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def save_device_tokens(tokens):
    """Save device tokens to file"""
    try:
        os.makedirs(os.path.dirname(DEVICE_TOKENS_FILE), exist_ok=True)
        with open(DEVICE_TOKENS_FILE, "w") as f:
            json.dump(tokens, f, indent=2)
    except Exception as e:
        print(f"[AUTH] Error saving device tokens: {e}")

def generate_token():
    """Generate a secure authentication token"""
    return secrets.token_urlsafe(32)

def hash_password(password):
    """Hash a password using HMAC-SHA256"""
    salt = secrets.token_hex(16)
    hash_obj = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
    return salt + hash_obj.hex()

def verify_password(password, hashed):
    """Verify a password against its hash"""
    try:
        salt = hashed[:32]  # First 32 chars are salt
        hash_part = hashed[32:]
        hash_obj = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
        return hmac.compare_digest(hash_obj.hex(), hash_part)
    except Exception:
        return False

def get_user_credentials():
    """Get user credentials from PostgreSQL"""
    try:
        import psycopg2
        conn = psycopg2.connect(
            host="localhost",
            database="rec_io_db",
            user="rec_io_user",
            password="rec_io_password"
        )
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT user_id, first_name, last_name, email, phone, account_type
                FROM users.user_info_0001 WHERE user_no = '0001'
            """)
            result = cursor.fetchone()
            if result:
                user_id, first_name, last_name, email, phone, account_type = result
                return {
                    "username": user_id,
                    "name": f"{first_name} {last_name}" if first_name and last_name else user_id,
                    "email": email,
                    "phone": phone,
                    "account_type": account_type
                }
    except Exception as e:
        print(f"[AUTH] Error loading user credentials from PostgreSQL: {e}")
    
    # Fallback to JSON file for backward compatibility
    try:
        user_info_path = os.path.join(get_data_dir(), "users", "user_0001", "user_info.json")
        if os.path.exists(user_info_path):
            with open(user_info_path, "r") as f:
                user_info = json.load(f)
                return {
                    "username": user_info.get("user_id", "admin"),
                    "password": user_info.get("password", "admin"),  # Plain text fallback
                    "name": user_info.get("name", "Admin User")
                }
    except Exception as e:
        print(f"[AUTH] Error loading user credentials from JSON: {e}")
    
    # Default credentials if nothing works
    return {
        "username": "admin",
        "password": "admin",
        "name": "Admin User"
    }

def verify_password(password, hashed_password):
    """Verify a password against its hash"""
    try:
        import bcrypt
        return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception as e:
        print(f"[AUTH] Password verification error: {e}")
        return False

def load_preferences():
    global _preferences_cache, _cache_timestamp
    current_time = time.time()
    
    # Return cached version if still valid
    if _preferences_cache is not None and (current_time - _cache_timestamp) < CACHE_TTL:
        return _preferences_cache.copy()
    
    # Load from PostgreSQL
    try:
        prefs = get_all_preferences_postgresql()
        
        # Update cache
        _preferences_cache = prefs
        _cache_timestamp = current_time
        return prefs
    except Exception as e:
        print(f"[Preferences Load Error] {e}")
        # Default preferences
        default_prefs = {"auto_stop": True, "auto_entry": False, "diff_mode": False, "position_size": 1, "multiplier": 1}
        _preferences_cache = default_prefs
        _cache_timestamp = current_time
        return default_prefs

async def save_preferences(prefs):
    global _preferences_cache, _cache_timestamp
    try:
        # Update PostgreSQL
        update_data = {}
        if "auto_stop" in prefs:
            update_data["auto_stop"] = bool(prefs["auto_stop"])
        if "auto_entry" in prefs:
            update_data["auto_entry"] = bool(prefs["auto_entry"])
        if "position_size" in prefs:
            update_data["position_size"] = int(prefs["position_size"])
        if "multiplier" in prefs:
            update_data["multiplier"] = int(prefs["multiplier"])
        
        if update_data:
            # Update auto_trade_settings for auto_stop and auto_entry
            auto_settings = {k: v for k, v in update_data.items() if k in ["auto_stop", "auto_entry"]}
            if auto_settings:
                update_auto_trade_settings_postgresql(**auto_settings)
            
            # Update trade_preferences for position_size and multiplier
            trade_settings = {k: v for k, v in update_data.items() if k in ["position_size", "multiplier"]}
            if trade_settings:
                update_trade_preferences_postgresql(**trade_settings)
        
        # Update cache
        _preferences_cache = prefs.copy()
        _cache_timestamp = time.time()
        print(f"[Preferences] ✅ Updated PostgreSQL: {list(update_data.keys())}")
    except Exception as e:
        print(f"[Preferences Save Error] {e}")

# Broadcast helper function for preferences updates
async def broadcast_preferences_update():
    try:
        data = json.dumps(load_preferences())
        to_remove = set()
        
        # Send to all connected clients concurrently
        tasks = []
        for client in connected_clients:
            task = asyncio.create_task(send_to_client(client, data))
            tasks.append(task)
        
        # Wait for all sends to complete with timeout
        if tasks:
            await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=1.0)
        
        # Clean up disconnected clients
        connected_clients.difference_update(to_remove)
    except Exception as e:
        print(f"[Broadcast Preferences Error] {e}")

async def send_to_client(client, data):
    try:
        await client.send_text(data)
    except Exception:
        # Client will be removed in the main function
        pass

# Broadcast helper function for account mode updates
async def broadcast_account_mode(mode: str):
    message = json.dumps({"account_mode": mode})
    to_remove = set()
    for client in connected_clients:
        try:
            await client.send_text(message)
        except Exception:
            to_remove.add(client)
    connected_clients.difference_update(to_remove)

# Broadcast helper function for database changes
async def broadcast_db_change(db_name: str, change_data: dict):
    message = json.dumps({
        "type": "db_change",
        "database": db_name,
        "data": change_data,
        "timestamp": datetime.now().isoformat()
    })
    to_remove = set()
    for client in db_change_clients:
        try:
            await client.send_text(message)
        except Exception:
            to_remove.add(client)
    db_change_clients.difference_update(to_remove)

# Create FastAPI app
app = FastAPI(title="Trading System Main App")

# Import universal host system
from backend.util.paths import get_host

# Configure CORS with universal host origins
host = get_host()
origins = [
    f"http://{host}:{MAIN_APP_PORT}",
    f"http://localhost:{MAIN_APP_PORT}",
    f"http://127.0.0.1:{MAIN_APP_PORT}",
    # Allow access from any device on the local network (192.168.x.x, 10.x.x.x, 172.16-31.x.x)
    "*"  # Allow all origins for local network access
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files with cache busting
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

# Custom static file handler with cache busting
class CacheBustingStaticFiles(StaticFiles):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
    async def __call__(self, scope, receive, send):
        # Add cache-busting headers to all static files
        async def send_with_cache_busting(message):
            if message["type"] == "http.response.start":
                message["headers"].extend([
                    (b"cache-control", b"no-cache, no-store, must-revalidate"),
                    (b"pragma", b"no-cache"),
                    (b"expires", b"0")
                ])
            await send(message)
        
        await super().__call__(scope, receive, send_with_cache_busting)

# Mount static files
from backend.util.paths import get_frontend_dir
frontend_dir = get_frontend_dir()

app.mount("/tabs", CacheBustingStaticFiles(directory=f"{frontend_dir}/tabs"), name="tabs")
app.mount("/audio", CacheBustingStaticFiles(directory=f"{frontend_dir}/audio"), name="audio")
app.mount("/js", CacheBustingStaticFiles(directory=f"{frontend_dir}/js"), name="js")
app.mount("/images", CacheBustingStaticFiles(directory=f"{frontend_dir}/images"), name="images")
app.mount("/styles", CacheBustingStaticFiles(directory=f"{frontend_dir}/styles"), name="styles")
app.mount("/mobile", CacheBustingStaticFiles(directory=f"{frontend_dir}/mobile"), name="mobile")

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "main_app",
        "port": MAIN_APP_PORT,
        "timestamp": datetime.now().isoformat(),
        "port_system": "centralized"
    }

# Port information endpoint
@app.get("/api/ports")
async def get_ports():
    """Get all port assignments from centralized system."""
    return get_port_info()

# Test endpoint
@app.get("/api/test-health")
async def test_health():
    """Test endpoint to verify routing works."""
    return {"message": "Test health endpoint working"}

# System health endpoint
@app.get("/api/system-health")
async def get_system_health():
    """Get comprehensive system health status."""
    try:
        # Import system monitor
        from backend.system_monitor import SystemMonitor
        
        # Create system monitor instance and generate health report
        monitor = SystemMonitor()
        health_report = monitor.generate_health_report()
        
        # Determine overall system status
        overall_status = "healthy"
        issues = []
        
        # Check supervisor status
        if health_report.get("supervisor_status", {}).get("status") != "running":
            overall_status = "offline"
            issues.append("Supervisor not running")
        
        # Check critical services
        critical_services = ["main_app", "trade_manager", "trade_executor", "active_trade_supervisor"]
        unhealthy_services = []
        
        for service in critical_services:
            service_status = health_report.get("services", {}).get(service, {})
            if service_status.get("status") != "healthy":
                unhealthy_services.append(service)
        
        if unhealthy_services:
            if len(unhealthy_services) >= len(critical_services) // 2:
                overall_status = "offline"
            else:
                overall_status = "degraded"
            issues.append(f"Unhealthy services: {', '.join(unhealthy_services)}")
        
        # Check database health
        db_health = health_report.get("database_health", {})
        if db_health.get("status") != "healthy":
            overall_status = "degraded"
            issues.append("Database issues detected")
        
        return {
            "status": overall_status,
            "issues": issues,
            "timestamp": datetime.now().isoformat(),
            "health_report": health_report
        }
        
    except Exception as e:
        return {
            "status": "offline",
            "issues": [f"System monitor error: {str(e)}"],
            "timestamp": datetime.now().isoformat(),
            "error": str(e)
        }

# WebSocket connections
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"[WEBSOCKET] ✅ Client connected. Total clients: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        print(f"[WEBSOCKET] ❌ Client disconnected. Total clients: {len(self.active_connections)}")

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except:
                # Remove dead connections
                self.active_connections.remove(connection)

manager = ConnectionManager()

# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await manager.send_personal_message(f"Message text was: {data}", websocket)
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# WebSocket endpoint for preferences updates
@app.websocket("/ws/preferences")
async def websocket_preferences(websocket: WebSocket):
    await websocket.accept()
    connected_clients.add(websocket)
    try:
        while True:
            await websocket.receive_text()  # Keep connection alive
    except WebSocketDisconnect:
        connected_clients.remove(websocket)

@app.websocket("/ws/db_changes")
async def websocket_db_changes(websocket: WebSocket):
    await websocket.accept()
    db_change_clients.add(websocket)
    try:
        while True:
            await websocket.receive_text()  # Keep connection alive
    except WebSocketDisconnect:
        db_change_clients.remove(websocket)

# Serve main index.html
@app.get("/", response_class=HTMLResponse)
async def read_root():
    """Serve the main application or login page based on authentication."""
    # For now, always serve the main app
    # In production, this would check authentication
    with open("index.html", "r") as f:
        content = f.read()
        return HTMLResponse(
            content=content,
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )

@app.get("/app", response_class=HTMLResponse)
async def serve_main_app():
    """Serve the main application (protected route)."""
    with open("index.html", "r") as f:
        content = f.read()
        return HTMLResponse(
            content=content,
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )

@app.get("/login", response_class=HTMLResponse)
async def serve_login():
    """Serve the login page."""
    try:
        with open("login.html", "r") as f:
            content = f.read()
            return HTMLResponse(
                content=content,
                headers={
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                    "Pragma": "no-cache",
                    "Expires": "0"
                }
            )
    except FileNotFoundError:
        return HTMLResponse(content="<h1>Login</h1><p>Login page not found.</p>", status_code=404)

# Serve favicon
@app.get("/favicon.ico")
async def serve_favicon():
    """Serve favicon."""
    from fastapi.responses import FileResponse
    import os
    file_path = os.path.join("frontend", "images", "icons", "fave.ico")
    if os.path.exists(file_path):
        return FileResponse(file_path)
    else:
        return {"error": "Favicon not found"}, 404

# Serve terminal control page
@app.get("/terminal-control.html", response_class=HTMLResponse)
async def serve_terminal_control():
    """Serve terminal control page."""
    import os
    file_path = "terminal-control.html"
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            return HTMLResponse(content=f.read())
    else:
        return HTMLResponse(content="<h1>Terminal Control not found</h1>", status_code=404)

# Serve log viewer page
@app.get("/log-viewer.html", response_class=HTMLResponse)
async def serve_log_viewer():
    """Serve log viewer page."""
    import os
    file_path = "log-viewer.html"
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            return HTMLResponse(content=f.read())
    else:
        return HTMLResponse(content="<h1>Log Viewer not found</h1>", status_code=404)

# Serve CSS files with cache busting
@app.get("/styles/{filename:path}")
async def serve_css(filename: str):
    """Serve CSS files with cache busting headers."""
    file_path = f"{frontend_dir}/styles/{filename}"
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            content = f.read()
            return HTMLResponse(
                content=content,
                headers={
                    "Content-Type": "text/css",
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                    "Pragma": "no-cache",
                    "Expires": "0"
                }
            )
    else:
        return HTMLResponse(content="CSS file not found", status_code=404)

# Serve JS files with cache busting
@app.get("/js/{filename:path}")
async def serve_js(filename: str):
    """Serve JS files with cache busting headers."""
    file_path = f"{frontend_dir}/js/{filename}"
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            content = f.read()
            return HTMLResponse(
                content=content,
                headers={
                    "Content-Type": "application/javascript",
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                    "Pragma": "no-cache",
                    "Expires": "0"
                }
            )
    else:
        return HTMLResponse(content="JS file not found", status_code=404)

# Serve mobile trade monitor with cache busting
@app.get("/mobile/trade_monitor", response_class=HTMLResponse)
async def serve_mobile_trade_monitor():
    """Serve mobile trade monitor with cache busting headers."""
    file_path = f"{frontend_dir}/mobile/trade_monitor_mobile.html"
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            content = f.read()
            return HTMLResponse(
                content=content,
                headers={
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                    "Pragma": "no-cache",
                    "Expires": "0"
                }
            )
    else:
        return HTMLResponse(content="Mobile trade monitor not found", status_code=404)

# Serve mobile account manager with cache busting
@app.get("/mobile/account_manager", response_class=HTMLResponse)
async def serve_mobile_account_manager():
    """Serve mobile account manager with cache busting headers."""
    file_path = f"{frontend_dir}/mobile/account_manager_mobile.html"
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            content = f.read()
            return HTMLResponse(
                content=content,
                headers={
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                    "Pragma": "no-cache",
                    "Expires": "0"
                }
            )
    else:
        return HTMLResponse(content="Mobile account manager not found", status_code=404)

# Serve mobile index with cache busting
@app.get("/mobile", response_class=HTMLResponse)
async def serve_mobile_index():
    """Serve mobile index with cache busting headers."""
    file_path = f"{frontend_dir}/mobile/index.html"
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            content = f.read()
            return HTMLResponse(
                content=content,
                headers={
                    "Cache-Control": "no-cache, no-store, must-revalidate",
                    "Pragma": "no-cache",
                    "Expires": "0"
                }
            )
    else:
        return HTMLResponse(content="Mobile index not found", status_code=404)

# Test route for debugging
@app.get("/test-mobile")
async def test_mobile():
    """Test route for debugging mobile routes."""
    return {"message": "Mobile test route works!"}

# Test route for debugging mobile path
@app.get("/mobile/test")
async def test_mobile_path():
    """Test route for debugging mobile path."""
    return {"message": "Mobile path test route works!"}

@app.get("/api/ttc")
async def get_ttc_data():
    """Get time to close data from live data analyzer."""
    try:
        from live_data_analysis import get_ttc_data
        return get_ttc_data()
    except Exception as e:
        print(f"Error getting TTC data: {e}")
        return {"error": str(e)}

# Core data endpoint
@app.get("/core")
async def get_core_data():
    """Get core trading data."""
    try:
        # Get current time
        now = datetime.now(pytz.timezone('US/Eastern'))
        date_str = now.strftime("%A, %B %d, %Y")
        time_str = now.strftime("%I:%M:%S %p EDT")
        
        # Get TTC from live data analyzer
        ttc_seconds = 0
        try:
            from live_data_analysis import get_ttc_data
            ttc_data = get_ttc_data()
            ttc_seconds = ttc_data.get('ttc_seconds', 0)
        except Exception as e:
            print(f"Error getting TTC from live data analyzer: {e}")
            # Fallback calculation
            close_time = now.replace(hour=16, minute=0, second=0, microsecond=0)
            if now.time() >= close_time.time():
                close_time += timedelta(days=1)
            ttc_seconds = int((close_time - now).total_seconds())
        
        # Get BTC price from watchdog data
        btc_price = 0
        try:
            # First try to get the latest price from the watchdog's database
            from backend.util.paths import get_btc_price_history_dir
            btc_price_history_db = os.path.join(get_btc_price_history_dir(), "btc_price_history.db")
            
            if os.path.exists(btc_price_history_db):
                conn = sqlite3.connect(btc_price_history_db)
                cursor = conn.cursor()
                cursor.execute("SELECT price FROM price_log ORDER BY timestamp DESC LIMIT 1")
                result = cursor.fetchone()
                conn.close()
                
                if result:
                    btc_price = float(result[0])
                    print(f"[MAIN] Using watchdog BTC price: ${btc_price:,.2f}")
                else:
                    # Fallback to direct API call if no watchdog data
                    response = requests.get("https://api.kraken.com/0/public/Ticker?pair=BTCUSD", timeout=5)
                    if response.status_code == 200:
                        data = response.json()
                        btc_price = float(data['result']['XXBTZUSD']['c'][0])
                        print(f"[MAIN] Using fallback API BTC price: ${btc_price:,.2f}")
            else:
                # Fallback to direct API call if watchdog DB doesn't exist
                response = requests.get("https://api.kraken.com/0/public/Ticker?pair=BTCUSD", timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    btc_price = float(data['result']['XXBTZUSD']['c'][0])
                    print(f"[MAIN] Using fallback API BTC price: ${btc_price:,.2f}")
        except Exception as e:
            print(f"Error fetching BTC price: {e}")
            # Final fallback to direct API call
            try:
                response = requests.get("https://api.kraken.com/0/public/Ticker?pair=BTCUSD", timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    btc_price = float(data['result']['XXBTZUSD']['c'][0])
                    print(f"[MAIN] Using emergency fallback API BTC price: ${btc_price:,.2f}")
            except Exception as e2:
                print(f"Emergency fallback also failed: {e2}")
        
        # Get momentum data from live data analyzer
        momentum_data = {}
        try:
            from live_data_analysis import get_momentum_data
            momentum_data = get_momentum_data()
            print(f"[MAIN] Momentum analysis: {momentum_data.get('weighted_momentum_score', 'N/A'):.4f}%")
        except Exception as e:
            print(f"Error getting momentum data: {e}")
            # Fallback to null momentum data
            momentum_data = {
                'delta_1m': None,
                'delta_2m': None,
                'delta_3m': None,
                'delta_4m': None,
                'delta_15m': None,
                'delta_30m': None,
                'weighted_momentum_score': None
            }
        
        # Get latest database price from PostgreSQL
        latest_db_price = 0
        try:
            import psycopg2
            conn = psycopg2.connect(
                host="localhost",
                database="rec_io_db",
                user="rec_io_user",
                password="rec_io_password"
            )
            with conn.cursor() as cursor:
                cursor.execute("SELECT buy_price FROM users.trades_0001 ORDER BY date DESC, time DESC LIMIT 1")
                result = cursor.fetchone()
                if result:
                    latest_db_price = result[0]
            conn.close()
        except Exception as e:
            print(f"Error getting latest DB price: {e}")
        
        # Get Kraken changes
        kraken_changes = {}
        try:
            response = requests.get("https://api.kraken.com/0/public/Ticker?pair=BTCUSD", timeout=5)
            if response.status_code == 200:
                data = response.json()
                ticker = data['result']['XXBTZUSD']
                
                # Calculate changes
                current_price = float(ticker['c'][0])
                for period in ['1h', '3h', '1d']:
                    if period == '1h':
                        old_price = float(ticker['p'][0])  # 24h low as proxy
                    elif period == '3h':
                        old_price = float(ticker['p'][0])  # 24h low as proxy
                    else:  # 1d
                        old_price = float(ticker['p'][0])  # 24h low as proxy
                    
                    change = (current_price - old_price) / old_price
                    kraken_changes[f"change{period}"] = change
        except Exception as e:
            print(f"Error getting Kraken changes: {e}")
        
        # Get Kalshi markets (placeholder)
        kalshi_markets = []
        
        return {
            "date": date_str,
            "time": time_str,
            "ttc_seconds": ttc_seconds,
            "btc_price": btc_price,
            "latest_db_price": latest_db_price,
            "timestamp": datetime.now().isoformat(),
            **momentum_data,  # Include all momentum deltas and weighted score
            "status": "online",
            "volScore": 0,
            "volSpike": 0,
            **kraken_changes,
            "kalshi_markets": kalshi_markets
        }
    except Exception as e:
        print(f"Error in core data: {e}")
        return {"error": str(e)}

# Account mode endpoints
@app.get("/api/get_account_mode")
async def get_account_mode_endpoint():
    """Get current account mode."""
    return {"mode": get_account_mode()}

@app.post("/api/set_account_mode")
async def set_account_mode(mode_data: dict):
    """Set account mode."""
    from backend.account_mode import set_account_mode
    mode = mode_data.get("mode")
    if mode in ["prod", "demo"]:
        set_account_mode(mode)
        return {"status": "success", "mode": mode}
    return {"status": "error", "message": "Invalid mode"}

# Trade data endpoints
@app.get("/trades")
async def get_trades(status: Optional[str] = None):
    """Get trade data from PostgreSQL database."""
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        
        # Connect to PostgreSQL
        conn = psycopg2.connect(
            host="localhost",
            database="rec_io_db",
            user="rec_io_user",
            password="rec_io_password"
        )
        
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            # Build query based on status filter
            if status:
                cursor.execute("""
                    SELECT * FROM users.trades_0001 
                    WHERE status = %s 
                    ORDER BY id DESC 
                    LIMIT 100
                """, (status,))
            else:
                cursor.execute("""
                    SELECT * FROM users.trades_0001 
                    ORDER BY id DESC 
                    LIMIT 100
                """)
            
            trades = cursor.fetchall()
            
            # Convert RealDictRow objects to regular dictionaries
            result = []
            for trade in trades:
                trade_dict = dict(trade)
                
                # Create a combined timestamp field for frontend compatibility
                if 'date' in trade_dict and 'time' in trade_dict:
                    trade_dict['timestamp'] = f"{trade_dict['date']} {trade_dict['time']}"
                
                # Create a combined price field for frontend compatibility
                if 'buy_price' in trade_dict:
                    trade_dict['price'] = trade_dict['buy_price']
                
                result.append(trade_dict)
            
            conn.close()
            return result
            
    except Exception as e:
        print(f"Error getting trades from PostgreSQL: {e}")
        return []

@app.get("/trades/{trade_id}")
async def get_trade(trade_id: int):
    """Forward trade GET request to trade_manager."""
    try:
        # Get trade_manager port from centralized system
        trade_manager_port = get_port("trade_manager")
        trade_manager_url = f"http://{get_host()}:{trade_manager_port}/trades/{trade_id}"
        
        print(f"[MAIN] Forwarding trade GET request to trade_manager at {trade_manager_url}")
        
        # Forward the request to trade_manager
        response = requests.get(
            trade_manager_url,
            timeout=10
        )
        
        if response.status_code == 200:
            print(f"[MAIN] ✅ Trade GET request forwarded successfully to trade_manager")
            return response.json()
        else:
            print(f"[MAIN] ❌ Trade GET request forwarding failed: {response.status_code}")
            return {"error": f"Trade manager returned status {response.status_code}"}
            
    except Exception as e:
        print(f"[MAIN] ❌ Error forwarding trade GET request: {e}")
        return {"error": str(e)}

@app.post("/trades")
async def create_trade(trade_data: dict):
    """Forward trade ticket to trade_manager."""
    try:
        # Get trade_manager port from centralized system
        trade_manager_port = get_port("trade_manager")
        trade_manager_url = f"http://{get_host()}:{trade_manager_port}/trades"
        
        print(f"[MAIN] Forwarding trade ticket to trade_manager at {trade_manager_url}")
        
        # Forward the request to trade_manager
        response = requests.post(
            trade_manager_url,
            json=trade_data,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        if response.status_code == 201:
            print(f"[MAIN] ✅ Trade ticket forwarded successfully to trade_manager")
            return response.json()
        else:
            print(f"[MAIN] ❌ Trade ticket forwarding failed: {response.status_code}")
            return {"error": f"Trade manager returned status {response.status_code}"}
            
    except Exception as e:
        print(f"[MAIN] ❌ Error forwarding trade ticket: {e}")
        return {"error": str(e)}

# Additional endpoints for other data
@app.get("/btc_price_changes")
async def get_btc_changes():
    """Get BTC price changes from btc_price_change.json if available, else fallback."""
    try:
        from backend.util.paths import get_btc_price_history_dir
        import json as _json
        import os as _os
        change_path = _os.path.join(get_btc_price_history_dir(), "btc_price_change.json")
        if _os.path.exists(change_path):
            with open(change_path, "r") as f:
                data = _json.load(f)
            return {
                "change1h": data.get("change1h"),
                "change3h": data.get("change3h"),
                "change1d": data.get("change1d"),
                "timestamp": data.get("timestamp")
            }
    except Exception as e:
        print(f"[btc_price_changes API] Error reading btc_price_change.json: {e}")
    # fallback: return nulls if file missing or error
    return {"change1h": None, "change3h": None, "change1d": None, "timestamp": None}

@app.get("/kalshi_market_snapshot")
async def get_kalshi_snapshot():
    """Get Kalshi market snapshot."""
    try:
        # Read from the latest market snapshot file
        snapshot_file = os.path.join("backend", "data", "live_data", "markets", "kalshi", "latest_market_snapshot.json")
        
        if os.path.exists(snapshot_file):
            with open(snapshot_file, 'r') as f:
                snapshot_data = json.load(f)
                return snapshot_data
        else:
            print(f"Kalshi snapshot file not found: {snapshot_file}")
            return {"markets": []}
    except Exception as e:
        print(f"Error getting Kalshi snapshot: {e}")
        return {"markets": []}

# API endpoints for account data
@app.get("/api/account/balance")
async def get_account_balance(mode: str = "prod"):
    """Get account balance from PostgreSQL database."""
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        
        # Connect to PostgreSQL
        conn = psycopg2.connect(
            host="localhost",
            database="rec_io_db",
            user="rec_io_user",
            password="rec_io_password"
        )
        
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("""
                SELECT balance, timestamp 
                FROM users.account_balance_0001 
                ORDER BY timestamp DESC 
                LIMIT 1
            """)
            result = cursor.fetchone()
            
            conn.close()
            
            if result:
                return {"balance": result['balance']}
            else:
                return {"balance": 0}
            
    except Exception as e:
        print(f"Error getting account balance from PostgreSQL: {e}")
        return {"balance": 0}

@app.get("/api/db/fills")
def get_fills():
    """Get fills data from PostgreSQL database."""
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        
        # Connect to PostgreSQL
        conn = psycopg2.connect(
            host="localhost",
            database="rec_io_db",
            user="rec_io_user",
            password="rec_io_password"
        )
        
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("""
                SELECT * FROM users.fills_0001 
                ORDER BY id DESC 
                LIMIT 100
            """)
            fills = cursor.fetchall()
            
            # Convert RealDictRow objects to regular dictionaries
            fills_list = []
            for fill in fills:
                fill_dict = dict(fill)
                fills_list.append(fill_dict)
            
            conn.close()
            return {"fills": fills_list}
            
    except Exception as e:
        print(f"Error getting fills from PostgreSQL: {e}")
        return {"fills": []}

@app.get("/api/db/positions")
def get_positions():
    """Get positions data from PostgreSQL database."""
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        
        # Connect to PostgreSQL
        conn = psycopg2.connect(
            host="localhost",
            database="rec_io_db",
            user="rec_io_user",
            password="rec_io_password"
        )
        
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("""
                SELECT * FROM users.positions_0001 
                ORDER BY id DESC 
                LIMIT 100
            """)
            positions = cursor.fetchall()
            
            # Convert RealDictRow objects to regular dictionaries
            positions_list = []
            for position in positions:
                position_dict = dict(position)
                positions_list.append(position_dict)
            
            conn.close()
            return {"positions": positions_list}
            
    except Exception as e:
        print(f"Error getting positions from PostgreSQL: {e}")
        return {"positions": []}

@app.get("/api/db/settlements")
def get_settlements():
    """Get settlements data from PostgreSQL database."""
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        
        # Connect to PostgreSQL
        conn = psycopg2.connect(
            host="localhost",
            database="rec_io_db",
            user="rec_io_user",
            password="rec_io_password"
        )
        
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("""
                SELECT * FROM users.settlements_0001 
                ORDER BY id DESC 
                LIMIT 100
            """)
            settlements = cursor.fetchall()
            
            # Convert RealDictRow objects to regular dictionaries
            settlements_list = []
            for settlement in settlements:
                settlement_dict = dict(settlement)
                settlements_list.append(settlement_dict)
            
            conn.close()
            return {"settlements": settlements_list}
            
    except Exception as e:
        print(f"Error getting settlements from PostgreSQL: {e}")
        return {"settlements": []}

@app.get("/api/db/system_health")
def get_system_health_from_db():
    """Get current system health from database"""
    try:
        import psycopg2
        
        conn = psycopg2.connect(
            host="localhost",
            database="rec_io_db",
            user="rec_io_user",
            password="rec_io_password"
        )
        
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM system.health_status WHERE id = 1")
            result = cursor.fetchone()
            
            if result:
                return {
                    "overall_status": result[1],
                    "cpu_percent": float(result[2]) if result[2] else None,
                    "memory_percent": float(result[3]) if result[3] else None,
                    "disk_percent": float(result[4]) if result[4] else None,
                    "database_status": result[5],
                    "supervisor_status": result[6],
                    "services_healthy": result[7],
                    "services_total": result[8],
                    "failed_services": result[9] or [],
                    "timestamp": result[11].isoformat() if result[11] else None
                }
            else:
                return {"error": "No health data available"}
                
    except Exception as e:
        print(f"[DB SYSTEM HEALTH] Error: {e}")
        return {"error": "Database error"}

@app.get("/api/db/trades")
def get_trades_from_postgresql():
    """Get trades data from PostgreSQL database."""
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        
        # Connect to PostgreSQL
        conn = psycopg2.connect(
            host="localhost",
            database="rec_io_db",
            user="rec_io_user",
            password="rec_io_password"
        )
        
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            # Get all trades from PostgreSQL
            cursor.execute("""
                SELECT * FROM users.trades_0001 
                ORDER BY id DESC 
                LIMIT 100
            """)
            trades = cursor.fetchall()
            
            # Convert RealDictRow objects to regular dictionaries
            trades_list = []
            for trade in trades:
                trade_dict = dict(trade)
                # Ensure all fields are present for frontend compatibility
                trade_dict.update({
                    'id': trade_dict.get('id'),
                    'status': trade_dict.get('status', ''),
                    'date': trade_dict.get('date', ''),
                    'time': trade_dict.get('time', ''),
                    'symbol': trade_dict.get('symbol', 'BTC'),
                    'trade_strategy': trade_dict.get('trade_strategy', ''),
                    'contract': trade_dict.get('contract', ''),
                    'strike': trade_dict.get('strike', ''),
                    'side': trade_dict.get('side', ''),
                    'prob': trade_dict.get('prob'),
                    'diff': trade_dict.get('diff'),
                    'buy_price': trade_dict.get('buy_price'),
                    'sell_price': trade_dict.get('sell_price'),
                    'position': trade_dict.get('position'),
                    'closed_at': trade_dict.get('closed_at'),
                    'fees': trade_dict.get('fees'),
                    'pnl': trade_dict.get('pnl'),
                    'symbol_open': trade_dict.get('symbol_open'),
                    'symbol_close': trade_dict.get('symbol_close'),
                    'momentum': trade_dict.get('momentum'),
                    'win_loss': trade_dict.get('win_loss')
                })
                trades_list.append(trade_dict)
            
            conn.close()
            return {"trades": trades_list}
            
    except Exception as e:
        print(f"Error getting trades from PostgreSQL: {e}")
        return {"trades": []}

# Fingerprint and strike probability endpoints
@app.get("/api/current_fingerprint")
async def get_current_fingerprint():
    """Get current fingerprint information."""
    try:
        from util.probability_calculator import get_probability_calculator
        
        calculator = get_probability_calculator()
        
        fingerprint_info = {
            "symbol": calculator.symbol,
            "current_momentum_bucket": calculator.current_momentum_bucket,
            "last_used_momentum_bucket": calculator.last_used_momentum_bucket,
            "fingerprint": f"{calculator.symbol}_fingerprint_directional_momentum_{calculator.current_momentum_bucket:03d}.csv",
            "fingerprint_file": f"{calculator.symbol}_fingerprint_directional_momentum_{calculator.current_momentum_bucket:03d}.csv",
            "available_buckets": list(calculator.momentum_fingerprints.keys()) if hasattr(calculator, 'momentum_fingerprints') else []
        }
        
        print(f"[FINGERPRINT] Current fingerprint: {fingerprint_info['fingerprint_file']}")
        return fingerprint_info
        
    except Exception as e:
        print(f"Error getting fingerprint: {e}")
        return {"fingerprint": "error", "error": str(e)}

@app.get("/api/momentum")
async def get_current_momentum():
    """Get current momentum score from the unified API."""
    try:
        # Get momentum data from live_data_analysis (the correct source)
        from live_data_analysis import get_momentum_data
        momentum_data = get_momentum_data()
        
        # Extract the weighted momentum score
        momentum_score = momentum_data.get('weighted_momentum_score', 0)
        
        return {
            "status": "ok",
            "momentum_score": momentum_score
        }
    except Exception as e:
        print(f"Error getting momentum from live_data_analysis: {e}")
        return {
            "status": "error",
            "momentum_score": 0,
            "error": "Unable to get momentum from live_data_analysis"
        }

@app.get("/api/btc_price")
async def get_btc_price():
    """Get current BTC price directly from btc_price_watchdog database."""
    try:
        from backend.util.paths import get_btc_price_history_dir
        import sqlite3
        import os
        
        btc_price_history_db = os.path.join(get_btc_price_history_dir(), "btc_price_history.db")
        
        if not os.path.exists(btc_price_history_db):
            return {"price": None, "error": "BTC price database not found"}
        
        conn = sqlite3.connect(btc_price_history_db)
        cursor = conn.cursor()
        cursor.execute("SELECT price FROM price_log ORDER BY timestamp DESC LIMIT 1")
        result = cursor.fetchone()
        conn.close()
        
        if result:
            price = float(result[0])
            return {"price": price, "source": "btc_price_watchdog"}
        else:
            return {"price": None, "error": "No price data available"}
            
    except Exception as e:
        print(f"Error getting BTC price: {e}")
        return {"price": None, "error": str(e)}

@app.get("/api/momentum_score")
async def get_momentum_score():
    """Get current momentum score for mobile."""
    try:
        from live_data_analysis import get_momentum_data
        momentum_data = get_momentum_data()
        weighted_score = momentum_data.get('weighted_momentum_score', 0)
        return {"weighted_score": weighted_score}
    except Exception as e:
        print(f"Error getting momentum score: {e}")
        return {"weighted_score": 0, "error": str(e)}

@app.get("/api/strike_table")
async def get_strike_table_mobile():
    """Get strike table data for mobile."""
    try:
        from live_data_analysis import get_strike_table_data
        strike_data = get_strike_table_data()
        return {"strikes": strike_data}
    except Exception as e:
        print(f"Error getting strike table: {e}")
        return {"strikes": [], "error": str(e)}

# === PREFERENCES API ENDPOINTS ===

@app.post("/api/set_auto_stop")
async def set_auto_stop(request: Request):
    data = await request.json()
    enabled = bool(data.get("enabled", False))
    
    # Return immediate response
    response_data = {"status": "ok", "enabled": enabled}
    
    # Handle file operations asynchronously
    async def update_preferences():
        try:
            # Update PostgreSQL directly (new workflow)
            update_auto_trade_settings_postgresql(auto_stop=enabled)
            
            # Broadcast the update to connected clients
            await broadcast_preferences_update()
        except Exception as e:
            print(f"[Auto Stop Update Error] {e}")
    
    # Start async task without waiting
    import asyncio
    asyncio.create_task(update_preferences())
    
    return response_data

@app.post("/api/set_auto_entry")
async def set_auto_entry(request: Request):
    data = await request.json()
    enabled = bool(data.get("enabled", False))
    
    # Return immediate response
    response_data = {"status": "ok", "enabled": enabled}
    
    # Handle file operations asynchronously
    async def update_preferences():
        try:
            # Update PostgreSQL directly (new workflow)
            update_auto_trade_settings_postgresql(auto_entry=enabled)
            
            # Broadcast the update to connected clients
            await broadcast_preferences_update()
            
            # Trigger auto entry supervisor to reload settings
            try:
                import subprocess
                import sys
                # Import the auto_entry_supervisor module and call reload function
                sys.path.append('/Users/ericwais1/rec_io_20')
                from backend.auto_entry_supervisor import log
                log("[AUTO ENTRY] Settings updated via API - supervisor will reload on next check")
            except Exception as e:
                print(f"[Auto Entry Status Update Error] {e}")
        except Exception as e:
            print(f"[Auto Entry Update Error] {e}")
    
    # Start async task without waiting
    import asyncio
    asyncio.create_task(update_preferences())
    
    return response_data

# Diff mode is now local only - no API endpoint needed

@app.post("/api/set_position_size")
async def set_position_size(request: Request):
    data = await request.json()
    position_size = int(data.get("position_size", 100))
    
    # Update PostgreSQL
    update_trade_preferences_postgresql(position_size=position_size)
    
    # Also update legacy JSON for compatibility during migration
    prefs = load_preferences()
    try:
        prefs["position_size"] = position_size
        await save_preferences(prefs)
        await broadcast_preferences_update()
    except Exception as e:
        print(f"[Set Position Size Error] {e}")
    return {"status": "ok"}

@app.post("/api/set_multiplier")
async def set_multiplier(request: Request):
    data = await request.json()
    multiplier = int(data.get("multiplier", 1))
    
    # Update PostgreSQL
    update_trade_preferences_postgresql(multiplier=multiplier)
    
    # Also update legacy JSON for compatibility during migration
    prefs = load_preferences()
    try:
        prefs["multiplier"] = multiplier
        await save_preferences(prefs)
        await broadcast_preferences_update()
    except Exception as e:
        print(f"[Set Multiplier Error] {e}")
    return {"status": "ok"}

@app.post("/api/update_preferences")
async def update_preferences(request: Request):
    data = await request.json()
    prefs = load_preferences()
    updated = False

    if "position_size" in data:
        try:
            prefs["position_size"] = int(data["position_size"])
            updated = True
        except Exception as e:
            print(f"[Invalid Position Size] {e}")

    if "multiplier" in data:
        try:
            prefs["multiplier"] = int(data["multiplier"])
            updated = True
        except Exception as e:
            print(f"[Invalid Multiplier] {e}")

    if updated:
        await save_preferences(prefs)
        await broadcast_preferences_update()
    return {"status": "ok"}

@app.get("/api/get_preferences")
async def get_preferences():
    """Get current preferences"""
    prefs = load_preferences()
    
    # Add trade strategy from PostgreSQL
    try:
        trade_prefs = get_trade_preferences_postgresql()
        prefs["trade_strategy"] = trade_prefs["trade_strategy"]
    except Exception as e:
        print(f"[Get Preferences Error] Failed to get trade strategy from PostgreSQL: {e}")
        prefs["trade_strategy"] = "Hourly HTC"  # Default fallback
    
    return prefs

# === ACTIVE TRADES PROXY ROUTE ===
@app.get("/api/active_trades")
async def proxy_active_trades():
    """Proxy route to forward active trades requests to the active trade supervisor"""
    try:
        # Forward request to active trade supervisor
        response = requests.get(f"http://localhost:{ACTIVE_TRADE_SUPERVISOR_PORT}/api/active_trades", timeout=5)
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"Active trade supervisor returned status {response.status_code}"}, response.status_code
    except requests.exceptions.RequestException as e:
        return {"error": f"Failed to connect to active trade supervisor: {str(e)}"}, 503

# Legacy trade history preferences path removed - all data now in PostgreSQL

def load_trade_history_preferences():
    """Load trade history preferences from PostgreSQL"""
    try:
        return get_trade_history_preferences_postgresql()
    except Exception as e:
        print(f"[Trade History Preferences Load Error] {e}")
        return {
            "date_filter": "TODAY",
            "custom_date_start": None,
            "custom_date_end": None,
            "win_filter": True,
            "loss_filter": True,
            "sort_key": None,
            "sort_asc": True,
            "page_size": 50,
            "last_search_timestamp": time.time()
        }

def save_trade_history_preferences(preferences):
    """Save trade history preferences to PostgreSQL"""
    try:
        # Prepare data for PostgreSQL
        update_data = {}
        if "date_filter" in preferences:
            update_data["date_filter"] = str(preferences["date_filter"])
        if "custom_date_start" in preferences:
            update_data["custom_date_start"] = preferences["custom_date_start"]
        if "custom_date_end" in preferences:
            update_data["custom_date_end"] = preferences["custom_date_end"]
        if "win_filter" in preferences:
            update_data["win_filter"] = bool(preferences["win_filter"])
        if "loss_filter" in preferences:
            update_data["loss_filter"] = bool(preferences["loss_filter"])
        if "sort_key" in preferences:
            update_data["sort_key"] = preferences["sort_key"]
        if "sort_asc" in preferences:
            update_data["sort_asc"] = bool(preferences["sort_asc"])
        if "page_size" in preferences:
            update_data["page_size"] = int(preferences["page_size"])
        if "last_search_timestamp" in preferences:
            update_data["last_search_timestamp"] = int(preferences["last_search_timestamp"])
        
        if update_data:
            update_trade_history_preferences_postgresql(**update_data)
            print(f"[Trade History Preferences] ✅ Updated PostgreSQL: {list(update_data.keys())}")
    except Exception as e:
        print(f"[Trade History Preferences Save Error] {e}")

@app.get("/api/get_trade_history_preferences")
async def get_trade_history_preferences():
    """Get trade history preferences"""
    return load_trade_history_preferences()

@app.post("/api/set_trade_history_preferences")
async def set_trade_history_preferences(request: Request):
    """Set trade history preferences"""
    try:
        data = await request.json()
        preferences = load_trade_history_preferences()
        
        # Update preferences with new data
        for key, value in data.items():
            preferences[key] = value
        
        # Update timestamp
        preferences["last_search_timestamp"] = time.time()
        
        # Save preferences
        save_trade_history_preferences(preferences)
        
        return {"status": "ok", "preferences": preferences}
    except Exception as e:
        print(f"[Trade History Preferences Set Error] {e}")
        return {"status": "error", "message": str(e)}

@app.get("/api/get_auto_stop")
async def get_auto_stop():
    prefs = load_preferences()
    return {"enabled": prefs.get("auto_stop", True)}

@app.get("/api/get_auto_trade_settings")
async def get_auto_trade_settings():
    """Get auto trade settings from PostgreSQL"""
    settings = get_auto_trade_settings_postgresql()
    return settings

@app.get("/api/get_auto_entry_status")
async def get_auto_entry_status():
    """Get current auto entry status and cooldown timer from PostgreSQL"""
    try:
        conn = psycopg2.connect(
            host="localhost",
            database="rec_io_db",
            user="rec_io_user",
            password="rec_io_password"
        )
        with conn.cursor() as cursor:
            cursor.execute("SELECT auto_entry_status, cooldown_timer FROM users.auto_trade_settings_0001 WHERE id = 1")
            result = cursor.fetchone()
            status = result[0] if result else "DISABLED"
            cooldown_timer = result[1] if result and result[1] is not None else 0
            conn.close()
            return {"status": status, "cooldown_timer": cooldown_timer}
    except Exception as e:
        print(f"Error getting auto entry status: {e}")
        return {"status": "DISABLED", "cooldown_timer": 0, "error": str(e)}

@app.get("/api/get_trade_preferences")
async def get_trade_preferences():
    """Get trade preferences from PostgreSQL"""
    return get_trade_preferences_postgresql()

@app.post("/api/update_trade_preferences")
async def update_trade_preferences(request: Request):
    """Update trade preferences in PostgreSQL"""
    try:
        data = await request.json()
        
        # Update PostgreSQL
        update_trade_preferences_postgresql(**data)
        
        # Also update legacy JSON for compatibility during migration
        prefs = load_preferences()
        if 'trade_strategy' in data:
            prefs['trade_strategy'] = data['trade_strategy']
        if 'position_size' in data:
            prefs['position_size'] = data['position_size']
        if 'multiplier' in data:
            prefs['multiplier'] = data['multiplier']
        
        await save_preferences(prefs)
        await broadcast_preferences_update()
        
        return {"status": "ok", "updated": data}
    except Exception as e:
        print(f"Error updating trade preferences: {e}")
        return {"status": "error", "message": str(e)}

@app.post("/api/update_auto_entry_settings")
async def update_auto_entry_settings(request: Request):
    """Update auto entry settings in PostgreSQL"""
    data = await request.json()
    
    # Extract auto entry settings
    update_data = {}
    if "min_probability" in data:
        update_data["min_probability"] = int(data["min_probability"])
    if "min_differential" in data:
        update_data["min_differential"] = float(data["min_differential"])
    if "min_time" in data:
        update_data["min_time"] = int(data["min_time"])
    if "max_time" in data:
        update_data["max_time"] = int(data["max_time"])
    if "allow_re_entry" in data:
        update_data["allow_re_entry"] = bool(data["allow_re_entry"])
    if "spike_alert_enabled" in data:
        update_data["spike_alert_enabled"] = bool(data["spike_alert_enabled"])
    if "spike_alert_momentum_threshold" in data:
        update_data["spike_alert_momentum_threshold"] = int(data["spike_alert_momentum_threshold"])
    if "spike_alert_cooldown_threshold" in data:
        update_data["spike_alert_cooldown_threshold"] = int(data["spike_alert_cooldown_threshold"])
    if "spike_alert_cooldown_minutes" in data:
        update_data["spike_alert_cooldown_minutes"] = int(data["spike_alert_cooldown_minutes"])
    
    if update_data:
        update_auto_trade_settings_postgresql(**update_data)
    
    return {"status": "ok", "updated": update_data}

@app.post("/api/update_auto_stop_settings")
async def update_auto_stop_settings(request: Request):
    """Update auto stop settings in PostgreSQL"""
    data = await request.json()
    
    # Extract auto stop settings
    update_data = {}
    if "current_probability" in data:
        update_data["current_probability"] = int(data["current_probability"])
    if "min_ttc_seconds" in data:
        update_data["min_ttc_seconds"] = int(data["min_ttc_seconds"])
    if "momentum_spike_enabled" in data:
        update_data["momentum_spike_enabled"] = bool(data["momentum_spike_enabled"])
    if "momentum_spike_threshold" in data:
        update_data["momentum_spike_threshold"] = int(data["momentum_spike_threshold"])
    
    if update_data:
        update_auto_trade_settings_postgresql(**update_data)
    
    return {"status": "ok", "updated": update_data}

import os
# Legacy auto stop settings path removed - all data now in PostgreSQL

# Legacy auto stop settings functions removed - all data now in PostgreSQL

@app.get("/api/get_auto_stop_settings")
async def get_auto_stop_settings():
    return get_auto_stop_settings_postgresql()

@app.post("/api/set_auto_stop_settings")
async def set_auto_stop_settings(request: Request):
    data = await request.json()
    
    # Update PostgreSQL database
    try:
        update_data = {}
        if "current_probability" in data:
            update_data["current_probability"] = int(data["current_probability"])
        if "min_ttc_seconds" in data:
            update_data["min_ttc_seconds"] = int(data["min_ttc_seconds"])
        if "momentum_spike_enabled" in data:
            update_data["momentum_spike_enabled"] = bool(data["momentum_spike_enabled"])
        if "momentum_spike_threshold" in data:
            update_data["momentum_spike_threshold"] = int(data["momentum_spike_threshold"])
        
        if update_data:
            update_auto_trade_settings_postgresql(**update_data)
            print(f"[Auto Stop Settings] ✅ Updated PostgreSQL: {list(update_data.keys())}")
    except Exception as e:
        print(f"[Auto Stop Settings] ❌ PostgreSQL Update Error: {e}")
    
    # Return updated settings from PostgreSQL
    updated_settings = get_auto_stop_settings_postgresql()
    return {"status": "ok", **updated_settings}

# Legacy auto entry settings path removed - all data now in PostgreSQL

# Legacy auto entry settings functions removed - all data now in PostgreSQL

@app.get("/api/get_auto_entry_settings")
async def get_auto_entry_settings():
    return get_auto_trade_settings_postgresql()

@app.post("/api/set_auto_entry_settings")
async def set_auto_entry_settings(request: Request):
    data = await request.json()
    
    # Update PostgreSQL database
    try:
        update_data = {}
        if "min_probability" in data:
            update_data["min_probability"] = int(data["min_probability"])
        if "min_differential" in data:
            update_data["min_differential"] = float(data["min_differential"])
        if "min_time" in data:
            update_data["min_time"] = int(data["min_time"])
        if "max_time" in data:
            update_data["max_time"] = int(data["max_time"])
        if "allow_re_entry" in data:
            update_data["allow_re_entry"] = bool(data["allow_re_entry"])
        if "spike_alert_enabled" in data:
            update_data["spike_alert_enabled"] = bool(data["spike_alert_enabled"])
        if "spike_alert_momentum_threshold" in data:
            update_data["spike_alert_momentum_threshold"] = int(data["spike_alert_momentum_threshold"])
        if "spike_alert_cooldown_threshold" in data:
            update_data["spike_alert_cooldown_threshold"] = int(data["spike_alert_cooldown_threshold"])
        if "spike_alert_cooldown_minutes" in data:
            update_data["spike_alert_cooldown_minutes"] = int(data["spike_alert_cooldown_minutes"])
        
        if update_data:
            update_auto_trade_settings_postgresql(**update_data)
            print(f"[Auto Entry Settings] ✅ Updated PostgreSQL: {list(update_data.keys())}")
    except Exception as e:
        print(f"[Auto Entry Settings] ❌ PostgreSQL Update Error: {e}")
    
    # Return updated settings from PostgreSQL
    updated_settings = get_auto_trade_settings_postgresql()
    return {"status": "ok", **updated_settings}

@app.post("/api/trigger_open_trade")
async def trigger_open_trade(request: Request):
    """Trigger trade opening directly via the trade_manager service."""
    try:
        data = await request.json()
        strike = data.get("strike")
        side = data.get("side")
        ticker = data.get("ticker")
        buy_price = data.get("buy_price")
        prob = data.get("prob")
        symbol_open = data.get("symbol_open")
        momentum = data.get("momentum")
        contract = data.get("contract")
        symbol = data.get("symbol")
        position = data.get("position")
        trade_strategy = data.get("trade_strategy")
        
        print(f"[TRIGGER OPEN TRADE] Received request: strike={strike}, side={side}, ticker={ticker}, buy_price={buy_price}, prob={prob}, symbol_open={symbol_open}, momentum={momentum}")
        
        # Forward the request directly to the trade_manager service
        trade_manager_port = get_port("trade_manager")
        from backend.util.paths import get_host
        trade_manager_host = get_host()
        trade_manager_url = f"http://{trade_manager_host}:{trade_manager_port}/trades"
        
        # Create the exact same payload that trade_initiator would create
        import uuid
        from datetime import datetime
        from zoneinfo import ZoneInfo
        
        # Generate unique ticket ID (same format as trade_initiator)
        ticket_id = f"TICKET-{uuid.uuid4().hex[:9]}-{int(datetime.now().timestamp() * 1000)}"
        
        # Get current time in Eastern Time (same as trade_initiator)
        now = datetime.now(ZoneInfo("America/New_York"))
        eastern_date = now.strftime('%Y-%m-%d')
        eastern_time = now.strftime('%H:%M:%S')
        
        # Convert side format (yes/no to Y/N) - same as trade_initiator
        converted_side = side
        if side == "yes":
            converted_side = "Y"
        elif side == "no":
            converted_side = "N"
        
        # Prepare the trade data exactly like trade_initiator does
        trade_data = {
            "ticket_id": ticket_id,
            "status": "pending",
            "date": eastern_date,
            "time": eastern_time,
            "symbol": symbol or "BTC",
            "market": "Kalshi",
            "trade_strategy": trade_strategy or "Hourly HTC",
            "contract": contract or "BTC Market",
            "strike": strike,
            "side": converted_side,
            "ticker": ticker,
            "buy_price": buy_price,
            "position": position or 1,
            "symbol_open": symbol_open,
            "symbol_close": None,
            "momentum": momentum,
            "prob": prob,
            "win_loss": None,
            "entry_method": data.get("entry_method", "manual")
        }
        
        # Send request directly to trade_manager
        response = requests.post(trade_manager_url, json=trade_data, timeout=10)
        
        if response.status_code == 201:
            result = response.json()
            print(f"[TRIGGER OPEN TRADE] Trade initiated successfully: {result}")
            return {
                "status": "success",
                "message": "Trade initiated successfully",
                "trade_data": result
            }
        else:
            print(f"[TRIGGER OPEN TRADE] Trade initiation failed: {response.status_code} - {response.text}")
            return {
                "status": "error",
                "message": f"Trade initiation failed: {response.status_code}",
                "details": response.text
            }
        
    except Exception as e:
        print(f"[TRIGGER OPEN TRADE] Error: {e}")
        return {"status": "error", "message": str(e)}



@app.get("/frontend-changes")
def frontend_changes():
    """Get the latest modification time of frontend files for cache busting."""
    import os
    latest = 0
    for root, dirs, files in os.walk("frontend"):
        for f in files:
            path = os.path.join(root, f)
            try:
                mtime = os.path.getmtime(path)
                if mtime > latest:
                    latest = mtime
            except Exception:
                pass
    return {"last_modified": latest}

@app.get("/api/live_probabilities")
async def get_live_probabilities():
    """Get live probabilities from the unified probability endpoint"""
    try:
        live_prob_file = os.path.join(get_data_dir(), "live_data", "live_probabilities", "btc_live_probabilities.json")
        
        if os.path.exists(live_prob_file):
            with open(live_prob_file, 'r') as f:
                data = json.load(f)
            return data
        else:
            return {"error": "Live probabilities file not found"}
    except Exception as e:
        return {"error": f"Error loading live probabilities: {str(e)}"}

def safe_read_json(filepath: str, timeout: float = 0.1):
    """Read JSON data with file locking to prevent race conditions"""
    try:
        with open(filepath, 'r') as f:
            # Try to acquire a shared lock with timeout
            fcntl.flock(f.fileno(), fcntl.LOCK_SH | fcntl.LOCK_NB)
            try:
                return json.load(f)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except (IOError, OSError) as e:
        # If locking fails, fall back to normal read (rare)
        print(f"Warning: File locking failed for {filepath}: {e}")
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except Exception as read_error:
            print(f"Error reading JSON from {filepath}: {read_error}")
            return None

@app.get("/api/strike_tables/{symbol}")
async def get_strike_table(symbol: str):
    """Get strike table data for a specific symbol"""
    try:
        # Convert symbol to lowercase for consistency
        symbol_lower = symbol.lower()
        strike_table_file = os.path.join(get_data_dir(), "live_data", "markets", "kalshi", "strike_tables", f"{symbol_lower}_strike_table.json")
        
        if os.path.exists(strike_table_file):
            data = safe_read_json(strike_table_file)
            if data is None:
                return {"error": f"Error reading strike table file for {symbol}"}
            return data
        else:
            return {"error": f"Strike table file not found for {symbol}"}
    except Exception as e:
        return {"error": f"Error loading strike table for {symbol}: {str(e)}"}

@app.get("/api/watchlist/{symbol}")
async def get_watchlist(symbol: str):
    """Get watchlist data for a specific symbol"""
    try:
        # Convert symbol to lowercase for consistency
        symbol_lower = symbol.lower()
        watchlist_file = os.path.join(get_data_dir(), "live_data", "markets", "kalshi", "strike_tables", f"{symbol_lower}_watchlist.json")
        
        if os.path.exists(watchlist_file):
            data = safe_read_json(watchlist_file)
            if data is None:
                return {"error": f"Error reading watchlist file for {symbol}"}
            return data
        else:
            return {"error": f"Watchlist file not found for {symbol}"}
    except Exception as e:
        return {"error": f"Error loading watchlist for {symbol}: {str(e)}"}

@app.get("/api/unified_ttc/{symbol}")
async def get_unified_ttc(symbol: str):
    """Get unified TTC data for a specific symbol from unified production coordinator"""
    try:
        from unified_production_coordinator import get_unified_ttc
        return get_unified_ttc(symbol)
    except Exception as e:
        return {"error": f"Error getting unified TTC: {str(e)}"}

@app.get("/api/failure_detector_status")
async def get_failure_detector_status():
    """Get the current status of the cascading failure detector."""
    try:
        from backend.cascading_failure_detector import CascadingFailureDetector
        detector = CascadingFailureDetector()
        return detector.generate_status_report()
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/auto_entry_indicator")
async def get_auto_entry_indicator():
    """Proxy endpoint to get auto entry indicator state from auto_entry_supervisor"""
    try:
        from backend.core.port_config import get_port
        port = get_port("auto_entry_supervisor")
        # Use localhost for internal service communication
        url = f"http://localhost:{port}/api/auto_entry_indicator"
        response = requests.get(url, timeout=2)
        if response.ok:
            return response.json()
        else:
            return {"error": f"Auto entry supervisor returned {response.status_code}"}
    except Exception as e:
        return {"error": f"Error getting auto entry indicator: {str(e)}"}

# Log event endpoint
from backend.util.trade_logger import log_trade_event, get_trade_logs

@app.get("/api/trade_logs")
async def get_trade_logs_endpoint(ticket_id: str = None, service: str = None, limit: int = 100):
    """Get trade logs from PostgreSQL"""
    try:
        logs = get_trade_logs(ticket_id=ticket_id, service=service, limit=limit)
        return {"status": "ok", "logs": logs}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/historical_price_data")
async def get_historical_price_data(symbol: str = "BTC", limit: int = 1000, start_date: str = None, end_date: str = None):
    """Get historical price data from PostgreSQL"""
    try:
        import psycopg2
        from datetime import datetime
        
        # Connect to PostgreSQL
        conn = psycopg2.connect(
            host="localhost",
            database="rec_io_db",
            user="rec_io_user",
            password="rec_io_password"
        )
        
        # Build query
        query = """
            SELECT timestamp, open_price, high_price, low_price, close_price, volume, momentum
            FROM live_data.historical_price_data 
            WHERE symbol = %s
        """
        params = [symbol.upper()]
        
        # Add date filters if provided
        if start_date:
            query += " AND timestamp >= %s"
            params.append(start_date)
        if end_date:
            query += " AND timestamp <= %s"
            params.append(end_date)
        
        query += " ORDER BY timestamp DESC LIMIT %s"
        params.append(limit)
        
        with conn.cursor() as cursor:
            cursor.execute(query, params)
            results = cursor.fetchall()
            
        conn.close()
        
        # Format results
        data = []
        for row in results:
            data.append({
                "timestamp": row[0].isoformat() if row[0] else None,
                "open": float(row[1]) if row[1] else None,
                "high": float(row[2]) if row[2] else None,
                "low": float(row[3]) if row[3] else None,
                "close": float(row[4]) if row[4] else None,
                "volume": float(row[5]) if row[5] else None,
                "momentum": float(row[6]) if row[6] else None
            })
        
        return {
            "status": "ok",
            "symbol": symbol.upper(),
            "count": len(data),
            "data": data
        }
        
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/log_event")
async def log_event(request: Request):
    """Log trade events to PostgreSQL instead of text files"""
    try:
        data = await request.json()
        ticket_id = data.get("ticket_id", "UNKNOWN")
        message = data.get("message", "No message provided")

        # Log to PostgreSQL
        log_trade_event(ticket_id, message, service="main")

        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/notify_automated_trade")
async def notify_automated_trade(request: Request):
    """Receive automated trade notification and broadcast to frontend via WebSocket"""
    try:
        data = await request.json()
        print(f"[MAIN] 🔔 Received automated trade notification: {data}")
        
        # Broadcast to all connected WebSocket clients
        message = {
            "type": "automated_trade_triggered",
            "data": data
        }
        
        # Send to preferences WebSocket clients
        for websocket in connected_clients.copy():
            try:
                await websocket.send_text(json.dumps(message))
            except Exception as e:
                print(f"Error sending to WebSocket client: {e}")
                connected_clients.discard(websocket)
        
        print(f"[MAIN] ✅ Automated trade notification broadcasted to {len(connected_clients)} clients")
        return {"success": True, "message": "Notification broadcasted"}
        
    except Exception as e:
        print(f"[MAIN] ❌ Error handling automated trade notification: {e}")
        return {"success": False, "error": str(e)}

@app.post("/api/notify_automated_close")
async def notify_automated_close(request: Request):
    """Receive automated trade close notification and broadcast to frontend via WebSocket"""
    try:
        data = await request.json()
        print(f"[MAIN] 🔔 Received automated trade close notification: {data}")
        
        # Broadcast to all connected WebSocket clients
        message = {
            "type": "automated_trade_closed",
            "data": data
        }
        
        # Send to preferences WebSocket clients
        for websocket in connected_clients.copy():
            try:
                await websocket.send_text(json.dumps(message))
            except Exception as e:
                print(f"Error sending to WebSocket client: {e}")
                connected_clients.discard(websocket)
        
        print(f"[MAIN] ✅ Automated trade close notification broadcasted to {len(connected_clients)} clients")
        return {"success": True, "message": "Close notification broadcasted"}
        
    except Exception as e:
        print(f"[MAIN] ❌ Error handling automated trade close notification: {e}")
        return {"success": False, "error": str(e)}

@app.post("/api/broadcast_auto_entry_indicator")
async def broadcast_auto_entry_indicator(request: Request):
    """Receive auto entry indicator change and broadcast to frontend via WebSocket"""
    try:
        data = await request.json()
        print(f"[MAIN] 🔔 Received auto entry indicator change: {data}")
        
        # Broadcast to all connected WebSocket clients
        message = {
            "type": "auto_entry_indicator_change",
            "data": data
        }
        
        # Send to preferences WebSocket clients
        for websocket in connected_clients.copy():
            try:
                await websocket.send_text(json.dumps(message))
            except Exception as e:
                print(f"Error sending to WebSocket client: {e}")
                connected_clients.discard(websocket)
        
        print(f"[MAIN] ✅ Auto entry indicator change broadcasted to {len(connected_clients)} clients")
        return {"success": True, "message": "Indicator change broadcasted"}
        
    except Exception as e:
        print(f"[MAIN] ❌ Error handling auto entry indicator change: {e}")
        return {"success": False, "error": str(e)}

@app.post("/api/broadcast_active_trades_change")
async def broadcast_active_trades_change(request: Request):
    """Receive active trades change and broadcast to frontend via WebSocket"""
    try:
        data = await request.json()
        print(f"[MAIN] 🔔 Received active trades change: {data.get('count', 0)} trades")
        
        # Broadcast to all connected WebSocket clients
        message = {
            "type": "active_trades_change",
            "data": data
        }
        
        # Send to preferences WebSocket clients
        for websocket in connected_clients.copy():
            try:
                await websocket.send_text(json.dumps(message))
            except Exception as e:
                print(f"Error sending to WebSocket client: {e}")
                connected_clients.discard(websocket)
        
        print(f"[MAIN] ✅ Active trades change broadcasted to {len(connected_clients)} clients")
        return {"success": True, "message": "Active trades change broadcasted"}
        
    except Exception as e:
        print(f"[MAIN] ❌ Error handling active trades change: {e}")
        return {"success": False, "error": str(e)}

# Momentum and fingerprint now consolidated in strike table - no separate broadcast endpoints needed

@app.post("/api/notify_db_change")
async def notify_db_change(request: Request):
    """Handle database change notifications from kalshi_account_sync"""
    try:
        data = await request.json()
        db_name = data.get("db_name")
        timestamp = data.get("timestamp")
        change_data = data.get("change_data", {})
        
        print(f"📡 Received DB change notification: {db_name} at {timestamp}")
        
        # Broadcast to all connected WebSocket clients
        await broadcast_db_change(db_name, {
            "timestamp": timestamp,
            "change_data": change_data
        })
        
        return {"status": "ok", "message": f"Notification sent for {db_name}"}
    except Exception as e:
        print(f"❌ Error handling DB change notification: {e}")
        return {"status": "error", "message": str(e)}

# Authentication endpoints
@app.post("/api/auth/login")
async def login(request: Request):
    """Handle user login"""
    try:
        data = await request.json()
        username = data.get("username", "")
        password = data.get("password", "")
        remember_device = data.get("rememberDevice", False)
        
        # Get user credentials
        credentials = get_user_credentials()
        
        # Check credentials
        if username == credentials["username"]:
            # Check if we have a hashed password (PostgreSQL) or plain text (JSON fallback)
            if "password_hash" in credentials:
                # PostgreSQL authentication with hashed password
                if verify_password(password, credentials["password_hash"]):
                    auth_success = True
                else:
                    auth_success = False
            else:
                # JSON fallback with plain text password
                if password == credentials["password"]:
                    auth_success = True
                else:
                    auth_success = False
            
            if auth_success:
                # Generate authentication token
                token = generate_token()
                device_id = f"device_{secrets.token_hex(8)}"
                
                # Store token
                auth_tokens = load_auth_tokens()
                auth_tokens[token] = {
                    "username": username,
                    "created": datetime.now().isoformat(),
                    "expires": (datetime.now() + timedelta(days=30)).isoformat() if remember_device else (datetime.now() + timedelta(hours=24)).isoformat()
                }
                save_auth_tokens(auth_tokens)
                
                # Store device token if remember device
                if remember_device:
                    device_tokens = load_device_tokens()
                    device_tokens[device_id] = {
                        "username": username,
                        "token": token,
                        "created": datetime.now().isoformat(),
                        "expires": (datetime.now() + timedelta(days=365)).isoformat()
                    }
                    save_device_tokens(device_tokens)
                
                print(f"[AUTH] User {username} logged in successfully")
                return {
                    "success": True,
                    "token": token,
                    "deviceId": device_id,
                    "username": username,
                    "name": credentials["name"]
                }
            else:
                print(f"[AUTH] Failed login attempt for username: {username}")
                return {
                    "success": False,
                    "error": "Invalid username or password"
                }
        else:
            print(f"[AUTH] Failed login attempt for username: {username}")
            return {
                "success": False,
                "error": "Invalid username or password"
            }
    except Exception as e:
        print(f"[AUTH] Login error: {e}")
        return {
            "success": False,
            "error": "Authentication error"
        }

@app.post("/api/auth/verify")
async def verify_auth(request: Request):
    """Verify authentication token"""
    try:
        data = await request.json()
        token = data.get("token", "")
        device_id = data.get("deviceId", "")
        
        # Check for local development bypass
        if token.startswith("local_dev_"):
            return {"authenticated": True, "username": "local_dev", "name": "Local Development"}
        
        # Check auth tokens
        auth_tokens = load_auth_tokens()
        if token in auth_tokens:
            token_data = auth_tokens[token]
            expires = datetime.fromisoformat(token_data["expires"])
            
            if datetime.now() < expires:
                return {
                    "authenticated": True,
                    "username": token_data["username"],
                    "name": get_user_credentials()["name"]
                }
        
        # Check device tokens
        device_tokens = load_device_tokens()
        if device_id in device_tokens:
            device_data = device_tokens[device_id]
            expires = datetime.fromisoformat(device_data["expires"])
            
            if datetime.now() < expires:
                return {
                    "authenticated": True,
                    "username": device_data["username"],
                    "name": get_user_credentials()["name"]
                }
        
        return {"authenticated": False}
    except Exception as e:
        print(f"[AUTH] Verification error: {e}")
        return {"authenticated": False}

@app.post("/api/auth/logout")
async def logout(request: Request):
    """Handle user logout"""
    try:
        data = await request.json()
        token = data.get("token", "")
        device_id = data.get("deviceId", "")
        
        # Remove auth token
        auth_tokens = load_auth_tokens()
        if token in auth_tokens:
            del auth_tokens[token]
            save_auth_tokens(auth_tokens)
        
        # Remove device token
        device_tokens = load_device_tokens()
        if device_id in device_tokens:
            del device_tokens[device_id]
            save_device_tokens(device_tokens)
        
        print(f"[AUTH] User logged out successfully")
        return {"success": True}
    except Exception as e:
        print(f"[AUTH] Logout error: {e}")
        return {"success": False, "error": str(e)}

@app.get("/api/user/info")
async def get_user_info():
    """Get current user information from database"""
    try:
        # Get user credentials from database
        credentials = get_user_credentials()
        
        return {
            "user_id": credentials.get("username"),
            "name": credentials.get("name"),
            "email": credentials.get("email"),
            "phone": credentials.get("phone"),
            "account_type": credentials.get("account_type")
        }
    except Exception as e:
        print(f"[USER INFO] Error getting user info: {e}")
        return {"error": "Failed to get user information"}

@app.get("/api/system/health")
async def get_system_health():
    """Get current system health status from database"""
    try:
        import psycopg2
        
        conn = psycopg2.connect(
            host="localhost",
            database="rec_io_db",
            user="rec_io_user",
            password="rec_io_password"
        )
        
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM system.health_status WHERE id = 1")
            result = cursor.fetchone()
            
            if result:
                # Unpack the result (adjust column order as needed)
                id, overall_status, cpu_percent, memory_percent, disk_percent, \
                database_status, supervisor_status, services_healthy, services_total, \
                failed_services, health_details, timestamp = result
                
                return {
                    "overall_status": overall_status,
                    "cpu_percent": float(cpu_percent) if cpu_percent else None,
                    "memory_percent": float(memory_percent) if memory_percent else None,
                    "disk_percent": float(disk_percent) if disk_percent else None,
                    "database_status": database_status,
                    "supervisor_status": supervisor_status,
                    "services_healthy": services_healthy,
                    "services_total": services_total,
                    "failed_services": failed_services or [],
                    "timestamp": timestamp.isoformat() if timestamp else None
                }
            else:
                return {"error": "No health data available"}
                
    except Exception as e:
        print(f"[SYSTEM HEALTH] Error getting system health: {e}")
        return {"error": "Failed to get system health information"}

# Startup and shutdown events
@app.on_event("startup")
async def startup_event():
    """Called when the application starts."""
    print(f"[MAIN] 🚀 Main app started on centralized port {MAIN_APP_PORT}")

@app.on_event("shutdown")
async def shutdown_event():
    """Called when the application shuts down."""
    print("[MAIN] 🛑 Main app shutting down")
    # No port release needed for static ports

@app.post("/api/admin/supervisor-status")
async def get_supervisor_status():
    """Execute supervisorctl status command and return output"""
    try:
        import subprocess
        import os
        
        # Change to the project directory
        project_dir = "/Users/ericwais1/rec_io_20"
        os.chdir(project_dir)
        
        # Use full path to supervisorctl and set environment
        supervisorctl_path = "/opt/homebrew/bin/supervisorctl"
        env = os.environ.copy()
        
        # Execute the supervisorctl command with full path
        result = subprocess.run(
            [supervisorctl_path, "-c", "backend/supervisord.conf", "status"],
            capture_output=True,
            text=True,
            timeout=10,
            env=env,
            cwd=project_dir
        )
        
        # supervisorctl returns non-zero exit codes when any process is stopped
        # but the output is still valid, so we should return success if we got output
        if result.stdout.strip():
            return {
                "success": True,
                "output": result.stdout
            }
        else:
            return {
                "success": False,
                "error": f"Command failed with return code {result.returncode}",
                "output": result.stderr
            }
            
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "Command timed out"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@app.post("/api/admin/execute-restart")
async def execute_restart():
    """Execute the restart script in background"""
    try:
        import subprocess
        import os
        
        # Change to the project directory
        project_dir = "/Users/ericwais1/rec_io_20"
        os.chdir(project_dir)
        
        # Set up environment with proper PATH
        env = os.environ.copy()
        env['PATH'] = '/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin'
        
        # Execute the restart script in background (don't wait for it)
        subprocess.Popen(
            ["/bin/bash", "./scripts/restart"],
            cwd=project_dir,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )
        
        # Return immediately - the script will run in background
        return {
            "success": True,
            "message": "Restart script initiated in background"
        }
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@app.post("/api/admin/execute-command")
async def execute_command(request: dict):
    """Execute arbitrary command at project level"""
    try:
        import subprocess
        import os
        
        command = request.get("command", "")
        if not command:
            return {"success": False, "error": "No command provided"}
        
        # Change to the project directory
        project_dir = "/Users/ericwais1/rec_io_20"
        os.chdir(project_dir)
        
        # Set up environment with proper PATH
        env = os.environ.copy()
        env['PATH'] = '/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin'
        
        # Execute the command
        result = subprocess.run(
            command.split(),
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
            cwd=project_dir
        )
        
        if result.returncode == 0:
            return {"success": True, "output": result.stdout}
        else:
            return {"success": False, "error": f"Command failed with return code {result.returncode}", "output": result.stderr}
            
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Command timed out after 30 seconds"}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/api/admin/get-log-stream")
async def get_log_stream(request: dict):
    """Stream log output for a specific script."""
    from fastapi.responses import StreamingResponse
    import subprocess
    import os
    
    script_name = request.get("script", "")
    if not script_name:
        return {"success": False, "error": "No script name provided"}
    
    # Determine log file path based on script name
    log_file = f"logs/{script_name}.out.log"
    project_dir = "/Users/ericwais1/rec_io_20"
    
    if not os.path.exists(os.path.join(project_dir, log_file)):
        return {"success": False, "error": f"Log file not found: {log_file}"}
    
    def generate_log_stream():
        try:
            # Set up environment with proper PATH
            env = os.environ.copy()
            env['PATH'] = '/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin'
            
            # First, get the last 100 lines of the log file
            try:
                result = subprocess.run(
                    ["/usr/bin/tail", "-n", "100", log_file],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    cwd=project_dir,
                    env=env
                )
                if result.returncode == 0 and result.stdout:
                    # Send the last 100 lines first
                    yield "=== Last 100 lines of log ===\n"
                    yield result.stdout
                    yield "\n=== Live tail starting ===\n"
            except Exception as e:
                yield f"Warning: Could not read existing log content: {str(e)}\n"
                yield "=== Starting live tail ===\n"
            
            # Start tail -f process with full path for live streaming
            process = subprocess.Popen(
                ["/usr/bin/tail", "-f", log_file],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=project_dir,
                env=env
            )
            
            # Stream live output
            while True:
                line = process.stdout.readline()
                if not line:
                    break
                yield line
            
        except Exception as e:
            yield f"Error: {str(e)}\n"
        finally:
            if 'process' in locals():
                process.terminate()
    
    return StreamingResponse(
        generate_log_stream(),
        media_type="text/plain",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
    )

# Main entry point
if __name__ == "__main__":
    print(f"[MAIN] 🚀 Launching app on centralized port {MAIN_APP_PORT}")
    uvicorn.run(app, host="0.0.0.0", port=MAIN_APP_PORT)

