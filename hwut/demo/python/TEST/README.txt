==============================================================================
THE DEMONSTRATION OVER PYTHON -- one test directory, everything a test
directory can say, each thing shown once
==============================================================================

    hwut --plain                    every test here: 28 ok
    hwut.report.features            every feature below, and the run that
                                    proves it ('hwut-features.conf')
    hwut.play <file> <choice>       one choice, run and shown
    hwut.config.show <file>         what hwut read, and from where

Every test application is a file whose header ('@hwut { }') is its whole
configuration; 'hwut.conf' is what the directory says. A file's comment
says what each of its choices shows. Where a run is seeded by the clock or
the scheduler its output differs from run to run, and every choice passes
anyway.

FILE              WHAT IT SHOWS
------------------------------------------------------------------------------
demo.py           THE COMPARISON'S TOLERANCES, one per choice
                  plain        exact, line by line
                  tolerance    'eq_pattern', 'numeric_ratio'
                  constraints  '((name: value))' judged by laws
                  analogies    '((handle))' consistent throughout
                  race         '##! potpourri': lines in any order
                  pool         '##! potpourri subset duplicates'
                  progress     'nothing': lines that count as none
                  lisp         'analogy' markers of one's own
                  clusters     '##! point-cloud ... pair dist=Linf'

chamber.py        REGIONS, UNITS, LAWS: '##! verbatim', '##! table',
                  '##! point-cloud', '##! ignore'; '((settle: 201 s))'
                  against 'settle <= 4 min'; a string law; a 'tolerance'
                  for every choice; '##' notes

protocol.sh       AN ORDER LAW AS A PYPE, fed live by a bash producer:
                  clean, broken (the violation report as GOOD), slow
                  ('tick:' and a wait guard over 'pype.time()')
door.py           A PYPE THAT BINDS ITS VERDICT, '((breaches: N))', judged
door.pype         by the header; modes inheriting two bases; 'caps'; a
                  known-broken version whose GOOD is its violation
                  report; potpourri against pype; analogies in a region

garage.py         CASES GENERATED, NOT WRITTEN: 'space_iterator',
garage-space.hocon 'hwut_hocon', 'DeterministicStream',
                  'deterministic_timeline' (races drawn as strings);
                  'HwutRunner' as front end, 'interactive = true'

shop.py           THE DIRECTORY'S WORD -- read 'hwut.conf' with it:
delivery.json     'on_entry'/'on_exit', 'on_before_test'/'on_after_test',
fixture.py        'script_caps', 'ignore', 'admit', 'app_defaults',
hwut.conf         'collision', 'dependency', 'apps' (a test without a
                  header), 'execute', a choice-less test, 'target'
                  ('hwut.execute fixture open'); 'output' files;
                  'stderr_ignored'; '##! table unordered sep={;}'

screen.py         A TERMINAL PROGRAM'S SCREEN: hwut_vterm runs 'viewer.py'
viewer.py         on a pseudo-terminal and presses its keys; the screen is
                  compared as seen -- 'regions', 'comment', 'whitespace'
                  off. Needs libvterm ('apt install libvterm0').

build.py          A PYPE NAMED IN THE HEADER, 'pype = "build.pypes"': a
build.pypes       system of two scripts; push/pop over nested
normalise.pype    directories, '<exit>', 'import:', a repeat group,
build.pype        'quantity(s)', '<bol>'/'<eol>', globs, 'flush';
compiler.pype     'same = true' -- serial and parallel share one GOOD;
                  'choices' as a list

NOT HERE, ON PURPOSE
------------------------------------------------------------------------------
'language-setup', 'variant_group', 'procsitter', 'free_disk_min_mb'
                  the root's alone ('hwut-root.conf', which
                  'hwut.demo.python' writes beside this directory)
'build'           a compiled test application's word: the demonstrations
                  over compiled languages
'##! unaccepted', '##! constraint-violation'
                  written by hwut itself, into a recording or a GOOD
'diff_display_parameters'
                  how a difference is shown, not what passes
script_runner     a fixture for hwut's own tests of its faces
==============================================================================
