==============================================================================
THE DEMONSTRATION OVER C -- one test directory, everything a test directory
can say, each thing shown once
==============================================================================

    hwut --plain                    every test here: 27 ok
    hwut.report.features            every feature below, and the run that
                                    proves it ('hwut-features.conf')
    hwut.play <file> <choice>       one choice, built, run and shown
    hwut.config.show <file>         what hwut read, and from where

It is the Python demonstration ('../../python/TEST'), choice for choice, in
C: the same stems, the same pype scripts and data, and -- by '.link' -- the
same GOOD files. A C program here prints what the Python program prints.

Every test application is a file whose header ('@hwut { }', in the file's
first comment) is its whole configuration; 'hwut.conf' is what the directory
says. A C test's header says 'build { framework = "make", executable =
"%.exe" }': hwut runs 'make <stem>.exe' HERE, where the 'Makefile' stands
(services E-210), several tests at once -- the Makefile builds each program
whole from its source and the C support modules it uses, sharing no object
file. A file's comment says what each of its choices shows. Where a run is
seeded by the clock or the scheduler its output differs from run to run, and
every choice passes anyway.

FILE              WHAT IT SHOWS
------------------------------------------------------------------------------
demo.c            THE COMPARISON'S TOLERANCES, one per choice
                  plain        exact, line by line
                  tolerance    'eq_pattern', 'numeric_ratio'
                  constraints  '((name: value))' judged by laws
                  analogies    '((handle))' consistent throughout
                  race         '##! potpourri': lines in any order (threads)
                  pool         '##! potpourri subset duplicates'
                  progress     'nothing': lines that count as none
                  lisp         'analogy' markers of one's own
                  clusters     '##! point-cloud ... pair dist=Linf'

chamber.c         REGIONS, UNITS, LAWS: '##! verbatim', '##! table',
                  '##! point-cloud', '##! ignore'; '((settle: 201 s))'
                  against 'settle <= 4 min'; a string law; a 'tolerance'
                  for every choice; '##' notes

protocol.sh       AN ORDER LAW AS A PYPE, fed live by a producer in C
producer.c        ('producer.exe', five clients in threads): clean, broken
                  (the violation report as GOOD), slow ('tick:' and a wait
                  guard over 'pype.time()'). The test stays a bash script:
                  the pipe into 'hwut.pype' is the shell's.
door.c            A PYPE THAT BINDS ITS VERDICT, '((breaches: N))', judged
door.pype         by the header; a state machine as the door's model; a
                  known-broken controller whose GOOD is its breach report

garage.c          CASES GENERATED, NOT WRITTEN, by the C support:
garage-space.hocon 'SpaceIterator', 'Hocon_parse', 'DeterministicStream',
                  'deterministic_timeline' (races drawn as strings);
                  'HwutRunner' as front end, 'interactive = true'

shop.c            THE DIRECTORY'S WORD -- read 'hwut.conf' with it:
delivery.json     'on_entry'/'on_exit', 'on_before_test'/'on_after_test',
fixture.c         'script_caps', 'ignore', 'admit', 'app_defaults',
hwut.conf         'collision', 'dependency', 'apps' (a test without a
                  header), 'execute', a choice-less test, 'target'
                  ('hwut.execute fixture open'); 'output' files;
                  'stderr_ignored'; '##! table unordered sep={;}'.
                  SQLite through its C library (libsqlite3-dev).

screen.c          A TERMINAL PROGRAM'S SCREEN: hwut_vterm runs 'viewer.exe'
viewer.c          ('viewer.c') on a pseudo-terminal and presses its keys;
                  the screen is compared as seen -- 'regions', 'comment',
                  'whitespace' off. Needs libvterm at run time ('apt install
                  libvterm0'); no header of it to build.

build.c           A PYPE NAMED IN THE HEADER, 'pype = "build.pypes"': a
build.pypes       system of two scripts; push/pop over nested
normalise.pype    directories, '<exit>', 'import:', a repeat group,
build.pype        'quantity(s)', '<bol>'/'<eol>', globs, 'flush';
compiler.pype     'same = true' -- serial and parallel share one GOOD;
                  'choices' as a list

Makefile          how every program here is built; the ONE place that
                  says where the C test support stands (below)

THE HELPERS no test's 'build' makes -- 'fixture.exe', 'producer.exe', and
'shop.exe' that 'delivery.json' is executed by -- are built by 'on_entry'
before the shop is opened. 'viewer.exe' is built with 'screen.exe'. By hand:
'make <name>.exe'; 'make clean' removes them all.

GOOD FILES: every one a '.link' to the Python demo's GOOD, but three cases
whose output names a C file -- 'screen.c open' and 'screen.c scroll' say
'> viewer.exe race.txt', 'shop.c report' lists the frame log's 'shop.c sell'
-- and the 'stock.csv' of 'shop.c report' (a link holds stdout alone).
'hwut.good.link.show GOOD' lists the links; '../RATIONALE.txt' says why.

MAKE IT IMPORTABLE
------------------------------------------------------------------------------
The C test support is a directory of '.h' and '.c' files, compiled with the
test -- no library to install. Where it was written to '<dir>' (the port at
'<dir>/c'):

    export HWUT_SUPPORT_C=<dir>/c
    export CPATH="<dir>/c${CPATH:+:$CPATH}"

The first is what this Makefile reads (and what a Makefile of one's own
compiles the support's sources from: '$(HWUT_SUPPORT_C)/hwut_runner.c ...');
the second lets the compiler (gcc, clang) find the headers without '-I'. A
test then writes

    #include "hwut_runner.h"

and links '$(HWUT_SUPPORT_C)/hwut_runner.c $(HWUT_SUPPORT_C)/hwut_pytext.c',
plus the '.c' of every other module it includes ('hwut_vterm.c' with '-ldl
-lutil'). Where HWUT_SUPPORT_C is set it wins over the path the Makefile
names itself.

NOT HERE, ON PURPOSE
------------------------------------------------------------------------------
'language-setup', 'variant_group', 'procsitter', 'free_disk_min_mb'
                  the root's alone ('hwut-root.conf' beside this directory)
'##! unaccepted', '##! constraint-violation'
                  written by hwut itself, into a recording or a GOOD
'diff_display_parameters'
                  how a difference is shown, not what passes
the pype scripts in C
                  'hwut.pype' is hwut's face, a Python program: a C test
                  pipes through it, and its scripts are the Python demo's
==============================================================================
