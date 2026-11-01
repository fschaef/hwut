==============================================================================
support/test_writing/prolog -- THE PYTHON TEST SUPPORT, IN PROLOG
==============================================================================

1  WHAT STANDS HERE
------------------------------------------------------------------------------
Every module a Python test author is given in '../python' is given to a
Prolog test author here (SWI-Prolog 9), with the same behaviour and the same
printed words:

    hwut_runner.pro            hwut_runner.py           the front end of a test
                                                        application: --hwut-info,
                                                        one choice, --interactive
    deterministic_random.pro   deterministic_random.py  a random stream that is
                                                        the same everywhere
    deterministic_timeline.pro deterministic_timeline.py races drawn as strings
    space_iterator.pro         space_iterator.py        every combination of a
                                                        parameter basis
    hwut_fsm.pro               hwut_fsm.py              a state machine as the
                                                        test's model
    hwut_hocon.pro             hwut_hocon.py            the HOCON subset, the
                                                        annotated tree
    hwut_vterm.pro             hwut_vterm.py            a terminal's screen, read
                                                        by a test (libvterm)
    hwut_pytext.pro            --                       text as Python prints it

Each is a MODULE (':- module(...)'); a test loads the ones it uses relative
to its own file -- 'use_module('../hwut_fsm.pro')' -- and a module loads what
it needs relative to its own. The predicates carry their module's prefix
('fsm_', 'dr_', 'dt_', 'hocon_', 'vterm_', 'py_'), so that two modules
imported into one test never clash; the rest of the name is Python's
('fsm_path_to', 'dr_next_int', 'vterm_region_text').

A Prolog test starts:

    % @hwut {
    %     choices     = ["plain", "tricky"]
    %     interactive = true
    % }
    :- use_module('../hwut_runner.pro').
    :- initialization(main, main).
    plain  :- ... .
    tricky :- ... .
    main   :- hwut_runner_run("my title", [plain-plain, tricky-tricky], []).

hwut runs it with the 'swipl' interpreter of 'hwut-root.conf' ('.pro'):
'swipl test-x.pro <choice>'; under 'initialization(main, main)' the flag
'argv' holds what follows the file. There is nothing to build -- but for
'hwut_vterm' (section 3). The heads of the modules say how each is used;
where a Python README explains a module ('../python/README-hwut_fsm.txt',
'-hwut_hocon', '-hwut_vterm', '-hwut_runner'), it explains the Prolog module
too.

THE IDIOMS OF PROLOG, the same across the modules:

    Python                          Prolog
    m = Machine.from_string(text)   fsm_from_string(Text, M)
    m.fire("grant", where=3)        fsm_fire(M, grant, [where(3)])     % succeeds: moved
    m.path_to("busy")  # or None    fsm_path_to(M, busy, Path)         % fails: None
    s = DeterministicStream(66)     dr_stream_new(66, S0)
    a, b = s.next_int(0, 9), ...    dr_next_int(0, 9, A, S0, S1), dr_next_int(0, 9, B, S1, S2)
                                    -- or in a DCG body: dr_next_int(0, 9, A), dr_next_int(0, 9, B)
    for p in space_iterator.do(b)   forall(space_point(B, P), ...)
    await asyncio.sleep(0)          dt_yield
    asyncio.run(d.run())            dt_run(dt_dispatcher_run(D))
    class MyTrigger(Trigger)        a behaviour: my(fire(T), Self) :- ... .
                                                 my(on_termination(E), Self) :- ... .
    with Screen(4, 12) as s: ...    setup_call_cleanup(vterm_screen_new(4, 12, S), ..., vterm_close(S))
    with m.disallowed("x"): ...     fsm_disallowed(M, x, [], Goal)

    a bool           SUCCESS or failure: 'fsm_fire', 'fsm_can', 'vterm_send'
                     -- 'py_bool(Goal, T)' prints it 'True'/'False'
    None             failure, where a value is asked ('fsm_path_to'); the
                     atom 'none' where None is a value (a HOCON null, a
                     default colour)
    keyword args     an option list: [where(3), masked(false), start(now)]
    an exception     error(Formal, _) whose message is Python's text:
                     fsm_error(Message), vterm_error(Kind, Message) -- Kind
                     Python's exception name -- not_implemented_error(''),
                     cancelled_error(''); HOCON never raised, its faults are
                     a list
    a dataclass      a term, field for field: position(Line, Column),
                     scalar_node(Value, Position), cell(Text, Width, ...)
    str / bytes      a string; bytes(Codes)
    a tuple          tuple(List) where printed ('py_repr'), else a list


