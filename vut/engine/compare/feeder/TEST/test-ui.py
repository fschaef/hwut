#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: Test the UI Feeder Protocol (feeder/ui.py).

DESCRIPTION:
    The UI feeder acts as an adapter between the comparison engine and a 
    visualizer. It serializes the comparison results into a stream of 
    DisplayInst objects.

    This test verifies:
    1. Serialization of all LineElement types (E_ToleranceId).
    2. Status codes (GOOD, TOLERATED, BAD/DIFFERS).
    3. Structural mismatches (Insertions/Deletions) in Line Sequences.
    4. Structural mismatches in Potpourri (Missing/Extra lines).
    5. Analogy provenance tracking.

________________________________________________________________________________
"""
import os
import sys
import io
from itertools import zip_longest

# Setup Path to find vut package
# Depth: vut/engine/compare/feeder/TEST/ -> ../../../../../
sys.path.insert(0, "../../../../../")

from config import HwutRunner
from vut.engine.compare.configuration        import Configuration
import vut.engine.compare.feeder.ui          as ui

# --- Helper Functions ---

def get_cell_str(c):
    """Formats a cell for side-by-side display."""
    if c is None: return ""
    
    # 1. Content
    content = c.subject if hasattr(c, 'subject') else c.nominal
    if content is None: content = "<None>"
    
    # 2. Status & Tolerance Type
    # We strip "OK_" and "BAD_" to keep it compact, but keep the core status
    status_full = c.relation_id.name
    if   "OK_"  in status_full: status = status_full.replace("OK_", "")
    elif "BAD_" in status_full: status = "BAD_" + status_full.replace("BAD_", "")
    else:                       status = status_full

    tol = c.tolerance_id.name[:3] # STR, NUM, ANA, SEP, EQU, VIS

    # 3. Provenance
    prov = ""
    if c.analogy_origin_line_number_pair:
        lnp = c.analogy_origin_line_number_pair
        prov = f" [Orig:S={lnp.line_n_in_subject},N={lnp.line_n_in_nominal}]"
    
    return f"({tol}) '{content}' [{status}]{prov}"

async def run_feeder(name, subject_str, nominal_str, config):
    print(f"--- TEST: {name} ---")
    
    s_stream = io.StringIO(subject_str)
    n_stream = io.StringIO(nominal_str)
    
    # Run the feeder
    async for inst in ui.feed(config, s_stream, n_stream):
        if isinstance(inst, ui.ProtocolHeader):
            print(f"Packet: HEADER (Signature: (({inst.signature})) )")
            
        elif isinstance(inst, ui.ConfigInst):
            print("Packet: CONFIG")
            
        elif isinstance(inst, ui.SectionBeginInst):
            print(f"Packet: SECTION '{inst.title}' Type: {inst.chunk_type}")
            
        elif isinstance(inst, ui.LinePairInst):
            ls = f"{inst.line_n_s:02d}" if inst.line_n_s != -1 else "--"
            ln = f"{inst.line_n_n:02d}" if inst.line_n_n != -1 else "--"
            print(f"Packet: ROW S:{ls} | N:{ln} (Cost: {inst.cost:.2f})")
            
            # Side-by-side display
            for sc, nc in zip_longest(inst.cells_s, inst.cells_n):
                s_str = get_cell_str(sc)
                n_str = get_cell_str(nc)
                # 65 chars width for Subject column to accommodate detailed status
                print(f"    {s_str:<65} | {n_str}")
            print()
                
        elif isinstance(inst, ui.EndOfStreamInst):
            print("Packet: EOS")
            
    print("----")
    with open(os.path.dirname(__file__) + "/../../../../adm/SIGNATURE_UI_PROTOCOL.txt") as fh:
        print(f"Signature in 'adm/SIGNATURE_UI_PROTOCOL.txt': (({fh.read().strip()}))")
    print("----")

# --- Choice Functions ---

async def test_types_tolerance():
    """
    Cover all E_ToleranceId types in both GOOD (Exact) and TOLERATED states.
    """
    cfg = Configuration()
    cfg.pattern_finder.numeric_tolerance_ratio = 0.1
    cfg.pattern_finder.whitespace_f = True
    cfg.pattern_finder.analogy_f = True
    cfg.pattern_finder.visible_nothing_pattern_list = ["<VN>"]
    cfg.pattern_finder.equivalent_pattern_list = ["alpha|beta"]

    # 1. STRING: Exact vs Diff
    s_str = "ExactString DiffString"
    n_str = "ExactString DiffTarget"

    # 2. NUMERIC: Exact vs Tolerated
    # 10.0 == 10.0 (GOOD)
    # 10.0 ~= 10.05 (TOLERATED, within 10%)
    s_num = "10.0 10.0"
    n_num = "10.0 10.05"

    # 3. SEPERATOR (Whitespace): Exact vs Tolerated
    # Single space vs Single space (GOOD)
    # Single space vs Triple space (TOLERATED - normalized)
    s_sep = "A B A B"
    n_sep = "A B A   B"

    # 4. EQUIVALENCE PATTERN: Exact vs Tolerated
    # alpha == alpha (GOOD)
    # alpha ~= beta  (TOLERATED - via regex)
    s_equ = "alpha alpha"
    n_equ = "alpha beta"

    # 5. VISIBLE NOTHING
    # <VN> (GOOD / IGNORED)
    s_vis = "<VN>"
    n_vis = "<VN>"

    # 6. ANALOGY
    # ((A)) == ((A)) (GOOD - Identical text)
    # ((A)) ~= ((1)) (TOLERATED - Text differs, but analogy valid)
    s_ana = "((Same)) ((Diff))"
    n_ana = "((Same)) ((1))"

    # Assemble lines
    s = f"{s_str}\n{s_num}\n{s_sep}\n{s_equ}\n{s_vis}\n{s_ana}"
    n = f"{n_str}\n{n_num}\n{n_sep}\n{n_equ}\n{n_vis}\n{n_ana}"

    await run_feeder("All Types (GOOD vs TOLERATED)", s, n, cfg)

async def test_structural_mismatch():
    """
    Cover insertion and deletion of lines (Subject has line / Nominal has line).
    """
    cfg = Configuration()
    
    # 1. Match
    # 2. Subject Extra (Delete)
    # 3. Nominal Extra (Insert)
    # 4. Match
    
    s = "Match 1\nExtra Subject Line\nMatch 2"
    n = "Match 1\nExtra Nominal Line\nMatch 2"
    
    await run_feeder("Structural Mismatch (LineSequence)", s, n, cfg)

async def test_potpourri_mismatch():
    """
    Cover Potpourri logic including orphan lines (no match found).
    """
    cfg = Configuration()
    
    # Subject has A, B, C
    # Nominal has A, D
    # Expect: A matches A. B, C are orphans (BAD_SUBJECT_HAS). D is orphan (BAD_NOMINAL_HAS).
    
    s = "##! potpourri\nCommon\nSubjectOnly_1\nSubjectOnly_2\n####"
    n = "##! potpourri\nNominalOnly_1\nCommon\n####"
    
    await run_feeder("Potpourri Mismatch", s, n, cfg)

# --- Main Execution ---

if __name__ == "__main__":
    choices = {
        "types":     test_types_tolerance,
        "structure": test_structural_mismatch,
        "potpourri": test_potpourri_mismatch,
    }
    
    HwutRunner(sys.argv, 
               "UI Feeder Protocol (Comprehensive)", 
               choices).run()
