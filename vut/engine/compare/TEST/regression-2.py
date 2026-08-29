#! /usr/bin/env python3
"""
Regression Test Suite 2: Potpourri Engine Bugs.

Covers:
1. CSP Solver Crash (Mutable AnalogyDb passed to solver missing .merge())
2. Boolean Logic Bug (Failure flag not tripping on mismatch)
"""
import sys

# --- Path Setup ---
from config import HwutRunner

from vut.engine.compare.core.edit_operations.line_sequence import do as calc_seq_ops # noqa E402
from vut.engine.compare.region.potpourri.matching import pairing_analogy_lines, pairing_non_analogy_lines # noqa E402
from vut.engine.compare.region.potpourri.result import Result, PairedGraph # noqa E402
from vut.engine.compare.region.potpourri.potential_pair_db import PotentialPairDb # noqa E402
from vut.engine.compare.contract.analogy_db import AnalogyDb # noqa E402
from vut.engine.compare.contract.frozen_analogy_db import FrozenAnalogyDb # noqa E402
from vut.engine.compare.engine.line import Line # noqa E402
from vut.engine.compare.contract.enums import E_ToleranceId # noqa E402
from vut.engine.compare.reading.pattern_finder import PatternFinder # noqa E402
from vut.engine.compare.configuration import Configuration # noqa E402
from vut.engine.compare.core.edit_operations.edit import list_EditGOOD_line # noqa E402
# --- Formatting Helpers ---

def print_header(title):
    print(f"\n{'='*80}")
    print(f"SCENARIO: {title}")
    print(f"{'-'*80}")

def print_verdict(passed: bool, message: str):
    status = "PASS" if passed else "FAIL"
    print(f"VERDICT: {status}")
    print(f"  {message}")
    print(f"{'='*80}\n")

# --- Helper to create real input data ---
def create_numeric_conflict_db():
    # Configure pattern finder for numeric tolerance (10%)
    c = Configuration()
    pf_config = c.pattern_finder
    pf_config.numeric_tolerance_ratio = 0.1
    pf = PatternFinder(pf_config)

    # Subject: Two identical lines "1.0"
    s_lines = [Line(1, "1.0", pf), Line(2, "1.0", pf)]
    # Nominal: One line "1.0"
    n_lines = [Line(1, "1.0", pf)]

    # Generate the DB from raw lines.
    # This ensures 'AnalogyDb' objects are created correctly (as empty, but present).
    # Since they are Numeric matches, they impose NO analogy constraints, 
    # making them "Unconstrained" candidates.
    return PotentialPairDb.from_raw(s_lines, n_lines, abort_early_f=False)

# --- Test Cases ---

def test_csp_crash():
    print_header("CSP Solver Crash / Mutable State Check")
    print("OBJECTIVE: Verify 'pairing_analogy_lines' handles the AnalogyDb object correctly.")
    print("BUG:       Passing a mutable AnalogyDb causes AttributeError (.merge missing).")
    
    # Setup manually as this is a specific type-safety check
    pp_db = PotentialPairDb()
    # Subject 0 matches Nominal 0 with constraint A=1
    constraint = FrozenAnalogyDb().clone_and_add(("A", "1"))
    pp_db[0] = [(0, constraint)]

    # Setup Result object with MUTABLE Global AnalogyDb
    mutable_global_db = AnalogyDb() 
    
    state = Result(
        potential_pair_db     = pp_db,
        pair_db               = PairedGraph(),
        analogy_constraint_db = mutable_global_db, 
        required_pair_n       = 1,
        aborted_f             = False
    )

    try:
        _ = pairing_analogy_lines(state)
        print_verdict(True, "Function handled mutable DB (Frozen conversion applied).")
    except AttributeError as e:
        if "merge" in str(e):
            print_verdict(False, f"Crash confirmed: {e}")
        else:
            print_verdict(False, f"Unexpected Error: {e}")
    except Exception as e:
        print_verdict(False, f"Unexpected Crash: {e}")

