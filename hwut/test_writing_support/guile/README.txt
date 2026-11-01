==============================================================================
test_writing_support/guile -- THE PYTHON TEST SUPPORT, IN SCHEME (GNU GUILE)
==============================================================================

1  WHAT STANDS HERE
------------------------------------------------------------------------------
Every module a Python test author is given in '../python' is given to a
Scheme test author here, with the same behaviour and the same printed words
-- one Guile module '(hwut ...)' per Python module, in 'hwut/':

    (hwut runner)                 hwut_runner.py           the front end of a
                                                           test application:
                                                           --hwut-info, one
                                                           choice, --interactive
    (hwut deterministic-random)   deterministic_random.py  a random stream that
                                                           is the same everywhere
    (hwut deterministic-timeline) deterministic_timeline.py races drawn as
                                                           strings; tasks
    (hwut space-iterator)         space_iterator.py        every combination of
                                                           a parameter basis
    (hwut fsm)                    hwut_fsm.py              a state machine as
                                                           the test's model
    (hwut hocon)                  hwut_hocon.py            the HOCON subset, the
                                                           annotated tree
    (hwut vterm)                  hwut_vterm.py            a terminal's screen,
                                                           read by a test
    (hwut pytext)                 --                       values as Python
                                                           prints them

Nothing is built and nothing is installed: GNU Guile 3.0 and its standard
modules ('(system foreign)', SRFI-1, -9, -41, '(ice-9 ...)'), and libvterm at
run time for '(hwut vterm)'.

A Scheme test starts (hwut runs it by the 'scheme' interpreter of
'hwut-root.conf', 'guile --no-auto-compile <test> <choice>'):

    ;; @hwut {
    ;;     choices = ["plain", "tricky"]
    ;;     interactive = true
    ;; }
    (add-to-load-path (string-append (dirname (canonicalize-path (current-filename)))
                                     "/.."))        ; where 'hwut/' stands
    (use-modules (hwut runner))
    (define (run-plain)  ...)
    (define (run-tricky) ...)
    (hwut-runner-run
     (make-hwut-runner (command-line) "my title"
                       `(("plain" . ,run-plain) ("tricky" . ,run-tricky))))

The choice map is an association list of name and thunk; a single thunk in
its place is the choice-less test. Each module's head says how it is used,
each procedure's docstring what it returns; where a Python README explains a
module ('../python/README-hwut_fsm.txt', '-hwut_hocon', '-hwut_vterm',
'-hwut_runner'), it explains the Scheme module too.

    Python                               Scheme
    m = Machine.from_string(text)        (define m (fsm-from-string text))
    m.fire("grant", where=3)             (fsm-fire! m "grant" #:where 3)
    m.path_to("busy", masked=False)      (fsm-path-to m "busy" #:masked? #f)
    with m.disallowed("release"): ...    (fsm-disallowed m "release" thunk)
    stream.next_int(0, 9)                (stream-next-int stream 0 9)
    for a, b in space_iterator.do(B):    (space-for-each (lambda (a b) ...) B)
    document, faults = parse(lines, f)   (call-with-values (lambda () (hocon-parse lines f)) ...)
    with Screen(24, 80) as s: ...        (call-with-screen 24 80 (lambda (s) ...))
    class MyTrigger(Trigger)             (make-trigger timeline name #:fire proc)
    asyncio.run(d.run())                 (timeline-run (lambda () (dispatcher-run d)))
    except FsmError as e: str(e)         (guard (e ((fsm-error? e) (exception-message e))) ...)


2  THE SAME GOOD FILES -- THE PROOF THAT THE PORT IS ONE
------------------------------------------------------------------------------
'TEST/' holds one test per Python test, choice for choice, printing the same
text. Its GOOD files are not copies: every one is a '.link' to the Python
test's '.txt' (bookkeeper B-32):

    TEST/GOOD/test-hwut_fsm.scm--masks.link
        ../../../python/TEST/GOOD/test-hwut_fsm.py--masks.txt

47 cases in six tests; 'hwut.good.link.show TEST/GOOD' lists them. What
Python prints of its own values Scheme prints by '(hwut pytext)':
'py-float-repr' (Python's 'repr(float)'), 'py-str-repr', 'py-bytes-repr',
'py-repr' -- which needs no hint for int against float: Scheme's exact
integer is Python's int, its inexact real Python's float.

WHERE SCHEME DIFFERS FROM PYTHON, and how the port meets it (RATIONALE SCM-1
says, module by module, what the language made of each):

    coroutines        none needed: a TASK is a computation suspended by a
                      DELIMITED CONTINUATION -- '(pause)' aborts to the task's
                      prompt, the scheduler keeps the continuation and calls
                      it later. 'fire' is an ordinary procedure.
    classes           records ('define-record-type') holding data, closures
                      holding behaviour: a trigger is its timeline, name and
                      two procedures; a terminal is a screen record whose
                      terminal part is filled
    exceptions        exception types of Python's names ('&fsm-error',
                      '&library-missing', '&index-error', '&key-error',
                      '&timeout-error', '&not-implemented', '&task-cancelled');
                      the message is Python's text
    None              #f where a procedure answers 'nothing' (a path not
                      found); in the HOCON tree the symbol 'null' (HOCON's own
                      word), since #f is a value there
    tuples            a pair for two (the cursor '(row . column)'), a vector
                      for more (a colour '#(r g b)'), a list where Python's
                      tuple is a sequence ('fsm-path-to')
    keyword args      keywords: '#:where', '#:state', '#:masked?', '#:start'
    'with'            'call-with-...' and 'dynamic-wind': left whatever way,
                      and -- a continuation being able to re-enter -- set up
                      again on re-entry
    identity          'eq?': a SelectionMarker keys by it, and a candidate
                      that is the same wherever written is a SYMBOL
    a choice ends     by returning, by '(exit n)' (status n: the runner
                      catches Guile's 'quit'), or by an exception (status 1,
                      the backtrace in the error sink). Interactive mode runs
                      the choices one after another IN THIS PROCESS, as
                      Python's default scheme does.


3  WHAT IT WANTS
------------------------------------------------------------------------------
GNU Guile 3.0 (measured on 3.0.9) -- 'guile' on the PATH, as hwut-root.conf
names it -- and, for '(hwut vterm)' alone, libvterm AT RUN TIME (Debian: apt
install libvterm0, as for Python). No package beyond Guile: the library is
loaded by '(system foreign)' -- 'libvterm.so.0', or the file HWUT_LIBVTERM
names -- and so are libc's 'openpty', 'read' and 'write' for the
pseudo-terminal. Where the library is missing, every choice of
'test-hwut_vterm.scm' but 'missing' says 'NOT PROBED' -- and differs from
its GOOD, as the Python test does. The two applications 'test-hwut_vterm.scm'
runs on its pseudo-terminal are the Python test's own (the system under
test), so 'python3' must stand on the PATH.

    guile --no-auto-compile -L . hwut/vterm.scm

(in this directory) says whether the library is there: its name and exit 0,
or the message and exit 1.


4  NOT HERE, ON PURPOSE
------------------------------------------------------------------------------
'script_runner.py'     a fixture for hwut's own tests of its faces.
'hwut_pype'            a face, not a library a test links.
parallel="process"     the runner's forked scheme of interactive mode: the
                       47 cases do not ask for it; the sequential scheme is
                       Python's default and is what stands.
==============================================================================
