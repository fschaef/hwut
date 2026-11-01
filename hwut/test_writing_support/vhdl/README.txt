==============================================================================
test_writing_support/vhdl -- THE PYTHON TEST SUPPORT, IN VHDL
==============================================================================

1  WHAT STANDS HERE
------------------------------------------------------------------------------
Every module a Python test author is given in '../python' is given to a VHDL
test author here, with the same behaviour and the same printed words -- as
VHDL-2008 packages and protected types:

    hwut_runner.vhd            hwut_runner.py           the front end of a
                                                        test: --hwut-info, one
                                                        choice, --interactive
    deterministic_random.vhd   deterministic_random.py  a random stream that
                                                        is the same everywhere
    deterministic_timeline.vhd deterministic_timeline.py races drawn as strings
    space_iterator.vhd         space_iterator.py        every combination of a
                                                        parameter basis
    hwut_fsm.vhd               hwut_fsm.py              a state machine as the
                                                        test's model
    hwut_hocon.vhd             hwut_hocon.py            the HOCON subset, the
                                                        annotated tree
    hwut_vterm.vhd             hwut_vterm.py            a terminal's screen,
                                                        read by a test (libvterm)
    hwut_pytext.vhd            --                       text as Python prints it
    hwut_vhpi.vhd, hwut_vhpi.c --                       the VHPIDIRECT glue
    hwut_launch.sh             --                       runs a test's design

WHAT VHDL DOES ITSELF (VHDL RATIONALE VH-1): the runner and its interactive
protocol (stdin by textio), the random stream, the space iterator, the
timeline and its tasks. WHAT IT CANNOT -- fork and file descriptors, libm's
cos, Python's repr of a float, str and bytes, the parsing of model text and
HOCON, libvterm and the pseudo-terminal -- it calls by VHPIDIRECT in
'hwut_vhpi.c', which wraps the C modules of '../c': one implementation, as
'../cpp' is (C++ CPP-1).

A VHDL test starts:

    -- @hwut {
    --     build   { framework = "make", executable = "%.exe" }
    --     choices = ["plain", "tricky"]
    --     interactive = true
    -- }
    use work.hwut_runner.all;
    entity test_x is
        generic (HWUT_ARGC : natural := 0; HWUT_ARGV1 : string := "");
    end entity;
    architecture test of test_x is
    begin
        main : process
            variable runner : HwutRunner;
        begin
            runner.init(HWUT_ARGC, HWUT_ARGV1, "my title");
            runner.add("plain");  runner.add("tricky");
            while runner.dispatch loop
                if    runner.choice = "plain"  then run_plain;
                elsif runner.choice = "tricky" then run_tricky;
                end if;
                runner.choice_done;
            end loop;
        end process;
    end architecture;

HOW IT RUNS: VHDL reads no command line, and GHDL's mcode backend writes no
executable. 'TEST/Makefile' builds, per test, a directory 'test-x.work' --
the design analysed by GHDL and 'libhwut_vhdl.so', the glue with the C
modules -- and 'test-x.exe', a launcher: hwut's 'test-x.exe <choice>' becomes
'ghdl -r test_x -gHWUT_ARGC=1 -gHWUT_ARGV1=<choice>' ('hwut_launch.sh'), the
library found along LD_LIBRARY_PATH. The build runs IN THE TEST DIRECTORY
(services E-210); no file is shared between two targets.

THE NAMES ARE PYTHON'S, IN VHDL'S PLACES:

    Python                          VHDL
    DeterministicStream(0x42)       variable s : DeterministicStream; s.init(16#42#);
    stream.select(pool)             item(pool, s.select_index(n))      ('select' is reserved)
    space_iterator.do(basis)        it.do((3, 2)); while it.next_point loop ... it.point ...
    class MyTrigger(Trigger)        a kind: d.add(timeline, name, MY_KIND), and the test's
                                    'fire'/'on_termination' as generics of
                                    'package timeline is new work.deterministic_timeline_run'
    await dispatcher.run()          timeline.run(d, turn, tasks)
    asyncio tasks, gather, cancel   processes taking turns: task_begin/_yield/_end,
                                    task_gather, tasks.cancel, task_await
    Machine.from_string(text)       variable m : Machine; m.from_string(text)
    m.report()                      m.print_report                     ('report' is reserved)
    parse(lines, file)              parse(lines, "f.hocon", document, faults)
    with Screen(24, 80) as s:       variable s : Screen; s.create(24, 80); ... s.close;
    terminal.on_change(f)           package t is new work.hwut_vterm_terminal
                                        generic map (on_event => ..., on_change => f);
    terminal.wait()                 t.wait_exit                        ('wait' is reserved)
    list[str]                       str_list: one string, every item ended by LF


2  THE SAME GOOD FILES -- THE PROOF THAT THE PORT IS ONE
------------------------------------------------------------------------------
'TEST/' holds one test per Python test, choice for choice, printing the same
text. Its GOOD files are not copies: every one is a '.link' to the Python
test's '.txt' (bookkeeper B-32):

    TEST/GOOD/test-hwut_fsm.vhd--masks.link
        ../../../python/TEST/GOOD/test-hwut_fsm.py--masks.txt

47 cases in six tests. 'hwut.good.link.show TEST/GOOD' lists them.

WHERE VHDL DIFFERS FROM PYTHON, and how the port meets it:

    no exceptions       a function Python lets raise returns false (or "");
                        the text is 'error' / 'error_message', the name
                        'error_kind' (Vterm); an abstract 'fire' sets
                        'd.raised' = "NotImplementedError" and the run ends
    no function values  a choice is chosen by name in the process
                        ('runner.choice'); a trigger's methods and a
                        terminal's callbacks are GENERIC SUBPROGRAMS
    no coroutines       a task is a PROCESS; 'turn', a signal resolved to the
                        newest serial, hands the turn on in asyncio's order --
                        one process runs at a time, whatever order the
                        simulator resumes a delta's processes in
    no 'with'           'disallow ... allow', 'forbid ... permit',
                        'create ... close'
    32-bit integers     MINSTD by Schrage's decomposition; a HOCON number is
                        kept as its text ('value', 'value_repr')
    no list of str in   a str_list (LF-ended items); where IDENTITY counts --
    a function          'select_unchosen' -- a line_vector: a candidate is
                        the line (access value) it is, Python's id()
    a callback from C   is queued by the glue and delivered by the Terminal
                        method that caused it, before it returns
    a choice ends       by 'choice_done', which ends the process; in
                        --interactive mode each choice runs in a child
                        process (fork in the glue)


3  WHAT IT WANTS
------------------------------------------------------------------------------
GHDL with VHDL-2008 (measured: 4.1.0, mcode backend, which loads the
VHPIDIRECT subprograms from a shared library), a C99 compiler to build
'libhwut_vhdl.so', make, POSIX. For 'hwut_vterm' alone libvterm AT RUN TIME
(Debian: apt install libvterm0), no header -- as for C. Where it is missing,
every choice of 'test-hwut_vterm.vhd' but 'missing' says 'NOT PROBED'. The
two applications it runs are the Python test's own, so 'python3' must stand
on the PATH. No other package is wanted.


4  NOT HERE, ON PURPOSE
------------------------------------------------------------------------------
Anything the C modules do: the FSM, the HOCON parser and libvterm are not
written again in VHDL. Python's 'Machine(...)' from a transition list (only
'from_string'), 'disallowed'/'forbidding' as blocks, and 'parallel' choices
in --interactive mode. 'script_runner.py' and 'hwut_pype', as for C.
==============================================================================