2  THE SAME GOOD FILES -- THE PROOF THAT THE PORT IS ONE
------------------------------------------------------------------------------
'TEST/' holds one test per Python test, choice for choice, printing the same
text. Its GOOD files are not copies: every one is a '.link' to the Python
test's '.txt' (bookkeeper B-32):

    TEST/GOOD/test-hwut_fsm.pro--masks.link
        ../../../../python/TEST/GOOD/test-hwut_fsm.py--masks.txt

So the Prolog module is held against what the Python module was accepted
for, byte for byte -- as the other ports are; 47 cases in six tests.
'hwut.good.link.show TEST/GOOD' lists them.

What Python prints of its own values the Prolog tests print by 'hwut_pytext':

    py_repr(0.1, T)            "0.1"      py_bool(fsm_can(M, x), T)   "False"
    py_repr("it's", T)         "\"it's\""  py_repr(bytes(`\e[A`), T)   "b'\\x1b[A'"
    py_repr(tuple([a]), T)     "('a',)"   py_ljust("'ä'", 6, T)       "'ä'   "
    py_round(2.5, I)           2          (Python's round: half to even)

WHERE PROLOG DIFFERS FROM PYTHON, and how the port meets it:

    no mutable objects     a stream, a marker, a trigger, a task is a VALUE
                           -- the state after is a new term, threaded on;
                           where two parties must see one change (a
                           producer's item and its consumer, a run and the
                           trigger that stops it) one cell is changed in
                           place ('nb_setarg')
    no object identity     a SelectionMarker remembers a candidate by its
                           value -- two equal candidates are one (as in Perl)
    a machine's world      the FSM's model and what it saw are FACTS of the
                           module's database, keyed by the machine; 'fsm_free'
                           retracts them
    no coroutines          a task is a goal suspended at 'dt_yield' -- a
                           delimited continuation (reset/3, shift/1); stepped
                           in turn, in the order given -- asyncio's order
    no classes             a trigger's behaviour is a closure sent messages;
                           a message it has no clause for FAILS: 'fire' so is
                           abstract (NotImplementedError), 'on_termination'
                           silent
    text, not str          strings for texts; source and streams are UTF-8
                           ('encoding(utf8)'; the runner sets stdout and
                           stderr so, whatever the locale)
    a float's text         SWI writes the shortest text that reads back;
                           'py_float_repr' lays its digits out as Python does
    a choice ends          by succeeding; failing or raising is status 1, the
                           reason on stderr. In --interactive mode each choice
                           runs in a child process (fork/1), so a 'halt' in a
                           choice ends that choice alone
    no C library calls     'hwut_vterm.pro' reaches the C port's
                           'hwut_vterm.c' through SWI-Prolog's foreign
                           interface (section 3)


3  WHAT IT WANTS
------------------------------------------------------------------------------
SWI-Prolog 9 ('swipl'; Debian: apt install swi-prolog) -- its libraries
'unix' (fork, dup), 'process', 'time', 'strings' come with it -- nothing
else, for every module but one.

'hwut_vterm.pro' wants libvterm AT RUN TIME (Debian: apt install libvterm0,
as for Python and C), a C compiler and make, and SWI-Prolog's header
'SWI-Prolog.h' (installed with the 'swi-prolog' package, in the 'include'
directory of the installation -- 'swipl --dump-runtime-variables' names it).
When the module is loaded it runs 'make' in this directory, which builds
'hwut_vterm4pl.so' from 'hwut_vterm4pl.c' (the glue: foreign predicates) and
'../c/hwut_vterm.c' (no header of libvterm is needed: the C module loads it
by 'dlopen' -- 'libvterm.so.0', or the file HWUT_LIBVTERM names), then loads
it ('load_foreign_library'). One 'cc' call compiles and links, no object
file is written beside a source; the library is linked under a name of its
own and renamed into place, so tests that load at once never load a
half-written one; it is built again where a source is newer. The test needs
no build declaration in its header.

'on_event' and 'on_change' closures are called while the predicate that
caused them runs (the C side calls back into Prolog). An application is
started with the process's environment -- set by 'setenv/2' beforehand --
less LINES and COLUMNS, TERM 'xterm-256color'; 'vterm_run' takes no
environment of its own (the C port reads the process's).

Where the library is missing, every choice of 'test-hwut_vterm.pro' but
'missing' says 'NOT PROBED' -- and differs from its GOOD, as the Python test
does. The two applications 'test-hwut_vterm.pro' runs on its
pseudo-terminal are the Python test's own (they are the system under test,
copied verbatim in quasi-quotations), so 'python3' must stand on the PATH.
'vterm_detection_text(T)' says whether the library is there.


4  NOT HERE, ON PURPOSE
------------------------------------------------------------------------------
'script_runner.py'   a fixture for hwut's own tests of its faces, not given
                     to test authors.
'hwut.pype'          a face ('services/lib/pype') and its scripts, not a library a
                     test loads: a Prolog test pipes through it as a Python
                     test does.
==============================================================================
