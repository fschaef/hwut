==============================================================================
THE DEMONSTRATION OVER C++ -- one test directory, everything a test
directory can say, each thing shown once
==============================================================================

    hwut --plain                    every test here, built and run: 27 ok
    hwut.report.features            every feature below, and the run that
                                    proves it ('hwut-features.conf')
    hwut.play <file> <choice>       one choice, run and shown
    hwut.config.show <file>         what hwut read, and from where

The Python demonstration ('../../python/TEST'), application for
application, choice for choice, in C++ -- with C++'s port of the test
writing support ('hwut::', 'support/test_writing/cpp'). Its GOOD files are
LINKS to the Python demonstration's: the C++ applications are held against
what the Python ones were accepted for (bookkeeper B-32). Three are its
own (../RATIONALE.txt, DEMO-CPP-4).

Every test application is a '.cpp' whose header ('@hwut { }') is its whole
configuration -- 'build { framework = "make", target = "%.exe" }': hwut
runs 'make <stem>.exe' HERE, where the 'Makefile' stands, and then the
'.exe'. 'hwut.conf' is what the directory says. A file's comment says what
each of its choices shows. Where a run is seeded by the clock or the
scheduler its output differs from run to run, and every choice passes
anyway.

FILE              WHAT IT SHOWS
------------------------------------------------------------------------------
demo.cpp          THE COMPARISON'S TOLERANCES, one per choice
                  plain        exact, line by line
                  tolerance    'eq_pattern', 'numeric_ratio'
                  constraints  '((name: value))' judged by laws
                  analogies    '((handle))' consistent throughout
                  race         '##! potpourri': lines in any order
                  pool         '##! potpourri subset duplicates'
                  progress     'nothing': lines that count as none
                  lisp         'analogy' markers of one's own
                  clusters     '##! point-cloud ... pair dist=Linf'

chamber.cpp       REGIONS, UNITS, LAWS: '##! verbatim', '##! table',
                  '##! point-cloud', '##! ignore'; '((settle: 201 s))'
                  against 'settle <= 4 min'; a string law; a 'tolerance'
                  for every choice; '##' notes

protocol.cpp      AN ORDER LAW AS A PYPE, fed live by a C++ producer (five
protocol.pype     threads; the program starts 'hwut.pype' and writes into
                  it): clean, broken (the violation report as GOOD), slow
                  ('tick:' and a wait guard over 'pype.time()')
door.cpp          A PYPE THAT BINDS ITS VERDICT, '((breaches: N))', judged
door.pype         by the header; modes inheriting two bases; 'caps'; a
                  known-broken version whose GOOD is its violation
                  report. The model is in the pype: Python's 'hwut_fsm'

garage.cpp        CASES GENERATED, NOT WRITTEN: 'hwut::space_iterator',
garage-space.hocon 'hwut::hocon', 'hwut::DeterministicStream',
                  'hwut::TriggerDispatcher' (races drawn as strings);
                  'hwut::HwutRunner' as front end, 'interactive = true'

shop.cpp          THE DIRECTORY'S WORD -- read 'hwut.conf' with it:
delivery.json     'on_entry'/'on_exit', 'on_before_test'/'on_after_test',
fixture.cpp       'script_caps', 'ignore', 'admit', 'app_defaults',
hwut.conf         'collision', 'dependency', 'apps' (a test without a
                  header, BUILT and run by its 'apps' entry), 'execute',
                  a choice-less test, 'target' ('hwut.execute fixture
                  open'); 'output' files; 'stderr_ignored'; '##! table
                  unordered sep={;}'. Needs SQLite ('apt install
                  libsqlite3-dev').

screen.cpp        A TERMINAL PROGRAM'S SCREEN: 'hwut::vterm::Terminal' runs
viewer.cpp        'viewer.exe' on a pseudo-terminal and presses its keys;
                  the screen is compared as seen -- 'regions', 'comment',
                  'whitespace' off. Needs libvterm ('apt install libvterm0').

build.cpp         A PYPE NAMED IN THE HEADER, 'pype = "build.pypes"': a
build.pypes       system of two scripts; push/pop over nested
normalise.pype    directories, '<exit>', 'import:', a repeat group,
build.pype        'quantity(s)', '<bol>'/'<eol>', globs, 'flush';
compiler.pype     'same = true' -- serial and parallel share one GOOD;
                  'choices' as a list

Makefile          builds every '.exe' here, each WHOLE: hwut builds
                  several at once, and no two share a file. Its one line
                  marked 'HWUT-SUPPORT-PATH' says where the support stands.

WHAT IT WANTS: g++ (C++17) or clang++, a C99 compiler, make; SQLite's
header and library; libvterm at run time; python3 (hwut itself, and the
pypes).

MAKE IT IMPORTABLE
------------------------------------------------------------------------------
Where the support was written to '<dir>' -- the C++ port in '<dir>/cpp',
the C modules it wraps beside it in '<dir>/c' -- one line makes it known
to this directory's Makefile and to a Makefile of one's own:

    export HWUT_SUPPORT_CPP=<dir>/cpp

C++ has no search path for sources a test compiles, so the variable names
the place; the C modules are found as '$HWUT_SUPPORT_CPP/../c'. A test of
one's own writes

    #include "hwut_runner.hpp"

(and 'hwut_vterm.hpp', 'hwut_hocon.hpp', ... as it uses them), and its
Makefile compiles the support sources it uses with it, as this one does:

    g++ -std=c++17 -I$HWUT_SUPPORT_CPP -o test-x.exe test-x.cpp \
        $HWUT_SUPPORT_CPP/hwut_runner.cpp $HWUT_SUPPORT_CPP/hwut_pytext.cpp \
        <the C modules, $HWUT_SUPPORT_CPP/../c/*.c, compiled as C>

NOT HERE, ON PURPOSE
------------------------------------------------------------------------------
'language-setup', 'variant_group', 'procsitter', 'free_disk_min_mb'
                  the root's alone ('hwut-root.conf')
'##! unaccepted', '##! constraint-violation'
                  written by hwut itself, into a recording or a GOOD
'diff_display_parameters'
                  how a difference is shown, not what passes
script_runner     a fixture for hwut's own tests of its faces
==============================================================================
