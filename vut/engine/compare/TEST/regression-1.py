#! /usr/bin/env python3
"""
Regression Test Suite: A* Search Bugs in VUT Edit Operations.

This script validates fixes for:
1. State Pruning Bug (Subject Modification)
2. State Pruning Bug (Analogy Constraints)
3. Transposition Amnesia Bug

It uses HwutRunner for execution control.
"""
import sys

# --- Path Setup ---
from config import HwutRunner # noqa E401

from vut.engine.compare.engine.association.edit_operations.line import do as calc_edit_ops
from vut.engine.compare.engine.line import Line
from vut.engine.compare.engine.enums import E_ToleranceId
from vut.engine.compare.input.pattern_finder import PatternFinder
from vut.engine.compare.configuration import Configuration

# --- Formatting Helpers ---

def print_header(title):
    print(f"\n{'='*80}")
    print(f"SCENARIO: {title}")
    print(f"{'-'*80}")

def print_stimuli(s_text, n_text, s_seq, n_seq):
    print("STIMULI:")
    print(f"  Subject Text: '{s_text}'")
    print(f"  Nominal Text: '{n_text}'")
    print(f"  Subject Seq:  {s_seq}")
    print(f"  Nominal Seq:  {n_seq}")
    print(f"{'-'*80}")

def print_response(result):
    ops = [op.id.name for op in result.edit_list]
    print("RESPONSE:")
    print(f"  Operations: {ops}")
    print(f"  Cost:       {result.cost:.6f}")
    # Indent analogy DB output
    db_str = str(result.analogy_db).replace('\n', '\n              ')
    print(f"  Analogy DB: {db_str}")
    print(f"{'-'*80}")

def print_verdict(passed: bool, message: str):
    status = "PASS" if passed else "FAIL"
    print(f"VERDICT: {status}")
    print(f"  {message}")
    print(f"{'='*80}\n")

# --- Execution Engine ---

def run_engine(s_text, n_text, visible_nothing=None):
    # 1. Configuration
    c = Configuration()
    pf_config = c.pattern_finder
    pf_config.analogy_f = True
    pf_config.numeric_tolerance_ratio = 0.1
    if visible_nothing:
        pf_config.visible_nothing_pattern_list = visible_nothing
    
    pf = PatternFinder(pf_config)
    
    # 2. Input Processing
    line_s = Line(1, s_text, pf)
    line_n = Line(1, n_text, pf)
    
    # Strip separators as the engine expects pure content sequences
    seq_s = tuple(x for x in line_s.sequence if x.tolerance_id != E_ToleranceId.SEPERATOR)
    seq_n = tuple(x for x in line_n.sequence if x.tolerance_id != E_ToleranceId.SEPERATOR)
    
    # 3. Print Stimuli
    print_stimuli(s_text, n_text, seq_s, seq_n)
    
    # 4. Calculation
    return calc_edit_ops(seq_s, seq_n)

# --- Test Cases ---

def test_pruning_transpose():
    print_header("State Pruning (Subject Modification)")
    print("OBJECTIVE: Verify A* distinguishes states where the subject tail has changed.")
    print("BUG:       Greedy Transpose(X<->A) reaches index (2,2) cheaply but mangles the tail.")
    print("           Optimal Subst(X->A) reaches (2,2) with higher cost but perfect tail.")
    print("           If state=(si,ni), Optimal is pruned. If state=(si,ni,subj_mod), it survives.")
    
    result = run_engine("X Z A", "A Z A")
    print_response(result)
    
    ops = [op.id.name for op in result.edit_list]
    
    if "TRANSPOSE" in ops:
        print_verdict(False, "Engine selected TRANSPOSE. Pruning logic likely ignored subject modification.")
    elif result.cost > 0.4:
         print_verdict(False, f"Cost {result.cost} is too high. Optimal path was pruned.")
    else:
        print_verdict(True, "Engine avoided the local trap and found the global optimal (SUBSTITUTE).")

def test_pruning_analogy():
    print_header("State Pruning (Analogy Constraints)")
    print("OBJECTIVE: Verify A* distinguishes states with different analogy constraints.")
    print("BUG:       Greedy Delete(_) reaches index (2,2) cheaply with constraint {A:1}.")
    print("           Optimal Insert(1) reaches (2,2) with constraint {A:2}.")
    print("           If state does not include AnalogyDB, Optimal is pruned.")
    
    # '_' is defined as Visible Nothing
    result = run_engine("_ ((A)) ((A))", "1 ((2)) ((2))", visible_nothing=["_"])
    print_response(result)
    
    ops = [op.id.name for op in result.edit_list]
    db_str = str(result.analogy_db)
    
    if '"((A))"="((2))"' in db_str:
        print_verdict(True, "Optimal analogy A=2 was found. State pruning respected constraints.")
    else:
        print_verdict(False, "Analogy A=2 NOT found. Valid path was pruned by conflicting A=1 path.")

def test_amnesia():
    print_header("Transposition Amnesia")
    print("OBJECTIVE: Verify Transpose operation records the implied analogy.")
    print("SCENARIO:  Transpose ((A)) to match ((1)). This implies A=1.")
    print("           Later, ((A)) matches ((2)). This implies A=2.")
    print("BUG:       If A=1 is not recorded during transpose, engine accepts A=2 (No Conflict).")
    print("           This makes the invalid Transpose path look cheap.")
    
    result = run_engine("X ((A)) ((A))", "((1)) Y ((2))")
    print_response(result)
    
    ops = [op.id.name for op in result.edit_list]
    db_str = str(result.analogy_db)
    
    if "TRANSPOSE" in ops:
        # If it picked Transpose, it MUST have recorded A=1.
        if '"((A))"="((1))"' not in db_str:
            print_verdict(False, "Engine Transposed A->1 but FAILED to record A=1 in DB (Amnesia).")
        elif '"((A))"="((2))"' in db_str:
             print_verdict(False, "Engine recorded A=1 but also accepted conflicting A=2.")
        else:
             # It is theoretically possible (though unlikely given costs) to pick Transpose if A=2 was rejected.
             print_verdict(True, "Engine Transposed and recorded A=1.")
    else:
        print_verdict(True, "Engine correctly avoided the Transpose path (due to Analogy Conflict).")

if __name__ == "__main__":
    choices = {
        "pruning_trans":   test_pruning_transpose,
        "pruning_analogy": test_pruning_analogy,
        "amnesia":         test_amnesia,
    }
    
    runner = HwutRunner(
        argv=sys.argv,
        title="VUT Edit Operations Debugger",
        choice_map=choices,
    )
    runner.run()
