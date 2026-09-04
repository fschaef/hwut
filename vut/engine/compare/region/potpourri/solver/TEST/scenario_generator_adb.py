"""
PURPOSE: Generate graph scenarios with FrozenAnalogyDb constraints.
"""
from vut.engine.compare.contract.frozen_analogy_db import FrozenAnalogyDb

def _adb(mapping: dict):
    """Helper to create a FrozenAnalogyDb from a dict {subject_val: nominal_val}"""
    adb = FrozenAnalogyDb()
    for s_val, n_val in mapping.items():
        # Assuming the standard VUT interface for adding analogies
        adb = adb.merge(FrozenAnalogyDb({s_val: n_val}))
    return adb

def analogy_pipe(n):
    """O(N) - Simple 1-to-1 matching with consistent analogies."""
    return {i: [(i, _adb({f"S{i}": f"N{i}"}))] for i in range(n)}

def mrv_trap(n):
    """
    A true MRV Trap:
    1. Subjects 1..N-1 are highly constrained (1 choice) and consistent.
    2. Subject 0 is less constrained (2 choices).
    3. One choice of Subject 0 conflicts with the ONLY choice of Subject 1.
    """
    adj = {}

    # Subjects 1 to N-1: All consistent with each other.
    # They all map unique wildcards.
    for i in range(1, n):
        adj[i] = [(i, _adb({f"Wildcard_{i}": f"Value_{i}"}))]

    # Subject 0: The "Sudoku" decision.
    # Choice A (Nominal 0): Conflicts with Subject 1's wildcard mapping.
    # Choice B (Nominal N): Clean, allows the whole chain to work.
    adj[0] = [
        (0, _adb({"Wildcard_1": "WRONG_VALUE"})), # Conflicts with Subj 1
        (n, _adb({"Wildcard_Pivot": "Clean"}))     # Clean
    ]
    return adj

def combinatorial_explosion(n):
    adj = {}
    for i in range(n):
        # We ensure that Choice B is ALWAYS consistent with other Choice Bs
        # Choice A: Subject i maps wildcard 'Common' to a UNIQUE value (Conflict!)
        # Choice B: Subject i maps unique wildcard 'K{i}' to 'V{i}' (Clean)
        adj[i] = [
            (i,     _adb({"COMMON": f"Value_{i}"})),
            (i + n, _adb({f"K{i}": f"V{i}"}))
        ]
    return adj

def lane_trap(n):
    """
    s0...sN-1 have two choices each.
    Choice A maps a 'Global_Constraint' wildcard to 'Value_A'.
    Choice B maps a 'Global_Constraint' wildcard to 'Value_B'.

    The final subject sN ONLY has candidates that require 'Value_B'.
    If the solver picked 'Value_A' at any point in the first N-1 subjects,
    the final subject will fail to match ANY of its nominals.
    """
    adj = {}

    # Global wildcard that will act as the 'Lock'
    lock = "GLOBAL_LOCK"

    # 1. THE LANES: s0 to sN-1
    for i in range(n - 1):
        # Every subject i can pick two different nominals.
        # Candidate 0 (Lane A): Sets the lock to 'POISON'
        # Candidate 1 (Lane B): Sets the lock to 'CLEAN'
        adj[i] = [
            (i,          _adb({lock: "POISON"})),
            (i + n + 1,  _adb({lock: "CLEAN"}))
        ]

    # 2. THE DEAD END: sN
    # Subject sN has many nominals, but all of them require the lock to be 'CLEAN'.
    # If ANY previous subject chose the 'POISON' lane, this subject fails.
    last_idx = n - 1
    s_n_candidates = []
    for j in range(n):
        # All potential nominals for the last subject require 'CLEAN'
        s_n_candidates.append((j + (2 * n), _adb({lock: "CLEAN"})))

    adj[last_idx] = s_n_candidates
    return adj
