#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: Orthogonal Space Sampling (Consistency Check).

This test renders the behavior of the two internal engines:
  1. 'is_equivalent' (The Judge): Fast, boolean result.
  2. 'associate'     (The Lawyer): Detailed, visual result.

It traverses the critical intersections of the problem space (Structure, 
Token Logic, Complexity). The output documents the input scenario and 
verifies if Judge and Lawyer agree.
________________________________________________________________________________
"""
import sys
import io

sys.path.insert(0, "../" * 4)

# 1. Setup Path to find 'vut' package using the provided runner
from vut.language_support.python.hwut_runner import HwutRunner # noqa e402

from vut.engine.compare.configuration import Configuration # noqa e402
import vut.engine.compare.main        as main # noqa e402

# --- Configuration Factory ---
def get_config():
    c = Configuration()
    pf = c.pattern_finder
    pf.analogy_f = True
    pf.numeric_tolerance_ratio = 0.1  # 10% Tolerance
    pf.equivalent_pattern_list = [r"happy|glad"] 
    return c

CONFIG = get_config()

# --- The Verification Core ---
async def verify(name, subject, nominal, expected_verdict):
    """
    Prints the scenario, runs both engines, and prints their verdicts.
    This makes the internal logic visible in the output log.
    """
    print(f"\nSCENARIO: {name}")
    print("-" * 60)
    
    # Visualizing Input (Side-by-Side for "The Ruler Effect")
    s_lines = subject.strip().splitlines()
    n_lines = nominal.strip().splitlines()
    print(f"{'SUBJECT':<30} | {'NOMINAL':<30}")
    print("-" * 60)
    for s, n in zip(s_lines, n_lines):
        print(f"{s.strip():<30} | {n.strip():<30}")
    # Handle length mismatch in display
    if len(s_lines) != len(n_lines):
        print(f"... (Lines count mismatch: {len(s_lines)} vs {len(n_lines)})")
    print("-" * 60)
    
    # 1. Equivalence Check (The Judge)
    
    judge_bool = await main.is_equivalent(CONFIG, 
                                          io.StringIO(subject), 
                                          io.StringIO(nominal))
    
    # 2. Association Check (The Lawyer)
    lawyer_bool = True
    bad_relations = set()
    async for chunk in main.associate(CONFIG, 
                                      io.StringIO(subject), 
                                      io.StringIO(nominal)):
        for lp in chunk:
            if lp.cost > 0:
                lawyer_bool = False
            
            for c in lp.subject_list() + lp.nominal_list():
                if "BAD_" in c.relation_id.name:
                    lawyer_bool = False
                    bad_relations.add(c.relation_id.name)
    
    # 3. Report Results
    print(f"Judge (is_equivalent): {judge_bool}")
    print(f"Lawyer (associate):    {lawyer_bool}")
    
    if not lawyer_bool and bad_relations:
        print(f"  -> Errors: {sorted(list(bad_relations))}")

    # 4. Verdicts
    consistency = "OK" if judge_bool == lawyer_bool else "FAIL (DIVERGENCE)"
    expectation = "MATCH" if judge_bool == expected_verdict else f"FAIL (Expected {expected_verdict})"
    
    print(f"Consistency:         {consistency}")
    print(f"Expectation:         {expectation}")

async def test_numeric():
    print("=== AXIS: TOKEN LOGIC (Numeric 10%) ===")
    
    # PROBE: [Lower_Bound, Nominal, Upper_Bound]
    # Nominal is 100.
    # 10% tolerance means range [90, 110] (depending on <= implementation)
    
    # Case 1: All Inside (90, 100, 110)
    sub_in = "Values: 90.0  100.0 110.0"
    nom_in = "Values: 100.0 100.0 100.0"
    await verify("Numeric: Boundary Inclusive", sub_in, nom_in, True)

    # Case 2: One Outside (89 is < 90, 111 is > 110)
    sub_out = "Values: 89.999999999999  100.0 110.00000000001"
    nom_out = "Values: 100.0 100.0 100.0"
    await verify("Numeric: Boundary Exclusive", sub_out, nom_out, False)

async def test_analogy():
    print("=== AXIS: TOKEN LOGIC (Analogy) ===")
    
    # Case 1: Simple Mapping (A->1, B->2)
    # Note: Analogies must appear on BOTH sides to be treated as such.
    sub_ok = "Map ((A)) to ((B))"
    nom_ok = "Map ((1)) to ((2))"
    await verify("Analogy: Basic Consistent", sub_ok, nom_ok, True)
    
    # Case 2: Inconsistency (A->1, then A->2)
    sub_bad = "Map ((A)) ... and ... ((A))"
    nom_bad = "Map ((1)) ... and ... ((2))"
    await verify("Analogy: Inconsistent", sub_bad, nom_bad, False)

async def test_potpourri():
    print("=== AXIS: STRUCTURE (Potpourri) ===")
    
    # Shuffled lines test
    sub = """||||
    Item ((A))
    Item ((B))
    ||||"""
    
    nom = """||||
    Item ((2))
    Item ((1))
    ||||"""
    
    # Should Pass: A maps to 2, B maps to 1 (or vice versa).
    # Since they are in a potpourri, the engine aligns them to find a consistent mapping.
    await verify("Potpourri: Shuffle + Analogy", sub, nom, True)

async def test_sudoku():
    print("=== INTERSECTION: STRUCTURE + AMBIGUITY (The Sudoku Trap) ===")
    # Subject: Two identical lines using ((A)).
    # Nominal: Two different lines using ((1)) and ((2)).
    # Constraint: ((A)) can map to ((1)) OR ((2)), but NOT both simultaneously.
    # Result: Pigeonhole violation.
    
    sub = """||||
    Val ((A))
    Val ((A))
    ||||"""
    
    nom = """||||
    Val ((1))
    Val ((2))
    ||||"""
    
    await verify("Sudoku: Pigeonhole (2 items into 1 slot)", sub, nom, False)

async def test_leakage():
    print("=== INTERSECTION: GLOBAL + LOCAL (Leakage) ===")

    async def test_leakage_case(direction, nom_val_2, expected_verdict):
        """
        Constructs a leakage scenario based on direction and consistency.
        
        Logic:
          1. Step 1 always defines: Subject=((A)) <-> Nominal=1
          2. Step 2 always uses:    Subject=((A)) <-> Nominal={nom_val_2}
        
        Args:
            direction: "line->pot" (Line defines, Potpourri uses)
                       "pot->line" (Potpourri defines, Line uses)
            nom_val_2: The value in the second step (e.g., "1" for match, "2" for conflict).
        """
        # 1. Define the raw segments
        def_s, def_n = "Define ((A))", "Define ((1))"
        use_s, use_n = "Use ((A))",    f"Use (({nom_val_2}))"
        
        # 2. Wrap segments based on direction
        def pot_wrapper(s): return f"||||\n{s}\n||||"
        
        if direction == "line->pot":
            # Line region defines state -> Potpourri must respect it
            part1_s, part1_n = def_s, def_n
            part2_s, part2_n = pot_wrapper(use_s), pot_wrapper(use_n)
            desc = "Leakage (Line -> Pot)"
        else:
            # Potpourri defines state -> Line region must respect it
            # (Note: HWUT processes sequentially, so Pot state flows to Line)
            part1_s, part1_n = pot_wrapper(def_s), pot_wrapper(def_n)
            part2_s, part2_n = use_s, use_n
            desc = "Leakage (Pot -> Line)"

        # 3. Assemble
        sub = f"{part1_s}\n{part2_s}"
        nom = f"{part1_n}\n{part2_n}"
        
        # 4. Detailed Test Name
        consistency = "Consistent" if nom_val_2 == "1" else "Conflicting"
        test_name = f"{desc}: {consistency} ({'1->' + nom_val_2})"

        await verify(test_name, sub, nom, expected_verdict)

    # --- The Orthogonal Sampling ---

    # Case 1: Line defines ((A))=1, Potpourri matches ((A))=1
    await test_leakage_case(direction="line->pot", nom_val_2="1", expected_verdict=True)

    # Case 2: Line defines ((A))=1, Potpourri expects ((A))=2 (Violation)
    await test_leakage_case(direction="line->pot", nom_val_2="2", expected_verdict=False)

    # Case 3: Potpourri defines ((A))=1, Line matches ((A))=1
    await test_leakage_case(direction="pot->line", nom_val_2="1", expected_verdict=True)

    # Case 4: Potpourri defines ((A))=1, Line expects ((A))=2 (Violation)
    await test_leakage_case(direction="pot->line", nom_val_2="2", expected_verdict=False)

async def test_all():
    await test_numeric()
    await test_analogy()
    await test_potpourri()
    await test_sudoku()
    await test_leakage()

# --- Main Execution ---
if __name__ == "__main__":
    choices = {
        "numeric":   test_numeric,
        "analogy":   test_analogy,
        "potpourri": test_potpourri,
        "sudoku":    test_sudoku,
        "leakage":   test_leakage,
    }

    HwutRunner(sys.argv, 
               "Orthogonal Space Consistency Check", 
               choices,
               happy="Consistency:         OK").run()
