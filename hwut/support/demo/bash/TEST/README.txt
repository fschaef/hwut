==============================================================================
THE DEMONSTRATION OVER BASH -- one test directory, everything a test
directory can say, each thing shown once
==============================================================================

    hwut --plain                    every test here: 27 ok
    hwut.report.features            every feature, and the run that proves
                                    it -- this port's one is 'demo-bash'
    hwut.play <file> <choice>       one choice, run and shown
    hwut.config.show <file>         what hwut read, and from where

The Python demonstration ('../../python/TEST'), choice for choice, in bash,
with the bash port of the test writing support. Its GOOD files are LINKS to
the Python demonstration's ('GOOD/*.link'): the bash tests print the same
text. Three print what by nature differs -- they name a bash file -- and a
fourth subject may not link (see '../RATIONALE.txt').

Every test application is a file whose header ('@hwut { }') is its whole
configuration; 'hwut.conf' is what the directory says. A file's comment
says what each of its choices shows; where it says no more than its Python
twin, it points there. Where a run is seeded by the clock or the scheduler
its output differs from run to run, and every choice passes anyway.

FILE              WHAT IT SHOWS
------------------------------------------------------------------------------
demo.sh           THE COMPARISON'S TOLERANCES, one per choice
                  plain        exact, line by line
                  tolerance    'eq_pattern', 'numeric_ratio'
                  constraints  '((name: value))' judged by laws
                  analogies    '((handle))' consistent throughout
                  race         '##! potpourri': lines in any order
                  pool         '##! potpourri subset duplicates'
                  progress     'nothing': lines that count as none
                  lisp         'analogy' markers of one's own
                  clusters     '##! point-cloud ... pair dist=Linf'

chamber.sh        REGIONS, UNITS, LAWS: '##! verbatim', '##! table',
                  '##! point-cloud', '##! ignore'; '((settle: 201 s))'
                  against 'settle <= 4 min'; a string law; a 'tolerance'
                  for every choice; '##' notes

protocol.sh       AN ORDER LAW AS A PYPE, fed live by a bash producer:
                  clean, broken (the violation report as GOOD), slow
                  ('tick:' and a wait guard over 'pype.time()')
door.sh           A PYPE THAT BINDS ITS VERDICT: 'door.pype' fires the
door.pype         log's events into a state machine; a known-broken door
                  whose GOOD is its breach report

garage.sh         CASES GENERATED, NOT WRITTEN: 'space_iterator.sh',
garage-space.hocon 'hwut_hocon.sh', 'dr_stream' (deterministic_random.sh),
                  'deterministic_timeline.sh' (races drawn as strings);
                  'hwut_runner.sh' as front end, 'interactive = true'

shop.sh           THE DIRECTORY'S WORD -- read 'hwut.conf' with it:
delivery.json     'on_entry'/'on_exit', 'on_before_test'/'on_after_test',
fixture.sh        'script_caps', 'ignore', 'admit', 'app_defaults',
hwut.conf         'collision', 'dependency', 'apps' (a test without a
                  header), 'execute', a choice-less test, 'target'
                  ('hwut.execute fixture open'); 'output' files;
                  'stderr_ignored'; '##! table unordered sep={;}'

screen.sh         A TERMINAL PROGRAM'S SCREEN: hwut_vterm.sh runs
viewer.sh         'viewer.sh' on a pseudo-terminal and presses its keys;
                  the screen is compared as seen -- 'regions', 'comment',
                  'whitespace' off. Needs libvterm ('apt install
                  libvterm0'), cc and make (the port builds its server).

build.sh          A PYPE NAMED IN THE HEADER, 'pype = "build.pypes"': a
build.pypes       system of two scripts; push/pop over nested
normalise.pype    directories, '<exit>', 'import:', a repeat group,
build.pype        'quantity(s)', '<bol>'/'<eol>', globs, 'flush';
compiler.pype     'same = true' -- serial and parallel share one GOOD;
                  'choices' as a list

support.sh        WHERE THE BASH SUPPORT STANDS, for every test here: the
                  one line marked 'HWUT-SUPPORT-PATH'

MAKE IT IMPORTABLE
------------------------------------------------------------------------------
Bash looks a sourced name without '/' up on PATH ('shopt sourcepath', on
by default). With the support written to '<dir>' -- the bash port at
'<dir>/bash' -- one line, in the shell that runs hwut:

    export PATH="<dir>/bash:$PATH"

and a test of one's own then writes:

    source hwut_runner.sh

(and 'source space_iterator.sh', 'source hwut_vterm.sh', ... as it needs).
'hwut_vterm.sh' wants cc and make besides libvterm: it builds its server
in '<dir>/bash' on first use, from the C port's 'hwut_vterm.c', which it
expects at '<dir>/c'.

NOT HERE, ON PURPOSE
------------------------------------------------------------------------------
'language-setup', 'variant_group', 'procsitter', 'free_disk_min_mb'
                  the root's alone ('hwut-root.conf')
'build'           nothing is built: bash runs each '.sh' as it stands
'##! unaccepted', '##! constraint-violation'
                  written by hwut itself, into a recording or a GOOD
'diff_display_parameters'
                  how a difference is shown, not what passes
==============================================================================
