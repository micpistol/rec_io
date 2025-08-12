#!/usr/bin/env python3
"""
TEST UPC WITH LOOKUP CALCULATOR

A test version of the unified production coordinator that uses the lookup calculator
to generate strike tables. This allows us to validate the entire pipeline using
the existing test probability table before spending money on cloud generation.

Usage:
    python backend/util/test_upc_with_lookup.py
"""

import os
import sys
import time
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional

# Add backend to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.util.probability_calculator_lookup_test import ProbabilityCalculatorLookupTest
from backend.util.probability_calculator_postgresql import ProbabilityCalculatorPostgreSQL
from backend.util.paths import get_data_dir

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TestUPCWithLookup:
    """
    Test version of UPC that uses lookup calculator to generate strike tables.
    """
    
    def __init__(self):
        self.symbol = "btc"
        self.test_count = 0
        
        # Initialize both calculators for comparison
        try:
            self.lookup_calculator = ProbabilityCalculatorLookupTest("btc")
            logger.info("✅ Lookup calculator initialized successfully")
        except Exception as e:
            logger.error(f"❌ Failed to initialize lookup calculator: {e}")
            self.lookup_calculator = None
            
        try:
            self.live_calculator = ProbabilityCalculatorPostgreSQL()
            logger.info("✅ Live calculator initialized successfully")
        except Exception as e:
            logger.error(f"❌ Failed to initialize live calculator: {e}")
            self.live_calculator = None
    
    def generate_test_strike_table(self, current_price: float, ttc_seconds: float, 
                                  momentum_score: float = 0.0, step: int = 250, 
                                  num_steps: int = 10) -> Dict:
        """
        Generate a test strike table using the lookup calculator.
        
        Args:
            current_price: Current BTC price
            ttc_seconds: Time to close in seconds
            momentum_score: Momentum score
            step: Strike step size (default $250)
            num_steps: Number of steps above and below (default 10)
            
        Returns:
            Strike table data dictionary
        """
        try:
            # Round current price to nearest step
            base_strike = int(round(current_price / step) * step)
            strikes = [base_strike + (i * step) for i in range(-num_steps, num_steps + 1)]
            
            # Generate probabilities using lookup calculator
            if self.lookup_calculator:
                start_time = time.time()
                lookup_probabilities = self.lookup_calculator.calculate_strike_probabilities(
                    current_price=current_price,
                    ttc_seconds=ttc_seconds,
                    strikes=strikes,
                    momentum_score=momentum_score
                )
                lookup_time = (time.time() - start_time) * 1000
                
                logger.info(f"📊 Lookup calculation: {lookup_time:.3f}ms for {len(strikes)} strikes")
            else:
                lookup_probabilities = []
                lookup_time = 0
            
            # Generate probabilities using live calculator for comparison
            if self.live_calculator:
                start_time = time.time()
                live_probabilities = self.live_calculator.calculate_strike_probabilities(
                    current_price=current_price,
                    ttc_seconds=ttc_seconds,
                    strikes=strikes,
                    momentum_score=momentum_score
                )
                live_time = (time.time() - start_time) * 1000
                
                logger.info(f"📊 Live calculation: {live_time:.3f}ms for {len(strikes)} strikes")
            else:
                live_probabilities = []
                live_time = 0
            
            # Compare results
            comparison_stats = self._compare_probabilities(lookup_probabilities, live_probabilities)
            
            # Create strike table output
            strike_table = {
                "timestamp": datetime.now().isoformat(),
                "symbol": self.symbol.upper(),
                "current_price": current_price,
                "base_strike": base_strike,
                "ttc_seconds": ttc_seconds,
                "momentum_score": momentum_score,
                "strikes": strikes,
                "lookup_probabilities": lookup_probabilities,
                "live_probabilities": live_probabilities,
                "performance": {
                    "lookup_time_ms": lookup_time,
                    "live_time_ms": live_time,
                    "speed_improvement": live_time / lookup_time if lookup_time > 0 else 0
                },
                "comparison": comparison_stats
            }
            
            return strike_table
            
        except Exception as e:
            logger.error(f"❌ Error generating strike table: {e}")
            return {}
    
    def _compare_probabilities(self, lookup_probs: List[Dict], live_probs: List[Dict]) -> Dict:
        """Compare lookup and live probability results."""
        if not lookup_probs or not live_probs:
            return {"error": "Missing probability data"}
        
        if len(lookup_probs) != len(live_probs):
            return {"error": "Probability count mismatch"}
        
        differences = []
        max_difference = 0.0
        total_difference = 0.0
        matching_count = 0
        
        for i, (lookup_prob, live_prob) in enumerate(zip(lookup_probs, live_probs)):
            lookup_within = lookup_prob.get('prob_within', 0)
            live_within = live_prob.get('prob_within', 0)
            
            difference = abs(lookup_within - live_within)
            differences.append(difference)
            total_difference += difference
            max_difference = max(max_difference, difference)
            
            if difference < 0.01:  # Within 0.01%
                matching_count += 1
        
        avg_difference = total_difference / len(differences) if differences else 0
        
        return {
            "total_strikes": len(differences),
            "matching_strikes": matching_count,
            "max_difference": max_difference,
            "avg_difference": avg_difference,
            "total_difference": total_difference,
            "accuracy_percentage": (matching_count / len(differences)) * 100 if differences else 0
        }
    
    def save_strike_table(self, strike_table: Dict, filename: str = None) -> str:
        """Save strike table to JSON file."""
        try:
            if filename is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"test_strike_table_{timestamp}.json"
            
            output_dir = os.path.join(get_data_dir(), "test_data")
            os.makedirs(output_dir, exist_ok=True)
            
            filepath = os.path.join(output_dir, filename)
            
            with open(filepath, 'w') as f:
                json.dump(strike_table, f, indent=2)
            
            logger.info(f"✅ Strike table saved to: {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"❌ Error saving strike table: {e}")
            return ""
    
    def run_test_scenarios(self) -> List[Dict]:
        """Run multiple test scenarios to validate the lookup system."""
        test_scenarios = [
            {
                "name": "5-minute TTC, neutral momentum",
                "current_price": 120000,
                "ttc_seconds": 300,  # 5 minutes
                "momentum_score": 0.0,
                "step": 250,
                "num_steps": 5
            },
            {
                "name": "10-minute TTC, positive momentum",
                "current_price": 120000,
                "ttc_seconds": 600,  # 10 minutes
                "momentum_score": 5.0,
                "step": 250,
                "num_steps": 5
            },
            {
                "name": "15-minute TTC, negative momentum",
                "current_price": 120000,
                "ttc_seconds": 900,  # 15 minutes
                "momentum_score": -3.0,
                "step": 250,
                "num_steps": 5
            },
            {
                "name": "30-minute TTC, high momentum",
                "current_price": 120000,
                "ttc_seconds": 1800,  # 30 minutes (within test table range)
                "momentum_score": 5.0,  # Clamped to test table range (-5 to +5)
                "step": 250,
                "num_steps": 5
            }
        ]
        
        results = []
        
        for scenario in test_scenarios:
            logger.info(f"\n{'='*60}")
            logger.info(f"Running test scenario: {scenario['name']}")
            logger.info(f"{'='*60}")
            
            try:
                strike_table = self.generate_test_strike_table(
                    current_price=scenario['current_price'],
                    ttc_seconds=scenario['ttc_seconds'],
                    momentum_score=scenario['momentum_score'],
                    step=scenario['step'],
                    num_steps=scenario['num_steps']
                )
                
                if strike_table:
                    # Save to file
                    filename = f"test_strike_table_{scenario['name'].replace(' ', '_').replace(',', '')}.json"
                    filepath = self.save_strike_table(strike_table, filename)
                    
                    # Log summary
                    performance = strike_table.get('performance', {})
                    comparison = strike_table.get('comparison', {})
                    
                    logger.info(f"📊 Performance Summary:")
                    logger.info(f"   Lookup time: {performance.get('lookup_time_ms', 0):.3f}ms")
                    logger.info(f"   Live time: {performance.get('live_time_ms', 0):.3f}ms")
                    logger.info(f"   Speed improvement: {performance.get('speed_improvement', 0):.1f}x")
                    
                    logger.info(f"📊 Accuracy Summary:")
                    logger.info(f"   Matching strikes: {comparison.get('matching_strikes', 0)}/{comparison.get('total_strikes', 0)}")
                    logger.info(f"   Max difference: {comparison.get('max_difference', 0):.4f}%")
                    logger.info(f"   Avg difference: {comparison.get('avg_difference', 0):.4f}%")
                    logger.info(f"   Accuracy: {comparison.get('accuracy_percentage', 0):.1f}%")
                    
                    results.append({
                        "scenario": scenario['name'],
                        "success": True,
                        "filepath": filepath,
                        "performance": performance,
                        "comparison": comparison
                    })
                else:
                    logger.error(f"❌ Failed to generate strike table for scenario: {scenario['name']}")
                    results.append({
                        "scenario": scenario['name'],
                        "success": False,
                        "error": "Strike table generation failed"
                    })
                    
            except Exception as e:
                logger.error(f"❌ Error in scenario {scenario['name']}: {e}")
                results.append({
                    "scenario": scenario['name'],
                    "success": False,
                    "error": str(e)
                })
        
        return results
    
    def generate_live_probabilities_json(self, current_price: float, ttc_seconds: float, 
                                       momentum_score: float = 0.0, step: int = 250, 
                                       num_steps: int = 10) -> str:
        """
        Generate btc_live_probabilities.json using lookup calculator.
        This mimics the function in probability_calculator.py that UPC calls.
        """
        try:
            # Round current price to nearest step
            base_strike = int(round(current_price / step) * step)
            strikes = [base_strike + (i * step) for i in range(-num_steps, num_steps + 1)]
            
            # Get probabilities using lookup calculator
            if self.lookup_calculator:
                probabilities = self.lookup_calculator.calculate_strike_probabilities(
                    current_price=current_price,
                    ttc_seconds=ttc_seconds,
                    strikes=strikes,
                    momentum_score=momentum_score
                )
            else:
                logger.error("❌ Lookup calculator not available")
                return ""
            
            # Create output structure
            output = {
                "timestamp": datetime.now().isoformat(),
                "current_price": current_price,
                "base_strike": base_strike,
                "ttc_seconds": ttc_seconds,
                "momentum_score": momentum_score,
                "strikes": strikes,
                "probabilities": probabilities,
                "fingerprint_csv": "lookup_table_test"  # Indicate source
            }
            
            # Save to file
            output_dir = os.path.join(get_data_dir(), "live_data", "live_probabilities")
            os.makedirs(output_dir, exist_ok=True)
            
            output_path = os.path.join(output_dir, "btc_live_probabilities.json")
            
            with open(output_path, 'w') as f:
                json.dump(output, f, indent=2)
            
            logger.info(f"✅ Generated live probabilities JSON: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"❌ Error generating live probabilities JSON: {e}")
            return ""


def main():
    """Main function to run the test UPC with lookup."""
    logger.info("🚀 Starting Test UPC with Lookup Calculator")
    logger.info("This will test the entire pipeline using the existing test probability table")
    
    # Initialize test UPC
    test_upc = TestUPCWithLookup()
    
    # Check if calculators are available
    if not test_upc.lookup_calculator:
        logger.error("❌ Lookup calculator not available. Cannot proceed.")
        return 1
    
    if not test_upc.live_calculator:
        logger.warning("⚠️ Live calculator not available. Will only test lookup calculator.")
    
    # Run test scenarios
    logger.info("\n📋 Running test scenarios...")
    results = test_upc.run_test_scenarios()
    
    # Summary
    logger.info(f"\n{'='*60}")
    logger.info("TEST RESULTS SUMMARY")
    logger.info(f"{'='*60}")
    
    successful_tests = [r for r in results if r['success']]
    failed_tests = [r for r in results if not r['success']]
    
    logger.info(f"✅ Successful tests: {len(successful_tests)}/{len(results)}")
    logger.info(f"❌ Failed tests: {len(failed_tests)}/{len(results)}")
    
    if successful_tests:
        logger.info(f"\n📊 Performance Summary:")
        total_speed_improvement = 0
        total_accuracy = 0
        
        for result in successful_tests:
            performance = result.get('performance', {})
            comparison = result.get('comparison', {})
            
            speed_improvement = performance.get('speed_improvement', 0)
            accuracy = comparison.get('accuracy_percentage', 0)
            
            total_speed_improvement += speed_improvement
            total_accuracy += accuracy
            
            logger.info(f"   {result['scenario']}: {speed_improvement:.1f}x faster, {accuracy:.1f}% accurate")
        
        avg_speed_improvement = total_speed_improvement / len(successful_tests)
        avg_accuracy = total_accuracy / len(successful_tests)
        
        logger.info(f"\n📊 Averages:")
        logger.info(f"   Speed improvement: {avg_speed_improvement:.1f}x faster")
        logger.info(f"   Accuracy: {avg_accuracy:.1f}%")
    
    if failed_tests:
        logger.info(f"\n❌ Failed Tests:")
        for result in failed_tests:
            logger.info(f"   {result['scenario']}: {result.get('error', 'Unknown error')}")
    
    # Test live probabilities JSON generation
    logger.info(f"\n{'='*60}")
    logger.info("Testing live probabilities JSON generation...")
    logger.info(f"{'='*60}")
    
    json_path = test_upc.generate_live_probabilities_json(
        current_price=120000,
        ttc_seconds=300,
        momentum_score=0.0
    )
    
    if json_path:
        logger.info(f"✅ Live probabilities JSON test successful: {json_path}")
    else:
        logger.error("❌ Live probabilities JSON test failed")
    
    logger.info(f"\n🎉 Test UPC with Lookup completed!")
    logger.info(f"Check the generated JSON files in backend/data/test_data/ for detailed results")
    
    return 0 if len(failed_tests) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
