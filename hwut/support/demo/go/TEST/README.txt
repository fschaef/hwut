==============================================================================
THE DEMONSTRATION OVER GO -- one test directory, everything a test directory
can say, each thing shown once; the Python demonstration's, program for
program, held against its GOOD files
==============================================================================

    hwut --plain                    every test here: 27 ok
    hwut.report.features            every feature, and the run that proves
                                    it -- this port's one is 'demo-go'
    hwut.play <file> <choice>       one choice, run and shown
    hwut.config.show <file>         what hwut read, and from where

Every test application is a file whose header ('@hwut { }', in '//'
comments above 'package main') is its whole configuration; 'hwut.conf' is
what the directory says. Each program is '../../python/TEST/<stem>.py' in
Go, choice for choice, printing the same text: its GOOD files are '.link's
to the Python texts ('hwut.good.link.show GOOD'). Where a run is seeded by
the clock or the scheduler its output differs from run to run, and every
choice passes anyway. A file's comment says what each of its choices shows;
the Python file says it at length.

BUILT, NOT INTERPRETED: each header says 'build { framework = "make",
target = "%.exe" }', and hwut runs 'make <stem>.exe' here, where the
'Makefile' stands (services E-210); several tests build at once. The
programs that are no test -- 'fixture.exe', 'viewer.exe', 'producer.exe',
and 'shop.exe' for 'delivery.json' -- are built by 'on_entry' ('make
helpers') before any test runs. By hand: 'make demo.exe && ./demo.exe race'.

WANTS: Go 1.24 (GOTOOLCHAIN=local, nothing is downloaded), make, a C
compiler for cgo ('screen.go' through 'hwutvterm', 'shop.go' and
'fixture.go' through 'sqlite.go'), libvterm ('apt install libvterm0') and
libsqlite3 ('libsqlite3-0') at run time -- no header of either.

FILE              WHAT IT SHOWS
------------------------------------------------------------------------------
demo.go           THE COMPARISON'S TOLERANCES, one per choice
                  plain        exact, line by line
                  tolerance    'eq_pattern', 'numeric_ratio'
                  constraints  '((name: value))' judged by laws
                  analogies    '((handle))' consistent throughout
                  race         '##! potpourri': lines in any order
                  pool         '##! potpourri subset duplicates'
                  progress     'nothing': lines that count as none
                  lisp         'analogy' markers of one's own
                  clusters     '##! point-cloud ... pair dist=Linf'

chamber.go        REGIONS, UNITS, LAWS: '##! verbatim', '##! table',
                  '##! point-cloud', '##! ignore'; '((settle: 201 s))'
                  against 'settle <= 4 min'; a string law; a 'tolerance'
                  for every choice; '##' notes

protocol.sh       AN ORDER LAW AS A PYPE, fed live by a Go producer
producer.go       ('producer.exe'): clean, broken (the violation report as
                  GOOD), slow ('tick:' and a wait guard over 'pype.time()')
door.go           A PYPE THAT BINDS ITS VERDICT: 'door.pype' fires the
door.pype         door's events into a state machine; a door that breaks
                  the model, its breaches as GOOD. The pype's actions are
                  Python -- the pype is hwut's face, not Go's

garage.go         CASES GENERATED, NOT WRITTEN: 'spaceiterator',
garage-space.hocon 'hwuthocon', 'deterministicrandom',
                  'deterministictimeline' (races drawn as strings);
                  'hwutrunner' as front end, 'interactive = true'

shop.go           THE DIRECTORY'S WORD -- read 'hwut.conf' with it:
delivery.json     'on_entry'/'on_exit', 'on_before_test'/'on_after_test',
fixture.go        'script_caps', 'ignore', 'admit', 'app_defaults',
sqlite.go         'collision', 'dependency', 'apps' (a test without a
hwut.conf         header), 'execute', a choice-less test, 'target'
                  ('hwut.execute fixture open'); 'output' files;
                  'stderr_ignored'; '##! table unordered sep={;}'

screen.go         A TERMINAL PROGRAM'S SCREEN: 'hwutvterm' runs 'viewer.exe'
viewer.go         on a pseudo-terminal and presses its keys; the screen is
                  compared as seen -- 'regions', 'comment', 'whitespace'
                  off. Needs libvterm ('apt install libvterm0').

build.go          A PYPE NAMED IN THE HEADER, 'pype = "build.pypes"': a
build.pypes       system of two scripts; push/pop over nested
normalise.pype    directories, '<exit>', 'import:', a repeat group,
build.pype        'quantity(s)', '<bol>'/'<eol>', globs, 'flush';
compiler.pype     'same = true' -- serial and parallel share one GOOD;
                  'choices' as a list

Makefile, go.mod  the build: this directory is the module 'hwutdemo'; the
                  support's module is found as 'MAKE IT IMPORTABLE' says

GOOD FILES OF THEIR OWN (every other one is a link -- RATIONALE DEMO-GO-4)
------------------------------------------------------------------------------
screen.go open, scroll     the screen names 'viewer.exe', not 'viewer.py'
shop.go report             the frame log names 'shop.go', not 'shop.py'
shop.go report stock.csv   the same text as Python's; an output file
                           cannot link (bookkeeper B-32: only stdout links)

MAKE IT IMPORTABLE
------------------------------------------------------------------------------
Where the Go support was written out -- '<dir>/go', the module
'hwut/support/test_writing/go' -- one line makes it known to this
directory's Makefile, and to a test of your own built by a copy of it:

    export HWUT_SUPPORT_GO=<dir>/go

Go has no search path for a module; a test of your own with a 'go.mod' of
its own (and no copy of this Makefile) is pointed at the support once, in
its directory:

    go mod edit -require=hwut/support/test_writing/go@v0.0.0 -replace=hwut/support/test_writing/go=$HWUT_SUPPORT_GO

The test then writes, one line per package it uses:

    import "hwut/support/test_writing/go/hwutrunner"

(and '.../deterministicrandom', '.../deterministictimeline',
'.../spaceiterator', '.../hwutfsm', '.../hwuthocon', '.../hwutvterm',
'.../pytext'). Its header says 'build { framework = "make", target =
"%.exe" caps { file_size_mb = 256 } }' -- the cap because Go's runtime
archive exceeds the default 10 MB per file on a cold build cache.

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
