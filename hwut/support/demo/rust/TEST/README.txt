==============================================================================
THE DEMONSTRATION OVER RUST -- one test directory, everything a test
directory can say, each thing shown once
==============================================================================

    hwut --plain                    every test here: 27 ok
    hwut.report.features            every feature below, and the run that
                                    proves it ('hwut-features.conf')
    hwut.play <file> <choice>       one choice, run and shown
    hwut.config.show <file>         what hwut read, and from where

The same demonstration as '../../python/TEST', choice for choice, in Rust.
Every test application is a file whose header ('@hwut { }') is its whole
configuration -- here with 'build { framework = "make", target =
"%.exe" }': hwut runs the 'Makefile' beside it, which makes 'x.exe' of
'x.rs' with rustc alone (no cargo, no crate from outside). 'hwut.conf' is
what the directory says. A file's comment says what each of its choices
shows. Where a run is seeded by the clock or the scheduler its output
differs from run to run, and every choice passes anyway.

THE GOOD FILES ARE THE PYTHON DEMONSTRATION'S, by '.link' (bookkeeper
B-32), wherever the output is the same -- 24 of 27 cases. Three print a
file of their own name, and have a GOOD of their own: 'screen.rs open',
'screen.rs scroll', 'shop.rs report' (see '../RATIONALE.txt', DEMO-RUST-3).

FILE              WHAT IT SHOWS
------------------------------------------------------------------------------
demo.rs           THE COMPARISON'S TOLERANCES, one per choice
                  plain        exact, line by line
                  tolerance    'eq_pattern', 'numeric_ratio'
                  constraints  '((name: value))' judged by laws
                  analogies    '((handle))' consistent throughout
                  race         '##! potpourri': lines in any order
                  pool         '##! potpourri subset duplicates'
                  progress     'nothing': lines that count as none
                  lisp         'analogy' markers of one's own
                  clusters     '##! point-cloud ... pair dist=Linf'

chamber.rs        REGIONS, UNITS, LAWS: '##! verbatim', '##! table',
                  '##! point-cloud', '##! ignore'; '((settle: 201 s))'
                  against 'settle <= 4 min'; a string law; a 'tolerance'
                  for every choice; '##' notes

protocol.sh       AN ORDER LAW AS A PYPE, fed live by a Rust producer
producer.rs       ('producer.rs', five clients in threads): clean, broken
                  (the violation report as GOOD), slow ('tick:' and a wait
                  guard over 'pype.time()')
door.rs           A PYPE THAT BINDS ITS VERDICT: the door's log fired into
door.pype         a state machine ('hwut_fsm', in the pype); a known-broken
                  version whose GOOD is its violation report

garage.rs         CASES GENERATED, NOT WRITTEN, by the Rust support crate
garage-space.hocon 'hwut': 'space_iterator', 'hwut_hocon',
                  'DeterministicStream', 'deterministic_timeline' (races
                  drawn as strings); 'HwutRunner' as front end,
                  'interactive = true'

shop.rs           THE DIRECTORY'S WORD -- read 'hwut.conf' with it:
shop_db.rs        'on_entry'/'on_exit', 'on_before_test'/'on_after_test',
delivery.json     'script_caps', 'ignore', 'admit', 'app_defaults',
fixture.rs        'collision', 'dependency', 'apps' (a test without a
hwut.conf         header), 'execute', a choice-less test, 'target'
                  ('hwut.execute fixture open'); 'output' files;
                  'stderr_ignored'; '##! table unordered sep={;}'.
                  SQLite through libsqlite3, declared in 'shop_db.rs'

screen.rs         A TERMINAL PROGRAM'S SCREEN: the support's 'hwut_vterm'
viewer.rs         runs 'viewer.exe' on a pseudo-terminal and presses its
                  keys; the screen is compared as seen -- 'regions',
                  'comment', 'whitespace' off. Needs libvterm ('apt install
                  libvterm0').

build.rs          A PYPE NAMED IN THE HEADER, 'pype = "build.pypes"': a
build.pypes       system of two scripts; push/pop over nested
normalise.pype    directories, '<exit>', 'import:', a repeat group,
build.pype        'quantity(s)', '<bol>'/'<eol>', globs, 'flush';
compiler.pype     'same = true' -- serial and parallel share one GOOD;
                  'choices' as a list

Makefile          the programs; 'make helpers' (run by 'on_entry') builds
clock_random.rs   those that are no tests. 'clock_random.rs': random
                  numbers seeded by the clock, for the applications that
                  draw (Rust's standard library has none)

WHAT IT WANTS
------------------------------------------------------------------------------
rustc (written with 1.97, edition 2021) and make; libsqlite3 to link
('shop.rs', 'fixture.rs'; Debian: libsqlite3-dev); libvterm at run time
('screen.rs'); python3 for hwut and its pype. The first run compiles ten
programs, the support crate twice (some 100 s of CPU); later runs reuse
them.

MAKE IT IMPORTABLE
------------------------------------------------------------------------------
The Rust support is the crate 'hwut', written to '<dir>/rust'. Rust has no
search path for a crate of its own: a program names the compiled crate by
'--extern'. Two lines make it importable -- the first is all this
demonstration's Makefile needs (it compiles the crate itself, per test),
the second compiles it once for a test of your own:

    export HWUT_SUPPORT_RUST=<dir>/rust
    rustc --edition 2021 -O --crate-type rlib --crate-name hwut -o <dir>/libhwut.rlib $HWUT_SUPPORT_RUST/src/lib.rs

A test then writes

    use hwut::hwut_runner::HwutRunner;

and is built by

    rustc --edition 2021 -O --extern hwut=<dir>/libhwut.rlib my-test.rs

THE ONE LINE that names where the support stands is in 'Makefile', marked
'HWUT-SUPPORT-PATH': HWUT_SUPPORT_RUST where it is set, else the port
beside this demonstration in hwut's own tree.

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
