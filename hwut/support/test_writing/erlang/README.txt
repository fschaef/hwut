==============================================================================
test_writing_support/erlang -- THE PYTHON TEST SUPPORT, IN ERLANG
==============================================================================

1  WHAT STANDS HERE
------------------------------------------------------------------------------
Every module a Python test author is given in '../python' is given to an
Erlang test author here, with the same behaviour and the same printed words:

    hwut_runner.erl            hwut_runner.py           the front end of a test
                                                        application: --hwut-info,
                                                        one choice, --interactive
    deterministic_random.erl   deterministic_random.py  a random stream that is
                                                        the same everywhere
    deterministic_timeline.erl deterministic_timeline.py races drawn as strings
    space_iterator.erl         space_iterator.py        every combination of a
                                                        parameter basis
    hwut_fsm.erl               hwut_fsm.py              a state machine as the
                                                        test's model
    hwut_hocon.erl (.hrl)      hwut_hocon.py            the HOCON subset, the
                                                        annotated tree
    hwut_vterm.erl             hwut_vterm.py            a terminal's screen, read
                                                        by a test (libvterm)
    pytext.erl (_unicode.hrl)  --                       text as Python prints it
    hwut_boot.hrl              --                       finds (and builds) the
                                                        modules for a test
    hwut_vterm_port.c          --                       the C port's libvterm
                                                        module as an Erlang port

Erlang/OTP 25 or later (maps:groups_from_list, float_to_list [short]); the
heads of the '.erl' files say how each module is used; where a Python README
explains a module ('../python/README-hwut_fsm.txt', '-hwut_hocon',
'-hwut_vterm', '-hwut_runner'), it explains the Erlang module too.

AN ERLANG TEST IS AN ESCRIPT -- hwut-root.conf runs '.erl' with 'escript':

    %% @hwut { choices = ["plain", "tricky"]  interactive = true }
    -mode(compile).
    -include("../hwut_boot.hrl").
    main(Argv) ->
        hwut_boot(),
        hwut_runner:run(Argv, "my title", #{"plain"  => fun plain/0,
                                            "tricky" => fun tricky/0}).
    plain()  -> io:format("...~n").
    tricky() -> ...

LINE 1 IS ESCRIPT'S: it skips it, so it is the '@hwut' header's comment
(a '-mode' there would be lost). '-mode(compile)' is needed: an interpreted
escript knows no 'fun plain/0'. 'hwut_boot()' puts '../ebin' on the code
path -- found from the script's own place, so a test runs from anywhere --
and runs 'make' in this directory first where a module is missing or older
than its source. Nothing is declared in the header and nothing is built in
'TEST/'.

