"""SPDX-License: MIT; (C) Frank-Rene Schaefer; Project: VUT
________________________________________________________________________________
PURPOSE: Analyze cProfile stats to find which functions are triggering 
         typeguard overhead.
________________________________________________________________________________
"""
import pstats
import sys

def analyze(stats_file):
    print(f"Analyzing {stats_file} to find callers of type-checking functions...\n")
    
    # Load stats
    p = pstats.Stats(stats_file)
    p.strip_dirs()
    p.sort_stats('cumtime')

    # 1. Find the "Typeguard Callers"
    # This will show exactly which VUT functions are the parents of the type checks
    print("="*80)
    print("FUNCTIONS TRIGGERING 'check_type_internal':")
    print("="*80)
    p.print_callers('check_type_internal')

    print("\n" + "="*80)
    print("FUNCTIONS TRIGGERING 'check_argument_types':")
    print("="*80)
    p.print_callers('check_argument_types')

    # 2. Show full paths for top bottlenecks
    print("\n" + "="*80)
    print("TOP 20 BOTTLENECKS WITH FULL PATHS:")
    print("="*80)
    # Re-init without strip_dirs to see absolute locations
    p_full = pstats.Stats(stats_file)
    p_full.sort_stats('tottime').print_stats(20)

if __name__ == "__main__":
    file = 'stats.log' if len(sys.argv) < 2 else sys.argv[1]
    try:
        analyze(file)
    except FileNotFoundError:
        print(f"Error: Could not find {file}. Ensure you have run your profile first.")
