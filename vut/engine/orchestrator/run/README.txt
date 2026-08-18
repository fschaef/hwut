==============================================================================
orchestrator/run -- THE OUTER FACE AND THE REPORT STREAM
==============================================================================

This component is the orchestrator's OUTER FACE: one call takes a root and
a wish, and what comes back is a QUEUE of report events. Determination and
execution stand behind it; consumers -- a TUI, a web server, a customer
application -- read the queue and are unknown to everything behind it.

    orchestrate(root, wish)                 -> CTreePlan     (plan/tree.py)
    orchestrator(root, wish, dispatcher_factory,
                 worker_max_n=None, clock=None) -> asyncio.Queue

'orchestrator' explores the tree, determines the plans, and sets a
CTreeScheduler running as an asyncio task. Determination happens before the
first event: a refused wish raises at the call. The queue carries the
events of 'vocabulary.py'; one 'None' after 'tree-done' closes it.


1  THE VOCABULARY  (vocabulary.py)
______________________________________________________________________________

One flat JSON-able dict per event; every event carries 'format' (integer),
'kind' (plain string) and 'when' (ISO-8601 UTC). The kinds:

    tree-begun  dir-begun  frame  run-begun  run-ended
    fault  report  dir-done  tree-done

'run-ended' carries 'verdict' -- WHY it ended so: ok, test-failed,
build-failed, launch-failed, unsupported, misdep, open-ended -- and
'cause', the node whose breaking failed this one, where one did. A
'run-ended' may arrive without a 'run-begun': a node that never dispatched
ends without starting.

THE PROMISE: fields are only ever added; kinds are never removed; a
consumer ignores unknown kinds and fields and reads an unknown verdict as
not-ok. 'format_text()' prints the whole description. 'event(kind, when,
**fields)' builds one event and ASSERTS it against the table: a wrong
event is the emitter's defect, named at emission.


2  THE TREE SCHEDULER  (orchestrate.py)
______________________________________________________________________________

'CTreeScheduler(dispatcher_factory, worker_max_n, clock).run(tree_plan,
queue)' runs the directories SERIALLY, in walk order. Per directory: its
faults and reports, 'dir-begun', one 'run-ended  verdict=misdep' per
[MISDEP] node, then the directory's own Scheduler under its own frame and
its own dispatcher -- 'dispatcher_factory' takes the absolute directory
path and answers its I_Dispatcher. 'clock' answers the 'when' string and
is a parameter so that a test may state it. Event 'directory' fields are
RELATIVE to the root; no event carries a machine-chosen path.


3  THE SUMMARY  (summary.py)
______________________________________________________________________________

'fold(events) -> CRunSummary' -- a pure function over the stream; the
stream is the one carrier of the run's truth, and whoever wants the whole
at the end folds it. 'drain(queue)' reads to the closing 'None' and folds.
CRunSummary holds the verdicts per (directory, node), the causes, the
frames, faults, reports, per-directory goodness, and 'tree-done's own
'good_f'/'fail_n'.


4  THE RECEIVER  (receiver.py)
______________________________________________________________________________

'CRunReportReceiver' -- derive, override what you care about, hand
'receive' the queue. Every 'on_<kind>' is a concrete no-op with NAMED
parameters (the vocabulary's fields; optionals default to 'None'; newer
fields are dropped before the call). The catch-alls take '**fields':

    on_any(kind, **fields)      every event, raw, before its handler
    on_unknown(kind, **fields)  a kind the vocabulary does not carry
    on_misfit(kind, **fields)   a known kind whose structure does not
                                fit -- required field missing or badly
                                typed, or no dict at all


5  THE REAL DISPATCHER  (dispatcher.py, adapter.py)
______________________________________________________________________________

'TestRunDispatcher(directory, entry, record=None)' binds the seam onto
operations: one directory lock and one Store for its lifetime
(DirectoryBusy refused at the door), 'run_test_held' per choice,
'build_action' per BUILD node, a MultiExecute per session with the
choice's own ChoiceExecute plugged as the provision. 'record' is the
store knob (n-1). 'report_of(node)' answers the operation's own word
for a failure; the tree scheduler puts it on the wire as
'run-ended.report' (O-6). 'test_run_dispatcher_factory(record=)'
yields the factory 'orchestrator()' consumes: callable(directory,
entry) -> dispatcher.

'adapter.py' maps exploration's resolved CTestApp onto operations'
TestConfiguration: language -> interpreter argv, stated build ->
BuildConfig under the '<framework> <file>' action name, caps folded
onto procsitter's defaults, a stated pype -> the stdout canonicaliser.
Unmapped statements are refused by name, never guessed into defaults.

'TEST/test-endtoend.py' drives the whole over REAL processes -- bash
under procsitter, a real make, a real pype filter, two live sessions
over the stdin/stdout protocol -- and blesses the stream byte for
byte; the pype leg's green verdict is the proof the filter ran.
