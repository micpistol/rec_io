#!/usr/bin/env python3
"""
Debug script for PostgreSQL probability calculator.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from backend.util.probability_calculator_postgresql import ProbabilityCalculatorPostgreSQL

def test_postgresql_calculator():
    """Test the PostgreSQL calculator initialization."""
    try:
        print("🔍 Testing PostgreSQL Probability Calculator")
        print("=" * 50)
        
        # Initialize the calculator
        calculator = ProbabilityCalculatorPostgreSQL("btc")
        
        print(f"✅ Calculator initialized successfully")
        print(f"📊 Loaded {len(calculator.momentum_fingerprints)} momentum fingerprints")
        
        # Test a simple calculation
        current_price = 50000.0
        ttc_seconds = 300  # 5 minutes
        strikes = [49500, 50500]  # Simple test strikes
        momentum_score = 0.0
        
        print(f"\n🧮 Testing calculation:")
        print(f"  Price: ${current_price}")
        print(f"  TTC: {ttc_seconds} seconds")
        print(f"  Strikes: {strikes}")
        print(f"  Momentum: {momentum_score}")
        
        results = calculator.calculate_strike_probabilities(
            current_price, ttc_seconds, strikes, momentum_score
        )
        
        print(f"\n📈 Results:")
        for result in results:
            print(f"  Strike ${result['strike']}: {result['prob_beyond']:.2f}% beyond")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_postgresql_calculator()
    if success:
        print("\n🎉 PostgreSQL calculator is working!")
    else:
        print("\n❌ PostgreSQL calculator has issues.")

