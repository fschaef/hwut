#! /usr/bin/env python3
"""
SPDX-License-Identifier: MIT
Benchmark for VUT Equivalence Checking
"""
import sys
import time
import asyncio
import io

# Adjust path to find the vut package
sys.path.insert(0, "../../../../")

from vut.engine.compare.configuration import Configuration
import vut.engine.compare.main as main
from vut.language_support.python.deterministic_random import DeterministicStream

# --- Configuration Constants ---
POTPOURRI_BLOCK_SIZE = 32
NUMERIC_TOLERANCE    = 0.1
HAPPY_REGEX          = [r"fast|quick", r"fox|henn", r"happy|glad"]
RANDOM_SEED          = 0x12345678

def setup_configuration():
    """
    Define happy patterns, numeric tolerances, and analogy settings.
    """
    config = Configuration()
    
    # 1. Define Happy Patterns (Regex equivalence)
    # Matches "fast" in Subject to "quick" in Nominal (or vice versa)
    config.pattern_finder.equivalent_pattern_list.extend(HAPPY_REGEX)
    
    # 2. Define Numeric Tolerances
    config.pattern_finder.numeric_tolerance_ratio = NUMERIC_TOLERANCE
    
    return config

def generate_streams(n_lines):
    """
    Produces two streams (subject, nominal) that are 'equivalent'
    but differ structurally via shuffling, tolerances, and analogies.
    Uses DeterministicStream for reproducible results.
    """
    subject_lines = []
    nominal_lines = []
    
    # Initialize Deterministic Random Generator
    rng = DeterministicStream(RANDOM_SEED)
    
    # Consistent analogy mapping for this run
    # Subject: ((A)), ((B)) -> Nominal: ((1)), ((2))
    s_sym = ["((A))", "((B))", "((C))"]
    n_sym = ["((1))", "((2))", "((3))"]
    
    i = 0
    while i < n_lines:
        mode = rng.select(['normal'] * 10 + ['numeric', 'happy', 'potpourri'])
        
        if mode == 'potpourri' and i + POTPOURRI_BLOCK_SIZE < n_lines:
            # --- Potpourri Region (Shuffled Lines) ---
            # Both streams get |||| markers
            subject_lines.append("||||")
            nominal_lines.append("||||")
            
            block_content = []
            for _ in range(POTPOURRI_BLOCK_SIZE):
                # Generate unique content for the block to avoid ambiguity
                # Using rng to generate the content ID
                val = f"line_content_{rng.next_int(0, 100000)}"
                block_content.append(val)
            
            # Subject gets distinct order (Sample all elements = Shuffle)
            s_block = rng.sample(block_content, len(block_content))
            subject_lines.extend(s_block)
            
            # Nominal gets different order (Sample all elements = Shuffle)
            n_block = rng.sample(block_content, len(block_content))
            nominal_lines.extend(n_block)
            
            subject_lines.append("||||")
            nominal_lines.append("||||")
            i += POTPOURRI_BLOCK_SIZE
            
        elif mode == 'numeric':
            # --- Numeric Tolerance ---
            base = rng.next_int(10, 1000)
            # Create an offset within the tolerance ratio
            # offset = random_float * (tolerance * 0.9) to be safe
            offset = rng.next_float() * (NUMERIC_TOLERANCE * 0.9)
            
            subject_lines.append(f"Value: {float(base):.4f}")
            nominal_lines.append(f"Value: {float(base) + offset:.4f}")
            i += 1
            
        elif mode == 'happy':
            # --- Happy Pattern (fast vs quick, fox vs henn) ---
            subject_lines.append("The process is fast. The fox is happy.")
            nominal_lines.append("The process is quick. The henn is glad.")
            i += 1
            
        else:
            # --- Analogies (Consistent) ---
            # Select index 0, 1, or 2
            idx = rng.next_int(0, 2)
            subject_lines.append(f"Data element {s_sym[idx]} here.")
            nominal_lines.append(f"Data element {n_sym[idx]} here.")
            i += 1

    return "\n".join(subject_lines), "\n".join(nominal_lines)

async def run_benchmark(mode):
    
    # 1. Setup
    config = setup_configuration()

    if mode == "associate": STREAM_SIZE_LINES = 5000  
    else:                   STREAM_SIZE_LINES = 40000 
    print(f"--- Starting Benchmark: Mode={mode} Lines={STREAM_SIZE_LINES} ---")

    s_data, n_data = generate_streams(STREAM_SIZE_LINES)
    
    # Convert to streams as expected by the API (io.StringIO or similar)
    s_stream = io.StringIO(s_data)
    n_stream = io.StringIO(n_data)
    
    start_time = time.time()
    
    # 2. Execution
    if mode == 'associate':
        # Calls the association engine to view line-by-line pairings
        print("Running main.associate()...")
        pair_count = 0
        async for chunk_pair in main.associate(config, s_stream, n_stream):
            # Just consuming the generator
            pair_count += 1
        print(f"Processed {pair_count} chunks.")
        
    elif mode == 'equivalence':
        # Calls the full equivalence check
        print("Running main.compare()...")
        
        try:
            # Try Async
            result = await main.is_equivalent(config, s_stream, n_stream)
        except TypeError:
            print("ERROR: async handling failed.")
            
        if result:
            print("Verdict: EQUIVALENT (Success)")
        else:
            print(f"Verdict: {result.verdict} (Fail)")
            print("Result details:", result)
            sys.exit(1)

    duration = time.time() - start_time
    print(f"--- Finished in {duration:.4f} seconds ---")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: ./benchmark.py [associate|equivalence]")
        
        # Default behavior if no args provided (useful for quick checks)
        print("\nRunning default check (both modes)...")
        try:                       
            asyncio.run(run_benchmark("associate"))
            print("")
            asyncio.run(run_benchmark("equivalence"))
        except KeyboardInterrupt: 
            print("\nAborted.")
        sys.exit(0)
        
    mode_arg = sys.argv[1]
    
    try:                       
        asyncio.run(run_benchmark(mode_arg))
    except KeyboardInterrupt: 
        print("\nAborted.")
