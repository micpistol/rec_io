# System Data Packaging Guide

This guide explains how to package and transfer system-critical data between machines for the rec_io trading platform.

## Overview

The system data packaging scripts allow you to:
- Export all non-user system data from a PostgreSQL database
- Package it into a single compressed archive
- Import it into a new machine's database

This is useful for:
- Setting up new development environments
- Deploying to production servers
- Creating backups of system data
- Sharing system data between team members

## What Gets Packaged

### Included Data (System-Critical)
- **Analytics Schema**: Probability lookup tables, fingerprint tables
- **Historical Data Schema**: BTC and ETH price history
- **Live Data Schema**: Price logs, strike tables, live market data
- **System Schema**: Health status and system monitoring data
- **Work Progress Schema**: TTC progress tracking data
- **Public Schema System Tables**: fills, positions, trades, active_trades

### Excluded Data (User-Specific)
- **Users Schema**: All user-specific data (trade logs, orders, fills, etc.)
- **User Credentials**: Kalshi API credentials and user settings
- **User Preferences**: Individual user configurations

## Scripts

### 1. Package System Data (`package_system_data.py`)

**Purpose**: Export system data from the current database into a compressed archive.

**Usage**:
```bash
cd /path/to/rec_io_20
python scripts/package_system_data.py
```

**Output**:
- Creates a timestamped archive: `system_data_export_YYYYMMDD_HHMMSS.tar.gz`
- Archive contains SQL files for each table organized by schema
- Includes metadata.json with export information

**Example Output**:
```
🚀 System Data Packaging Script
==================================================
📁 Output directory: system_data_export_20250814_143022

🔌 Connecting to database...
  ✓ Database connection established

📊 Exporting system schemas...

📦 Schema: analytics
  Exporting 61 tables from schema 'analytics':
    - btc_fingerprint_directional_baseline
      ✓ Exported 1234 bytes
    - btc_fingerprint_directional_momentum_-30
      ✓ Exported 5678 bytes
    ...

📦 Schema: historical_data
  Exporting 2 tables from schema 'historical_data':
    - btc_price_history
      ✓ Exported 1234567 bytes
    - eth_price_history
      ✓ Exported 987654 bytes

...

🗜️ Creating compressed archive...
  ✓ Created archive: system_data_export_20250814_143022.tar.gz
  📏 Archive size: 2.34 MB

✅ System data packaging completed successfully!
📦 Archive: system_data_export_20250814_143022.tar.gz
📏 Size: 2.34 MB

📋 Next steps:
   1. Copy system_data_export_20250814_143022.tar.gz to target machine
   2. Run unpack_system_data.py on target machine
```

### 2. Unpack System Data (`unpack_system_data.py`)

**Purpose**: Import system data from an archive into a new database.

**Usage**:
```bash
cd /path/to/rec_io_20
python scripts/unpack_system_data.py system_data_export_20250814_143022.tar.gz
```

**Options**:
- `--force`: Force import even if data already exists (skips confirmation prompts)

**Behavior**:
- If no tables exist with data, the script will automatically import all data
- If tables exist with data, the script will prompt for confirmation before overwriting
- Use `--force` to skip the confirmation prompt and automatically overwrite existing data

