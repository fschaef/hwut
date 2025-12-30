#! /usr/bin/env python
"""
Benchmark for vut.engine.compare.edit_operations.string module.
Measures the performance of the edit distance algorithm, bypassing the LRU cache
to ensure the actual computational logic is tested.
"""
import timeit
import sys
import os
import random

sys.path.insert(0, "../../../../../")

import string as py_string #noqa E402

# Ensure the package is in path
if os.getcwd() not in sys.path:
    sys.path.append(os.getcwd())

try:
    from vut.engine.compare.edit_operations import string
except ImportError:
    print("Error: Could not import 'vut.engine.compare.edit_operations.string'.")
    print("Ensure you are running from the project root directory.")
    sys.exit(1)

def get_random_string(length):
    """Generates a random string of fixed length."""
    chars = py_string.ascii_letters + " "
    return ''.join(random.choices(chars, k=length))

def run_benchmark():
    print(f"{'Scenario':<25} | {'Len':<5} | {'Calls':<8} | {'Total(s)':<8} | {'us/Call':<8}")
    print("-" * 70)

    # Scenarios to test different paths in the logic:
    # 1. Identical (Early exit check)
    # 2. Short (Direct Levenshtein, < 16 chars)
    # 3. Medium/Long (Split Iterable logic + Sum, > 16 chars)
    
    scenarios = [
        ("Identical (Early Exit)", 10, 1000000, True),
        ("Short (Levenshtein)",    10, 100000, False), 
        ("Medium (Split)",         50, 10000, False),  
        ("Long (Split)",           200, 1000, False),
        ("Very Long (Split)",      2000, 100, False),
    ]

    # Access the unwrapped function to measure algorithmic speed, 
    # not the LRU cache lookup speed.
    if hasattr(string.do, '__wrapped__'):
        func = string.do.__wrapped__
    else:
        func = string.do

    for name, length, loops, identical in scenarios:
        s1 = get_random_string(length)
        if identical:
            s2 = s1
        else:
            # Create a distinct string
            s2 = get_random_string(length)
            # Ensure they aren't accidentally identical for short strings
            while s2 == s1:
                s2 = get_random_string(length)

        # Run benchmark
        t = timeit.timeit(lambda: func(s1, s2), number=loops)
        
        us_per_call = (t / loops) * 1e6
        print(f"{name:<25} | {length:<5} | {loops:<8} | {t:.4f}   | {us_per_call:.2f}")

if __name__ == "__main__":
    run_benchmark()
