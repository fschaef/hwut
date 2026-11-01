==============================================================================
test_writing_support/node -- THE PYTHON TEST SUPPORT, IN JAVASCRIPT FOR NODE.JS
==============================================================================

1  WHAT STANDS HERE
------------------------------------------------------------------------------
Every module a Python test author is given in '../python' is given to a
node.js test author here, with the same behaviour and the same printed words
-- one CommonJS module per Python module, the Python names kept:

    hwut_runner.js            hwut_runner.py           the front end of a test
      HwutRunner                                       application: --hwut-info,
                                                       one choice, --interactive
    deterministic_random.js   deterministic_random.py  a random stream that is
      DeterministicStream, SelectionMarker             the same everywhere
    deterministic_timeline.js deterministic_timeline.py races drawn as strings
      Trigger, TriggerDispatcher, create_task, gather, sleep0, CancelledError
    space_iterator.js         space_iterator.py        every combination of a
      do (= product)                                   parameter basis
    hwut_fsm.js               hwut_fsm.py              a state machine as the
      Machine, FsmError                                test's model
    hwut_hocon.js             hwut_hocon.py            the HOCON subset, the
      parse, SourceLine, ...                           annotated tree
    hwut_vterm.js             hwut_vterm.py            a terminal's screen, read
      Screen, Terminal, ...                            by a test (libvterm)
    pytext.js                 --                       text as Python prints it

A node test is run by 'node' as it stands -- the 'javascript' interpreter of
'hwut-root.conf'; nothing is built. It finds the modules by a path relative to
its OWN file, so it runs from any working directory:

    // @hwut {
    //     choices = ["plain", "tricky"]
    //     interactive = true
    // }
    'use strict';
    const path = require('path');
    const { HwutRunner } = require(path.join(__dirname, '..', 'hwut_runner.js'));
    function plain()        { console.log('...'); }
    async function tricky() { ... }                // awaited, as a coroutine is
    new HwutRunner({
        argv:       process.argv.slice(1),        // as Python's 'sys.argv'
        title:      "my title",
        choice_map: { plain, tricky },             // '-' alone: choice-less
    }).run();

(the path is the test's own way to '<...>/test_writing_support/node'.) The
heads of the modules say how each is used; where a Python README explains a
module ('../python/README-hwut_fsm.txt', '-hwut_hocon', '-hwut_vterm',
'-hwut_runner'), it explains the node module too.


2  THE SAME GOOD FILES -- THE PROOF THAT THE PORT IS ONE
------------------------------------------------------------------------------
'TEST/' holds one test per Python test, choice for choice, printing the same
text. Its GOOD files are not copies: every one is a '.link' to the Python
test's '.txt' (bookkeeper B-32):

    TEST/GOOD/test-hwut_fsm.js--masks.link
        ../../../python/TEST/GOOD/test-hwut_fsm.py--masks.txt

So the node module is held against what the Python module was accepted for,
byte for byte -- as the Perl and the C modules are; 47 cases in six tests.
'hwut.good.link.show TEST/GOOD' lists them.

What Python prints of its own values the node tests print by 'pytext.js':

    floatRepr(0.1)          '0.1'        boolText(true)           'True'
    floatRepr(-1500)        '-1500.0'    noneOr(null)             'None'
    tupleRepr(['a'], true)  "('a',)"     listRepr([3, 1])         '[3, 1]'
    strRepr("it's")         "\"it's\""   bytesRepr(Buffer.from('\x1b[A'))  "b'\\x1b[A'"

WHERE NODE DIFFERS FROM PYTHON, and how the port meets it:

    one number type        the caller says int or float: 'floatRepr' for a
                           float, 'String' for an int. HOCON's ScalarNode
                           carries 'py_type' ('int', 'float', 'str', 'bool',
                           'NoneType') and 'repr()'; an int beyond 2^53 is a
                           BigInt. MINSTD's '48271 * state' stays below 2^47,
                           exact in a double. JS's shortest round-trip digits
                           are Python's; only the layout ('1e+16', '1e-05',
                           '-0.0', 'inf') is rewritten
    keyword arguments      positional, in Python's order -- 'fire(event,
                           where)', 'path_to(state, start, masked)',
                           'region(name, row, row_n, column, column_n)',
                           'press(key, modifier_list, react_s)'; the options
                           of a constructor are an object ('from_string(text,
                           { DFA, name, write })'); None is 'null'
    tuples                 arrays ('cursor()' is [row, column])
    'with'                 'm.disallowed(event, state, where).run(block)',
                           'screen.use(block)': the block runs, the phase ends
                           or the screen closes whatever way it leaves
    exceptions             thrown, classes named as Python's -- FsmError,
                           NotImplementedError, CancelledError, LibraryMissing,
                           IndexError, KeyError, TimeoutError -- 'message' is
                           Python's text. HOCON throws nothing, as in Python
    asyncio                node's loop: 'sleep0()' is 'asyncio.sleep(0)' (one
                           turn: 'setImmediate', FIFO as asyncio's ready
                           queue); 'create_task(fn)' starts 'fn' at the next
                           turn, 'task.cancel()' throws CancelledError at its
                           next 'sleep0()' (the task found by
                           AsyncLocalStorage); 'gather(fn, ...)' starts them
                           in the order given. The GOODs' interleavings are
                           asyncio's, line for line
    no dup2                in --interactive mode each choice runs in a CHILD
                           -- 'node <app> <choice>' -- whose fd 1 and 2 ARE
                           the two sinks: what it and what it spawns write
                           lands there; 'process.exit(n)' ends that choice
                           with status n (SystemExit); a throw is status 1, its
                           stack in the error sink; 'parallel: "process"'
                           runs the children concurrently
    no fork, no ctypes     'hwut_vterm' loads libvterm through 'koffi' (and
                           libc for the pseudo-terminal); the application is
                           started by 'posix_spawnp' in a new session, the
                           pty's slave opened as its fd 0 -- so its
                           controlling terminal -- every signal at its
                           default. 'run', 'pump', 'send', 'wait' block, as in
                           Python
    'fuzz' bound           a 'vm' script timeout interrupts a parse that
                           loops, where Python sets an interval timer


3  WHAT IT WANTS
------------------------------------------------------------------------------
node 22 (or later) -- nothing else for every module but 'hwut_vterm'.

For 'hwut_vterm' alone:

    npm install            IN THIS DIRECTORY, once: it installs 'koffi'
                           (package.json pins 2.9.0; prebuilt binaries, no
                           compiler) into 'node_modules/'. node has no foreign
                           function interface of its own; koffi is the one
                           package this port wants. 'node_modules/' is not
                           part of the tree ('.gitignore').
    libvterm AT RUN TIME   Debian: apt install libvterm0, as for Python --
                           'libvterm.so.0', or the file HWUT_LIBVTERM names.
                           No header: the cell's layout is measured.
    python3                on the PATH, for 'TEST/test-hwut_vterm.js' alone:
                           the two applications it runs on its pseudo-terminal
                           are the Python test's own -- the system under test.

Where koffi or the library is missing, every choice of 'test-hwut_vterm.js'
but 'missing' says 'NOT PROBED' -- and differs from its GOOD, as the Python
test does.

    node hwut_vterm.js     says whether the library is there


4  NOT HERE, ON PURPOSE
------------------------------------------------------------------------------
'script_runner.py'   a fixture for hwut's own tests of its faces, not given
                     to test authors.
'hwut_pype'          a face ('hwut.pype') and its scripts, not a library a
                     test links: a node test pipes through it as a Python
                     test does.
==============================================================================
