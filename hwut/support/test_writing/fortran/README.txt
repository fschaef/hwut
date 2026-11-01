==============================================================================
support/test_writing/fortran -- THE PYTHON TEST SUPPORT, IN FORTRAN
==============================================================================

1  WHAT STANDS HERE
------------------------------------------------------------------------------
Every module a Python test author is given in '../python' is given to a
Fortran test author here (Fortran 2018, gfortran 13), with the same behaviour
and the same printed words:

    hwut_runner.f90           hwut_runner.py           the front end of a test
                                                       application: --hwut-info,
                                                       one choice, --interactive
    deterministic_random.f90  deterministic_random.py  a random stream that is
                                                       the same everywhere
    deterministic_timeline.f90 deterministic_timeline.py races drawn as strings
    space_iterator.f90        space_iterator.py        every combination of a
                                                       parameter basis
    hwut_fsm.f90              hwut_fsm.py              a state machine as the
                                                       test's model
    hwut_hocon.f90            hwut_hocon.py            the HOCON subset, the
                                                       annotated tree
    hwut_vterm.f90            hwut_vterm.py            a terminal's screen, read
                                                       by a test (libvterm,
                                                       through the C port)
    hwut_pytext.f90           --                       text as Python prints it
    hwut_text.f90             --                       texts of any length, and
                                                       lists of them ('string')
    hwut_posix.f90            --                       the few libc calls Fortran
                                                       has no word for (fork,
                                                       dup2, setenv), 'bind(c)'

One Fortran MODULE per Python module, of the same name. A test compiles the
ones it uses with its own source, a module after the modules it uses -- there
is no library to install. Everything is Fortran but 'hwut_vterm', which binds
'../c/hwut_vterm.c' (README.txt there) through ISO_C_BINDING.

A Fortran test starts:

    ! @hwut {
    !     build   { framework = "make", executable = "%.exe" }
    !     choices = ["plain", "tricky"]
    ! }
    module test_x_choices
        use hwut_text
        implicit none
    contains
        subroutine run_plain()
            call say("...")
        end subroutine
        subroutine run_tricky()
            ...
        end subroutine
    end module

    program test_x
        use hwut_runner
        use test_x_choices
        implicit none
        type(HwutRunner) :: runner
        runner = HwutRunner("my title", [HwutChoice("plain",  run_plain), &
                                         HwutChoice("tricky", run_tricky)])
        call runner%run()
    end program

THE CHOICES ARE MODULE PROCEDURES, not procedures contained in the program: a
procedure pointer to an internal procedure needs a trampoline, and the
trampoline an executable stack (the linker says so).

