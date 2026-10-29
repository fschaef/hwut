==============================================================================
hwut_fsm -- A STATE MACHINE AS THE TEST'S MODEL OF THE SYSTEM
==============================================================================

A system with states -- a protocol, a door, a game round, a connection --
may only move in certain ways. A test that compares output sees what the
system printed; it does not see that the system went from 'waiting' to
'idle' without the 'cancel' that alone allows it. 'hwut_fsm' holds the
MODEL: the states, the events that move between them, the states that must
never be reached. The test fires every event it observes into it; every
move the model does not allow is printed as one line, and so it lands in
the GOOD file, where the comparison judges it.

    from hwut.test_writing_support.python.hwut_fsm import Machine

    m = Machine.from_string("""
        initial:   idle
        forbidden: crashed
        final:     idle
        idle    ---( request )---> waiting ---( grant )---> busy
        busy    ---( release )---> idle
        :       ---( fault )--->   crashed
        waiting ---( cancel )---> idle
    """)
    m.fire("request", where=1)
    m.fire("release", where=2)   # BREACH line 2: 'release' in 'waiting' -- allowed: cancel, grant
    m.report()

Under hwut the launchers put hwut on PYTHONPATH, so the import works in a
test application and in a pype script's effect alike.

NOT PYPE'S MODES. A pype script's modes are the READER's state: what it
expects to parse next. A Machine is the SYSTEM's. A script parses with its
modes and fires what it parsed into a Machine; the demo
'demo/python/TEST/door.py' with 'door.pype' shows the pair.


1  THE MODEL AS TEXT
______________________________________________________________________________

'Machine.from_string(text)' reads one statement per line; '#' begins a
comment.

    A ---( ev )---> B             a transition: dashes, '( event )',
                                  dashes, '>'; blanks are free --
                                  '---(ev) -->' reads the same
    A ---( x )---> B ---( y )---> C
                                  a chain: B is left by y
    state A ---( x )---> state B  the word 'state' may stand before a name
    :   ---( z )---> D            ':' is the state that BEGAN the line
                                  above -- here A
    state E                       a state, before any transition names it
    initial: A                    where the machine starts; without it,
                                  the first state the text names
    forbidden: X, Y               states the system must never enter
    final: A, B                   states it may end in

A state is a word: letters, digits, '_', '.', '-'. An event is whatever
stands between the brackets, blanks trimmed.

'to_string()' writes the model back in the same text, one transition per
line, sorted -- what a book page or a GOOD file can show of it.

'Machine(transitions, initial, forbidden=(), final=(), DFA=True,
name="fsm", write=print, states=())' builds the same from (state, event,
state) triples, for a model a program computes.


2  WHAT IS REFUSED
______________________________________________________________________________

A model that cannot be meant raises 'FsmError' where it is read, with its
line:

    line 2: 'A' --(x)--> 'C', and line 1: --> 'B' -- a DFA moves one way
            per event, or 'DFA=False'
    line 1: an arrow names no event -- '---( event )--->'
    line 1: ':' stands for the state of the line above, and none stands there
    line 1: 'A B' names no state -- a state is a word ('A', 'state A')
    line 1: 'initial:' names one state
    forbidden state(s) 'Q': named nowhere else in the model
    the model names no state

Nothing is refused while events are fired: what the system does is what
the test reports.


3  FIRING EVENTS
______________________________________________________________________________

    fire(event, where=None)   True: the machine moved. False: the event
                              is not allowed where it stands -- written as
                              a BREACH line, and the machine STAYS, so one
                              surprise is one line, not a cascade -- or it
                              entered a forbidden state, which is ENTERED
                              (it is what the system did) and written.
                              'where' names the place: an int is 'line N',
                              a text stands as written ('t=3.5 s').

    BREACH line 2: 'release' in 'waiting' -- allowed: cancel, grant
    BREACH line 5: 'jump' in 'idle' -- an event the model never names
    BREACH line 3: 'crashed' entered by 'fault' -- a forbidden state
    BREACH t=y: 'y' in 'F' -- no event leaves it

    state                     the one state it stands in
    current()                 every state it stands in (a frozenset)
    in_state(s)               True if it stands in 's'
    can(event)                True if the event would move it now
    allowed()                 the events that would move it now, sorted
    trace()                   (where, state, event, state) per transition
    breach_n                  the breaches so far
    reset()                   back to the initial state; all forgotten

