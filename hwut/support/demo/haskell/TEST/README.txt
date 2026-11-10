==============================================================================
THE DEMONSTRATION OVER HASKELL -- one test directory, everything a test
directory can say, each thing shown once
==============================================================================

    hwut --plain                    every test here: 27 ok
    hwut.report.features            every feature, and the run that proves
                                    it -- this port's one is 'demo-haskell'
    hwut.play <file> <choice>       one choice, run and shown
    hwut.config.show <file>         what hwut read, and from where

The Python demonstration ('../../python/TEST'), choice for choice, written
in Haskell (GHC) over the Haskell port of the test writing support. Every
test application is a file whose header ('-- @hwut { }') is its whole
configuration; 'hwut.conf' is what the directory says. A file's comment
says what each of its choices shows. Where a run is seeded by the clock or
the scheduler its output differs from run to run, and every choice passes
anyway. The GOOD files are the Python demonstration's, by '.link', but
where the output names a Haskell file ('../RATIONALE.txt', DEMO-HASKELL-3).

BUILT, NOT INTERPRETED: each test's header says 'build { framework = "make",
target = "%.exe" }'; hwut runs 'make demo.exe' HERE, where the
'Makefile' stands, and runs 'demo.exe <choice>'. 'on_entry' builds the
helpers no header builds. GHC with its boot packages, make, a C compiler
(for 'screen.hs'), libsqlite3 and libvterm -- no cabal, no Hackage.

FILE              WHAT IT SHOWS
------------------------------------------------------------------------------
demo.hs           THE COMPARISON'S TOLERANCES, one per choice
                  plain        exact, line by line
                  tolerance    'eq_pattern', 'numeric_ratio'
                  constraints  '((name: value))' judged by laws
                  analogies    '((handle))' consistent throughout
                  race         '##! potpourri': lines in any order
                  pool         '##! potpourri subset duplicates'
                  progress     'nothing': lines that count as none
                  lisp         'analogy' markers of one's own
                  clusters     '##! point-cloud ... pair dist=Linf'

chamber.hs        REGIONS, UNITS, LAWS: '##! verbatim', '##! table',
                  '##! point-cloud', '##! ignore'; '((settle: 201 s))'
                  against 'settle <= 4 min'; a string law; a 'tolerance'
                  for every choice; '##' notes

protocol.sh       AN ORDER LAW AS A PYPE, fed live by a Haskell producer
producer.hs       ('producer.exe'): clean, broken (the violation report as
                  GOOD), slow ('tick:' and a wait guard over 'pype.time()')
door.hs           A PYPE THAT BINDS ITS VERDICT: 'door.pype' fires the log's
door.pype         events into the door's state machine (the pype is Python
                  whatever the program is: its model is the Python
                  support's 'hwut_fsm'); a door that keeps the model, one
                  that breaks it, whose GOOD is its violation report

garage.hs         CASES GENERATED, NOT WRITTEN: 'Hwut.SpaceIterator',
garage-space.hocon 'Hwut.Hocon', 'Hwut.DeterministicRandom',
                  'Hwut.DeterministicTimeline' (races drawn as strings);
                  'Hwut.Runner' as front end, 'interactive = true'

shop.hs           THE DIRECTORY'S WORD -- read 'hwut.conf' with it:
delivery.json     'on_entry'/'on_exit', 'on_before_test'/'on_after_test',
fixture.hs        'script_caps', 'ignore', 'admit', 'app_defaults',
hwut.conf         'collision', 'dependency', 'apps' (a test without a
                  header), 'execute', a choice-less test, 'target'
                  ('hwut.execute fixture open'); 'output' files;
                  'stderr_ignored'; '##! table unordered sep={;}'
Sqlite.hs         SQLite for both, bound to the C library by the FFI

screen.hs         A TERMINAL PROGRAM'S SCREEN: 'Hwut.Vterm' runs 'viewer.exe'
viewer.hs         on a pseudo-terminal and presses its keys; the screen is
                  compared as seen -- 'regions', 'comment', 'whitespace'
                  off. Needs libvterm ('apt install libvterm0').

build.hs          A PYPE NAMED IN THE HEADER, 'pype = "build.pypes"': a
build.pypes       system of two scripts; push/pop over nested
normalise.pype    directories, '<exit>', 'import:', a repeat group,
build.pype        'quantity(s)', '<bol>'/'<eol>', globs, 'flush';
compiler.pype     'same = true' -- serial and parallel share one GOOD;
                  'choices' as a list

ClockRandom.hs    a random generator seeded by the clock, for the tests
                  whose runs differ on purpose (GHC ships no 'random')
Makefile          how each program is built; where the support stands

MAKE IT IMPORTABLE
------------------------------------------------------------------------------
Where the support was written to '<dir>' (the port at '<dir>/haskell', the C
port it binds for 'Hwut.Vterm' at '<dir>/c'), one line makes it importable
for a test of one's own:

    export HWUT_SUPPORT_HASKELL=<dir>/haskell

GHC has no variable of the environment for a directory to import modules
from: a build names it, as the Makefile here does ('-i$(SUPPORT)', the
variable winning over the directory beside):

    ghc --make -dynamic -package-env - -i$HWUT_SUPPORT_HASKELL -outputdir build-x -o x.exe x.hs

The test then writes

    import Hwut.Runner

(and 'Hwut.DeterministicRandom', 'Hwut.SpaceIterator', ... as it needs).
A test of 'Hwut.Vterm' builds as 'screen.exe' does: 'hsc2hs' over
'$HWUT_SUPPORT_HASKELL/Hwut/Vterm.hsc', 'cc' over '<dir>/c/hwut_vterm.c'
('Makefile', 'screen.exe').

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
