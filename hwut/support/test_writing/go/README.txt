==============================================================================
test_writing_support/go -- THE PYTHON TEST SUPPORT, IN GO
==============================================================================

1  WHAT STANDS HERE
------------------------------------------------------------------------------
Every module a Python test author is given in '../python' is given to a Go
test author here, with the same behaviour and the same printed words -- one
package per module, in the module 'hwut/test_writing_support/go' ('go.mod'):

    hwutrunner/             hwut_runner.py           the front end of a test
                                                     application: --hwut-info,
                                                     one choice, --interactive
    deterministicrandom/    deterministic_random.py  a random stream that is
                                                     the same everywhere
    deterministictimeline/  deterministic_timeline.py races drawn as strings
    spaceiterator/          space_iterator.py        every combination of a
                                                     parameter basis
    hwutfsm/                hwut_fsm.py              a state machine as the
                                                     test's model
    hwuthocon/              hwut_hocon.py            the HOCON subset, the
                                                     annotated tree
    hwutvterm/              hwut_vterm.py            a terminal's screen, read
                                                     by a test (libvterm)
    pytext/                 --                       text as Python prints it

Go 1.24 and its standard library; nothing is downloaded -- 'go.mod' requires
no module. 'hwutvterm' alone is built by cgo (a C compiler; no header of
libvterm).

A Go test starts:

    // @hwut {
    //     build   { framework = "make", executable = "%.exe"
    //               caps { file_size_mb = 256 } }
    //     choices = ["plain", "tricky"]
    // }

    package main

    import (
        "os"
        "hwut/test_writing_support/go/hwutrunner"
    )

    func main() {
        os.Exit(hwutrunner.New(os.Args, "my title", map[string]func(){
            "plain":  runPlain,
            "tricky": runTricky,
        }).Run())
    }

(the blank line before 'package' keeps 'gofmt' off the header: a comment
right above it is a doc comment, and gofmt re-indents doc comments). Beside
it a Makefile builds 'test-x.exe' from 'test-x.go' by 'go build'; the build
runs IN THE TEST DIRECTORY, where the Makefile stands (services E-210), and
the support packages are found through the 'go.mod' above it.
'TEST/Makefile' is the example. A test may also be run by hand with
'go run test-x.go <choice>' from its directory.

