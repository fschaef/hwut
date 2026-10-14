import pstats
import sys

# Increase recursion depth for very deep call stacks if necessary
sys.setrecursionlimit(2000)

def get_all_callees(stats, func_key, visited=None):
    """Recursively collect all functions called by a specific function."""
    if visited is None:
        visited = set()

    if func_key in visited:
        return visited

    visited.add(func_key)

    # stats.all_callees is a dict mapping callers to their children
    callees = stats.all_callees.get(func_key, {})
    for callee in callees:
        get_all_callees(stats, callee, visited)
    return visited

def analyze(stats_file):
    print(f"Analyzing {stats_file} for nested calls...\n")

    p = pstats.Stats(stats_file)
    p.strip_dirs()

    # MANDATORY: This populates the all_callees attribute
    p.calc_callees()

    # Identify the specific entry points
    # We look for functions named 'associate' or 'is_equivalent'
    targets = [k for k in p.stats.keys() if k[2] in ['associate', 'is_equivalent']]

    if not targets:
        print("Target functions not found. Available functions include:")
        # Print a few examples to help debugging
        for k in list(p.stats.keys())[:10]:
            print(f"  - {k[2]}")
        return

    print(f"Found entry points: {[t[2] for t in targets]}")

    # Collect all nested function keys
    nested_funcs = set()
    for target in targets:
        get_all_callees(p, target, nested_funcs)

    # Header for the output
    header = f"{'ncalls':>10} {'tottime':>10} {'cumtime':>10} {'function'}"
    print("\n" + "=" * len(header))
    print(header)
    print("-" * len(header))

    # Sort by cumulative time (index 3 in pstats value tuple)
    sorted_nested = sorted(nested_funcs, key=lambda x: p.stats[x][3], reverse=True)

    for func in sorted_nested:
        # p.stats[func] returns (cc, nc, tt, ct, callers)
        _, nc, tt, ct, _ = p.stats[func]
        func_desc = f"{func[0]}:{func[1]}({func[2]})"
        print(f"{nc:10} {tt:10.4f} {ct:10.4f}  {func_desc}")

if __name__ == "__main__":
    file = 'stats.log' if len(sys.argv) < 2 else sys.argv[1]
    try:
        analyze(file)
    except FileNotFoundError:
        print(f"Error: Could not find {file}.")
