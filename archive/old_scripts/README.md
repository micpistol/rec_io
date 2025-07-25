# Archived Scripts

This directory contains the old independent scripts that were replaced by the unified production coordinator.

## Archived Files

- `probability_writer.py` - Old script that generated live probabilities


## Replacement

These scripts have been replaced by the **Unified Production Coordinator** (`backend/unified_production_coordinator.py`) which:

- Combines all functionality into a single coordinated pipeline
- Eliminates race conditions between independent scripts
- Provides better error handling and monitoring
- Runs on port 8010 with API endpoints for health monitoring
- Generates the same output files:
  - `btc_live_probabilities.json`
  - `btc_strike_table.json` 
  - `btc_watchlist.json`

## Migration Date

Archived on: July 23, 2025

## Status

- ✅ Old scripts removed from supervisor configuration
- ✅ Scripts moved to archive directory
- ✅ Unified coordinator running successfully (99.24% success rate)
- ✅ All data files being generated correctly 