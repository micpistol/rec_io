#!/usr/bin/env python3
"""
Momentum Database Writer
Continuously writes BTC price and weighted momentum scores to rolling 30-day database
"""

import time
import sys
from datetime import datetime
from live_data_analysis_cloud import LiveDataAnalyzerCloud

def main():
    """Main function to continuously write momentum data"""
    print("🚀 Starting Momentum Database Writer")
    print("📊 Writing BTC price and momentum scores to rolling 30-day database")
    print("⏰ Updates every second")
    print("=" * 60)
    
    analyzer = LiveDataAnalyzerCloud()
    
    try:
        while True:
            # Get current momentum data
            data = analyzer.get_momentum_data()
            
            if data['current_price']:
                print(f"⏰ {data['timestamp']} | 💰 ${data['current_price']:,.2f} | ⚖️ {data['weighted_momentum_score']:.4f}%")
            else:
                print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | ⚠️ No price data available")
            
            # Wait 1 second before next update
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n🛑 Momentum database writer stopped")
    except Exception as e:
        print(f"❌ Error: {e}")

def start_momentum_database_writer():
    """Start function for cloud service orchestration"""
    main()

if __name__ == "__main__":
    start_momentum_database_writer() 