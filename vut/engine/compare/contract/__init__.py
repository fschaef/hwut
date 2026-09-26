"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE CONTRACT of comparison -- the vocabulary in which the
         parties name the same things.

A NAME THAT THREE COMPONENTS REACH FOR IS NO PART OF WHICHEVER ONE
HAPPENS TO HOLD IT. Measured ('adm/import_graph.py --shared'):
'E_ToleranceId' is read by four sub-components of 'compare',
'E_Chunk' and 'E_Verdict' by three each -- and each of them lived
inside 'compare/engine', which is one of its own readers. A shared
name stored inside one party HOLDS A CYCLE SHUT, and four of this
component's cycles rested on exactly that.

WHAT BELONGS HERE: SHAPES, not machinery.

    an enum          -- pure naming; it has no behaviour at all, and
                        exists precisely so two parties may say the
                        same word
    a request shape  -- what one party asks of another
    an error kind    -- a failure is part of an interface

WHAT DOES NOT: anything whose move would move BEHAVIOUR. 'PatternFinder'
computes; 'Store' holds state; 'Provision' is a stage. Those are shared
because a real dependency exists, and the layering must express it
rather than hide it behind a shared package.

THE TEST: would moving it require moving behaviour? If yes, it is not
contract.

NOTHING HERE IMPORTS ANYTHING OF THIS TREE. That is the property that
makes a contract one -- every party sits above it, so no party can be
made to wait on another.
______________________________________________________________________________
"""
#  THE DOOR. Every name here is re-exported deliberately: '__all__'
#  says so, and says it to the reader before it says it to the tool.
from .analogy_db        import AnalogyDb
from .frozen_analogy_db import FrozenAnalogyDb
from .enums     import E_Chunk, E_ToleranceId, E_Verdict
from .semantics import (E_EditId, GOOD_EDIT_ID_SET, analogy_commitment,
                        commit_analogies,
                        element_cost_db, is_equivalent_verdict,
                        is_good_edit, is_insignificant_line,
                        is_plainly_equivalent_verdict, line_cost_db,
                        verdict_to_edit_id)


__all__ = [
                        "GOOD_EDIT_ID_SET",
                        "AnalogyDb",
                        "E_Chunk",
                        "E_EditId",
                        "E_ToleranceId",
                        "E_Verdict",
                        "FrozenAnalogyDb",
                        "analogy_commitment",
                        "commit_analogies",
                        "element_cost_db",
                        "is_equivalent_verdict",
                        "is_good_edit",
                        "is_insignificant_line",
                        "is_plainly_equivalent_verdict",
                        "line_cost_db",
                        "verdict_to_edit_id",
]