Beside it a Makefile builds 'test-x.exe' from 'test-x.f90' and the support
modules it needs. The build runs IN THE TEST DIRECTORY, where the Makefile
stands (services E-210); 'TEST/Makefile' is the example: each target keeps
its '.mod' files in a directory of its own ('-J<target>.d'), so several
targets build at once and share nothing. 'test-x.cov.exe' is the same built
with '--coverage' (hwut-root.conf's 'coverage_target'). The heads of the
'.f90' files say how each module is used; where a Python README explains a
module ('../python/README-hwut_fsm.txt', '-hwut_hocon', '-hwut_vterm',
'-hwut_runner'), it explains the Fortran module too.

THE CLASSES ARE DERIVED TYPES, THE METHODS TYPE-BOUND PROCEDURES; Python's
names stand, Fortran being blind to case:

    Python                          Fortran
    m = Machine.from_string(text)   m = Machine_from_string(text)
    m.fire("grant", where=3)        moved = m%fire("grant", where = 3)
    stream.next_int(0, 9)           stream%next_int(0, 9)
    with Screen(24, 80) as s: ...   s = Screen(24, 80); ...; call s%close()
    class Terminal(Screen)          type, extends(Screen) :: Terminal
    class MyTrigger(Trigger)        type, extends(Trigger) :: MyTrigger, overriding 'fire'
    DFA=False, masked=False         dfa = .false., masked = .false. (optional arguments)


2  THE SAME GOOD FILES -- THE PROOF THAT THE PORT IS ONE
------------------------------------------------------------------------------
'TEST/' holds one test per Python test, choice for choice, printing the same
text. Its GOOD files are not copies: every one is a '.link' to the Python
test's '.txt' (bookkeeper B-32):

    TEST/GOOD/test-hwut_fsm.f90--masks.link
        ../../../../python/TEST/GOOD/test-hwut_fsm.py--masks.txt

So the Fortran module is held against what the Python module was accepted
for, byte for byte -- as the C and the other ports are; 47 cases in six
tests. 'hwut.good.link.show TEST/GOOD' lists them.

What Python prints of its own values the Fortran tests print by
'hwut_pytext' -- ONE generic name, 'repr', as in Python:

    repr(0.1_real64)   '0.1'       repr(.true.)        'True'
    repr("it's")       "\"it's\""  bytes_repr(ESC//"[A") "b'\\x1b[A'"

WHERE FORTRAN DIFFERS FROM PYTHON, and how the port meets it:

    no exceptions        what Python raises is Fortran's own STAT/ERRMSG pair,
                         as 'allocate' and 'open' have it: a caller that
                         passes 'stat' gets 0 or 1 and the text (FsmError's
                         message in 'errmsg', Vterm's 'VtermError' with
                         'kind' -- the exception's name -- and 'message');
                         a caller that passes none is stopped by
                         'error stop "<Name>: <text>"', the uncaught
                         exception. HOCON's faults are a list (it never
                         raised).
    None, int, str       an optional argument absent is None; 'where' is
                         'class(*)': an integer names a line, a text stands
                         as written -- 'select type' tells them apart
    no list of texts     'hwut_text': 'type(string)' holds one deferred-length
                         text, an array of them is a list
    no object identity   a SelectionMarker remembers INTEGER identities the
                         caller gives its candidates ('id()' has no Fortran
                         counterpart: a value is only a value)
    arrays from 1        'select', 'choice', 'sample_indices' answer array
                         POSITIONS 1 .. n; the tests print Python's index,
                         one less. Rows and columns of a screen count from 0,
                         as the terminal does.
    no coroutines        a TASK is an object with a step function ('advance',
                         deferred): one 'step' runs to the next yield;
                         'gather' steps tasks in turn, in the order given --
                         asyncio.gather's. A TriggerDispatcher IS its run's
                         task. 'do concurrent' and coarrays promise no order,
                         the one thing a timeline is for: not used.
    no 'with'            'disallowed'/'forbidding' take the block as a
                         procedure argument, which is given the machine; a
                         Screen is opened by its constructor and closed by
                         'close', as a unit is
    no closures          a callback is a module procedure; what it shares
                         with the test is a module variable
    a choice ends        by returning, or by 'stop' -- in --interactive mode
                         each choice runs in a child process (libc 'fork'), so
                         a 'stop 3' ends that choice alone, status 3


3  WHAT IT WANTS
------------------------------------------------------------------------------
gfortran (13; '-std=f2018') and make; a C compiler (cc) for the one C module
'hwut_vterm' binds; Linux (the libc calls of 'hwut_posix' decode 'waitpid's
status as Linux does). Nothing else, but -- for 'hwut_vterm' alone -- libvterm
AT RUN TIME (Debian: apt install libvterm0, as for Python and C), found by
the C port's 'dlopen': 'libvterm.so.0', or the file HWUT_LIBVTERM names. No
header of libvterm is needed to build; the link wants '-ldl -lutil'. Where
the library is missing every choice of 'test-hwut_vterm.f90' but 'missing'
says 'NOT PROBED' -- and differs from its GOOD, as the Python test does. The
two applications 'test-hwut_vterm.f90' runs on its pseudo-terminal are the
Python test's own (they are the system under test), so 'python3' must stand
on the PATH.

    detection_text()

says whether the library is there.


4  NOT HERE, ON PURPOSE
------------------------------------------------------------------------------
'script_runner.py'   a fixture for hwut's own tests of its faces, not given
                     to test authors.
'hwut.pype'          a face ('services/lib/pype') and its scripts, not a library a
                     test links: a Fortran test pipes through it as a Python
                     test does.
==============================================================================
