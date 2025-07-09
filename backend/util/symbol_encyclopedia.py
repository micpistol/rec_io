#!/usr/bin/env python3
"""
Symbol Encyclopedia System

This module manages a comprehensive encyclopedia of symbol fingerprints,
storing (k, alpha, beta) triplets and metadata for different symbols
across various time periods and data sources.

Usage:
    python symbol_encyclopedia.py add <symbol> <csv_file> [year]
    python symbol_encyclopedia.py get <symbol> [year]
    python symbol_encyclopedia.py list
    python symbol_encyclopedia.py info <symbol>
"""

import json
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import argparse
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from pathlib import Path

# Import our fingerprinting system
from util.symbol_fingerprinter import load_and_format, fit_fingerprint

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SymbolEncyclopedia:
    """Manages a comprehensive encyclopedia of symbol fingerprints."""
    
    def __init__(self, encyclopedia_path: str = None):
        if encyclopedia_path is None:
            # Use absolute path that works from any directory
            import os
            encyclopedia_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'symbol_encyclopedia.json')
        self.encyclopedia_path = Path(encyclopedia_path)
        self.encyclopedia_path.parent.mkdir(parents=True, exist_ok=True)
        self.encyclopedia = self._load_encyclopedia()
    
    def _load_encyclopedia(self) -> Dict[str, Any]:
        """Load the encyclopedia from JSON file."""
        if self.encyclopedia_path.exists():
            try:
                with open(self.encyclopedia_path, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError as e:
                logger.error(f"Error loading encyclopedia: {e}")
                return self._create_empty_encyclopedia()
        else:
            return self._create_empty_encyclopedia()
    
    def _create_empty_encyclopedia(self) -> Dict[str, Any]:
        """Create an empty encyclopedia structure."""
        return {
            "metadata": {
                "created": datetime.now().isoformat(),
                "last_updated": datetime.now().isoformat(),
                "version": "1.0",
                "description": "Symbol fingerprint encyclopedia"
            },
            "symbols": {}
        }
    
    def _save_encyclopedia(self):
        """Save the encyclopedia to JSON file."""
        self.encyclopedia["metadata"]["last_updated"] = datetime.now().isoformat()
        with open(self.encyclopedia_path, 'w') as f:
            json.dump(self.encyclopedia, f, indent=2)
        logger.info(f"Encyclopedia saved to {self.encyclopedia_path}")
    
    def add_fingerprint(self, symbol: str, csv_file: str, year: Optional[str] = None) -> bool:
        """Add a fingerprint for a symbol from a CSV file."""
        try:
            # Generate fingerprint using our existing system
            data = load_and_format(csv_file)
            k, alpha, beta = fit_fingerprint(data)
            
            # Calculate R-squared for quality assessment
            from scipy.optimize import curve_fit
            from util.symbol_fingerprinter import touch_model
            import numpy as np
            
            xdata = (data["delta"].values, data["TTC"].values)
            ydata = data["P_touch"].values
            y_pred = touch_model(xdata, k, alpha, beta)
            # Convert to numpy arrays to avoid type issues
            ydata_np = np.array(ydata)
            y_pred_np = np.array(y_pred)
            r_squared = 1 - np.sum((ydata_np - y_pred_np) ** 2) / np.sum((ydata_np - np.mean(ydata_np)) ** 2)
            
            # Prepare fingerprint data
            fingerprint_data = {
                "k": float(k),
                "alpha": float(alpha),
                "beta": float(beta),
                "r_squared": float(r_squared),
                "data_points": len(data),
                "source_file": csv_file,
                "generated_at": datetime.now().isoformat(),
                "year": year or "unknown"
            }
            
            # Initialize symbol if it doesn't exist
            if symbol not in self.encyclopedia["symbols"]:
                self.encyclopedia["symbols"][symbol] = {
                    "metadata": {
                        "first_added": datetime.now().isoformat(),
                        "last_updated": datetime.now().isoformat(),
                        "total_fingerprints": 0
                    },
                    "fingerprints": {}
                }
            
            # Add fingerprint
            fingerprint_key = year or "default"
            self.encyclopedia["symbols"][symbol]["fingerprints"][fingerprint_key] = fingerprint_data
            self.encyclopedia["symbols"][symbol]["metadata"]["last_updated"] = datetime.now().isoformat()
            self.encyclopedia["symbols"][symbol]["metadata"]["total_fingerprints"] = len(
                self.encyclopedia["symbols"][symbol]["fingerprints"]
            )
            
            self._save_encyclopedia()
            
            logger.info(f"✅ Added fingerprint for {symbol} ({fingerprint_key}):")
            logger.info(f"   k: {k:.2e}")
            logger.info(f"   alpha: {alpha:.4f}")
            logger.info(f"   beta: {beta:.4f}")
            logger.info(f"   R²: {r_squared:.4f}")
            logger.info(f"   Data points: {len(data)}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error adding fingerprint for {symbol}: {e}")
            return False
    
    def get_fingerprint(self, symbol: str, year: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get a fingerprint for a symbol."""
        if symbol not in self.encyclopedia["symbols"]:
            logger.warning(f"Symbol '{symbol}' not found in encyclopedia")
            return None
        
        symbol_data = self.encyclopedia["symbols"][symbol]
        fingerprint_key = year or "default"
        
        if fingerprint_key not in symbol_data["fingerprints"]:
            available_keys = list(symbol_data["fingerprints"].keys())
            logger.warning(f"Fingerprint '{fingerprint_key}' not found for {symbol}")
            logger.info(f"Available fingerprints: {available_keys}")
            return None
        
        return symbol_data["fingerprints"][fingerprint_key]
    
    def list_symbols(self) -> List[str]:
        """List all symbols in the encyclopedia."""
        return list(self.encyclopedia["symbols"].keys())
    
    def get_symbol_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get comprehensive information about a symbol."""
        if symbol not in self.encyclopedia["symbols"]:
            logger.warning(f"Symbol '{symbol}' not found in encyclopedia")
            return None
        
        return self.encyclopedia["symbols"][symbol]
    
    def print_fingerprint(self, symbol: str, year: Optional[str] = None):
        """Print a fingerprint in a formatted way."""
        fingerprint = self.get_fingerprint(symbol, year)
        if fingerprint:
            print(f"\n🔍 Fingerprint for {symbol} ({fingerprint['year']}):")
            print(f"   k: {fingerprint['k']:.2e}")
            print(f"   alpha: {fingerprint['alpha']:.4f}")
            print(f"   beta: {fingerprint['beta']:.4f}")
            print(f"   R²: {fingerprint['r_squared']:.4f}")
            print(f"   Data points: {fingerprint['data_points']}")
            print(f"   Generated: {fingerprint['generated_at']}")
            print(f"   Source: {fingerprint['source_file']}")
        else:
            print(f"❌ No fingerprint found for {symbol}")
    
    def print_symbol_info(self, symbol: str):
        """Print comprehensive information about a symbol."""
        info = self.get_symbol_info(symbol)
        if info:
            print(f"\n📊 Symbol Information: {symbol}")
            print(f"   First added: {info['metadata']['first_added']}")
            print(f"   Last updated: {info['metadata']['last_updated']}")
            print(f"   Total fingerprints: {info['metadata']['total_fingerprints']}")
            print(f"\n   Available fingerprints:")
            for key, fp in info['fingerprints'].items():
                print(f"     {key}: k={fp['k']:.2e}, α={fp['alpha']:.4f}, β={fp['beta']:.4f}, R²={fp['r_squared']:.4f}")
        else:
            print(f"❌ Symbol '{symbol}' not found in encyclopedia")


def main():
    """Main CLI interface."""
    parser = argparse.ArgumentParser(description="Symbol Encyclopedia Management")
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Add command
    add_parser = subparsers.add_parser('add', help='Add a fingerprint for a symbol')
    add_parser.add_argument('symbol', help='Symbol name (e.g., BTC)')
    add_parser.add_argument('csv_file', help='Path to CSV file with strike probabilities')
    add_parser.add_argument('year', nargs='?', help='Year for the fingerprint (optional)')
    
    # Get command
    get_parser = subparsers.add_parser('get', help='Get a fingerprint for a symbol')
    get_parser.add_argument('symbol', help='Symbol name')
    get_parser.add_argument('year', nargs='?', help='Year for the fingerprint (optional)')
    
    # List command
    subparsers.add_parser('list', help='List all symbols in encyclopedia')
    
    # Info command
    info_parser = subparsers.add_parser('info', help='Get detailed info about a symbol')
    info_parser.add_argument('symbol', help='Symbol name')
    
    args = parser.parse_args()
    
    encyclopedia = SymbolEncyclopedia()
    
    if args.command == 'add':
        success = encyclopedia.add_fingerprint(args.symbol, args.csv_file, args.year)
        if success:
            print(f"✅ Successfully added fingerprint for {args.symbol}")
        else:
            print(f"❌ Failed to add fingerprint for {args.symbol}")
    
    elif args.command == 'get':
        encyclopedia.print_fingerprint(args.symbol, args.year)
    
    elif args.command == 'list':
        symbols = encyclopedia.list_symbols()
        if symbols:
            print("\n📚 Symbols in Encyclopedia:")
            for symbol in symbols:
                info = encyclopedia.get_symbol_info(symbol)
                print(f"   {symbol}: {info['metadata']['total_fingerprints']} fingerprints")
        else:
            print("\n📚 Encyclopedia is empty")
    
    elif args.command == 'info':
        if args.symbol:
            encyclopedia.print_symbol_info(args.symbol)
        else:
            print("❌ Symbol name is required for info command")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main() 