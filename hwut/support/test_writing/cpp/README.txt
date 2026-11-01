==============================================================================
test_writing_support/cpp -- THE PYTHON TEST SUPPORT, IN C++
==============================================================================

1  WHAT STANDS HERE
------------------------------------------------------------------------------
Every module a Python test author is given in '../python' is given to a C++
test author here, with the same behaviour and the same printed words -- as
classes in namespace 'hwut', THIN FACES over the C modules in '../c', which
do the work (C++ RATIONALE CPP-1):

    hwut_runner.hpp            hwut_runner.py           the front end of a
                                                        test: --hwut-info, one
                                                        choice, --interactive
    deterministic_random.hpp   deterministic_random.py  a random stream that
                                                        is the same everywhere
    deterministic_timeline.hpp deterministic_timeline.py races drawn as strings
    space_iterator.hpp         space_iterator.py        every combination of a
                                                        parameter basis
    hwut_fsm.hpp               hwut_fsm.py              a state machine as the
                                                        test's model
    hwut_hocon.hpp             hwut_hocon.py            the HOCON subset, the
                                                        annotated tree
    hwut_vterm.hpp             hwut_vterm.py            a terminal's screen,
                                                        read by a test (libvterm)
    hwut_pytext.hpp            --                       text as Python prints it

Each '.hpp' has its '.cpp' beside it ('space_iterator.hpp' is a header
alone); a test compiles the ones it uses with its own source, and the C
modules they wrap ('../c/*.c') AS C -- there is no library to install.
C++17 and POSIX; nothing beyond the C and C++ standard libraries, libm and,
for 'hwut_vterm', libdl and libutil.

A C++ test starts:

    /* @hwut {
     *     build   { framework = "make", executable = "%.exe" }
     *     choices = ["plain", "tricky"]
     * } */
    #include "hwut_runner.hpp"
    static void tricky() { ... }
    int main(int argc, char** argv)
    {
        hwut::HwutRunner runner(argc, argv, "my title", {
            { "plain",  [] { ... } },           -- any std::function<void()>
            { "tricky", tricky },
        });
        return runner.run();
    }

and beside it a Makefile that builds 'test-x.exe' from 'test-x.cpp', the
C++ support sources it needs and their C sources. The build runs IN THE TEST
DIRECTORY, where the Makefile stands (services E-210); 'TEST/Makefile' is
the example -- it compiles the C sources with $(CC) into a directory of the
target's own, so several targets may be built at once. The heads of the
'.hpp' files say how each module is used; where a Python README explains a
module ('../python/README-hwut_fsm.txt', '-hwut_hocon', '-hwut_vterm',
'-hwut_runner'), it explains the C++ module too.

THE NAMES ARE PYTHON'S, IN C++'s PLACES:

    Python                          C++
    HwutRunner(argv, title, map)    hwut::HwutRunner(argc, argv, title, { {name, f}, ... })
    DeterministicStream(0x42)       hwut::DeterministicStream(0x42)
    space_iterator.do(basis)        hwut::space_iterator::do_(basis)   ('do' is a keyword)
    class MyTrigger(Trigger)        struct MyTrigger : hwut::Trigger { void fire(int) override; }
    Machine.from_string(text)       hwut::fsm::Machine::from_string(text)
    with m.disallowed(e, s): ...    { auto phase = m.disallowed(e, s); ... }
    parse(lines, file)              auto [document, faults] = hwut::hocon::parse(lines, file);
    with Screen(24, 80) as s: ...   { hwut::vterm::Screen s(24, 80); ... }
    class Terminal(Screen)          class hwut::vterm::Terminal : public Screen
    terminal.on_change(lambda ...)  terminal.on_change([](auto& name, auto& lines) { ... });

The C core stands in namespace 'hwut::c' (its functions keep C linkage), so
'using namespace hwut;' names no C struct twice.