def test_bool_logic():
    print_header("Boolean Logic (Abort Flag)")
    print("OBJECTIVE: Verify 'pairing_non_analogy_lines' sets aborted_f=True on partial match.")
    print("STIMULI:   Pigeonhole Conflict (2 Subjects, 1 Nominal) using Numeric Tolerance.")
    print("           Subject 1 ('1.0') -> Nominal 1 ('1.0')")
    print("           Subject 2 ('1.0') -> Nominal 1 ('1.0')")
    print("BUG:       'aborted_f &= success' logic fails if aborted_f starts as False.")

    # 1. Create a real DB with a conflict
    pp_db = create_numeric_conflict_db()
    
    # Verify setup validity
    print(f"SETUP: Potential Pair DB keys (Subject IDs): {list(pp_db.keys())}")
    # We expect 2 keys (subjects) pointing to the same nominal
    
    state = Result(
        potential_pair_db     = pp_db,
        pair_db               = PairedGraph(),
        analogy_constraint_db = None,
        required_pair_n       = 2,
        aborted_f             = False # Initially Healthy
    )

    print(f"INPUT state.aborted_f: {state.aborted_f}")
    
    # EXECUTE
    # 1. extract_unconstrained will find 2 subjects (1 and 2) competing for Nominal 1.
    # 2. solver_max_bpm will match one of them.
    # 3. is_complete will be False (1 match != 2 candidates).
    new_state = pairing_non_analogy_lines(state)

    print(f"OUTPUT state.aborted_f: {new_state.aborted_f}")
    print(f"OUTPUT Matches Found:   {len(new_state.pair_db)}")

    if new_state.aborted_f is True:
        print_verdict(True, "Flag set to True. Mismatch detected correctly.")
    else:
        print_verdict(False, "Flag remained False. Engine ignored partial match.")

def get_le_lists(s_text, n_text, visible_nothing="_"):
    c = Configuration()
    c.pattern_finder.visible_nothing_pattern_list = [visible_nothing]
    pf = PatternFinder(c.pattern_finder)
    
    s_l = Line(1, s_text, pf)
    n_l = Line(1, n_text, pf)
    
    # We pass the raw sequence (including Visible Nothing)
    return s_l.sequence, n_l.sequence

# --- Test Case ---

def test_visible_nothing_alignment():
    print(f"\n{'='*80}")
    print("SCENARIO: Visible Nothing Alignment")
    print("OBJECTIVE: Verify 'list_EditGOOD' correctly skips Subject Visible Nothing.")
    print("STIMULI:   Subject='_ A' (where _ is nothing), Nominal='A'.")
    print("BUG:       Engine uses GOOD_INSERT (Skip Nominal) instead of GOOD_DELETE (Skip Subject).")
    print("           Result is misalignment: '_ A' vs 'A' becomes 3 ops instead of 2.")
    print(f"{'-'*80}")

    s_seq, n_seq = get_le_lists("_ A", "A")
    s_seq = [ le for le in s_seq if le.tolerance_id != E_ToleranceId.SEPERATOR ]

    print(f"Subject: {s_seq}")
    print(f"Nominal: {n_seq}")

    # This function is used for optimized "Happy Path" matching
    # We rely on the internal lambdas similar to how 'list_EditGOOD_line' calls it
    # But since we import list_EditGOOD_line directly, we use that.
    
    ops = list_EditGOOD_line(s_seq, n_seq)
    
    op_names = [op.id.name for op in ops]
    print(f"RESPONSE: {op_names}")
    
    # Analysis
    # Correct Path: 
    # 1. Subject '_': Visible Nothing. Nominal 'A'. -> Skip Subject (GOOD_DELETE).
    # 2. Subject 'A': Content. Nominal 'A'. -> Match (GOOD).
    # Expected: ['GOOD_DELETE', 'GOOD']
    
    # Buggy Path:
    # 1. Subject '_'. Nominal 'A'. -> Skip Nominal (GOOD_INSERT). (Subject still '_')
    # 2. Subject '_'. Nominal End. -> Skip Subject (GOOD_DELETE). (Subject now 'A')
    # 3. Subject 'A'. Nominal End. -> Skip Subject (GOOD_DELETE).
    # Result: ['GOOD_INSERT', 'GOOD_DELETE', 'GOOD_DELETE']
    
    if "GOOD" in op_names and "GOOD_DELETE" in op_names and len(op_names) == 2:
        print("VERDICT: PASS")
        print("  Sequence aligned correctly.")
    else:
        print("VERDICT: FAIL")
        print("  Sequence misaligned. Likely pushed Subject content to the end.")


