==============================================================================
THE DEMONSTRATION OVER SCHEME (GNU GUILE) -- one test directory, everything
a test directory can say, each thing shown once
==============================================================================

    hwut --plain                    every test here: 27 ok
    hwut.report.features            every feature below, and the run that
                                    proves it ('hwut-features.conf')
    hwut.play <file> <choice>       one choice, run and shown
    hwut.config.show <file>         what hwut read, and from where

The same demonstration as '../../python/TEST', choice for choice: every
Python application has its Scheme application of the same stem, and its
GOOD files are '.link's to the Python demo's -- the same choice prints the
same text. Every '.scm' runs as 'guile --no-auto-compile <file> <choice>'
(the 'scheme' interpreter of 'hwut-root.conf'); nothing is built. A file's
header ';; @hwut { }' is its whole configuration; 'hwut.conf' is what the
directory says. Where a run is seeded by the clock or the scheduler its
output differs from run to run, and every choice passes anyway.

FILE              WHAT IT SHOWS
------------------------------------------------------------------------------
demo.scm          THE COMPARISON'S TOLERANCES, one per choice
                  plain        exact, line by line
                  tolerance    'eq_pattern', 'numeric_ratio'
                  constraints  '((name: value))' judged by laws
                  analogies    '((handle))' consistent throughout
                  race         '##! potpourri': lines in any order
                  pool         '##! potpourri subset duplicates'
                  progress     'nothing': lines that count as none
                  lisp         'analogy' markers of one's own
                  clusters     '##! point-cloud ... pair dist=Linf'

chamber.scm       REGIONS, UNITS, LAWS: '##! verbatim', '##! table',
                  '##! point-cloud', '##! ignore'; '((settle: 201 s))'
                  against 'settle <= 4 min'; a string law; a 'tolerance'
                  for every choice; '##' notes

protocol.sh       AN ORDER LAW AS A PYPE, fed live by a producer in Scheme
                  (five Guile threads): clean, broken (the violation
                  report as GOOD), slow ('tick:' and a wait guard over
                  'pype.time()')
door.scm          A PYPE THAT BINDS ITS VERDICT, the door's log fired into
door.pype         a state machine by the pype; a known-broken door whose
                  GOOD is its breach report

garage.scm        CASES GENERATED, NOT WRITTEN, by the Scheme test support:
garage-space.hocon '(hwut hocon)', '(hwut space-iterator)',
                  '(hwut deterministic-random)',
                  '(hwut deterministic-timeline)' (races drawn as
                  strings); '(hwut runner)' as front end,
                  'interactive = true'

shop.scm          THE DIRECTORY'S WORD -- read 'hwut.conf' with it:
shop-db.scm       'on_entry'/'on_exit', 'on_before_test'/'on_after_test',
delivery.json     'script_caps', 'ignore', 'admit', 'app_defaults',
fixture.scm       'collision', 'dependency', 'apps' (a test without a
hwut.conf         header), 'execute', a choice-less test, 'target'
                  ('hwut.execute fixture open'); 'output' files;
                  'stderr_ignored'; '##! table unordered sep={;}'.
                  SQLite through 'shop-db.scm': libsqlite3 by
                  '(system foreign)'

screen.scm        A TERMINAL PROGRAM'S SCREEN: '(hwut vterm)' runs
viewer.scm        'viewer.scm' on a pseudo-terminal and presses its keys;
                  the screen is compared as seen -- 'regions', 'comment',
                  'whitespace' off. Needs libvterm ('apt install
                  libvterm0').

build.scm         A PYPE NAMED IN THE HEADER, 'pype = "build.pypes"': a
build.pypes       system of two scripts; push/pop over nested
normalise.pype    directories, '<exit>', 'import:', a repeat group,
build.pype        'quantity(s)', '<bol>'/'<eol>', globs, 'flush';
compiler.pype     'same = true' -- serial and parallel share one GOOD;
                  'choices' as a list

support-path.scm  WHERE THE SUPPORT STANDS, said once (the line marked
                  'HWUT-SUPPORT-PATH'): appended to '%load-path' after
                  GUILE_LOAD_PATH, so GUILE_LOAD_PATH wins

The pypes ('.pype', '.pypes') are hwut's, in Python, whatever the
application's language: they stay as the Python demo has them.

THREE GOOD FILES OF THEIR OWN (see '../RATIONALE.txt', DEMO-GUILE-2): the
output names this language's files -- 'screen.scm--open', '--scroll'
("> viewer.scm"), 'shop.scm--report' ("shop.scm sell" in the frame log) --
and 'shop.scm--report.stock.csv', the same bytes as the Python one, is a
copy: a '.link' holds stdout only.

MAKE IT IMPORTABLE
------------------------------------------------------------------------------
The support written to '<dir>' (the port at '<dir>/guile', its modules in
'<dir>/guile/hwut/'), one line makes it importable for a test of your own:

    export GUILE_LOAD_PATH=<dir>/guile${GUILE_LOAD_PATH:+:$GUILE_LOAD_PATH}

and the test then writes

    (use-modules (hwut runner))           ; and (hwut vterm), (hwut hocon), ...

NOT HERE, ON PURPOSE
------------------------------------------------------------------------------
'language-setup', 'variant_group', 'procsitter', 'free_disk_min_mb'
                  the root's alone ('hwut-root.conf')
'build'           a compiled test application's word: Guile interprets,
                  so this directory has no Makefile
'##! unaccepted', '##! constraint-violation'
                  written by hwut itself, into a recording or a GOOD
'diff_display_parameters'
                  how a difference is shown, not what passes
==============================================================================
