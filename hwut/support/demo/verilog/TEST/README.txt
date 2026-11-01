==============================================================================
THE DEMONSTRATION OVER SYSTEMVERILOG (Verilator) -- one test directory,
everything a test directory can say, each thing shown once
==============================================================================

    hwut --plain                    every test here: 27 ok
    hwut.report.features            every feature below, and the run that
                                    proves it ('hwut-features.conf')
    hwut.play <file> <choice>       one choice, run and shown
    hwut.config.show <file>         what hwut read, and from where

The same demonstration as '../../python/TEST', choice for choice, the same
GOOD files -- linked, not copied (RATIONALE DEMO-VERILOG-1). Every test
application is a '.sv' file whose header ('// @hwut { }') is its whole
configuration, its 'build' included: hwut runs 'make <stem>.exe' here, where
the 'Makefile' stands, and calls the simulation with the choice. 'hwut.conf'
is what the directory says. A file's comment says what each of its choices
shows. Where a run is seeded anew ('/dev/urandom') its output differs from
run to run, and every choice passes anyway.

WANTS: Verilator 5 (measured: 5.020) with g++, a C compiler, make; libsqlite3
for the shop, libvterm for the screen ('apt install libvterm0'). A first run
builds ten simulations, some 30 s to 2 min each.

FILE              WHAT IT SHOWS
------------------------------------------------------------------------------
demo.sv           THE COMPARISON'S TOLERANCES, one per choice
                  plain        exact, line by line
                  tolerance    'eq_pattern', 'numeric_ratio'
                  constraints  '((name: value))' judged by laws
                  analogies    '((handle))' consistent throughout
                  race         '##! potpourri': lines in any order
                  pool         '##! potpourri subset duplicates'
                  progress     'nothing': lines that count as none
                  lisp         'analogy' markers of one's own
                  clusters     '##! point-cloud ... pair dist=Linf'

chamber.sv        REGIONS, UNITS, LAWS: '##! verbatim', '##! table',
                  '##! point-cloud', '##! ignore'; '((settle: 201 s))'
                  against 'settle <= 4 min'; a string law; a 'tolerance'
                  for every choice; '##' notes

protocol.sh       AN ORDER LAW AS A PYPE, fed live by a SystemVerilog
producer.sv       producer ('producer.exe'): clean, broken (the violation
                  report as GOOD), slow ('tick:' and a wait guard over
                  'pype.time()')
door.sv           A PYPE THAT BINDS ITS VERDICT, '((breaches: N))', judged
door.pype         by the header; modes inheriting two bases; 'caps'; a
                  known-broken version whose GOOD is its violation
                  report; potpourri against pype; analogies in a region

garage.sv         CASES GENERATED, NOT WRITTEN: 'SpaceIterator',
garage-space.hocon 'hwut_hocon', 'DeterministicStream',
                  'deterministic_timeline' (races drawn as strings);
                  'HwutRunner' as front end, 'interactive = true'

shop.sv           THE DIRECTORY'S WORD -- read 'hwut.conf' with it:
shop_db.sv        'on_entry'/'on_exit', 'on_before_test'/'on_after_test',
delivery.json     'script_caps', 'ignore', 'admit', 'app_defaults',
fixture.sv        'collision', 'dependency', 'apps' (a test without a
hwut.conf         header), 'execute', a choice-less test, 'target'
                  ('hwut.execute fixture open'); 'output' files;
                  'stderr_ignored'; '##! table unordered sep={;}'.
                  SQLite through DPI-C ('-lsqlite3')

screen.sv         A TERMINAL PROGRAM'S SCREEN: hwut_vterm runs 'viewer.exe'
viewer.sv         ('viewer.sv') on a pseudo-terminal and presses its keys;
                  the screen is compared as seen -- 'regions', 'comment',
                  'whitespace' off. Needs libvterm ('apt install libvterm0').

build.sv          A PYPE NAMED IN THE HEADER, 'pype = "build.pypes"': a
build.pypes       system of two scripts; push/pop over nested
normalise.pype    directories, '<exit>', 'import:', a repeat group,
build.pype        'quantity(s)', '<bol>'/'<eol>', globs, 'flush';
compiler.pype     'same = true' -- serial and parallel share one GOOD;
                  'choices' as a list

Makefile          THE BUILD of every simulation, one directory per target
                  ('<target>.exe.obj', removed after): tests build at once.
                  The ONE line marked 'HWUT-SUPPORT-PATH' says where the
                  SystemVerilog test support stands.

The '.pype' scripts, 'build.pypes', 'garage-space.hocon' and 'delivery.json'
are the Python demonstration's; a pype script is Python whatever the
application, so 'door.pype' fires into Python's 'hwut_fsm'.

MAKE IT IMPORTABLE
------------------------------------------------------------------------------
Where the test support was written to '<dir>' -- this port at
'<dir>/verilog', the C port it reaches through DPI-C at '<dir>/c' -- one
line makes it the support of a test of one's own:

    export HWUT_SUPPORT_VERILOG=<dir>/verilog

SystemVerilog has no search path of its own for packages: the build names
them. A Makefile shaped like this one's reads the variable (its marked line
'HWUT_SUPPORT_VERILOG ?= ...' yields to the environment), hands Verilator
the packages a test imports and compiles the DPI-C sources beside them. The
test then writes

    import hwut_runner::*;

(and 'import space_iterator::*;', 'import hwut_vterm::*;', ... for what it
uses -- '<dir>/verilog/README.txt').

NOT HERE, ON PURPOSE
------------------------------------------------------------------------------
'language-setup', 'variant_group', 'procsitter', 'free_disk_min_mb'
                  the root's alone ('hwut-root.conf' beside this directory)
'##! unaccepted', '##! constraint-violation'
                  written by hwut itself, into a recording or a GOOD
'diff_display_parameters'
                  how a difference is shown, not what passes
script_runner     a fixture for hwut's own tests of its faces
==============================================================================
