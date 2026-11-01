==============================================================================
THE DEMONSTRATION OVER PROLOG -- one test directory, everything a test
directory can say, each thing shown once (SWI-Prolog 9)
==============================================================================

    hwut --plain                    every test here: 27 ok
    hwut.report.features            every feature below, and the run that
                                    proves it ('hwut-features.conf')
    hwut.play <file> <choice>       one choice, run and shown
    hwut.config.show <file>         what hwut read, and from where

The same demonstration as '../../python/TEST', choice for choice, written in
Prolog over the Prolog test support ('support/test_writing/prolog'). hwut
runs a '.pro' with the 'swipl' interpreter of 'hwut-root.conf': 'swipl
demo.pro <choice>'. Every test application is a file whose header ('% @hwut
{ }') is its whole configuration; 'hwut.conf' is what the directory says. A
file's comment says what each of its choices shows. Where a run is seeded
by the clock or the scheduler its output differs from run to run, and every
choice passes anyway.

THE GOOD FILES ARE THE PYTHON DEMONSTRATION'S: 'GOOD/<file>.pro--<choice>.link'
names '../../python/TEST/GOOD/<file>.py--<choice>.txt' -- the Prolog program
prints the same text. Three cases have a GOOD of their own -- what they
print names a Prolog file -- and the output file 'stock.csv', which no
link may stand for ('../RATIONALE.txt', DEMO-PROLOG-2).

FILE              WHAT IT SHOWS
------------------------------------------------------------------------------
demo.pro          THE COMPARISON'S TOLERANCES, one per choice
                  plain        exact, line by line
                  tolerance    'eq_pattern', 'numeric_ratio'
                  constraints  '((name: value))' judged by laws
                  analogies    '((handle))' consistent throughout
                  race         '##! potpourri': lines in any order
                  pool         '##! potpourri subset duplicates'
                  progress     'nothing': lines that count as none
                  lisp         'analogy' markers of one's own
                  clusters     '##! point-cloud ... pair dist=Linf'

chamber.pro       REGIONS, UNITS, LAWS: '##! verbatim', '##! table',
                  '##! point-cloud', '##! ignore'; '((settle: 201 s))'
                  against 'settle <= 4 min'; a string law; a 'tolerance'
                  for every choice; '##' notes

protocol.sh       AN ORDER LAW AS A PYPE, fed live by a Prolog producer
                  (a heredoc, five client threads): clean, broken (the
                  violation report as GOOD), slow ('tick:' and a wait
                  guard over 'pype.time()')
door.pro          A PYPE THAT BINDS ITS VERDICT, the door's model fired by
door.pype         'hwut_fsm'; a known-broken version whose GOOD is its
                  violation report

garage.pro        CASES GENERATED, NOT WRITTEN: 'space_point',
garage-space.hocon 'hwut_hocon', 'dr_stream_new' (the deterministic
                  stream), 'deterministic_timeline' (races drawn as
                  strings); 'hwut_runner_run' as front end,
                  'interactive = true'

shop.pro          THE DIRECTORY'S WORD -- read 'hwut.conf' with it:
delivery.json     'on_entry'/'on_exit', 'on_before_test'/'on_after_test',
fixture.pro       'script_caps', 'ignore', 'admit', 'app_defaults',
hwut.conf         'collision', 'dependency', 'apps' (a test without a
shop_db.pro       header), 'execute', a choice-less test, 'target'
                  ('hwut.execute fixture open'); 'output' files;
                  'stderr_ignored'; '##! table unordered sep={;}'.
                  SQLite through 'shop_db.pro', a foreign library built
                  here by 'make' ('Makefile', 'shop_db4pl.c') when it is
                  first loaded

screen.pro        A TERMINAL PROGRAM'S SCREEN: hwut_vterm runs 'viewer.pro'
viewer.pro        on a pseudo-terminal and presses its keys; the screen is
                  compared as seen -- 'regions', 'comment', 'whitespace'
                  off. Needs libvterm ('apt install libvterm0').

build.pro         A PYPE NAMED IN THE HEADER, 'pype = "build.pypes"': a
build.pypes       system of two scripts; push/pop over nested
normalise.pype    directories, '<exit>', 'import:', a repeat group,
build.pype        'quantity(s)', '<bol>'/'<eol>', globs, 'flush';
compiler.pype     'same = true' -- serial and parallel share one GOOD;
                  'choices' as a list

support_path.pro  WHERE THE SUPPORT STANDS, named once (below)

WHAT IT WANTS
------------------------------------------------------------------------------
SWI-Prolog 9 ('swipl'), a C compiler and make (two foreign libraries are
built on first load: the support's 'hwut_vterm4pl.so', this directory's
'shop_db4pl.so'), SWI-Prolog's header 'SWI-Prolog.h' (it comes with the
'swi-prolog' package), libvterm and libsqlite3 at run time (both loaded by
'dlopen': no header of either is needed), and python3 for hwut's pype.

MAKE IT IMPORTABLE
------------------------------------------------------------------------------
Where the support was written to '<dir>' (the Prolog port at
'<dir>/prolog'), one line makes it loadable by a test of your own:

    export HWUT_SUPPORT_PROLOG=<dir>/prolog

SWI-Prolog has no environment variable for its library path, so the
variable names the directory and the test makes it the alias 'hwut' --
then loads what it uses by that alias:

    :- getenv('HWUT_SUPPORT_PROLOG', Dir), asserta(user:file_search_path(hwut, Dir)).
    :- use_module(hwut('hwut_runner.pro')).

'hwut_vterm.pro' builds its foreign library in '<dir>/prolog' on first
load: that directory must be writable. Here, 'support_path.pro' does the
first line for every test, and falls back to the support beside this
tree where the variable is not set.

NOT HERE, ON PURPOSE
------------------------------------------------------------------------------
'language-setup', 'variant_group', 'procsitter', 'free_disk_min_mb'
                  the root's alone ('hwut-root.conf')
'build'           a compiled test application's word: the demonstrations
                  over compiled languages. The two foreign libraries are
                  built by the modules that load them, not by hwut
'##! unaccepted', '##! constraint-violation'
                  written by hwut itself, into a recording or a GOOD
'diff_display_parameters'
                  how a difference is shown, not what passes
script_runner     a fixture for hwut's own tests of its faces
==============================================================================
