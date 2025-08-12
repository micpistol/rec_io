#!/usr/bin/env python3
"""
Test script for chunked master table generator
Tests with a very small subset to verify functionality
"""

import os
import sys
import time

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.util.chunked_master_table_generator import ChunkedMasterTableGenerator

def test_chunked_generator():
    """Test the chunked generator with a very small subset"""
    print("Testing chunked master table generator...")
    
    # Create a test generator with very small ranges
    generator = ChunkedMasterTableGenerator("btc")
    
    # Override with tiny test ranges
    generator.ttc_range = (0, 10)  # Just 11 TTC values
    generator.buffer_range = (0, 50)  # Just 51 buffer values  
    generator.momentum_range = (-2, 2)  # Just 5 momentum values
    generator.num_chunks = 2  # Just 2 chunks for testing
    
    print(f"Test parameters:")
    print(f"  TTC: {generator.ttc_range[0]}-{generator.ttc_range[1]} ({generator.ttc_range[1] - generator.ttc_range[0] + 1} values)")
    print(f"  Buffer: {generator.buffer_range[0]}-{generator.buffer_range[1]} ({generator.buffer_range[1] - generator.buffer_range[0] + 1} values)")
    print(f"  Momentum: {generator.momentum_range[0]}-{generator.momentum_range[1]} ({generator.momentum_range[1] - generator.momentum_range[0] + 1} values)")
    print(f"  Chunks: {generator.num_chunks}")
    
    # Calculate expected combinations
    total_ttc = generator.ttc_range[1] - generator.ttc_range[0] + 1
    total_buffer = generator.buffer_range[1] - generator.buffer_range[0] + 1
    total_momentum = generator.momentum_range[1] - generator.momentum_range[0] + 1
    total_combinations = total_ttc * total_buffer * total_momentum * 2  # *2 for positive/negative
    
    print(f"  Total combinations: {total_combinations:,}")
    print(f"  Expected rows in table: {total_combinations // 2:,}")
    
    # Test chunk calculation
    chunks = generator.calculate_chunk_parameters()
    print(f"\nChunk configuration:")
    for chunk in chunks:
        ttc_size = chunk['ttc_end'] - chunk['ttc_start'] + 1
        print(f"  Chunk {chunk['chunk_id']}: TTC {chunk['ttc_start']}-{chunk['ttc_end']} ({ttc_size} values)")
    
    # Test database connection
    print(f"\nTesting database connection...")
    try:
        conn = generator.db_config
        print(f"  Database config: {conn['database']} on {conn['host']} as {conn['user']}")
        
        # Test actual connection
        import psycopg2
        test_conn = psycopg2.connect(**generator.db_config)
        test_conn.close()
        print("  ✅ Database connection successful")
        
    except Exception as e:
        print(f"  ❌ Database connection failed: {e}")
        return False
    
    # Test fingerprint data loading
    print(f"\nTesting fingerprint data loading...")
    try:
        # Test loading data for momentum bucket 0
        ttc_values, pos_move_percentages, neg_move_percentages, pos_data, neg_data = generator.load_fingerprint_data(0)
        print(f"  ✅ Loaded fingerprint data for momentum 0")
        print(f"     TTC values: {len(ttc_values)}")
        print(f"     Positive move percentages: {len(pos_move_percentages)}")
        print(f"     Negative move percentages: {len(neg_move_percentages)}")
        print(f"     Sample TTC range: {ttc_values.min():.1f} - {ttc_values.max():.1f}")
        print(f"     Sample positive move range: {pos_move_percentages.min():.3f}% - {pos_move_percentages.max():.3f}%")
        print(f"     Sample negative move range: {neg_move_percentages.min():.3f}% - {neg_move_percentages.max():.3f}%")
        
    except Exception as e:
        print(f"  ❌ Fingerprint data loading failed: {e}")
        return False
    
    # Test interpolation
    print(f"\nTesting interpolation...")
    try:
        prob_pos, prob_neg = generator.interpolate_probabilities(60, 100, 0)  # 1min TTC, 100pt buffer, momentum 0
        print(f"  ✅ Interpolation successful")
        print(f"     TTC=60s, Buffer=100pt, Momentum=0")
        print(f"     prob_within_positive: {prob_pos:.2f}%")
        print(f"     prob_within_negative: {prob_neg:.2f}%")
        
    except Exception as e:
        print(f"  ❌ Interpolation failed: {e}")
        return False
    
    print(f"\n✅ All tests passed! The chunked generator is ready to use.")
    return True

if __name__ == "__main__":
    success = test_chunked_generator()
    if success:
        print(f"\nReady to run full generation with:")
        print(f"  python backend/util/chunked_master_table_generator.py")
    else:
        print(f"\n❌ Tests failed. Please fix issues before running full generation.")
