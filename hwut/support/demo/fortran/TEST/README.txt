==============================================================================
THE DEMONSTRATION OVER FORTRAN -- one test directory, everything a test
directory can say, each thing shown once
==============================================================================

    hwut --plain                    every test here: 27 ok
    hwut.report.features            every feature below, and the run that
                                    proves it ('hwut-features.conf')
    hwut.play <file> <choice>       one choice, built, run and shown
    hwut.config.show <file>         what hwut read, and from where

The Python demonstration ('../../python/TEST'), choice for choice, in
Fortran 2018 (gfortran 13), with the Fortran port of the test support.
Every test application is a '.f90' whose header ('! @hwut { }') is its
whole configuration -- 'build { framework = "make" }' among it: hwut runs
the 'Makefile' here, which builds '<stem>.exe' from the source and the
support modules it uses. 'hwut.conf' is what the directory says. A file's
comment says what each of its choices shows. Where a run is seeded by the
clock or the scheduler its output differs from run to run, and every choice
passes anyway.

THE GOOD FILES ARE THE PYTHON DEMONSTRATION'S: 'GOOD/<file>.link' names
'../../python/TEST/GOOD/<file.py>.txt' -- one text, held by both. Four
GOOD files are this directory's own (RATIONALE.txt, DEMO-FORTRAN-3).

FILE              WHAT IT SHOWS
------------------------------------------------------------------------------
demo.f90          THE COMPARISON'S TOLERANCES, one per choice
                  plain        exact, line by line
                  tolerance    'eq_pattern', 'numeric_ratio'
                  constraints  '((name: value))' judged by laws
                  analogies    '((handle))' consistent throughout
                  race         '##! potpourri': lines in any order
                  pool         '##! potpourri subset duplicates'
                  progress     'nothing': lines that count as none
                  lisp         'analogy' markers of one's own
                  clusters     '##! point-cloud ... pair dist=Linf'

chamber.f90       REGIONS, UNITS, LAWS: '##! verbatim', '##! table',
                  '##! point-cloud', '##! ignore'; '((settle: 201 s))'
                  against 'settle <= 4 min'; a string law; a 'tolerance'
                  for every choice; '##' notes

protocol.sh       AN ORDER LAW AS A PYPE, fed live by a Fortran producer
producer.f90      ('producer.exe', five OpenMP threads): clean, broken
                  (the violation report as GOOD), slow ('tick:' and a
                  wait guard over 'pype.time()')
door.f90          A STATE MACHINE AS THE LAW: the door's log, piped through
door.pype         the header's 'door.pype', which fires every 'door:'
                  event into a machine ('hwut_fsm') -- kept (the report:
                  transitions taken, where the door ended), broken (one
                  'BREACH' line per surprise: the GOOD holds them)

garage.f90        CASES GENERATED, NOT WRITTEN: 'space_iterator',
garage-space.hocon 'hwut_hocon', 'DeterministicStream',
                  'deterministic_timeline' (races drawn as strings);
                  'HwutRunner' as front end, 'interactive = true'

shop.f90          THE DIRECTORY'S WORD -- read 'hwut.conf' with it:
shop_db.f90       'on_entry'/'on_exit', 'on_before_test'/'on_after_test',
delivery.json     'script_caps', 'ignore', 'admit', 'app_defaults',
fixture.f90       'collision', 'dependency', 'apps' (a test without a
hwut.conf         header), 'execute', a choice-less test, 'target'
                  ('hwut.execute fixture open'); 'output' files;
                  'stderr_ignored'; '##! table unordered sep={;}'.
                  SQLite through ISO_C_BINDING ('shop_db.f90')

screen.f90        A TERMINAL PROGRAM'S SCREEN: hwut_vterm runs 'viewer.exe'
viewer.f90        on a pseudo-terminal and presses its keys; the screen is
                  compared as seen -- 'regions', 'comment', 'whitespace'
                  off. Needs libvterm ('apt install libvterm0').

build.f90         A PYPE NAMED IN THE HEADER, 'pype = "build.pypes"': a
build.pypes       system of two scripts; push/pop over nested
normalise.pype    directories, '<exit>', 'import:', a repeat group,
build.pype        'quantity(s)', '<bol>'/'<eol>', globs, 'flush';
compiler.pype     'same = true' -- serial and parallel share one GOOD;
                  'choices' as a list

Makefile          THE BUILD: one rule for every program, each target's
                  '.mod' files in a directory of its own -- hwut builds
                  several tests at once. 'on_entry' builds what no header
                  builds: 'fixture.exe', 'producer.exe', 'viewer.exe',
                  'shop.exe' (which 'delivery.json' is executed by).

WHAT IT WANTS
------------------------------------------------------------------------------
gfortran (13, '-std=f2018') with OpenMP ('-fopenmp', the threads of 'demo',
'build', 'producer' and 'shop'), make, a C compiler (the one C module
'hwut_vterm' binds), libsqlite3 (link: '-lsqlite3', no header), libvterm at
run time, 'stty', Linux.

MAKE IT IMPORTABLE
------------------------------------------------------------------------------
The support written to '<dir>' stands in '<dir>/fortran'. One line makes it
known to this directory's Makefile -- and to a test of one's own built by a
Makefile like it:

    export HWUT_SUPPORT_FORTRAN=<dir>/fortran

Fortran has no search path for sources: a test COMPILES the support's
modules with itself, a module after the modules it uses. A test of one's own
names them in its Makefile from that variable:

    S = $(HWUT_SUPPORT_FORTRAN)
    test-x.exe: $(S)/hwut_text.f90 $(S)/hwut_posix.f90 $(S)/hwut_pytext.f90 \
                $(S)/hwut_runner.f90 test-x.f90
    <tab>mkdir -p $@.d && gfortran -std=f2018 -J$@.d -o $@ $^ && rm -rf $@.d

and the test writes

    use hwut_runner

('use space_iterator', 'use hwut_hocon', ... for the others; the heads of
'<dir>/fortran/*.f90' say what each needs before it). 'hwut_vterm' links the
C port's 'hwut_vterm.c' too: '<dir>/c', where the support was written with
it; this Makefile, where it is not, takes the one of the hwut it runs under.

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
