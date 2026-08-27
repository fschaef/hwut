#! /usr/bin/env python3
#
# hwut {
#     title      = "FrozenAnalogyDb Validation Suite"
#     choices    = ["consistency", "flyweight", "hybrid_masks",
#                   "immutability", "member_functions"]
# }
#
"""
PURPOSE: Aggressive validation of FrozenAnalogyDb member functions and state,
         including Hybrid Bitmask/ID validation logic.
"""
import sys
import os

# Path setup
this_directory = os.path.join(os.path.dirname(sys.argv[0]), "../../../../../")
sys.path.insert(0, this_directory)

from vut.engine.compare.engine.frozen_analogy_db import FrozenAnalogyDb

if "--hwut-info" in sys.argv:
    print("FrozenAnalogyDb Validation Suite;")
    print("CHOICES: flyweight, consistency, immutability, member_functions, hybrid_masks;")
    sys.exit()

def print_row(test_name, stimulus, expected, result):
    print(f"| {test_name:<25} | {stimulus:<35} | {expected:<12} | {result:<8} |")

def print_header():
    print("-" * 95)
    print(f"| {'Test Case':<25} | {'Stimulus (Input Data)':<35} | {'Expected':<12} | {'Result':<8} |")
    print("-" * 95)

if "member_functions" in sys.argv:
    print("\n--- INVARIANT: MEMBER FUNCTION INTEGRITY ---")
    print_header()

    # Stimulus A: Bitmask Generation Logic (Small Scale)
    # We check if the mask correctly reflects (1 << symbol_id)
    sym_s = "subject_alpha"
    sym_n = "nominal_omega"
    db = FrozenAnalogyDb({sym_s: sym_n})
    
    s_id = FrozenAnalogyDb()._registry.get_symbol_id(sym_s)
    n_id = FrozenAnalogyDb()._registry.get_symbol_id(sym_n)
    
    # Ensure we are below the limit for this basic test
    if s_id < 256 and n_id < 256:
        mask_check = (db.subj_mask == (1 << s_id)) and (db.nom_mask == (1 << n_id))
        print_row("Bitmask Alignment", "1 pair -> masks", "Match IDs", "PASS" if mask_check else "FAIL")
    else:
        print_row("Bitmask Alignment", "IDs too high for basic test", "SKIP", "WARN")

    # Stimulus B: Iteration / items()
    input_data = {"A": "1", "B": "2", "C": "3"}
    db_iter = FrozenAnalogyDb(input_data)
    output_data = dict(db_iter.items())
    print_row("Items() Reconstruction", "3 pairs -> items()", "Full Match", "PASS" if input_data == output_data else "FAIL")

    # Stimulus C: Round-trip to_AnalogyDb
    mutable = db_iter.to_AnalogyDb()
    print_row("to_AnalogyDb()", "Frozen -> Mutable", "Valid Dict", "PASS" if hasattr(mutable, 'items') and dict(mutable) == input_data else "FAIL")

    # Stimulus D: Bulk merge_all logic
    # Border: merging list with None and empty DBs
    db_x = FrozenAnalogyDb({"X": "X"})
    bulk = FrozenAnalogyDb.merge_all([db_x, None, FrozenAnalogyDb({})])
    print_row("Bulk merge_all", "[db, None, {}]", "Identity db", "PASS" if bulk is db_x else "FAIL")

if "flyweight" in sys.argv:
    print("\n--- INVARIANT: REFERENCE IDENTITY (FLYWEIGHT) ---")
    print_header()
    
    # Stimulus A: Different construction paths
    a = FrozenAnalogyDb({"A": "1"})
    b = FrozenAnalogyDb({"B": "2"})
    path1 = a.merge(b)
    path2 = FrozenAnalogyDb({"B": "2", "A": "1"})
    
    print_row("Order Independence", "Merge(A,B) vs Init(B,A)", "Identical", "PASS" if path1 is path2 else "FAIL")
    
    # Stimulus B: Subset reduction
    path3 = path1.merge(a)
    print_row("Subset Merging", "MergedSet.merge(Subset)", "Identical", "PASS" if path3 is path1 else "FAIL")
    
    # Stimulus C: Empty Set Identity
    print_row("Null Singleton", "Init({}) vs Init()", "Identical", "PASS" if FrozenAnalogyDb({}) is FrozenAnalogyDb() else "FAIL")

