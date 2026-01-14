#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: HWUT Unit Test for Analogy Solver (Global Consistency Logic).

CHOICES: basic, frequency, order, aggressive, monkey;

DESCRIPTION:

Tests the 'find_best_analogies' function which generates a 1:1 translation
map between subject and nominal tokens based on frequency signatures and
first-appearance order constraints.

Then, it maps towards pure integer ids according to their equivalences.
______________________________________________________________________________
"""
import sys

sys.path.insert(0, "../" * 9)

# Adjust import to match your project structure
import vut.engine.compare.engine.association.line_sequence.edit_operations.line_edit.analogy_sequence_edit as analogy_sequence_edit

if "--hwut-info" in sys.argv:
    print("Analogy Solver Verification;")
    print("CHOICES: basic, frequency, order, aggressive, monkey;")
    sys.exit()

def test_mapping(subject, nominal):
    print(f"   Subject: {subject}")
    print(f"   Nominal: {nominal}")
    
    # Run the algorithm
    analogy_map = analogy_sequence_edit.find_best_analogies(subject, nominal)

    # Print result deterministically (sorted by key)
    print("   => Mapping:")
    if not analogy_map:
        print("  <empty>")
    else:
        for key, value in sorted(analogy_map.items()):
            print(f"  '{key}' -> '{value}'")

    subject_ids, \
    nominal_ids  = analogy_sequence_edit.assign_token_ids(subject, nominal, analogy_map)

    print("   => Id representation: 'same id <=> analogy valid':")
    print(f"   Subject-ids: {subject_ids}")
    print(f"   Nominal-ids: {nominal_ids}")
    print("-" * 30)
    

if "basic" in sys.argv:
    print("--- CATEGORY: BASIC (Length Mismatches) ---")
    # Equal
    test_mapping([], [])
    test_mapping(['A'], ['1'])
    test_mapping(['A', 'B'], ['1', '2'])
    
    # 0 vs N
    print("[0 vs 1]")
    test_mapping([], ['1'])
    print("[0 vs 2]")
    test_mapping([], ['1', '2'])
    
    # N vs 0
    print("[1 vs 0]")
    test_mapping(['A'], [])
    print("[2 vs 0]")
    test_mapping(['A', 'B'], [])
    
    # Unequal lengths, partial subsets
    print("[1 vs 2]")
    test_mapping(['A'], ['1', '2']) 
    print("[2 vs 1]")
    test_mapping(['A', 'B'], ['1']) # B cannot map

if "frequency" in sys.argv:
    print("--- CATEGORY: FREQUENCY CONSTRAINTS ---")
    # Exact frequency matches
    test_mapping(['A', 'A'], ['1', '1'])
    test_mapping(['A', 'A', 'B'], ['1', '1', '2'])
    
    # Frequency Mismatches (Should NOT map)
    # A(2) vs 1(1), 2(1) -> No target has count 2
    test_mapping(['A', 'A'], ['1', '2']) 
    
    # A(1) vs 1(2) -> No target has count 1
    test_mapping(['A'], ['1', '1'])
    
    # Mixed success/fail
    # A(2) matches 1(2). B(1) has no match (Nominal '2' has count 3)
    test_mapping(['A', 'A', 'B'], ['1', '1', '2', '2', '2'])

if "order" in sys.argv:
    print("--- CATEGORY: ORDER TIE-BREAKING ---")
    # Both have count 1. First unique in Subject maps to First unique in Nominal.
    test_mapping(['A', 'B'], ['1', '2'])
    
    # Swapped appearance in Subject
    # Subject Firsts: B, then A. Nominal Firsts: 1, then 2.
    # Expect: B->1, A->2
    test_mapping(['B', 'A'], ['1', '2'])
    
    # Interleaved tie-breaking with higher frequencies
    # A(2), B(2) vs 1(2), 2(2)
    # First unique A is index 0. First unique B is index 1.
    # Expect: A->1, B->2
    test_mapping(['A', 'B', 'A', 'B'], ['1', '2', '1', '2'])
    
    # Complex Interleave
    # Subject: A(0), B(1). Nominal: 2(0), 1(1).
    # Expect: A->2, B->1
    test_mapping(['A', 'B', 'A', 'B'], ['2', '1', '2', '1'])

if "monkey" in sys.argv:
    print("--- CATEGORY: MONKEY LIKE TEST ---")
    # A structured sequence that looks chaotic but has clear frequency/order logic.
    # Subject: A(2), B(2), C(2), D(1), E(1)
    # Nominal: 1(2), 2(2), 3(2), 4(1), 5(1)
    # Appearance Order S: A, B, C, D, E
    # Appearance Order N: 1, 2, 3, 4, 5
    # Expected: A->1, B->2, C->3, D->4, E->5
    
    print("NOTE: B -> 2, because it can switch with a later 'D'")
    s_monkey = ['A', 'B', 'C', 
                'B', 'B', 'B', 
                'C', 'C', 'C',
                'A', 'B', 'C']
    n_monkey = ['1', '2', '3', 
                '1', '1', '1', 
                '2', '2', '2',
                '3', '2', '1']
    
    test_mapping(s_monkey, n_monkey)

if "aggressive" in sys.argv:
    print("--- CATEGORY: AGGRESSIVE / BORDER CASES ---")
    
    # 1. The Staircase (Distinct Frequencies)
    subj_stair = ['A'] + ['B']*2 + ['C']*3 + ['D']*4
    nom_stair  = ['3']*3 + ['1'] + ['4']*4 + ['2']*2 # Scrambled order
    # Expect: A->1, B->2, C->3, D->4
    test_mapping(subj_stair, nom_stair)
    
    # 2. The Pigeonhole Squeeze (More candidates than slots)
    s_pigeon = ['A','A', 'B','B', 'C','C', 'D','D', 'E','E'] 
    n_pigeon = ['1','1', '2','2', '3','3']                   
    # Expect: A->1, B->2, C->3. D, E unmapped.
    test_mapping(s_pigeon, n_pigeon)
    
    s_pigeon = ['1','1', '2','2', '3','3']                   
    n_pigeon = ['A','A', 'B','B', 'C','C', 'D','D', 'E','E'] 
    test_mapping(s_pigeon, n_pigeon)

    # 3. Transpose "Ghost" Logic Verification
    test_mapping(['A', 'VN', 'B', 'C'], ['A', 'C', 'B', 'VN'])
    
    # 4. Large Data Volume (Performance & Stability)
    s_large = [f"item_{i:02}" for i in range(32)]
    n_large = [f"num_{i:02}" for i in range(31, -1, -1)]
    print("Large Test: 100 unique items vs 100 unique items")
    
    # Use the imported module correctly
    test_mapping(s_large, n_large)
    