def get_lines(s_text_list, n_text_list):
    c = Configuration()
    # Default PatternFinder treats empty lines as separators
    pf = PatternFinder(c.pattern_finder)
    
    s_lines = [Line(i+1, txt, pf) for i, txt in enumerate(s_text_list)]
    n_lines = [Line(i+1, txt, pf) for i, txt in enumerate(n_text_list)]
    
    return s_lines, n_lines

def analyze_merge(s_list, n_list, label):
    def print_header(title):
        print(f"\n{'='*80}")
        print(f"SCENARIO: {title}")
        print(f"{'-'*80}")

    def print_verdict(passed: bool, message: str):
        status = "PASS" if passed else "FAIL"
        print(f"VERDICT: {status}")
        print(f"  {message}")
        print(f"{'='*80}\n")

    print(f"CASE: {label}")
    print(f"  Subject: {s_list}")
    print(f"  Nominal: {n_list}")
    
    s_lines, n_lines = get_lines(s_list, n_list)
    result = calc_seq_ops(s_lines, n_lines)
    ops = [op.id.name for op in result.edit_list]
    
    print(f"  Ops:     {ops}")
    
    # We accept SUBSTITUTE or SUBSTITUTE_TYPE
    # We REJECT split operations like ['GOOD_DELETE', 'INSERT']
    
    if len(ops) == 1 and "SUBSTITUTE" in ops[0]:
        print("  -> OK (Merged)")
        return True
    else:
        print("  -> FAIL (Not Merged)")
        return False

# --- Test Case ---

def test_edit_merging():
    print_header("Line Sequence Edit Merging")
    print("OBJECTIVE: Verify that Separator/Content mismatches merge into SUBSTITUTE.")
    print("BUG:       Adaptor missing _pair_db entries for (GOOD_DELETE, INSERT) etc.")
    
    all_passed = True
    
    # Case 1: Subject=Separator(""), Nominal=Content("A")
    # Generates: GOOD_DELETE (S) + INSERT (N)
    if not analyze_merge([""], ["ContentA"], "Separator vs Content"):
        all_passed = False
        
    print("-" * 40)
        
    # Case 2: Subject=Content("A"), Nominal=Separator("")
    # Generates: GOOD_INSERT (N) + DELETE (S)
    if not analyze_merge(["ContentA"], [""], "Content vs Separator"):
        all_passed = False

    # Note: Inverse pairs (INSERT+GOOD_DELETE) are structurally impossible 
    # due to the loop priority in reinsert_separators.

    if all_passed:
        print_verdict(True, "All combinations merged correctly.")
    else:
        print_verdict(False, "Some combinations failed to merge.")


if __name__ == "__main__":
    choices = {
        "csp":             test_csp_crash,
        "bool":            test_bool_logic,
        "visible-nothing": test_visible_nothing_alignment,
        "edit-merge":      test_edit_merging
    }
    
    runner = HwutRunner(
        argv=sys.argv,
        title="VUT Potpourri Regression Suite",
        choice_map=choices,
        happy=[r"VERDICT: PASS"]
    )
    runner.run()
