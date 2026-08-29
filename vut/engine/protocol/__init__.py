"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE RUN REPORT PROTOCOL -- what a producer of the run's event
         stream and a consumer of it agree on.

    vocabulary.py   the kinds of event, and the fields of each
    receiver.py     the class a consumer derives from: the
                    queue-draining loop and the wire validation
    summary.py      'fold', the pure fold that answers what a run came
                    to

THE STREAM IS THE ONE CARRIER OF THE RUN'S TRUTH (O-4). Whoever wants
the whole at the end folds it; whoever wants the events derives from
the receiver. NEITHER IS THE ORCHESTRATOR'S PRIVATE BUSINESS -- both
were written to be consumed from outside, and their own purposes say
so: "any consumer may use it: our exit-status logic, a TUI, a customer
application".

WHY IT MOVED. Measured ('adm/import_graph.py --shared'), 'fold' is
read by 'engine/display', 'services/run' and 'services/stability' --
the lowest common ancestor of its readers is THE TREE ROOT. Held
inside 'orchestrator/run', it made the one SIDEWAYS arrow in the whole
tree: 'engine/display -> engine/orchestrator', a consumer reaching
into a producer for the shape they share. A TUI, an HTML renderer or a
customer's own consumer had to drag the orchestrator along to get
three leaf modules.

IT IMPORTS NOTHING OF THIS TREE, which is what makes it a protocol
rather than a part of one party: every party sits above it, so no
party can be made to wait on another. Declared 'SEALED' in
'adm/LAYERING.txt', and the seal is checked.

WHAT IS NOT HERE: the QUEUE, the scheduler, the dispatcher, the fold's
callers. A protocol is the SHAPE two parties agree on; the transport
and the machinery stay where they run.
______________________________________________________________________________
"""
from .receiver   import CRunReportReceiver
from .summary    import CRunSummary, fold
from .vocabulary import KIND_DB

__all__ = ["KIND_DB", "CRunReportReceiver", "CRunSummary", "fold"]
