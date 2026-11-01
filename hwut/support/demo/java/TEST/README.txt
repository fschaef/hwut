==============================================================================
THE DEMONSTRATION OVER JAVA -- one test directory, everything a test
directory can say, each thing shown once
==============================================================================

    hwut --plain                    every test here: 27 ok
    hwut.report.features            every feature below, and the run that
                                    proves it ('hwut-features.conf')
    hwut.play <file> <choice>       one choice, built, run and shown
    hwut.config.show <file>         what hwut read, and from where

The Python demonstration ('../../python/TEST') in Java, file for file and
choice for choice, with the Java port of the test writing support
(support/test_writing/java, package 'hwut'). Its GOOD files are LINKS to
the Python demonstration's ('GOOD/*.link'): the Java tests print what the
Python tests print. Three do not, by nature -- they name a Java file
('../RATIONALE.txt', DEMO-JAVA-3).

Every test application is a file whose header ('@hwut { }', in the
file's first comment) is its whole configuration; 'hwut.conf' is what the
directory says. A file's comment says what each of its choices shows.
Where a run is seeded by the clock or the scheduler its output differs
from run to run, and every choice passes anyway.

A JAVA TEST IS BUILT, then run: its header says 'build { framework =
"make", executable = "%.exe" }', and hwut runs 'make x.exe' here, by the
'Makefile' beside it. 'make x.exe' compiles 'x.java' and the support
classes it uses into 'x.classes/' -- each its own directory, so tests
build at once -- and writes the launcher 'x.exe'. JDK 21; libvterm for
'screen.java' alone; libsqlite3 for the shop.

FILE              WHAT IT SHOWS
------------------------------------------------------------------------------
demo.java         THE COMPARISON'S TOLERANCES, one per choice
                  plain        exact, line by line
                  tolerance    'eq_pattern', 'numeric_ratio'
                  constraints  '((name: value))' judged by laws
                  analogies    '((handle))' consistent throughout
                  race         '##! potpourri': lines in any order
                  pool         '##! potpourri subset duplicates'
                  progress     'nothing': lines that count as none
                  lisp         'analogy' markers of one's own
                  clusters     '##! point-cloud ... pair dist=Linf'

chamber.java      REGIONS, UNITS, LAWS: '##! verbatim', '##! table',
                  '##! point-cloud', '##! ignore'; '((settle: 201 s))'
                  against 'settle <= 4 min'; a string law; a 'tolerance'
                  for every choice; '##' notes

protocol.sh       AN ORDER LAW AS A PYPE, fed live by a Java producer
producer.java     ('java producer.java', the single-file launcher):
                  clean, broken (the violation report as GOOD), slow
                  ('tick:' and a wait guard over 'pype.time()')
door.java         A PYPE THAT BINDS ITS VERDICT: 'door.pype' fires the
door.pype         door's events into a state machine; a known-broken
                  door whose GOOD is its breach report

garage.java       CASES GENERATED, NOT WRITTEN: 'SpaceIterator',
garage-space.hocon 'Hocon', 'DeterministicStream', 'TriggerDispatcher'
                  (races drawn as strings); 'HwutRunner' as front end,
                  'interactive = true'

shop.java         THE DIRECTORY'S WORD -- read 'hwut.conf' with it:
delivery.json     'on_entry'/'on_exit', 'on_before_test'/'on_after_test',
fixture.java      'script_caps', 'ignore', 'admit', 'app_defaults',
Sqlite.java       'collision', 'dependency', 'apps' (a test without a
hwut.conf         header), 'execute', a choice-less test, 'target'
                  ('hwut.execute fixture open'); 'output' files;
                  'stderr_ignored'; '##! table unordered sep={;}'.
                  SQLite through the library itself ('Sqlite.java')

screen.java       A TERMINAL PROGRAM'S SCREEN: 'VtermTerminal' runs
viewer.java       'viewer.exe' on a pseudo-terminal and presses its keys;
                  the screen is compared as seen -- 'regions', 'comment',
                  'whitespace' off. Needs libvterm ('apt install
                  libvterm0').

build.java        A PYPE NAMED IN THE HEADER, 'pype = "build.pypes"': a
build.pypes       system of two scripts; push/pop over nested
normalise.pype    directories, '<exit>', 'import:', a repeat group,
build.pype        'quantity(s)', '<bol>'/'<eol>', globs, 'flush';
compiler.pype     'same = true' -- serial and parallel share one GOOD;
                  'choices' as a list

Makefile          the builds -- and the ONE line that says where the
                  support stands ('HWUT-SUPPORT-PATH')

MAKE IT IMPORTABLE
------------------------------------------------------------------------------
Where the support was written to '<dir>' (the port at '<dir>/java'), one
line makes it importable for a test of your own -- Java's own CLASSPATH,
which javac searches for SOURCES too, so the classes a test uses are
compiled with it:

    export CLASSPATH="<dir>/java${CLASSPATH:+:$CLASSPATH}"

A test then writes

    import hwut.HwutRunner;

and is compiled and run (the support's terminal classes use the Foreign
Function & Memory API, a preview in JDK 21):

    javac --release 21 --enable-preview -d my-test.classes my-test.java
    java --enable-preview --enable-native-access=ALL-UNNAMED -cp my-test.classes MyTest

-- which the 'Makefile' here does for 'make my-test.exe'.

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