2  THE SAME GOOD FILES -- THE PROOF THAT THE PORT IS ONE
------------------------------------------------------------------------------
'TEST/' holds one test per Python test, choice for choice, printing the same
text. Its GOOD files are not copies: every one is a '.link' to the Python
test's '.txt' (bookkeeper B-32):

    TEST/GOOD/test-hwut_fsm.cpp--masks.link
        ../../../python/TEST/GOOD/test-hwut_fsm.py--masks.txt

So the C++ module is held against what the Python module was accepted for,
byte for byte -- as the C and Perl modules are; 47 cases in six tests.
'hwut.good.link.show TEST/GOOD' lists them.

What Python prints of its own values the C++ tests print by 'hwut::pytext':

    repr(0.1)          '0.1'        repr(true)                 'True'
    repr(std::string)  "'it\\'s'"... bytes_repr("\x1b[A")      "b'\\x1b[A'"
    repr(vector)       '[1, 2]'     tuple_repr(vector), repr(std::tuple)  '(1,)'
    repr(std::nullopt) 'None'       repr(optional)             value or 'None'

WHERE C++ DIFFERS FROM PYTHON, and how the port meets it:

    exceptions          what Python raises is thrown, its what() Python's
                        text: hwut::FsmError (a std::invalid_argument, as
                        FsmError is a ValueError), hwut::NotImplementedError,
                        hwut::CancelledError, hwut::vterm::LibraryMissing,
                        KeyError, TimeoutError, RuntimeError (all of
                        hwut::vterm::Error, whose kind() is Python's name)
                        and hwut::vterm::IndexError, a std::out_of_range. An
                        exception never crosses the C core: what a trigger
                        or a callback throws is kept and thrown again where
                        the C call returns
    no coroutines       a hwut::Task is a step function -- 'bool()', true
                        while it yields; 'gather' steps tasks in turn, in the
                        order given (asyncio.gather's), 'cancel' abandons
                        one and 'await' on it throws CancelledError
    no 'with'           a Phase object: the mask or the forbidden state
                        stands while it lives ('disallowed', 'forbidding')
    identity ('id()')   'select_unchosen' remembers a POINTER candidate by
                        what it points to, any other by its address -- so a
                        fresh vector of the same 'const char*' is the same
                        pool, as a fresh list of the same objects is
    'where' of a breach hwut::fsm::Where: an int names a line ('line 3'), a
                        text stands as written, nothing names no place
    state=None          std::nullopt -- every state
    a choice ends       by returning; an exception that leaves it is said on
                        stderr and the choice exits 1, without '<hwut-end>'
                        (Python: the traceback); in --interactive mode each
                        choice runs in a child process
    a hung parse        cannot be abandoned from C++: in the HOCON fuzz the
                        timer ends the choice, saying the text (the GOOD wants
                        0 hangs; Python counts on)


3  WHAT IT WANTS
------------------------------------------------------------------------------
A C++17 compiler and a C99 compiler (g++ 13 and gcc, or clang++ 18 and
clang), make, POSIX -- and, for 'hwut_vterm' alone, libvterm AT RUN TIME
(Debian: apt install libvterm0, as for Python and C). NO HEADER of libvterm
is needed to build: the C module loads it by 'dlopen' -- 'libvterm.so.0', or
the file HWUT_LIBVTERM names. Where the library is missing, every choice of
'test-hwut_vterm.cpp' but 'missing' says 'NOT PROBED' -- and differs from its
GOOD, as the Python test does. The two applications 'test-hwut_vterm.cpp'
runs on its pseudo-terminal are the Python test's own (they are the system
under test), so 'python3' must stand on the PATH.

    hwut::vterm::detection_text()

says whether the library is there. No other package is wanted.


4  NOT HERE, ON PURPOSE
------------------------------------------------------------------------------
Anything the C modules do: the C++ modules convert, own and throw; they
parse, draw and schedule nothing themselves.
'script_runner.py'   a fixture for hwut's own tests of its faces.
'hwut_pype'          a face ('hwut.pype'), not a library a test links.
==============================================================================
