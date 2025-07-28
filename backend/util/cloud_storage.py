"""
Cloud Storage Integration for REC.IO Trading System
Incremental test starting with trades.db migration to Google Drive
"""

import os
import json
import sqlite3
import tempfile
import shutil
from typing import Optional, Dict, Any
from datetime import datetime
import time

# Google Drive API imports
try:
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
    from googleapiclient.errors import HttpError
    import io
    GOOGLE_DRIVE_AVAILABLE = True
except ImportError:
    GOOGLE_DRIVE_AVAILABLE = False
    print("⚠️  Google Drive API not available. Install with: pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client")

class CloudStorageManager:
    """Manages cloud storage integration for critical databases."""
    
    def __init__(self):
        self.storage_type = os.getenv("TRADING_SYSTEM_STORAGE", "local")
        self.google_drive_folder_id = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
        self.credentials_path = os.getenv("GOOGLE_DRIVE_CREDENTIALS")
        self.drive_service = None
        
        if self.storage_type == "cloud" and GOOGLE_DRIVE_AVAILABLE:
            self._initialize_google_drive()
    
    def _initialize_google_drive(self):
        """Initialize Google Drive service."""
        try:
            if not self.credentials_path or not os.path.exists(self.credentials_path):
                print("❌ Google Drive credentials not found. Set GOOGLE_DRIVE_CREDENTIALS environment variable.")
                return
            
            # Load credentials
            creds = Credentials.from_authorized_user_file(self.credentials_path)
            self.drive_service = build('drive', 'v3', credentials=creds)
            print("✅ Google Drive service initialized")
            
        except Exception as e:
            print(f"❌ Failed to initialize Google Drive: {e}")
            self.storage_type = "local"
    
    def get_trades_db_path(self) -> str:
        """Get the path to trades.db with cloud sync capability."""
        if self.storage_type == "cloud" and self.drive_service:
            return self._get_cloud_trades_db_path()
        else:
            return self._get_local_trades_db_path()
    
    def _get_local_trades_db_path(self) -> str:
        """Get local trades.db path."""
        from .paths import get_trade_history_dir
        return os.path.join(get_trade_history_dir(), "trades.db")
    
    def _get_cloud_trades_db_path(self) -> str:
        """Get cloud-synced trades.db path."""
        # Create a temporary local copy for the application to use
        temp_dir = os.path.join(os.getcwd(), "temp_cloud_sync")
        os.makedirs(temp_dir, exist_ok=True)
        temp_path = os.path.join(temp_dir, "trades.db")
        
        # Download from Google Drive if it exists
        if self._download_from_google_drive("trades.db", temp_path):
            print(f"✅ Downloaded trades.db from Google Drive to {temp_path}")
        else:
            # If not in cloud, create empty local copy
            print(f"📝 Creating new trades.db at {temp_path}")
            self._create_empty_trades_db(temp_path)
        
        return temp_path
    
    def _download_from_google_drive(self, filename: str, local_path: str) -> bool:
        """Download file from Google Drive."""
        try:
            if not self.drive_service or not self.google_drive_folder_id:
                return False
            
            # Search for the file in the specified folder
            query = f"name='{filename}' and '{self.google_drive_folder_id}' in parents"
            results = self.drive_service.files().list(q=query).execute()
            files = results.get('files', [])
            
            if not files:
                print(f"📝 File {filename} not found in Google Drive")
                return False
            
            file_id = files[0]['id']
            
            # Download the file
            request = self.drive_service.files().get_media(fileId=file_id)
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            
            done = False
            while done is False:
                status, done = downloader.next_chunk()
                print(f"📥 Downloading {filename}: {int(status.progress() * 100)}%")
            
            # Save to local path
            with open(local_path, 'wb') as f:
                f.write(fh.getvalue())
            
            return True
            
        except Exception as e:
            print(f"❌ Failed to download {filename} from Google Drive: {e}")
            return False
    
    def _upload_to_google_drive(self, local_path: str, filename: str) -> bool:
        """Upload file to Google Drive."""
        try:
            if not self.drive_service or not self.google_drive_folder_id:
                return False
            
            # Check if file already exists
            query = f"name='{filename}' and '{self.google_drive_folder_id}' in parents"
            results = self.drive_service.files().list(q=query).execute()
            files = results.get('files', [])
            
            file_metadata = {
                'name': filename,
                'parents': [self.google_drive_folder_id]
            }
            
            media = MediaIoBaseUpload(
                io.BytesIO(open(local_path, 'rb').read()),
                mimetype='application/octet-stream',
                resumable=True
            )
            
            if files:
                # Update existing file
                file_id = files[0]['id']
                self.drive_service.files().update(
                    fileId=file_id,
                    media_body=media
                ).execute()
                print(f"✅ Updated {filename} in Google Drive")
            else:
                # Create new file
                self.drive_service.files().create(
                    body=file_metadata,
                    media_body=media
                ).execute()
                print(f"✅ Uploaded {filename} to Google Drive")
            
            return True
            
        except Exception as e:
            print(f"❌ Failed to upload {filename} to Google Drive: {e}")
            return False
    
    def _create_empty_trades_db(self, path: str):
        """Create an empty trades.db with proper schema."""
        conn = sqlite3.connect(path)
        cursor = conn.cursor()
        
        # Create trades table schema (based on existing trades.db structure)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id TEXT,
                status TEXT,
                date TEXT,
                time TEXT,
                symbol TEXT,
                market TEXT,
                trade_strategy TEXT,
                contract TEXT,
                strike TEXT,
                side TEXT,
                ticker TEXT,
                buy_price REAL,
                position INTEGER,
                symbol_open REAL,
                symbol_close REAL,
                momentum REAL,
                prob TEXT,
                win_loss REAL,
                entry_method TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        conn.close()
        print(f"📝 Created empty trades.db at {path}")
    
    def sync_trades_db_to_cloud(self):
        """Sync local trades.db to Google Drive."""
        if self.storage_type != "cloud" or not self.drive_service:
            return False
        
        local_path = self._get_local_trades_db_path()
        if os.path.exists(local_path):
            return self._upload_to_google_drive(local_path, "trades.db")
        return False
    
    def sync_trades_db_from_cloud(self):
        """Sync trades.db from Google Drive to local."""
        if self.storage_type != "cloud" or not self.drive_service:
            return False
        
        local_path = self._get_local_trades_db_path()
        return self._download_from_google_drive("trades.db", local_path)

# Global instance
cloud_storage = CloudStorageManager()

def get_trades_db_path() -> str:
    """Get the path to trades.db with cloud sync capability."""
    return cloud_storage.get_trades_db_path()

def sync_trades_db_to_cloud():
    """Sync local trades.db to Google Drive."""
    return cloud_storage.sync_trades_db_to_cloud()

def sync_trades_db_from_cloud():
    """Sync trades.db from Google Drive to local."""
    return cloud_storage.sync_trades_db_from_cloud() 