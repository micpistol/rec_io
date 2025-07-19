#!/usr/bin/env python3
"""
Database Poller - Monitors essential databases for changes
Polls trades.db, fills.db, positions.db, settlements.db twice per second
Logs any detected changes with details
"""

import os
import sqlite3
import time
import hashlib
import json
import sys
import requests
from datetime import datetime
from typing import Dict, Any, Optional

# Import project utilities
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.account_mode import get_account_mode
from backend.util.paths import get_data_dir, get_accounts_data_dir
from backend.core.config.settings import config
from backend.core.port_config import get_port

class DatabasePoller:
    def __init__(self):
        self.poll_interval = 0.5  # Poll twice per second - back to original
        self.last_hashes = {}
        self.db_paths = {}
        
        # Get service URLs using centralized port system
        main_app_port = get_port("main_app")
        trade_manager_port = get_port("trade_manager")
        active_trade_supervisor_port = get_port("active_trade_supervisor")
        
        self.main_app_url = f"http://localhost:{main_app_port}"
        self.trade_manager_url = f"http://localhost:{trade_manager_port}"
        self.active_trade_supervisor_url = f"http://localhost:{active_trade_supervisor_port}"
        
        self.setup_database_paths()
        
    def setup_database_paths(self):
        """Setup paths for all databases to monitor"""
        mode = get_account_mode()
        print(f"🔧 Account mode: {mode}")
        
        # Core trade database
        self.db_paths['trades'] = os.path.join(get_data_dir(), "trade_history", "trades.db")
        
        # Kalshi account databases
        kalshi_dir = os.path.join(get_accounts_data_dir(), "kalshi", mode)
        self.db_paths['fills'] = os.path.join(kalshi_dir, "fills.db")
        self.db_paths['positions'] = os.path.join(kalshi_dir, "positions.db")
        self.db_paths['settlements'] = os.path.join(kalshi_dir, "settlements.db")
        
        print(f"🔍 Database Poller initialized")
        print(f"📊 Monitoring databases:")
        for db_name, path in self.db_paths.items():
            exists = "✅" if os.path.exists(path) else "❌"
            print(f"   {exists} {db_name}: {path}")
    
    def get_database_hash(self, db_path: str) -> Optional[str]:
        """Get a hash representing the current state of a database"""
        if not os.path.exists(db_path):
            return None
            
        try:
            # Get file modification time and size for quick change detection
            stat = os.stat(db_path)
            file_info = f"{stat.st_mtime}_{stat.st_size}"
            
            # For faster detection, only use file stats initially
            # Only hash content if file stats indicate a change
            return file_info
        except Exception as e:
            print(f"❌ Error reading database {db_path}: {e}")
            return None
    
    def get_database_info(self, db_path: str, db_name: str) -> Dict[str, Any]:
        """Get detailed information about database changes"""
        if not os.path.exists(db_path):
            return {"error": "Database file not found"}
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Get table names
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row[0] for row in cursor.fetchall()]
            
            # Get row counts for each table
            table_counts = {}
            for table in tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                table_counts[table] = count
            
            # Get sample data for change detection
            sample_data = {}
            for table in tables:
                cursor.execute(f"SELECT * FROM {table} ORDER BY rowid DESC LIMIT 3")
                rows = cursor.fetchall()
                if rows:
                    # Get column names
                    cursor.execute(f"PRAGMA table_info({table})")
                    columns = [col[1] for col in cursor.fetchall()]
                    sample_data[table] = {
                        "columns": columns,
                        "recent_rows": [dict(zip(columns, row)) for row in rows]
                    }
            
            conn.close()
            
            return {
                "tables": tables,
                "table_counts": table_counts,
                "sample_data": sample_data,
                "file_size": os.path.getsize(db_path),
                "modified_time": datetime.fromtimestamp(os.path.getmtime(db_path)).isoformat()
            }
            
        except Exception as e:
            return {"error": f"Database read error: {e}"}
    
    def log_change(self, db_name: str, db_path: str, old_info: Dict[str, Any], new_info: Dict[str, Any]):
        """Log detailed information about database changes"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        
        print(f"\n🔔 [{timestamp}] DATABASE CHANGE DETECTED: {db_name.upper()}")
        print(f"📁 Path: {db_path}")
        sys.stdout.flush()
        
        # Prepare change data for broadcasting
        change_data = {
            "timestamp": timestamp,
            "path": db_path,
            "old_info": old_info,
            "new_info": new_info
        }
        
        # Notify main app about the change
        self.notify_main_app(db_name, change_data)
        
        # If positions.db changed, also notify trade manager
        if db_name == "positions":
            self.notify_trade_manager(db_name, change_data)
        
        # If trades.db changed, notify active trade supervisor
        if db_name == "trades":
            self.notify_active_trade_supervisor(db_name, change_data)
        
        if "error" in old_info or "error" in new_info:
            print(f"⚠️  Error reading database: {old_info.get('error', new_info.get('error'))}")
            return
        
        # Compare table counts
        old_counts = old_info.get("table_counts", {})
        new_counts = new_info.get("table_counts", {})
        
        all_tables = set(old_counts.keys()) | set(new_counts.keys())
        
        for table in all_tables:
            old_count = old_counts.get(table, 0)
            new_count = new_counts.get(table, 0)
            
            if old_count != new_count:
                change = new_count - old_count
                change_symbol = "➕" if change > 0 else "➖"
                print(f"   {change_symbol} Table '{table}': {old_count} → {new_count} rows ({change:+d})")
        
        # Show recent data changes
        old_data = old_info.get("sample_data", {})
        new_data = new_info.get("sample_data", {})
        
        for table in all_tables:
            if table in old_data and table in new_data:
                old_recent = old_data[table].get("recent_rows", [])
                new_recent = new_data[table].get("recent_rows", [])
                
                if old_recent != new_recent:
                    print(f"   📝 Table '{table}' data updated")
                    if new_recent:
                        latest = new_recent[0]
                        print(f"      Latest: {latest}")
        
        print(f"   📊 File size: {new_info.get('file_size', 'N/A')} bytes")
        print(f"   🕒 Modified: {new_info.get('modified_time', 'N/A')}")
        print("-" * 80)
    
    def notify_main_app(self, db_name: str, change_data: Dict[str, Any]):
        """Notify main app about database changes via HTTP"""
        try:
            url = f"{self.main_app_url}/api/db_change"
            payload = {
                "database": db_name,
                "change_data": change_data
            }
            # Use shorter timeout and fire-and-forget for speed
            response = requests.post(url, json=payload, timeout=1)
            if response.status_code == 200:
                print(f"✅ Notified main app about {db_name} change")
            else:
                print(f"⚠️  Failed to notify main app: {response.status_code}")
        except Exception as e:
            print(f"❌ Error notifying main app: {e}")
        
        # ALSO directly notify frontend via WebSocket if trades.db changed
        if db_name == "trades":
            self.notify_frontend_websocket(db_name, change_data)
    
    def notify_trade_manager(self, db_name: str, change_data: Dict[str, Any]):
        """Notify trade manager about database changes via HTTP"""
        try:
            url = f"{self.trade_manager_url}/api/positions_change"
            payload = {
                "database": db_name,
                "change_data": change_data
            }
            # Use shorter timeout and fire-and-forget for speed
            response = requests.post(url, json=payload, timeout=1)
            if response.status_code == 200:
                print(f"✅ Notified trade manager about {db_name} change")
            else:
                print(f"⚠️  Failed to notify trade manager: {response.status_code}")
        except Exception as e:
            print(f"❌ Error notifying trade manager: {e}")
    
    def notify_active_trade_supervisor(self, db_name: str, change_data: Dict[str, Any]):
        """Notify active trade supervisor about database changes via HTTP"""
        try:
            url = f"{self.active_trade_supervisor_url}/api/trades_db_change"
            payload = {
                "database": db_name,
                "change_data": change_data
            }
            # Use shorter timeout and fire-and-forget for speed
            response = requests.post(url, json=payload, timeout=1)
            if response.status_code == 200:
                print(f"✅ Notified active trade supervisor about {db_name} change")
            else:
                print(f"⚠️  Failed to notify active trade supervisor: {response.status_code}")
        except Exception as e:
            print(f"❌ Error notifying active trade supervisor: {e}")
    
    def poll_databases(self):
        """Main polling loop"""
        print(f"🚀 Starting database poller (interval: {self.poll_interval}s)")
        print(f"🔍 Monitoring {len(self.db_paths)} databases...")
        
        # Initial check of all databases
        for db_name, db_path in self.db_paths.items():
            if os.path.exists(db_path):
                print(f"✅ Found {db_name}: {db_path}")
            else:
                print(f"❌ Missing {db_name}: {db_path}")
        
        poll_count = 0
        while True:
            try:
                poll_count += 1
                if poll_count % 20 == 0:  # Log every 10 seconds
                    print(f"🔍 Poll #{poll_count} - monitoring databases...")
                
                for db_name, db_path in self.db_paths.items():
                    current_hash = self.get_database_hash(db_path)
                    
                    if current_hash is None:
                        # Database doesn't exist yet
                        if db_name in self.last_hashes:
                            print(f"⚠️  Database {db_name} no longer exists: {db_path}")
                            del self.last_hashes[db_name]
                        continue
                    
                    if db_name not in self.last_hashes:
                        # First time seeing this database
                        print(f"📋 Initializing monitoring for {db_name}: {db_path}")
                        self.last_hashes[db_name] = current_hash
                        self.last_info = {db_name: self.get_database_info(db_path, db_name)}
                        continue
                    
                    if current_hash != self.last_hashes[db_name]:
                        # Change detected
                        print(f"🔔 CHANGE DETECTED in {db_name}!")
                        old_info = self.last_info.get(db_name, {})
                        new_info = self.get_database_info(db_path, db_name)
                        
                        self.log_change(db_name, db_path, old_info, new_info)
                        
                        # Update our tracking
                        self.last_hashes[db_name] = current_hash
                        if 'last_info' not in self.__dict__:
                            self.last_info = {}
                        self.last_info[db_name] = new_info
                
                time.sleep(self.poll_interval)
                
            except KeyboardInterrupt:
                print("\n🛑 Database poller stopped by user")
                break
            except Exception as e:
                print(f"❌ Error in polling loop: {e}")
                time.sleep(self.poll_interval)

def main():
    """Main entry point"""
    poller = DatabasePoller()
    poller.poll_databases()

if __name__ == "__main__":
    main() 