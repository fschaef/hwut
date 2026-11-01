==============================================================================
THE DEMONSTRATION OVER ERLANG -- one test directory, everything a test
directory can say, each thing shown once
==============================================================================

    hwut --plain                    every test here: 27 ok
    hwut.report.features            every feature below, and the run that
                                    proves it ('hwut-features.conf')
    hwut.play <file> <choice>       one choice, run and shown
    hwut.config.show <file>         what hwut read, and from where

The Python demonstration ('../../python/TEST'), choice for choice, in
Erlang: the same stems, '.erl' for '.py', the same data files, and the
SAME GOOD FILES -- 'GOOD/*.link' names the Python demonstration's text
wherever the output is the same; four cases have a GOOD of their own (see
'../RATIONALE.txt', DEMO-ERLANG-7).

Every test application is an ESCRIPT -- 'hwut-root.conf' runs '.erl' with
'escript' -- whose header ('%% @hwut { }', line 1 onwards: escript skips
line 1) is its whole configuration; 'hwut.conf' is what the directory
says. A file's comment says what each of its choices shows. Where a run
is seeded by the clock or the scheduler its output differs from run to
run, and every choice passes anyway. Nothing is built here.

FILE              WHAT IT SHOWS
------------------------------------------------------------------------------
demo.erl          THE COMPARISON'S TOLERANCES, one per choice
                  plain        exact, line by line
                  tolerance    'eq_pattern', 'numeric_ratio'
                  constraints  '((name: value))' judged by laws
                  analogies    '((handle))' consistent throughout
                  race         '##! potpourri': lines in any order
                  pool         '##! potpourri subset duplicates'
                  progress     'nothing': lines that count as none
                  lisp         'analogy' markers of one's own
                  clusters     '##! point-cloud ... pair dist=Linf'

chamber.erl       REGIONS, UNITS, LAWS: '##! verbatim', '##! table',
                  '##! point-cloud', '##! ignore'; '((settle: 201 s))'
                  against 'settle <= 4 min'; a string law; a 'tolerance'
                  for every choice; '##' notes

protocol.sh       AN ORDER LAW AS A PYPE, fed live by an Erlang producer
                  ('erl -eval', five client processes): clean, broken (the
                  violation report as GOOD), slow ('tick:' and a wait
                  guard over 'pype.time()')
door.erl          A PYPE THAT BINDS ITS VERDICT: 'door.pype' fires the
door.pype         door's events into a state machine (a pype script is
                  Python: the model is Python's 'hwut_fsm'); a door that
                  keeps the model, and one whose GOOD is its breaches

garage.erl        CASES GENERATED, NOT WRITTEN: 'space_iterator',
garage-space.hocon 'hwut_hocon', 'deterministic_random',
                  'deterministic_timeline' (races drawn as strings);
                  'hwut_runner' as front end, 'interactive = true'

shop.erl          THE DIRECTORY'S WORD -- read 'hwut.conf' with it:
delivery.json     'on_entry'/'on_exit', 'on_before_test'/'on_after_test',
fixture.erl       'script_caps', 'ignore', 'admit', 'app_defaults',
shop_db.hrl       'collision', 'dependency', 'apps' (a test without a
hwut.conf         header), 'execute', a choice-less test, 'target'
                  ('hwut.execute fixture open'); 'output' files;
                  'stderr_ignored'; '##! table unordered sep={;}'

screen.erl        A TERMINAL PROGRAM'S SCREEN: hwut_vterm runs 'viewer.erl'
viewer.erl        on a pseudo-terminal and presses its keys; the screen is
                  compared as seen -- 'regions', 'comment', 'whitespace'
                  off. Needs libvterm ('apt install libvterm0') and a C
                  compiler (the support's port program).

build.erl         A PYPE NAMED IN THE HEADER, 'pype = "build.pypes"': a
build.pypes       system of two scripts; push/pop over nested
normalise.pype    directories, '<exit>', 'import:', a repeat group,
build.pype        'quantity(s)', '<bol>'/'<eol>', globs, 'flush';
compiler.pype     'same = true' -- serial and parallel share one GOOD;
                  'choices' as a list

hwut_support.hrl  WHERE THE SUPPORT STANDS, the one line that says it
                  (the marked line): 'ERL_LIBS' first, else the
                  support beside this demonstration -- built there, where
                  stale, on first use

MAKE IT IMPORTABLE
------------------------------------------------------------------------------
The support written to '<dir>', the Erlang port at '<dir>/erlang':

    make -C <dir>/erlang            its modules into '<dir>/erlang/ebin'
    export ERL_LIBS=<dir>           the VM puts '<dir>/*/ebin' on its
                                    code path when it starts

A test of one's own then imports nothing: Erlang calls a module by its
name, 'hwut_runner:run(Argv, Title, #{"plain" => fun plain/0})'. The one
line a test writes is for the records of the HOCON tree, where it reads
one:

    -include_lib("erlang/hwut_hocon.hrl").

'hwut_vterm' builds its port program in '<dir>/erlang' on first use from
the C port's 'hwut_vterm.c': it wants '<dir>/c' beside it.

NOT HERE, ON PURPOSE
------------------------------------------------------------------------------
'language-setup', 'variant_group', 'procsitter', 'free_disk_min_mb'
                  the root's alone ('hwut-root.conf')
'build'           a compiled test application's word: an escript is run
                  as it stands
'##! unaccepted', '##! constraint-violation'
                  written by hwut itself, into a recording or a GOOD
'diff_display_parameters'
                  how a difference is shown, not what passes
script_runner     a fixture for hwut's own tests of its faces
==============================================================================
