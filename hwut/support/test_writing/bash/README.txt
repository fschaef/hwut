==============================================================================
test_writing_support/bash -- THE PYTHON TEST SUPPORT, IN BASH
==============================================================================

1  WHAT STANDS HERE
------------------------------------------------------------------------------
Every module a Python test author is given in '../python' is given to a bash
test author here, with the same behaviour and the same printed words:

    hwut_runner.sh            hwut_runner.py           the front end of a test
                                                       application: --hwut-info,
                                                       one choice, --interactive
    deterministic_random.sh   deterministic_random.py  a random stream that is
                                                       the same everywhere
    deterministic_timeline.sh deterministic_timeline.py races drawn as strings
    space_iterator.sh         space_iterator.py        every combination of a
                                                       parameter basis
    hwut_fsm.sh               hwut_fsm.py              a state machine as the
                                                       test's model
    hwut_hocon.sh             hwut_hocon.py            the HOCON subset, the
                                                       annotated tree
    hwut_vterm.sh             hwut_vterm.py            a terminal's screen, read
                                                       by a test (libvterm)
    hwut_pytext.sh            --                       text as Python prints it

A module is SOURCED; it sources what it needs itself, relative to its own
place. Bash 5.2 (namerefs, associative arrays, EPOCHREALTIME), awk (POSIX)
for floats -- and, for 'hwut_vterm.sh' alone, the C port behind a small
server ('hwut_vterm_server.c', section 3).

A bash test starts:

    #! /usr/bin/env bash
    # @hwut { choices = ["plain", "tricky"]  interactive = true }
    source "$(dirname "$0")/../hwut_runner.sh"     # the path to this directory
    plain()  { ...; }
    tricky() { ...; }
    declare -A choice_map=([plain]=plain [tricky]=tricky)
    hwut_runner_new runner "my title" choice_map
    hwut_runner_run runner "$@"

hwut runs it with the 'bash' interpreter of 'hwut-root.conf' ('.sh'); there
is nothing to build. The heads of the '.sh' files say how each module is
used; where a Python README explains a module ('../python/README-hwut_fsm.txt',
'-hwut_hocon', '-hwut_vterm', '-hwut_runner'), it explains the bash module
too.

THE IDIOMS OF BASH, the same across the modules:

    Python                          bash
    m = Machine.from_string(text)   fsm_machine_from_string m "$text" || echo "$FSM_ERROR"
    m.fire("grant", 3)              fsm_machine_fire m grant 3          # status: the bool
    m.state                         fsm_machine_state m; echo "$REPLY"
    s = DeterministicStream(66)     dr_stream_new s 66
    s.next_int(0, 9)                dr_stream_next_int s 0 9; echo "$REPLY"
    s.sample(pool, 4)               dr_stream_sample s pool 4; echo "${REPLY_LIST[@]}"
    Machine(..., DFA=False)         fsm_machine_from_string m "$text" dfa=0
    with Screen(4, 12) as s: ...    vterm_screen_new s 4 12; ...; vterm_close s
    class MyTrigger(Trigger)        functions MyTrigger_fire, MyTrigger_on_termination;
                                    dt_trigger_new a MyTrigger "1 1" A

    an object        a global associative array, named by the caller and
                     passed by name; a method is '<module>_<class>_<method>
                     <object> ...' -- 'vterm_<method>' for Screen and
                     Terminal alike -- ('local -n self=$1' inside); helper
                     arrays are '<object>_...'
    a result         in REPLY (a text, a number) or REPLY_LIST (a list, a
                     tuple) -- never on stdout: '$(...)' costs a process and
                     loses what the call changed
    a bool           the exit status: 'if fsm_machine_can m grant; then'
    an exception     status 1 and the text in '<MODULE>_ERROR' (FSM_ERROR;
                     VTERM_ERROR with VTERM_ERROR_KIND, Python's exception
                     name); HOCON never raised, its faults are a list
    None             an empty text, or status 1 where '' is a value
                     ('fsm_machine_path_to': status 1 is None, success with
                     an empty REPLY_LIST is '()')
    keywords         'key=value' words after the positional ones: 'dfa=0',
                     'name=protocol', 'masked=0', 'start=now', 'bound_s=0.5',
                     'react_s=0'
    a class          a name whose functions are its methods; the base calls
                     '<class>_fire' where declared ('declare -F'), abstract
                     where not
    a coroutine      a step function: 'dt_task_step' runs to the next yield;
                     'dt_task_gather' steps tasks in turn, asyncio's order
    'with'           'fsm_machine_disallowed m ev state where <command ...>':
                     the block is a command


