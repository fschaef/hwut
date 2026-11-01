==============================================================================
test_writing_support/verilog -- THE PYTHON TEST SUPPORT, IN SYSTEMVERILOG
==============================================================================

1  WHAT STANDS HERE
------------------------------------------------------------------------------
Every module a Python test author is given in '../python' is given to a
SystemVerilog test author here, as a PACKAGE of the same name, with the same
behaviour and the same printed words (SV RATIONALE SV-1):

    hwut_runner.sv            hwut_runner.py           the front end of a test
                                                       application: --hwut-info,
                                                       one choice, --interactive
    deterministic_random.sv   deterministic_random.py  a random stream that is
                                                       the same everywhere
    deterministic_timeline.sv deterministic_timeline.py races drawn as strings
    space_iterator.sv         space_iterator.py        every combination of a
                                                       parameter basis
    hwut_fsm.sv               hwut_fsm.py              a state machine as the
                                                       test's model
    hwut_hocon.sv             hwut_hocon.py            the HOCON subset, the
                                                       annotated tree
    hwut_vterm.sv             hwut_vterm.py            a terminal's screen, read
                                                       by a test (libvterm)
    hwut_pytext.sv            --                       text as Python prints it

NATIVE SYSTEMVERILOG where the language can: the runner's logic, the random
stream, the iterator, the timeline -- triggers are classes, a task is an SV
process. THROUGH DPI-C INTO THE C PORT ('../c') where it cannot: the command
line, fork and the file descriptors ('hwut_runner_dpi.c'), the FSM's and
HOCON's text parsing ('hwut_fsm_dpi.c', 'hwut_hocon_dpi.c' over
'../c/hwut_fsm.c', '../c/hwut_hocon.c'), libvterm and the pseudo-terminal
('hwut_vterm_dpi.c' over '../c/hwut_vterm.c'), a double's shortest text and
Python's str and bytes literals ('hwut_pytext_dpi.c' over
'../c/hwut_pytext.c'). The '*_dpi.c' files only convert; the C port does the
work, so there is one implementation of each, held by the same GOODs.

A SystemVerilog test starts:

    // @hwut {
    //     build   { framework = "make", executable = "%.exe"
    //               caps { memory_mb = 2048 } }
    //     choices = ["plain", "tricky"]
    //     interactive = true
    // }
    import hwut_runner::*;
    class Test extends HwutRunner;
        function new(); super.new("my title", '{"plain", "tricky"}); endfunction
        virtual task play(string choice);
            case (choice)
                "plain":  run_plain();
                "tricky": run_tricky();
            endcase
        endtask
    endclass
    module test_x; initial begin Test t = new(); t.run(); end endmodule

and beside it a Makefile that builds 'test-x.exe' by 'verilator --binary':
the packages it imports, the test's source last (its module the top, the
stem with '_' for '-'), the '*_dpi.c' and '../c/*.c' it reaches compiled AS
C by $(CC) into the target's own directory '<target>.obj' (removed after
the link). The build runs IN THE TEST DIRECTORY, where the Makefile stands
(services E-210); 'TEST/Makefile' is the example. 'test-x.exe' IS the
simulation: hwut calls it with a choice, '--hwut-info' or '--interactive',
and 'run()' ends the process with the mode's exit status. A choice is a
task: it may fork, wait on events and consume simulation time.

