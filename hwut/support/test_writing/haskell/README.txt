==============================================================================
support/test_writing/haskell -- THE PYTHON TEST SUPPORT, IN HASKELL
==============================================================================

1  WHAT STANDS HERE
------------------------------------------------------------------------------
Every module a Python test author is given in '../python' is given to a
Haskell test author here, with the same behaviour and the same printed words:

    Hwut/Runner.hs                hwut_runner.py          the front end of a
                                                          test application:
                                                          --hwut-info, one
                                                          choice, --interactive
    Hwut/DeterministicRandom.hs   deterministic_random.py a random stream
                                                          that is the same
                                                          everywhere
    Hwut/DeterministicTimeline.hs deterministic_timeline.py races drawn as
                                                          strings
    Hwut/SpaceIterator.hs         space_iterator.py       every combination
                                                          of a parameter basis
    Hwut/Fsm.hs                   hwut_fsm.py             a state machine as
                                                          the test's model
    Hwut/Hocon.hs                 hwut_hocon.py           the HOCON subset,
                                                          the annotated tree
    Hwut/Vterm.hsc                hwut_vterm.py           a terminal's screen,
                                                          read by a test
                                                          (libvterm)
    Hwut/PyText.hs                --                      values as Python
                                                          prints them

GHC and the packages that ship with it (base, containers, mtl, bytestring,
unix, directory) -- no cabal, no Hackage. 'Hwut.Vterm' is an FFI binding of
the C port ('../c/hwut_vterm.c'), read through 'hsc2hs', which ships with GHC
too.

A Haskell test starts:

    -- @hwut {
    --     build   { framework = "make", target = "%.exe" }
    --     choices = ["plain", "tricky"]
    --     interactive = true
    -- }
    module Main (main) where
    import Hwut.Runner

    main :: IO ()
    main = hwutRunner "my title" [ ("plain", plain), ("tricky", tricky) ]

and beside it the Makefile of 'TEST/', whose pattern rule builds 'test-x.exe'
from 'test-x.hs' ('ghc --make -outputdir build-test-x -i..'). The build runs
IN THE TEST DIRECTORY, where the Makefile stands (services E-210), under the
default caps: MEASURED, one 'ghc' of these builds peaks at some 200 MB, below
the default 512 MB (where a larger program wants more, 'build { caps {
memory_mb = ... } }' caps the build alone, E-212). The heads of the modules
say how each is used; where a Python README explains a module
('../python/README-hwut_fsm.txt', '-hwut_hocon', '-hwut_vterm',
'-hwut_runner'), it explains the Haskell module too.

THE MODULES ARE VALUES AND FUNCTIONS, IO AT THE EDGE:

    Python                              Haskell
    s = DeterministicStream(0x42)       evalState draws (deterministicStream 0x42)
    s.next_int(0, 9)                    nextInt 0 9                  :: Draw Int
    m = Machine.from_string(text)       fromString defaultOptions text :: Either FsmError Machine
    m.fire("grant", where=3)            fire "grant" (Line 3)        :: Fsm Bool
    print(...) between machine lines    write "..."                  (the Fsm log)
    with m.disallowed("x"): ...         disallowed "x" Nothing Nowhere block
    parse(lines, "f.hocon")             parse lines "f.hocon"        (pure)
    for p in space_iterator.do(b)       SpaceIterator.do' b          (a lazy list)
    class T(Trigger): async def fire    (trigger tl "T") { fire = \t -> ... }
    asyncio.run(d.run())                runTask (run d)
    asyncio.gather(a, b)                gather [a, b]
    with Screen(24, 80) as s: ...       withScreen 24 80 $ \s -> ...
    class Terminal(Screen)              instance ScreenLike Terminal


2  THE SAME GOOD FILES -- THE PROOF THAT THE PORT IS ONE
------------------------------------------------------------------------------
'TEST/' holds one test per Python test, choice for choice, printing the same
text. Its GOOD files are not copies: every one is a '.link' to the Python
test's '.txt' (bookkeeper B-32):

    TEST/GOOD/test-hwut_fsm.hs--masks.link
        ../../../../python/TEST/GOOD/test-hwut_fsm.py--masks.txt