THE IDIOMS OF ERLANG, the same across the modules:

    Python                          Erlang
    m = Machine.from_string(text)   {ok, M} = hwut_fsm:from_string(Text)
    m.fire("grant", 3)              {Moved, M1} = hwut_fsm:fire(<<"grant">>, 3, M)
    m.state                         {ok, State} = hwut_fsm:state(M)
    Machine(..., DFA=False)         hwut_fsm:from_string(Text, #{dfa => false})
    m.disallow("x", state="s")      {ok, M1} = hwut_fsm:disallow(<<"x">>, #{state => <<"s">>}, M)
    with m.disallowed(...): ...     {ok, M1} = hwut_fsm:disallowed(E, Options, fun(Mi) -> ... end, M)
    s = DeterministicStream(66)     S = deterministic_random:new(66)
    s.next_int(0, 9)                {N, S1} = deterministic_random:next_int(0, 9, S)
    class MyTrigger(Trigger)        deterministic_timeline:trigger(#{fire => F, on_termination => G},
                                                                   "1 1", "A", State)
    asyncio.gather(d.run(), c())    deterministic_timeline:run(D, [fun(Yield) -> ... end])
    with Screen(4, 12) as s: ...    {ok, S} = hwut_vterm:screen(4, 12), ..., hwut_vterm:close(S)
    t.on_change(callback)           hwut_vterm:on_change(T), receive {hwut_vterm, T, {change, N, L}} ...

    an object        a VALUE where it is data (the stream, the marker, the
                     machine, the tree): every call that changes it returns
                     the one that follows, the value LAST among the
                     arguments (OTP's 'rand:uniform_s', 'maps:put'); a
                     PROCESS where it acts (a trigger, a task, the
                     dispatcher); a PORT where it is outside the VM (a
                     screen, a terminal)
    a str            a UTF-8 binary; bytes a binary too, written
                     {bytes, B} where Python's repr must say b'...'
    None             the atom 'none'
    an exception     a value: {error, {Kind, Text}} -- fsm_error,
                     library_missing, index_error, key_error, timeout_error,
                     runtime_error (Python's name, Erlang's spelling) -- or
                     {error, not_implemented | cancelled} of a run; a wrong
                     argument crashes (badarg, function_clause): let it crash
    keywords         an options map: #{start => now, masked => false},
                     #{row_n => 2}; a keyword every call names is a
                     trailing argument instead ('terminal(8, 30, 0.3)')
    a coroutine      a task process handed TURNS by the dispatcher; 'Yield()'
                     is 'await asyncio.sleep(0)'
    a callback       a MESSAGE to the process that made the object
    sys.exit(n)      hwut_runner:exit(N)


2  THE SAME GOOD FILES -- THE PROOF THAT THE PORT IS ONE
------------------------------------------------------------------------------
'TEST/' holds one test per Python test, choice for choice, printing the same
text. Its GOOD files are not copies: every one is a '.link' to the Python
test's '.txt' (bookkeeper B-32):

    TEST/GOOD/test-hwut_fsm.erl--masks.link
        ../../../python/TEST/GOOD/test-hwut_fsm.py--masks.txt

So the Erlang module is held against what the Python module was accepted
for, byte for byte -- 47 cases in six tests, as every other port is.
'hwut.good.link.show TEST/GOOD' lists them.

What Python prints of its own values the Erlang tests print by 'pytext':

    pytext:repr(0.1)        <<"0.1">>       pytext:repr(true)     <<"True">>
    pytext:repr(1.0e-6)     <<"1e-06">>     pytext:repr(none)     <<"None">>
    pytext:repr(<<"it's">>) <<"\"it's\"">>  pytext:repr({<<"a">>}) <<"('a',)">>
    pytext:repr({bytes, <<27,"[A">>})       <<"b'\\x1b[A'">>
    pytext:ljust(<<"'ä'">>, 6)              <<"'ä'   ">> (characters, not bytes)

WHERE ERLANG DIFFERS FROM PYTHON, and how the port meets it:

    no mutable objects     data is a value threaded through the calls; what
                           acts is a process; see section 1
    no object identity     a SelectionMarker remembers a candidate by its
                           VALUE -- two equal ones are one; tag them
                           ({make_ref(), X}) to keep them apart
    no asyncio loop        the dispatcher process is the loop: it fires one
                           trigger, waits for it, hands each task one turn,
                           and only then goes on -- so the drawn interleaving
                           is the one that happens, whatever the scheduler
    no dup2                a choice is a process whose GROUP LEADER is its
                           output -- stdout, or the sink file; every process
                           it spawns inherits it. In --interactive mode the
                           VM's own stdout ('user') is the UP channel, the
                           runner's group leader and the logger point at the
                           stray sink. A choice writes to stderr only through
                           'standard_error' -- the VM's fd 2, not sinkable:
                           its exception report is written to the error sink
    no infinity            a HOCON decimal beyond the double ('1e999') is the
                           atom inf / '-inf' (Python's float('inf'))
    float's reader         wants digits on both sides of the point: HOCON's
                           '.5', '1e-6' are rewritten before reading
    no Unicode categories  'str_repr' escapes what Python's 'isprintable'
                           refuses by Python's own table ('pytext_unicode.hrl',
                           made by Python 3.13, Unicode 15.1)
    no C library calls     'hwut_vterm' runs 'hwut_vterm_port' (section 3)
    a choice and the       each choice of a sequential --interactive session
    environment            starts from the OS environment at session entry:
                           what a choice set by 'os:putenv' (COLUMNS,
                           HWUT_LIBVTERM) is set back before the next


3  WHAT IT WANTS
------------------------------------------------------------------------------
Erlang/OTP 25 or later ('erl', 'erlc', 'escript') and make -- for every
module but one.

'hwut_vterm' wants libvterm AT RUN TIME (Debian: apt install libvterm0, as
for Python and C) and a C compiler: Erlang reaches a C library only through
a NIF or a port, and a NIF would put libvterm and a blocking 'select' into
the VM's own process. So 'hwut_vterm_port.c' puts '../c/hwut_vterm.c',
UNCHANGED, behind Erlang's '{packet, 4}' framing -- every message a length
and fields, every field a length and its bytes, nothing encoded -- and
'hwut_vterm' starts one such program per screen or terminal ('screen',
'terminal'), ends it at 'close' or when the process that made it ends. On
first use 'hwut_vterm' runs 'make hwut_vterm_port' here (again where a
source is newer); the program is linked under a name of its own and renamed
into place, so tests that start at once never run a half-written one. No
header of libvterm is needed: the C module loads it by 'dlopen'
('libvterm.so.0', or the file HWUT_LIBVTERM names -- read when the screen
is made, so a test that sets it with 'os:putenv' is heard, as
'hwut_vterm._library = None' is in Python).

'on_event' and 'on_change' make the calling process the RECEIVER: every
raw event and every changed region arrives as a message
{hwut_vterm, T, {event, Map}} / {hwut_vterm, T, {change, Name, Lines}}, in
libvterm's order, in the mailbox before the call that caused it returns.
An application is started with the VM's environment as it stands, less
LINES and COLUMNS, TERM 'xterm-256color'.

Where the library is missing, every choice of 'test-hwut_vterm.erl' but
'missing' says 'NOT PROBED' -- and differs from its GOOD, as the Python test
does. The two applications 'test-hwut_vterm.erl' runs on its
pseudo-terminal are the Python test's own (they are the system under
test), so 'python3' must stand on the PATH. 'hwut_vterm:detection_text()'
says whether the library is there.

THE BUILD PRODUCTS stand here, never in 'TEST/': 'ebin/*.beam' and
'hwut_vterm_port' ('.gitignore'); 'make clean' removes them.


4  MEASURED
------------------------------------------------------------------------------
On this worktree (Erlang/OTP 25, erts 13.2.2.5; libvterm 0.3.3; Python
3.13.17 for the GOODs):

    47 cases         byte-identical ('cmp') to the Python GOODs in normal
                     mode; 'hwut.run --plain' in 'TEST/' 47 ok, 0 fail,
                     twice (interactive sessions), the first from a clean
                     directory, building 'ebin' and the port program (8.5 s;
                     5.7 s the second)
    gauss            byte-identical: Erlang's 'math' is the platform's libm,
                     as Python's is; the 1e-12 band of the GOOD unused
    float_repr       against Python's 'repr' on 200000 doubles (random bit
                     patterns, uniform in [-1e6, 1e6], integral, rounded and
                     scaled): no difference
    str_repr         against Python's 'repr' on all 1112064 code points but
                     the surrogates: no difference
    fuzz             3000 mutated headers from seed 4711: 619 clean, 2381
                     with faults, 0 hang, 0 exception; the choice 0.45 s,
                     the VM's start included
    a VM's start     'erl -noshell' 130 ms; an escript test 250..280 ms with
                     '-mode(compile)' (the test compiled at each start),
                     about 145 ms interpreted (no 'fun f/0' then, and every
                     line evaluated); loading the support modules 8 ms;
                     compiling them at each start instead 770 ms
    hwut_vterm       a screen made and closed: 2 ms (a port program each)


5  NOT HERE, ON PURPOSE
------------------------------------------------------------------------------
'script_runner.py'   a fixture for hwut's own tests of its faces, not given
                     to test authors.
'hwut_pype'          a face ('hwut.pype') and its scripts, not a library a
                     test includes: an Erlang test pipes through it as a
                     Python test does.
==============================================================================