if "consistency" in sys.argv:
    print("\n--- INVARIANT: LOGICAL CONSISTENCY (1-to-1 MAPPING) ---")
    print_header()
    
    base = FrozenAnalogyDb({"S1": "N1"})
    
    # Stimulus A: 1-to-Many (Subject Conflict)
    other1 = FrozenAnalogyDb({"S1": "N2"})
    res1 = base.is_all_consistent(other1) 
    print_row("Subject Conflict", "{S1:N1} vs {S1:N2}", "False", "PASS" if not res1 else "FAIL")
    
    # Stimulus B: Many-to-1 (Nominal Conflict)
    other2 = FrozenAnalogyDb({"S2": "N1"})
    res2 = base.is_all_consistent(other2)
    print_row("Nominal Conflict", "{S1:N1} vs {S2:N1}", "False", "PASS" if not res2 else "FAIL")
    
    # Stimulus C: Disjoint sets
    other3 = FrozenAnalogyDb({"S2": "N2"})
    res3 = base.is_all_consistent(other3)
    print_row("Disjoint Set", "{S1:N1} vs {S2:N2}", "True", "FAIL" if not res3 else "PASS")

if "immutability" in sys.argv:
    print("\n--- INVARIANT: IMMUTABILITY & SIDE-EFFECTS ---")
    print_header()
    
    base = FrozenAnalogyDb({"X": "100"})
    old_id = id(base)
    
    # Stimulus A: Attempting to modify via merge
    _ = base.merge(FrozenAnalogyDb({"Y": "200"}))
    print_row("Merge Side-Effect", "id(base) post-merge", "Unchanged", "PASS" if id(base) == old_id else "FAIL")
    
    # Stimulus B: Attempting to overwrite internal masks
    try:
        base.subj_mask = 0
        status = "FAIL"
    except (AttributeError, TypeError):
        status = "PASS"
    print_row("Attribute Guard", "Write access to slots", "Error", status)

if "hybrid_masks" in sys.argv:
    print("\n--- INVARIANT: HYBRID BITMASK/ID LOGIC ---")
    print_header()

    # 1. SETUP: Force Registry ID Inflation
    # We must register enough symbols to exceed the _MASK_LIMIT (256)
    limit = FrozenAnalogyDb()._registry._MASK_LIMIT
    print(f"| {'INFO':<25} | {'Inflating Registry > ' + str(limit):<35} | {'...':<12} | {'...':<8} |")
    
    # Generate 300 dummy symbols to push counter high
    for i in range(limit + 50):
        FrozenAnalogyDb()._registry.get_symbol_id(f"DUMMY_SUBJ_{i}")
        FrozenAnalogyDb()._registry.get_symbol_id(f"DUMMY_NOM_{i}")

    # 2. TEST CASE: High-ID Analogies (Should have Masks Disabled)
    high_s = f"DUMMY_SUBJ_{limit + 10}"
    high_n = f"DUMMY_NOM_{limit + 10}"
    
    db_high = FrozenAnalogyDb({high_s: high_n})
    
    # Expectation: Mask should be -1 (All 1s) to indicate disabled state
    masks_disabled = (db_high.subj_mask == -1) and (db_high.nom_mask == -1)
    print_row("Mask Disable Logic", f"ID > {limit}", "Masks = -1", "PASS" if masks_disabled else "FAIL")

    # 3. TEST CASE: Consistency with Disabled Masks (The Fallback Check)
    # Even with masks disabled (-1), the ID check must detect conflicts correctly.
    
    # Case A: Conflict (Same Subject -> Diff Nominal)
    conflict_db = FrozenAnalogyDb({high_s: "CONFLICTING_VAL"})
    is_cons = db_high.is_all_consistent(conflict_db)
    print_row("High-ID Conflict", "Same Subj, Diff Nom", "False", "PASS" if not is_cons else "FAIL")
    
    # Case B: Conflict (Diff Subject -> Same Nominal)
    # We need a new high-ID subject mapping to the SAME high_n nominal
    high_s_2 = f"DUMMY_SUBJ_{limit + 20}"
    conflict_db_2 = FrozenAnalogyDb({high_s_2: high_n})
    is_cons_2 = db_high.is_all_consistent(conflict_db_2)
    print_row("High-ID Rule 2", "Diff Subj, Same Nom", "False", "PASS" if not is_cons_2 else "FAIL")

    # Case C: Valid Merge (Disjoint High IDs)
    high_s_3 = f"DUMMY_SUBJ_{limit + 30}"
    high_n_3 = f"DUMMY_NOM_{limit + 30}"
    valid_db = FrozenAnalogyDb({high_s_3: high_n_3})
    
    is_cons_3 = db_high.is_all_consistent(valid_db)
    print_row("High-ID Valid", "Disjoint High IDs", "True", "PASS" if is_cons_3 else "FAIL")

    # 4. TEST CASE: Low-ID Analogies (Should STILL use Bitmasks)
    # We use new symbols that we know are small (if registry was fresh) 
    # OR we assume the registry is append-only.
    # Since we can't easily "reset" the registry in a test without breaking internals,
    # we verify that the High-ID behavior didn't break the class generally.
    # Ideally, we check that a NEW small instance (if possible) has masks, 
    # but since IDs grow monotonically, we can only test the High-ID behavior here reliably.
    pass