A DFA (the default) stands in one state. With 'DFA=False' an event may lead
to several states, and the machine stands in all of them: an event moves
every state that has it and drops the others; an event none of them has is
the breach. 'state' is then refused -- ask 'current()'.


4  THE MODEL ALONE
______________________________________________________________________________

Questions a tester asks before any event, or to steer the system:

    path_to(s, start=None)    the shortest event sequence into 's' --
                              what the system must be told to get there;
                              None where no path exists. 'start' is the
                              initial state where None, 'now' for where
                              the machine stands, or a state
    state_reachable(s, start=None)
                              True if a path exists
    unreachable()             states no path from the initial state reaches
    dead_ends()               states no event leaves that are neither final
                              nor forbidden -- where a system would hang
    forbidden_reachable()     forbidden states the model itself allows
    check()                   all three, one 'MODEL:' line each, the
                              forbidden ones with their way there:

    MODEL: 'limbo' cannot be reached
    MODEL: forbidden 'crashed' is reachable: request grant fault

A forbidden state the model can reach is not a fault of the model: it says
what the system must never do although it could. 'check()' names the way,
and a test that drives the system along it proves the guard.


5  THE REPORT
______________________________________________________________________________

'report()' at the end -- in a pype script, in the '<eof>' handler -- writes
what the events covered of the model, sorted, without time:

    protocol: 3 of 3 states visited, 3 of 5 transitions taken, 1 breach
      not taken  busy ---( fault )---> crashed
      taken      busy ---( release )---> idle
      taken      idle ---( request )---> waiting   x2
      not taken  waiting ---( cancel )---> idle
      taken      waiting ---( grant )---> busy   x2
      ended in   'busy'
    BREACH: ended in 'busy' -- final: idle

States are counted without the model's forbidden ones; a state never
entered is listed as 'never in'. What the law still holds at the end
(section 6) follows 'ended in' -- 'disallowed ...', 'forbidden ...',
'permitted ...' -- so a phase never lifted is seen. In a GOOD file the report pins the COVERAGE OF THE
MODEL: a path the system stops taking, or starts taking, is a difference
like any other. It returns the breaches, a non-final end counted.


6  THE LAW, CHANGING WHILE THE MACHINE RUNS
______________________________________________________________________________

A system has phases: in maintenance a door must not open; after a fault a
state is out of bounds. The model stays as written; MASKS over it change:

    disallow(event, state=None, where=None)
                              from now on 'event' is a breach -- in every
                              state, or in 'state' alone
    allow(event, state=None, where=None)
                              that mask lifted; one of another scope stays
    forbid(state, where=None) from now on entering 'state' is a breach
    permit(state, where=None) no longer forbidden -- a state of the model's
                              own 'forbidden:' too
    with m.disallowed(event, state=None, where=None): ...
    with m.forbidding(state, where=None): ...
                              for one block, lifted on leaving it, whatever
                              way the block is left
    forbidden                 the states forbidden now

A refused event says why: not 'allowed: ...', but since when.

    BREACH line 4: 'grant' in 'waiting' -- disallowed since line 2
    BREACH line 10: 'busy' entered by 'grant' -- forbidden since line 7

FORBIDDING THE PRESENT is a breach at once -- the test forbade the state the
system stands in:

    BREACH line 7: stands in 'busy' -- forbidden since line 7

'allowed()' and 'can()' answer under the masks; so do the questions of
section 4 -- 'path_to', 'state_reachable', 'unreachable', 'dead_ends',
'forbidden_reachable', 'check' -- each with 'masked=False' to ask the model
as written:

    m.disallow("grant")
    m.path_to("busy")                  # None: not in this phase
    m.path_to("busy", masked=False)    # ('request', 'grant')

A mask over an event or a state the model never names is refused
('FsmError'): it would guard nothing. 'reset()' returns to the model as
written -- masks lifted, the model's own forbidden states forbidden again.
In a pype script the masks follow the log:

    on: "maintenance on"  => { door.disallow("open", where=pype.line_n()) }
    on: "maintenance off" => { door.allow("open", where=pype.line_n()) }
