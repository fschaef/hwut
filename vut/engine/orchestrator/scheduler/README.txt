==============================================================================
orchestrator/scheduler -- EXECUTING A TEST PLAN
==============================================================================

This component EXECUTES a test plan (orchestrator/plan): it obeys the plan's
constraints and hands every piece of work to a dispatcher. No process is
started here; running is test_run's, reached through the dispatcher.

    CTestPlan               CRunReport
        |                        ^
        v                        |
    +----------------------------------+       +--------------+
    | SCHEDULER  (scheduler.py)        |------>| I_Dispatcher |---> test_run
    |   asks CPlanState who MAY start, |       +--------------+
    |   picks, awaits the FIRST ending |
    +----------------------------------+


1  THE STATE MACHINE  (state.py)
______________________________________________________________________________

'CPlanState(plan)' holds one state per node and the readiness rules over
them. It runs nothing and knows no clock.

    PENDING RUNNING ENDED_GOOD ENDED_BAD UNSUPPORTED MISDEP

[MISDEP] nodes stand terminal at construction. 'ready()' answers every
PENDING node whose ordering sources stand terminal, whose supporters ended
GOOD, and no member of whose exclusion sets is RUNNING -- admission, never
choice. 'started(name)' refuses a node that is not ready. 'ended(name,
good_f)' answers the TEST nodes it left UNSUPPORTED: a BUILD or SESSION
node ending BAD fails what it supports. A TERMINAL state satisfies an
ordering link, whatever it says. 'failure_db()' names every node whose
state is ENDED_BAD, UNSUPPORTED or MISDEP; 'session_spent_f(name)' says a
SESSION has nothing left to serve.


2  THE SCHEDULER  (scheduler.py)
______________________________________________________________________________

'Scheduler(dispatcher, on_entry, on_exit, worker_max_n).run(plan)' is a
coroutine answering a 'CRunReport'.

    on_entry  runs before any dispatch; it failing stops the run
    on_exit   runs after all work has ended, in either case
    dispatch  readiness is asked anew before EVERY start; the first
              ready name starts; the loop awaits the FIRST ending,
              not a wave
    workers   'worker_max_n' bounds how many pieces of work stand at
              once: a number bounds this scheduler alone, a CBudget
              (budget.py) is shared with every scheduler holding it;
              'None' is no bound; a bound below one is refused. Frame
              scripts take a slot like any work.
    sessions  a SESSION node is closed once it launched and every TEST
              node it supports stands terminal; one that did not
              launch is never closed

'CBudget(limit)' (budget.py) is the count of work standing at once:
'take_f() -> bool' now or nothing, 'await take()' when free, 'give()',
'await changed()' resolves on the next give, '.peak' the most ever held.
A bound below one is refused.

'I_Dispatcher' is the seam to the world -- 'run_script(role, command)',
'run_build(node)', 'open_session(node)', 'close_session(node)',
'run_test(node)'. Every member is a coroutine and a failure is a value,
never an exception.

'CRunReport' carries the frame's outcome ('None' where the directory
states no script -- absence is data), the state of every node, and what
was dispatched in start order. 'good_f()' is True where the frame stood
and no node failed.
