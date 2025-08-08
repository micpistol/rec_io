#!/usr/bin/env python3
"""
REC.IO Database Backup Tool
Creates, lists, restores, and verifies PostgreSQL database backups.
"""

import os
import sys
import json
import tarfile
import subprocess
import psycopg2
from datetime import datetime
from pathlib import Path
import argparse

def get_project_root():
    """Get the project root directory."""
    current_dir = Path.cwd()
    while current_dir != current_dir.parent:
        if (current_dir / "backend" / "main.py").exists():
            return str(current_dir)
        current_dir = current_dir.parent
    raise FileNotFoundError("Could not find project root")

class DatabaseBackupTool:
    def __init__(self):
        self.project_root = Path(get_project_root())
        self.backup_dir = self.project_root / "backup" / "database_backups"
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Database configuration
        self.db_config = {
            'host': 'localhost',
            'port': 5432,
            'database': 'rec_io_db',
            'user': 'rec_io_user',
            'password': 'rec_io_password'
        }
    
    def get_database_info(self):
        """Get database size and table information."""
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            # Get database size
            cursor.execute("""
                SELECT pg_size_pretty(pg_database_size('rec_io_db')) as size,
                       pg_database_size('rec_io_db') as size_bytes
            """)
            size_info = cursor.fetchone()
            
            # Get table information
            cursor.execute("""
                SELECT schemaname, tablename, n_tup_ins as rows
                FROM pg_stat_user_tables
                ORDER BY schemaname, tablename
            """)
            tables = cursor.fetchall()
            
            cursor.close()
            conn.close()
            
            return {
                'size': size_info[0],
                'size_bytes': size_info[1],
                'tables': [{'schema': t[0], 'table': t[1], 'rows': t[2]} for t in tables]
            }
        except Exception as e:
            print(f"Error getting database info: {e}")
            return None
    
    def create_backup(self):
        """Create a database backup."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"rec_io_db_backup_{timestamp}"
        backup_path = self.backup_dir / f"{backup_name}.sql"
        archive_path = self.backup_dir / f"{backup_name}.tar.gz"
        
        print(f"Creating database backup: {backup_name}")
        
        # Get database info
        db_info = self.get_database_info()
        if not db_info:
            print("❌ Failed to get database information")
            return False
        
        print(f"Database size: {db_info['size']}")
        print(f"Tables found: {len(db_info['tables'])}")
        
        # Create SQL dump
        try:
            cmd = [
                'pg_dump',
                '-h', self.db_config['host'],
                '-p', str(self.db_config['port']),
                '-U', self.db_config['user'],
                '-d', self.db_config['database'],
                '--no-password',
                '--verbose',
                '--clean',
                '--if-exists',
                '--create',
                '--no-owner',
                '--no-privileges',
                '-f', str(backup_path)
            ]
            
            # Set password environment variable
            env = os.environ.copy()
            env['PGPASSWORD'] = self.db_config['password']
            
            result = subprocess.run(cmd, env=env, capture_output=True, text=True)
            
            if result.returncode != 0:
                print(f"❌ pg_dump failed: {result.stderr}")
                return False
            
            print(f"✅ SQL dump created: {backup_path}")
            
            # Create metadata
            metadata = {
                'backup_name': backup_name,
                'created_at': datetime.now().isoformat(),
                'database_info': db_info,
                'backup_size_bytes': backup_path.stat().st_size,
                'backup_size_mb': round(backup_path.stat().st_size / (1024 * 1024), 2)
            }
            
            # Create archive with metadata
            with tarfile.open(archive_path, 'w:gz') as tar:
                tar.add(backup_path, arcname=f"{backup_name}.sql")
                
                # Add metadata
                metadata_path = self.backup_dir / f"{backup_name}_metadata.json"
                with open(metadata_path, 'w') as f:
                    json.dump(metadata, f, indent=2)
                tar.add(metadata_path, arcname=f"{backup_name}_metadata.json")
            
            # Clean up individual files
            backup_path.unlink()
            metadata_path.unlink()
            
            archive_size = archive_path.stat().st_size
            compression_ratio = (1 - archive_size / db_info['size_bytes']) * 100
            
            print(f"✅ Backup archive created: {archive_path}")
            print(f"📊 Archive size: {round(archive_size / (1024 * 1024), 2)} MB")
            print(f"📊 Compression: {compression_ratio:.1f}% reduction")
            
            return True
            
        except Exception as e:
            print(f"❌ Backup creation failed: {e}")
            return False
    
    def list_backups(self):
        """List available backups."""
        print("Available database backups:")
        print("-" * 80)
        
        backups = []
        for file in self.backup_dir.glob("*.tar.gz"):
            if file.name.startswith("rec_io_db_backup_"):
                try:
                    with tarfile.open(file, 'r:gz') as tar:
                        metadata_member = None
                        for member in tar.getmembers():
                            if member.name.endswith('_metadata.json'):
                                metadata_member = member
                                break
                        
                        if metadata_member:
                            metadata_file = tar.extractfile(metadata_member)
                            metadata = json.load(metadata_file)
                            
                            backups.append({
                                'file': file,
                                'metadata': metadata,
                                'size': file.stat().st_size
                            })
                except Exception as e:
                    print(f"⚠️  Error reading {file.name}: {e}")
        
        if not backups:
            print("No backups found.")
            return
        
        # Sort by creation date
        backups.sort(key=lambda x: x['metadata'].get('created_at', ''), reverse=True)
        
        for backup in backups:
            metadata = backup['metadata']
            size_mb = round(backup['size'] / (1024 * 1024), 2)
            created = datetime.fromisoformat(metadata['created_at']).strftime("%Y-%m-%d %H:%M:%S")
            
            print(f"📦 {backup['file'].name}")
            print(f"   📅 Created: {created}")
            print(f"   📊 Size: {size_mb} MB")
            print(f"   🗄️  Database: {metadata['database_info']['size']}")
            print(f"   📋 Tables: {len(metadata['database_info']['tables'])}")
            print()
    
    def restore_backup(self, backup_file, dry_run=False):
        """Restore a database backup."""
        if not backup_file.exists():
            print(f"❌ Backup file not found: {backup_file}")
            return False
        
        print(f"Restoring from: {backup_file.name}")
        
        try:
            # Extract and read metadata
            with tarfile.open(backup_file, 'r:gz') as tar:
                metadata_member = None
                sql_member = None
                
                for member in tar.getmembers():
                    if member.name.endswith('_metadata.json'):
                        metadata_member = member
                    elif member.name.endswith('.sql'):
                        sql_member = member
                
                if not metadata_member or not sql_member:
                    print("❌ Invalid backup format")
                    return False
                
                # Read metadata
                metadata_file = tar.extractfile(metadata_member)
                metadata = json.load(metadata_file)
                
                print(f"📦 Backup: {metadata['backup_name']}")
                print(f"📅 Created: {metadata['created_at']}")
                print(f"🗄️  Database: {metadata['database_info']['size']}")
                print(f"📋 Tables: {len(metadata['database_info']['tables'])}")
                
                if dry_run:
                    print("🔍 Dry run - no changes will be made")
                    return True
                
                # Confirm restoration
                response = input("\n⚠️  This will DROP and RECREATE the database. Continue? (yes/no): ")
                if response.lower() != 'yes':
                    print("❌ Restoration cancelled")
                    return False
                
                # Extract SQL file
                temp_dir = self.backup_dir / "temp_restore"
                temp_dir.mkdir(exist_ok=True)
                
                sql_path = temp_dir / f"{metadata['backup_name']}.sql"
                tar.extract(sql_member, temp_dir)
                
                # Restore database
                print("🔄 Restoring database...")
                
                # Drop and recreate database
                conn = psycopg2.connect(
                    host=self.db_config['host'],
                    port=self.db_config['port'],
                    user=self.db_config['user'],
                    password=self.db_config['password'],
                    database='postgres'  # Connect to default database
                )
                conn.autocommit = True
                cursor = conn.cursor()
                
                # Terminate connections to rec_io_db
                cursor.execute("""
                    SELECT pg_terminate_backend(pid)
                    FROM pg_stat_activity
                    WHERE datname = 'rec_io_db' AND pid <> pg_backend_pid()
                """)
                
                # Drop and recreate database
                cursor.execute("DROP DATABASE IF EXISTS rec_io_db")
                cursor.execute("CREATE DATABASE rec_io_db")
                
                cursor.close()
                conn.close()
                
                # Restore from SQL file
                cmd = [
                    'psql',
                    '-h', self.db_config['host'],
                    '-p', str(self.db_config['port']),
                    '-U', self.db_config['user'],
                    '-d', 'rec_io_db',
                    '--no-password',
                    '-f', str(sql_path)
                ]
                
                env = os.environ.copy()
                env['PGPASSWORD'] = self.db_config['password']
                
                result = subprocess.run(cmd, env=env, capture_output=True, text=True)
                
                # Clean up
                import shutil
                shutil.rmtree(temp_dir)
                
                if result.returncode != 0:
                    print(f"❌ Restoration failed: {result.stderr}")
                    return False
                
                print("✅ Database restored successfully!")
                return True
                
        except Exception as e:
            print(f"❌ Restoration failed: {e}")
            return False
    
    def verify_backup(self, backup_file):
        """Verify backup integrity."""
        if not backup_file.exists():
            print(f"❌ Backup file not found: {backup_file}")
            return False
        
        print(f"Verifying backup: {backup_file.name}")
        
        try:
            with tarfile.open(backup_file, 'r:gz') as tar:
                # Check archive integrity
                tar.getmembers()
                print("✅ Archive integrity: OK")
                
                # Check for required files
                has_metadata = False
                has_sql = False
                
                for member in tar.getmembers():
                    if member.name.endswith('_metadata.json'):
                        has_metadata = True
                        # Read and validate metadata
                        metadata_file = tar.extractfile(member)
                        metadata = json.load(metadata_file)
                        
                        required_keys = ['backup_name', 'created_at', 'database_info']
                        if all(key in metadata for key in required_keys):
                            print("✅ Metadata: Valid")
                        else:
                            print("❌ Metadata: Invalid format")
                            return False
                    
                    elif member.name.endswith('.sql'):
                        has_sql = True
                        print(f"✅ SQL dump: {member.size} bytes")
                
                if not has_metadata:
                    print("❌ Missing metadata file")
                    return False
                
                if not has_sql:
                    print("❌ Missing SQL dump file")
                    return False
                
                print("✅ Backup verification: PASSED")
                return True
                
        except Exception as e:
            print(f"❌ Verification failed: {e}")
            return False

def main():
    parser = argparse.ArgumentParser(description="REC.IO Database Backup Tool")
    parser.add_argument('action', choices=['backup', 'list', 'restore', 'verify'],
                       help='Action to perform')
    parser.add_argument('-f', '--file', type=Path,
                       help='Backup file for restore/verify operations')
    parser.add_argument('--dry-run', action='store_true',
                       help='Dry run for restore (no actual changes)')
    
    args = parser.parse_args()
    
    tool = DatabaseBackupTool()
    
    if args.action == 'backup':
        success = tool.create_backup()
        sys.exit(0 if success else 1)
    
    elif args.action == 'list':
        tool.list_backups()
    
    elif args.action == 'restore':
        if not args.file:
            print("❌ Please specify backup file with -f")
            sys.exit(1)
        success = tool.restore_backup(args.file, args.dry_run)
        sys.exit(0 if success else 1)
    
    elif args.action == 'verify':
        if not args.file:
            print("❌ Please specify backup file with -f")
            sys.exit(1)
        success = tool.verify_backup(args.file)
        sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
