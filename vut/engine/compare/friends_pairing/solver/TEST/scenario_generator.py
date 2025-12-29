"""
PURPOSE: Generate graph scenarios for Bipartite Matching stress testing.
"""

def pipe_graph(n):
    """Exactly one match for each subject: O(N)"""
    return {i: {i} for i in range(n)}

def complete_bipartite(n):
    """Every subject matches every nominal: O(N^2) edges"""
    all_nominals = set(range(n))
    return {i: all_nominals for i in range(n)}

def long_augmenting_path(n):
    """
    Forces a chain reaction. 
    Subject i can match Nominal i or i+1.
    If processed in order, matching Subject N might require 
    shifting all previous N-1 matches.
    """
    adj = {i: {i, i + 1} for i in range(n - 1)}
    adj[n - 1] = {n - 1}
    return adj

def the_bottleneck(n):
    """Many subjects, but they all fight over one nominal."""
    adj = {i: {0} for i in range(n)}
    # Only one subject gets a partner; the rest fail.
    return adj

def sudoku_pivot(n):
    """N-1 subjects match everything, 1 subject matches only the last one."""
    all_noms = set(range(n))
    adj = {i: all_noms for i in range(1, n)}
    adj[0] = {n - 1}
    return adj