THE NAMES ARE PYTHON'S, IN SYSTEMVERILOG'S PLACES:

    Python                          SystemVerilog
    HwutRunner(argv, title, map)    class Test extends hwut_runner::HwutRunner, 'play' dispatches
    DeterministicStream(0x42)       deterministic_random::DeterministicStream s = new('h42)
    space_iterator.do(basis)        space_iterator::SpaceIterator::do_(basis)   ('do' is a keyword)
    class MyTrigger(Trigger)        class MyTrigger extends Trigger; virtual task fire(int t); ...
    asyncio.gather(a, b)            Loop::gather(task_list)      a Task: 'body' its coroutine
    await asyncio.sleep(0)          Loop::sleep0()
    task.cancel(); await task       t.cancel(); t.await_(raised)     raised 'CancelledError'
    Machine.from_string(text)       hwut_fsm::Machine::from_string(text)   null: Machine::refusal
    with m.disallowed(e, s): ...    phase = m.disallowed(e, s); ...; phase.close();
    m.state                         m.state_text(), or m.state(one) where it may be a set
    parse(lines, file)              document = hwut_hocon::parse(line_list, file, fault_list)
    with Screen(24, 80) as s: ...   s = hwut_vterm::Screen::create(24, 80); ...; s.close();
    screen.cell(r, c)               screen.cell_(r, c)           ('cell' is a keyword)
    terminal.wait() / .expect()     terminal.wait_(status) / .expect_(...)
    terminal.on_change(lambda ...)  terminal.on_change(cb)   cb: a ChangeCallback, 'on_change' overridden


2  THE SAME GOOD FILES -- THE PROOF THAT THE PORT IS ONE
------------------------------------------------------------------------------
'TEST/' holds one test per Python test, choice for choice, printing the same
text. Its GOOD files are not copies: every one is a '.link' to the Python
test's '.txt' (bookkeeper B-32):

    TEST/GOOD/test-hwut_fsm.sv--masks.link
        ../../../python/TEST/GOOD/test-hwut_fsm.py--masks.txt

47 cases in six tests, the same that hold the other ports.
'hwut.good.link.show TEST/GOOD' lists them.

What Python prints of its own values the tests print by 'hwut_pytext':
'float_repr(0.1)' '0.1', 'bool_repr(1)' 'True', 'str_repr' and 'bytes_repr'
Python's literals, 'list_repr', 'tuple_repr' ("('a',)"), 'padded' -- '%-6s'
counting characters, not bytes.

WHERE SYSTEMVERILOG DIFFERS FROM PYTHON, and how the port meets it:

    no exceptions       what Python raises is returned: null or 0/-1, the
                        text in the object's 'error' (FSM: a string; vterm:
                        'Error', 'kind' Python's exception name) or, for a
                        constructor, in 'Machine::refusal' / 'last_error';
                        a trigger's or a task's in 'raised'
                        ('NotImplementedError', 'CancelledError')
    no coroutines       a Task is an SV PROCESS; 'Loop::sleep0' hands the
                        turn to the next task waiting and waits for its own
                        (a semaphore each) -- asyncio's round-robin, made
                        explicit (SV-1: the simulator's own order of waking
                        does not give it); 'cancel' kills the process
    no 'with'           'close()' on the object, a Phase for the FSM's masks
    no callables        callbacks are objects whose method is overridden
                        (EventCallback, ChangeCallback, fsm::Writer)
    typed lists         candidates of the stream are strings (a value: equal
                        texts are one candidate, as Python's interned
                        literals are one object); anything else by INDEX
    None                '' -- a 'where' names no place, a state every state,
                        a 'start' the initial state
    no constructor that a factory: 'Screen::create', 'Terminal::create',
    can fail            'Machine::from_string' / 'create' -- null on refusal
    keywords            'do_', 'cell_', 'wait_', 'expect_', 'event_',
                        'initial_', 'final_'
    a choice ends       by returning; in --interactive mode each choice runs
                        in a child process ('fork' through DPI-C: the whole
                        simulation copied where it stood)


3  WHAT IT WANTS
------------------------------------------------------------------------------
VERILATOR 5 (measured: 5.020) with its C++ compiler (g++ 13, C++20
coroutines for '--timing'), a C99 compiler, make, POSIX, Linux ('/proc' for
the command line) -- and, for 'hwut_vterm' alone, libvterm AT RUN TIME
(Debian: apt install libvterm0, as for Python and C); no header needed. Where
the library is missing every choice of 'test-hwut_vterm.sv' but 'missing'
says 'NOT PROBED' -- and differs from its GOOD, as the Python test does. The
two applications 'test-hwut_vterm.sv' runs on its pseudo-terminal are the
Python test's own, so 'python3' must stand on the PATH.

WHY VERILATOR AND NOT ICARUS VERILOG 12: the port wants SV classes with
virtual methods, queues, associative arrays, strings, 'process', semaphores
and DPI-C with 'chandle', 'context' imports and exports -- Verilator 5 has
them; Icarus 12 has little of the class system and DPI-C (only VPI).

A BUILD WANTS MEMORY: measured, 435 MB at its peak (Verilator, then g++ on
the generated C++, '-j 2') -- the default cap is 512. Every test states
'build { ... caps { memory_mb = 2048 } }': the build alone (services E-212);
the runs keep the default. A build takes some 10 s; the files it writes
stay below 1 MB.

    hwut_vterm::detection_text()

says whether the library is there. No other package is wanted.


4  NOT HERE, ON PURPOSE
------------------------------------------------------------------------------
Anything the C modules do -- parse, draw a screen, run a pseudo-terminal.
'script_runner.py'   a fixture for hwut's own tests of its faces.
'hwut_pype'          a face ('hwut.pype'), not a library a test links.
==============================================================================