WHY A MAKEFILE AND NOT 'go run' (hwut-root.conf's interpreter for '.go'):
'go run' finds the support packages from 'TEST/' (the 'go.mod' in '..') and
works -- but it COMPILES AT EVERY CALL, under the RUN's caps. MEASURED: on a
cold build cache Go writes its runtime archive, above the default 10 MB per
file; 'go run' ends before the session answers, and every case fails
'no-session' (with 'caps { file_size_mb = 256 }' it passes, cold or warm).
Built by make, the compile is the build step's, under 'build { caps }'
alone (services E-212), and every run starts the executable.

WHY 'build { caps { file_size_mb = 256 } }': on a cold cache Go writes its
runtime's archive, larger than the default cap of 10 MB per file ('file too
large'). The cap stands in the BUILD scope, so it caps the build alone; the
test's runs keep the default (services E-212).

The heads of the packages ('go doc ./hwutfsm') say how each is used; where a
Python README explains a module ('../python/README-hwut_fsm.txt',
'-hwut_hocon', '-hwut_vterm', '-hwut_runner'), it explains the Go package
too.

THE NAMES ARE GO'S, PYTHON'S RECOGNISABLE in them:

    Python                          Go
    m = Machine.from_string(text)   m, err := hwutfsm.FromString(text)
    Machine(..., DFA=False)         hwutfsm.FromString(text, hwutfsm.DFA(false))
    m.fire("grant", where=3)        m.Fire("grant", 3)
    stream.next_int(0, 9)           stream.NextInt(0, 9)
    stream.select(pool)             deterministicrandom.Select(stream, pool)
    with Screen(24, 80) as s: ...   s, err := hwutvterm.NewScreen(24, 80); defer s.Close()
    class Terminal(Screen)          type Terminal struct{ *Screen; ... }
    class MyTrigger(Trigger)        type MyTrigger struct{ *deterministictimeline.TriggerBase }
    asyncio.run(d.run())            deterministictimeline.Run(d.Run)


2  THE SAME GOOD FILES -- THE PROOF THAT THE PORT IS ONE
------------------------------------------------------------------------------
'TEST/' holds one test per Python test, choice for choice, printing the same
text. Its GOOD files are not copies: every one is a '.link' to the Python
test's '.txt' (bookkeeper B-32):

    TEST/GOOD/test-hwut_fsm.go--masks.link
        ../../../python/TEST/GOOD/test-hwut_fsm.py--masks.txt

So the Go package is held against what the Python module was accepted for,
byte for byte -- as the Perl and the C ports are; 47 cases in six tests.
'hwut.good.link.show TEST/GOOD' lists them.

What Python prints of its own values -- True, None, a float's shortest form,
a str or bytes literal, a list, a tuple -- the Go tests print by 'pytext':

    pytext.FloatRepr(0.1)       '0.1'       pytext.Bool(true)               'True'
    pytext.StrRepr("it's")      "\"it's\""  pytext.BytesRepr([]byte("\x1b[A")) "b'\\x1b[A'"
    pytext.Repr([]int{3, 1})    '[3, 1]'    pytext.Repr(pytext.Tuple{"a"})  "('a',)"
    pytext.Repr(nil)            'None'      pytext.TypeName(1.5)            'float'

WHERE GO DIFFERS FROM PYTHON, and how the port meets it:

    exceptions             returned: an 'error' -- *hwutfsm.FsmError (its
                           text Python's), *hwutvterm.VtermError ('Kind' is
                           Python's exception name, 'Message' its text);
                           HOCON's faults are a list (it never raised).
                           ErrNotImplemented and ErrCancelled are Python's
                           NotImplementedError and CancelledError
    keyword arguments      options ('hwutfsm.DFA(false)', 'hwutfsm.Name(..)'),
                           a variadic bound ('Gauss(mu, sigma, lower, upper)'),
                           or a stated value: None is "" for a state or a
                           start ('PathTo(s, "", true)'), nil for a 'where',
                           a negative column count for 'to the right edge'
    coroutines             goroutines, ONE AT A TIME, in asyncio's order: a
                           FIFO of ready tasks ('Sleep0' to its end, 'Await',
                           'Gather', 'Cancel' -- the cancelled task's next
                           wait returns ErrCancelled). 'yielding' and
                           'cancel' print the Python lines because the
                           interleaving IS Python's
    inheritance            embedding: a trigger embeds *TriggerBase and
                           overrides 'Fire'; a Terminal embeds its *Screen
    a method with a type   Go has none: 'Select', 'Choice', 'Sample',
    parameter              'SelectUnchosen' are functions of the package,
                           the stream first
    identity in a marker   a candidate is 'comparable' and remembered as
                           itself: a pointer by its address ('id()'), a
                           string by its value -- as two equal short strings
                           are one object in Python
    'with'                 'Disallowed' and 'Forbidding' take the block as a
                           func; 'defer s.Close()' for a Screen
    a generator            'spaceiterator.Do' is an 'iter.Seq' ('for point
                           := range ...'); 'DoOf' for one element type
    an int without bound   a HOCON integer is int64, a *big.Int beyond it
    a column               counts characters (runes), as Python's str
    seconds                a time.Duration ('settle', 'react', 'timeout')
    no 'fork'              in --interactive mode each choice runs in a CHILD:
                           the own executable started again on that choice,
                           its stdout and stderr the sinks -- an 'os.Exit' or
                           a panic ends that choice alone, as SystemExit does
                           in Python
    Python's '\s'          Unicode's white space and 0x1c..0x1f
                           ('pytext.IsSpace', 'Strip', 'SplitLines')
    the libm path          'Gauss' uses Go's 'math' (log, cos are Go's own,
                           not libm): its full-precision draws differ from
                           Python's in the last digits -- MEASURED: 6 of the
                           20 printed values -- which the GOOD's 'table
                           numeric={1:1e-12}' region exists for (S3, as for
                           node); every integer draw is exact


3  WHAT IT WANTS
------------------------------------------------------------------------------
Go 1.24 (its toolchain is used as it stands: GOTOOLCHAIN=local), make --
and, for 'hwutvterm' alone, cgo's C compiler (gcc; CGO_ENABLED, Go's default
where one is found) and libvterm AT RUN TIME (Debian: apt install libvterm0,
as for Python). NO HEADER of libvterm is needed to build: the package's C
side ('hwutvterm/vterm_library.c') declares the library's few structures
itself and loads it by 'dlopen' -- 'libvterm.so.0', or the file
HWUT_LIBVTERM names. The pseudo-terminal is made by system calls in Go
('/dev/ptmx'), no library. Where the library is missing, every choice of
'test-hwut_vterm.go' but 'missing' says 'NOT PROBED' -- and differs from its
GOOD, as the Python test does. The two applications 'test-hwut_vterm.go'
runs on its pseudo-terminal are the Python test's own (they are the system
under test), so 'python3' must stand on the PATH.

    hwutvterm.DetectionText()

says whether the library is there. Where HOME is not writable, the Makefile
puts Go's build cache in 'TEST/.gocache'.


4  NOT HERE, ON PURPOSE
------------------------------------------------------------------------------
'script_runner.py'   a fixture for hwut's own tests of its faces, not given
                     to test authors.
'hwut_pype'          a face ('hwut.pype') and its scripts, not a library a
                     test imports: a Go test pipes through it as a Python
                     test does.
==============================================================================