2  THE SAME GOOD FILES -- THE PROOF THAT THE PORT IS ONE
------------------------------------------------------------------------------
'TEST/' holds one test per Python test, choice for choice, printing the same
text. Its GOOD files are not copies: every one is a '.link' to the Python
test's '.txt' (bookkeeper B-32):

    TEST/GOOD/test-hwut_fsm.sh--masks.link
        ../../../python/TEST/GOOD/test-hwut_fsm.py--masks.txt

So the bash module is held against what the Python module was accepted for,
byte for byte -- as the Perl and C modules are; 47 cases in six tests.
'hwut.good.link.show TEST/GOOD' lists them.

What Python prints of its own values the bash tests print by 'hwut_pytext':

    pytext_float_repr 0.1      '0.1'      pytext_bool 1               'True'
    pytext_str_repr "it's"     "\"it's\""  pytext_bytes_repr $'\e[A'   "b'\\x1b[A'"
    pytext_tuple_repr str a    "('a',)"   pytext_ljust "'ä'" 6        "'ä'   " (characters)

WHERE BASH DIFFERS FROM PYTHON, and how the port meets it:

    no float               a float is its TEXT; computed and written by awk
                           (POSIX; the platform's libm, as Python's):
                           'next_float', 'gauss' and every '%r' of a float.
                           'coin' compares without one: exactly, as rationals
    no object identity     a SelectionMarker remembers a candidate by its
                           VALUE -- two equal strings are one (as in Perl)
    bytes, not characters  the modules scan bytes (LC_ALL=C inside); where
                           Python counts characters -- a HOCON column, a
                           '%-6s' -- UTF-8 is counted ('pytext_char_n')
    no big integers        bash's arithmetic is 64 bit; a HOCON number in a
                           radix beyond 60 bits is converted in limbs, so it
                           prints as Python's int does
    no exceptions out of   the HOCON fuzz's bound: the parse looks at the clock
    a signal handler       (EPOCHREALTIME) in its loops and ends with status 2
                           -- Python's SIGALRM raises out of the parse
    a choice ends          by returning; in --interactive mode each choice runs
                           in a subshell, so an 'exit' in a choice ends that
                           choice alone; 'parallel=process' runs it in the
                           background and reports 'done' when it ends
    no C library calls     'hwut_vterm.sh' talks to 'hwut_vterm_server', the C
                           port's 'hwut_vterm.c' behind a line protocol, run
                           as a coprocess (section 3)
    a nameref is dynamic   an object's name must not be the name of a local
                           variable of the caller (bash: 'circular name
                           reference'); the modules' own locals carry a
                           module prefix ('_fsm_self', '_drs_pool', ...)


3  WHAT IT WANTS
------------------------------------------------------------------------------
Bash 5.2 and a POSIX awk -- nothing else, for every module but one.

'hwut_vterm.sh' wants libvterm AT RUN TIME (Debian: apt install libvterm0,
as for Python and C), a C compiler and make: on first use it runs 'make' in
this directory, which builds 'hwut_vterm_server' from 'hwut_vterm_server.c'
and '../c/hwut_vterm.c' (no header of libvterm is needed: the C module loads
it by 'dlopen' -- 'libvterm.so.0', or the file HWUT_LIBVTERM names). The
server is linked under a name of its own and renamed into place, so tests
that start at once never run a half-written one; it is built again where a
source is newer. The test needs no build declaration in its header.

The server runs as the shell's COPROCESS; one serves every screen and
terminal of the process and ends when the last is closed ('vterm_close').
'on_event' and 'on_change' are bash functions, called while the command
that caused them runs. An application is started with the shell's exported
environment, less LINES and COLUMNS, TERM 'xterm-256color'.

Where the library is missing, every choice of 'test-hwut_vterm.sh' but
'missing' says 'NOT PROBED' -- and differs from its GOOD, as the Python test
does. The two applications 'test-hwut_vterm.sh' runs on its
pseudo-terminal are the Python test's own (they are the system under
test), so 'python3' must stand on the PATH. 'vterm_detection_text' says
whether the library is there.


4  NOT HERE, ON PURPOSE
------------------------------------------------------------------------------
'script_runner.py'   a fixture for hwut's own tests of its faces, not given
                     to test authors.
'hwut_pype'          a face ('hwut.pype') and its scripts, not a library a
                     test sources: a bash test pipes through it as a Python
                     test does.
==============================================================================
