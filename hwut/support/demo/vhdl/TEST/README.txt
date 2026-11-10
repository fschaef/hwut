==============================================================================
THE DEMONSTRATION OVER VHDL -- one test directory, everything a test
directory can say, each thing shown once
==============================================================================

    hwut --plain                    every test here: 27 ok
    hwut.report.features            every feature, and the run that proves
                                    it -- this port's one is 'demo-vhdl'
    hwut.play <file> <choice>       one choice, run and shown
    hwut.config.show <file>         what hwut read, and from where

The Python demonstration ('../../python/TEST'), program for program and
choice for choice, written in VHDL-2008 over the VHDL test support
('support/test_writing/vhdl'). Every test application is a file whose
header ('-- @hwut { }') is its whole configuration; 'hwut.conf' is what the
directory says. Its GOOD files are LINKS to the Python demonstration's
('GOOD/*.link'): the VHDL programs print the same. Three are this
directory's own, because what they print names this directory's files
(RATIONALE DEMO-VHDL-4). Where a run is seeded by the clock its output
differs from run to run, and every choice passes anyway.

HOW IT RUNS. VHDL reads no command line and GHDL's mcode backend writes no
executable: hwut builds 'x.exe' by the header's 'build' with 'Makefile' --
a launcher ('demo_launch.sh') that runs the design analysed into 'x.work'
by 'ghdl -r', the command line handed in as generics, and the C the design
calls by VHPIDIRECT in 'x.work/libhwut_vhdl.so'. Each test builds its own
'x.work': several build at once and share nothing.

FILE              WHAT IT SHOWS
------------------------------------------------------------------------------
demo.vhd          THE COMPARISON'S TOLERANCES, one per choice: plain,
                  tolerance, constraints, analogies, race, pool, progress,
                  lisp, clusters -- the workers of 'race' and 'pool' are
                  processes waiting drawn times of the simulation

chamber.vhd       REGIONS, UNITS, LAWS: '##! verbatim', '##! table',
                  '##! point-cloud', '##! ignore'; '((settle: 201 s))'
                  against 'settle <= 4 min'; a string law; a 'tolerance'
                  for every choice; '##' notes

protocol.sh       AN ORDER LAW AS A PYPE, fed live by a producer in VHDL
producer.vhd      ('producer.vhd', five clients as five processes): clean,
                  broken (the violation report as GOOD), slow ('tick:' and
                  a wait guard over 'pype.time()'). The test itself stays a
                  bash script: it is the plumbing between two programs.

door.vhd          A PYPE THAT BINDS ITS VERDICT: the door's log, fired by
door.pype         'door.pype' into a state machine; a known-broken door
                  whose GOOD is its violation report

garage.vhd        CASES GENERATED, NOT WRITTEN: 'SpaceIterator' over
garage-space.hocon 'hwut_hocon', 'DeterministicStream',
                  'deterministic_timeline' (races drawn as strings; a gate
                  a trigger kind); 'HwutRunner' as front end,
                  'interactive = true'

shop.vhd          THE DIRECTORY'S WORD -- read 'hwut.conf' with it:
delivery.json     'on_entry'/'on_exit', 'on_before_test'/'on_after_test',
fixture.vhd       'script_caps', 'ignore', 'admit', 'app_defaults',
hwut.conf         'collision', 'dependency', 'apps' (a test without a
                  header), 'execute', a choice-less test, 'target'
                  ('hwut.execute fixture open'); 'output' files;
                  'stderr_ignored'; '##! table unordered sep={;}'. The
                  stock is SQLite's, by VHPIDIRECT ('demo_sql.vhd').

screen.vhd        A TERMINAL PROGRAM'S SCREEN: the support's Terminal runs
viewer.vhd        'viewer.exe' on a pseudo-terminal and presses its keys;
                  the screen is compared as seen -- 'regions', 'comment',
                  'whitespace' off. Needs libvterm ('apt install
                  libvterm0').

build.vhd         A PYPE NAMED IN THE HEADER, 'pype = "build.pypes"': a
build.pypes       system of two scripts; push/pop over nested
normalise.pype    directories, '<exit>', 'import:', a repeat group,
build.pype        'quantity(s)', '<bol>'/'<eol>', globs, 'flush';
compiler.pype     'same = true' -- serial and parallel share one GOOD;
                  'choices' as a list

Makefile          the build of every program, and WHERE THE SUPPORT
demo_launch.sh    STANDS (its line marked 'HWUT-SUPPORT-PATH'); the
demo_vhpi.vhd     launcher; what VHDL cannot do itself -- the clock, files,
demo_vhpi.c       stderr, SQLite, a raw terminal -- by VHPIDIRECT
demo_sql.vhd

MAKE IT IMPORTABLE
------------------------------------------------------------------------------
Where the support was written to <dir> -- the VHDL port at <dir>/vhdl, the
C modules it wraps beside it at <dir>/c -- one line makes it the support
of every test built by a Makefile of this directory's kind:

    export HWUT_SUPPORT_VHDL=<dir>/vhdl

A test of one's own takes 'Makefile' over (its '%.exe' rule analyses the
support's packages into the test's own work directory and builds its
'libhwut_vhdl.so') and then writes, before its entity:

    use work.hwut_runner.all;

WANTED: GHDL with VHDL-2008 (measured: 4.1.0, mcode), a C99 compiler,
make, libsqlite3 (for the shop), libvterm at run time (for the screen),
and python3 with hwut for the pype scripts.

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