**Example Output**:
```
🚀 System Data Unpacking Script
==================================================
📦 Extracting archive: system_data_export_20250814_143022.tar.gz
  ✓ Extracted to: temp_extract_20250814_143045/system_data_export_20250814_143022

📋 Loaded metadata:
  Export timestamp: 2025-08-14T14:30:22.123456
  Version: 1.0
  Schemas: analytics, historical_data, live_data, system, work_progress
  Public tables: fills, positions, trades, active_trades

🔌 Connecting to database...
  ✓ Database connection established

🔍 Checking existing data in database...
   📊 analytics.btc_fingerprint_directional_baseline: 1,234 rows
   📊 historical_data.btc_price_history: 123,456 rows

⚠️  Found 2 tables with existing data:
   - analytics.btc_fingerprint_directional_baseline: 1,234 rows
   - historical_data.btc_price_history: 123,456 rows

❓ Do you want to overwrite existing data? (y/N): y

🏗️ Creating schemas if they don't exist...
  ✓ Schema 'analytics' ready
  ✓ Schema 'historical_data' ready
  ✓ Schema 'live_data' ready
  ✓ Schema 'system' ready
  ✓ Schema 'work_progress' ready

📥 Importing schema data...

📦 Schema: analytics
  📥 Importing 61 tables to schema 'analytics':
    ✓ Imported btc_fingerprint_directional_baseline
    ✓ Imported btc_fingerprint_directional_momentum_-30
    ...

📦 Schema: historical_data
  📥 Importing 2 tables to schema 'historical_data':
    ✓ Imported btc_price_history
    ✓ Imported eth_price_history

...

🔍 Verifying import...
  📊 Schema 'analytics': 61 tables
    - btc_fingerprint_directional_baseline: 1,234 rows
    - btc_fingerprint_directional_momentum_-30: 5,678 rows
    ...
  📊 Schema 'historical_data': 2 tables
    - btc_price_history: 123,456 rows
    - eth_price_history: 98,765 rows
  ...

📈 Import Summary:
  Total tables: 163
  Total rows: 2,345,678

✅ System data import completed successfully!
📋 Next steps:
   1. Verify the application starts correctly
   2. Check that all system functionality works
   3. Set up user accounts and credentials

🧹 Cleaned up temporary files
```

## Prerequisites

### Source Machine (Packaging)
- PostgreSQL database with rec_io_db
- Python environment with required dependencies
- Access to database with rec_io_user credentials
- pg_dump command available

### Target Machine (Unpacking)
- PostgreSQL server running
- rec_io_db database created
- Python environment with required dependencies
- Access to database with rec_io_user credentials
- psql command available

## Database Configuration

Both scripts use the ConfigManager to get database connection details from:
- `backend/core/config/config.default.json`
- `backend/core/config/config.local.json`

Ensure these files are properly configured on both machines.

## Archive Structure

The packaged archive contains:
```
system_data_export_YYYYMMDD_HHMMSS/
├── metadata.json                    # Export metadata and instructions
├── analytics/                       # Analytics schema tables
│   ├── btc_fingerprint_directional_baseline.sql
│   ├── btc_fingerprint_directional_momentum_-30.sql
│   └── ...
├── historical_data/                 # Historical data schema tables
│   ├── btc_price_history.sql
│   └── eth_price_history.sql
├── live_data/                       # Live data schema tables
│   ├── btc_price_log.sql
│   ├── btc_strike_table.sql
│   └── ...
├── system/                          # System schema tables
│   └── health_status.sql
├── work_progress/                   # Work progress schema tables
│   ├── ttc_0069_btc.sql
│   ├── ttc_0070_btc.sql
│   └── ...
└── public/                          # Public schema system tables
    ├── fills.sql
    ├── positions.sql
    ├── trades.sql
    └── active_trades.sql
```

## Troubleshooting

### Common Issues

1. **Database Connection Failed**
   - Verify database is running
   - Check credentials in config files
   - Ensure network connectivity

2. **Permission Denied**
   - Check file permissions on scripts
   - Ensure database user has appropriate privileges
   - Verify pg_dump/psql access

3. **Import Errors**
   - Check if tables already exist (use --force if needed)
   - Verify schema creation permissions
   - Review error messages for specific table issues

4. **Archive Corruption**
   - Verify file transfer completed successfully
   - Check file size matches source
   - Re-run packaging if needed

### Verification Steps

After unpacking, verify the import by:
1. Checking table counts in each schema
2. Running a few sample queries
3. Starting the application and testing functionality
4. Verifying system health endpoints

## Security Considerations

- Archive files contain sensitive system data
- Store archives securely
- Use secure transfer methods (SCP, SFTP, etc.)
- Consider encrypting archives for sensitive environments
- Clean up temporary files after import

## Performance Notes

- Large databases may take significant time to package/unpack
- Monitor disk space during extraction
- Consider running during low-usage periods
- Archive size typically 2-3GB for full system data

## Version Compatibility

- Scripts are versioned and include metadata
- Check version compatibility between source and target
- Update scripts if database schema changes significantly
- Test with sample data before production use