47 cases in six tests. What Python prints of its own values -- True, None, a
float's shortest form, a str, bytes, list or tuple literal -- the Haskell
tests print by the class 'PyRepr' ('Hwut.PyText'):

    pyRepr (0.1 :: Double)   0.1          pyRepr True             True
    pyRepr "it's"            "it's"       pyRepr (Bytes "\ESC[A") b'\x1b[A'
    pyRepr ["a", "b"]        ['a', 'b']   pyRepr (PyTuple ["a"])  ('a',)

WHERE HASKELL DIFFERS FROM PYTHON, and how the port meets it:

    no mutable objects     a stream, a machine, a parse are VALUES; a step
                           returns the next value inside a monad ('Draw' =
                           State DeterministicStream; 'Fsm' = State Machine
                           with a Writer log and FsmError as ExceptT)
    no exceptions in pure  'fromString' is Either; 'parse' never fails (its
      code                 faults are part of its result); IO raises
                           'VtermError' and 'NotImplementedError' as
                           exceptions, one constructor per Python class
    no object identity     'SelectionMarker' keys on the candidate's VALUE
                           ('Ord a'); an unnamed Trigger is named by its
                           place, 'trigger-<i>'
    no coroutines          'Task' is a coroutine monad of the module's own:
                           'resume' runs to the next 'yield'; 'gather'
                           resumes round by round in the order given --
                           asyncio's; a cancellation DROPS the rest
                           ('runSteps n' says Nothing)
    no inheritance         a Trigger is a record of functions, a subclass a
                           record update; Screen/Terminal share the class
                           'ScreenLike'
    no 'with'              'bracket' ('withScreen', 'withTerminal'); the FSM's
                           phases take the block as an argument
    'show' is not 'repr'   'PyRepr'; floats by exact Rational arithmetic
                           (GHC's 'floatToDigits' is not Python's -- see
                           RATIONALE HS-1)
    no struct by value     the FFI cannot pass one, libvterm wants one: the
      in the FFI           binding calls the C port, which calls libvterm
    a choice ends          by returning; in --interactive mode each choice
                           runs in a child process ('forkProcess'), so an
                           'exitWith' in a choice ends that choice alone


3  WHAT IT WANTS
------------------------------------------------------------------------------
GHC (9.4.7 measured) with its boot packages and its 'hsc2hs', make, a C
compiler (for '../c/hwut_vterm.c') -- and, for 'Hwut.Vterm' alone, libvterm
AT RUN TIME (Debian: apt install libvterm0, as for Python and C); no header
of libvterm. The executables are linked '-dynamic' against GHC's shared boot
libraries: they run where that GHC is installed. Where libvterm is missing,
every choice of 'test-hwut_vterm.hs' but 'missing' says 'NOT PROBED' -- and
differs from its GOOD, as the Python test does. The two applications
'test-hwut_vterm.hs' runs on its pseudo-terminal are the Python test's own
(the system under test), so 'python3' must stand on the PATH.

    detectionText

says whether the library is there.

'hwut-root.conf' runs '.hs' with 'runghc'; the tests here declare a make
build instead. MEASURED: 'runghc' takes 0.7 - 0.9 s per CASE (it compiles
the modules to bytecode at every call; the fuzz takes 3.7 s), and cannot run
'test-hwut_vterm.hs' at all (it needs the hsc2hs step and the C object);
'make' builds a target in 1 - 1.5 s once, and a case then starts in 0.02 s.


4  NOT HERE, ON PURPOSE
------------------------------------------------------------------------------
'script_runner.py'   a fixture for hwut's own tests of its faces, not given
                     to test authors.
'hwut.pype'          a face ('services/lib/pype') and its scripts, not a library a
                     test links: a Haskell test pipes through it as a Python
                     test does.
==============================================================================
