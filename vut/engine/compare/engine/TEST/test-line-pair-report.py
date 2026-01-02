#! /usr/bin/env python
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
HWUT Unit Test for LinePair.subject_and_nominal_line_element_lists()
________________________________________________________________________________
"""
import sys
sys.path.insert(0, "../../../../../")

from vut.engine.compare.input.line_element                  import LineElementString
from vut.engine.compare.engine.line                             import Line
from vut.engine.compare.engine.association.edit_operations.edit import E_EditId, Edit
from vut.engine.compare.engine.association.line_pair            import LinePair

if "--hwut-info" in sys.argv:
    print("LinePair: subject_and_nominal_line_element_lists();")
    choices = ["transpose", "monkey", "visible-nothing", "accordion", "exhaustion", "circular"]
    print(f"CHOICES: {', '.join(choices)};")
    sys.exit()

# ------------------------------------------------------------------------------
# TEST SCENARIOS
# ------------------------------------------------------------------------------

def TEST_transpose():
    print("TEST: Standard Transpose")
    subject = FRAME_create_line(1, ["A", "B"])
    nominal = FRAME_create_line(1, ["B", "A"])
    edit_list = [
        Edit(E_EditId.TRANSPOSE, transpose_ai=1),
        Edit(E_EditId.TRANSPOSE, transpose_ai=0),
    ]
    FRAME_execute_and_print(subject, nominal, edit_list)

def TEST_visible_nothing():
    print("TEST: Visible Nothing (Placeholder Alignment)")
    subject = FRAME_create_line(1, ["Hello", "World"])
    nominal = FRAME_create_line(1, ["Hello", "[VN]", "World"]) 
    edit_list = [
        Edit(E_EditId.GOOD),
        Edit(E_EditId.GOOD_INSERT), 
        Edit(E_EditId.GOOD),
    ]
    FRAME_execute_and_print(subject, nominal, edit_list)

def TEST_accordion():
    print("TEST: Accordion (Large Displacement Gaps)")
    subject = FRAME_create_line(1, ["S1", "S2"])
    nominal = FRAME_create_line(1, ["N1", "N2"])
    edit_list = [
        Edit(E_EditId.DELETE), Edit(E_EditId.DELETE),
        Edit(E_EditId.INSERT), Edit(E_EditId.INSERT),
    ]
    FRAME_execute_and_print(subject, nominal, edit_list)

def TEST_exhaustion():
    print("TEST: Ghost Stream (Edit list exceeds sequences)")
    subject = FRAME_create_line(1, ["RealSubject"])
    nominal = FRAME_create_line(1, ["RealNominal"])
    edit_list = [
        Edit(E_EditId.GOOD),      
        Edit(E_EditId.SUBSTITUTE),
        Edit(E_EditId.DELETE),    
    ]
    FRAME_execute_and_print(subject, nominal, edit_list)

def TEST_circular():
    print("TEST: Circular Transpose (Jumping References)")
    subject = FRAME_create_line(1, ["A", "B", "C"])
    nominal = FRAME_create_line(1, ["C", "A", "B"])
    edit_list = [
        Edit(E_EditId.TRANSPOSE, transpose_ai=1),
        Edit(E_EditId.TRANSPOSE, transpose_ai=2),
        Edit(E_EditId.TRANSPOSE, transpose_ai=0),
    ]
    FRAME_execute_and_print(subject, nominal, edit_list)

def TEST_monkey_chaos():
    print("TEST: Monkey Chaos")
    subject = FRAME_create_line(10, ["S0", "S1"])
    nominal = FRAME_create_line(10, ["N0"])
    edit_list = [
        Edit(E_EditId.INSERT),    
        Edit(E_EditId.DELETE),    
        Edit(E_EditId.TRANSPOSE, transpose_ai=0),
        Edit(E_EditId.DELETE)     
    ]
    FRAME_execute_and_print(subject, nominal, edit_list)

# ------------------------------------------------------------------------------
# FRAMEWORK SUPPORT
# ------------------------------------------------------------------------------

def FRAME_create_line(line_n, texts):
    sequence = [LineElementString(t) for t in texts]
    return Line(line_n, sequence)

def FRAME_execute_and_print(subject, nominal, edit_list):
    lp = LinePair(subject, nominal, edit_list)
    
    print("INPUT SEQUENCES:")
    s_txt = [el._string for el in subject.sequence] if subject else []
    n_txt = [el._string for el in nominal.sequence] if nominal else []
    print(f"  Subject: {s_txt}")
    print(f"  Nominal: {n_txt}")
    
    print("EDIT LIST:")
    for i, e in enumerate(edit_list):
        aux = f" (aux:{e.transpose_ai})" if e.transpose_ai is not None else ""
        print(f"  [{i:02d}] {e.id.name}{aux}")
    print()

    s_cells, n_cells = lp.subject_list(), lp.nominal_list()
    FRAME_print_table(s_cells, n_cells)

def FRAME_print_table(subject_list, nominal_list):
    def get_brief(enum_member):
        # Strict handling: If None, it's a test failure
        if enum_member is None: return "ERR_NONE"
        return enum_member.name.replace("OK_", "").replace("BAD_", "")

    rows = []
    for i, (s_cell, n_cell) in enumerate(zip(subject_list, nominal_list)):
        # Relation ID and Tolerance ID must exist
        rows.append([
            f"S[{i:02d}]",
            get_brief(s_cell.relation_id),
            get_brief(s_cell.tolerance_id),
            f"'{s_cell.subject}'" if s_cell.subject is not None else "None",
            f"nom:{s_cell.nominal_ref_i}" if s_cell.nominal_ref_i is not None else "nom:-"
        ])
        rows.append([
            f"N[{i:02d}]",
            get_brief(n_cell.relation_id),
            get_brief(n_cell.tolerance_id),
            f"'{n_cell.nominal}'" if n_cell.nominal is not None else "None",
            f"sub:{n_cell.subject_ref_i}" if n_cell.subject_ref_i is not None else "sub:-"
        ])

    headers = ["SIDE", "RELATION", "TOL", "TEXT", "REF"]
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, val in enumerate(row):
            col_widths[i] = max(col_widths[i], len(str(val)))

    fmt = " | ".join([f"{{:<{w}}}" for w in col_widths])
    print("RESULT TABLE:")
    print(fmt.format(*headers))
    print("-+-".join(["-" * w for w in col_widths]))

    for i, row in enumerate(rows):
        print(fmt.format(*row))
        if i % 2 == 1:
            print("-+-".join(["-" * w for w in col_widths]))
    print("\n" + "="*80 + "\n")

if __name__ == "__main__":
    choice = sys.argv[1] if len(sys.argv) > 1 else ""
    test_map = {
        "transpose":       TEST_transpose,
        "monkey":          TEST_monkey_chaos,
        "visible-nothing": TEST_visible_nothing,
        "accordion":       TEST_accordion,
        "exhaustion":      TEST_exhaustion,
        "circular":        TEST_circular,
    }
    if choice in test_map:
        test_map[choice]()
