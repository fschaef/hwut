==============================================================================
test_writing_support/c -- THE PYTHON TEST SUPPORT, IN C
==============================================================================

1  WHAT STANDS HERE
------------------------------------------------------------------------------
Every module a Python test author is given in '../python' is given to a C
test author here, with the same behaviour and the same printed words:

    hwut_runner.h           hwut_runner.py           the front end of a test
                                                     application: --hwut-info,
                                                     one choice, --interactive
    deterministic_random.h  deterministic_random.py  a random stream that is
                                                     the same everywhere
    deterministic_timeline.h deterministic_timeline.py races drawn as strings
    space_iterator.h        space_iterator.py        every combination of a
                                                     parameter basis
    hwut_fsm.h              hwut_fsm.py              a state machine as the
                                                     test's model
    hwut_hocon.h            hwut_hocon.py            the HOCON subset, the
                                                     annotated tree
    hwut_vterm.h            hwut_vterm.py            a terminal's screen, read
                                                     by a test (libvterm)
    hwut_pytext.h           --                       text as Python prints it

Each '.h' has its '.c' beside it; a test compiles the ones it uses with its
own source -- there is no library to install. C99 and POSIX; nothing beyond
libc, libm and, for 'hwut_vterm', libdl and libutil.

A C test starts:

    /* @hwut {
     *     build   { framework = "make", executable = "%.exe" }
     *     choices = ["plain", "tricky"]
     * } */
    #include "hwut_runner.h"
    static void plain(void)  { ... }
    static void tricky(void) { ... }
    int main(int argc, char** argv)
    {
        static const HwutRunner_Choice choice_list[] = {
            { "plain", plain }, { "tricky", tricky }, { NULL, NULL } };
        HwutRunner runner;
        HwutRunner_init(&runner, argc, argv, "my title", choice_list);
        return HwutRunner_run(&runner);
    }

and beside it a Makefile that builds 'test-x.exe' from 'test-x.c' and the
support sources it needs. The build runs IN THE TEST DIRECTORY, where the
Makefile stands (services E-210); 'TEST/Makefile' is the example. The heads
of the '.h' files say how each module is used; where a Python README
explains a module ('../python/README-hwut_fsm.txt', '-hwut_hocon',
'-hwut_vterm', '-hwut_runner'), it explains the C module too.

THE CLASSES ARE STRUCTS, THE METHODS FUNCTIONS (asked, 2026-10-30): "map oo
features to functions with class prefix and 'self' pointer as first
argument":

    Python                          C
    m = Fsm.from_string(text)       FsmMachine* m = FsmMachine_from_string(text, 1, "fsm", error, size);
    m.fire("grant", 3)              FsmMachine_fire(m, "grant", "3");
    stream.next_int(0, 9)           DeterministicStream_next_int(&stream, 0, 9);
    with Screen(24, 80) as s: ...   VtermScreen* s = VtermScreen_new(24, 80, &error); ... VtermScreen_free(s);
    class Terminal(Screen)          struct VtermTerminal { VtermScreen base; ... } -- '&t->base'
    class MyTrigger(Trigger)        a 'Trigger_Vtable' of the overridden methods, 'Trigger_init(self, &vtable, ...)'


2  THE SAME GOOD FILES -- THE PROOF THAT THE PORT IS ONE
------------------------------------------------------------------------------
'TEST/' holds one test per Python test, choice for choice, printing the same
text. Its GOOD files are not copies: every one is a '.link' to the Python
test's '.txt' (bookkeeper B-32):

    TEST/GOOD/test-hwut_fsm.c--masks.link
        ../../../python/TEST/GOOD/test-hwut_fsm.py--masks.txt

So the C module is held against what the Python module was accepted for,
byte for byte -- as the Perl module is ('../perl/README.txt'); 47 cases in
six tests. 'hwut.good.link.show TEST/GOOD' lists them.

What Python prints of its own values -- True, None, a float's shortest form,
a str or bytes literal -- the C tests print by 'hwut_pytext':

    pytext_float_repr(b, n, 0.1)  '0.1'     pytext_bool(1)                  'True'
    pytext_str_repr(b, n, "it's") "\"it's\""  pytext_bytes_repr(b, n, "\x1b[A", 3) "b'\\x1b[A'"

WHERE C DIFFERS FROM PYTHON, and how the port meets it:

    no exceptions          a function that Python lets raise returns NULL or
                           -1; the text stands in 'self->error' (or in the
                           'error' buffer a constructor is given): FsmError's
                           message, Hocon's faults as a list (it never
                           raised), Vterm's 'VtermError' -- 'kind' is
                           Python's exception name, 'message' its text
    no coroutines          a TASK is a step function: one 'Task_step' runs to
                           the next yield. 'Task_gather' steps tasks in turn,
                           in the order given -- asyncio.gather's order -- and
                           'Task_cancel' abandons one
    no inheritance         a derived class holds its base as the first member
                           ('VtermTerminal.base'); an overridable method is a
                           function pointer in a vtable ('Trigger_Vtable')
    no 'with'              'FsmMachine_disallowed' and '_forbidding' take the
                           block as a function and a context pointer
    values, not objects    the iterator yields INDICES into the caller's own
                           arrays ('SpaceIterator'); 'select' and 'choice'
                           return an index; a marker remembers addresses
    'where' of a breach    a text: digits name a line ('line 3'), any other
                           text stands as written, NULL names no place
    a choice ends          by returning; in --interactive mode each choice
                           runs in a child process ('fork'), so an 'exit' in
                           a choice ends that choice alone


3  WHAT IT WANTS
------------------------------------------------------------------------------
A C99 compiler, make, POSIX -- and, for 'hwut_vterm' alone, libvterm AT RUN
TIME (Debian: apt install libvterm0, as for Python). NO HEADER of libvterm is
needed to build: the module declares the library's few structures itself and
loads it by 'dlopen' -- 'libvterm.so.0', or the file HWUT_LIBVTERM names.
Where the library is missing, every choice of 'test-hwut_vterm.c' but
'missing' says 'NOT PROBED' -- and differs from its GOOD, as the Python test
does. The two applications 'test-hwut_vterm.c' runs on its pseudo-terminal
are the Python test's own (they are the system under test), so 'python3'
must stand on the PATH.

    Vterm_detection_text(buffer, size)

says whether the library is there.


4  NOT HERE, ON PURPOSE
------------------------------------------------------------------------------
'script_runner.py'   a fixture for hwut's own tests of its faces, not given
                     to test authors.
'hwut_pype'          a face ('hwut.pype') and its scripts, not a library a
                     test links: a C test pipes through it as a Python test
                     does.
==============================================================================
