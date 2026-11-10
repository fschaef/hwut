==============================================================================
THE DEMONSTRATION OVER PERL -- one test directory, everything a test
directory can say, each thing shown once
==============================================================================

    hwut --plain                    every test here: 27 ok
    hwut.report.features            every feature, and the run that proves
                                    it -- this port's one is 'demo-perl'
    hwut.play <file> <choice>       one choice, run and shown
    hwut.config.show <file>         what hwut read, and from where

The Python demonstration ('../../python/TEST'), choice for choice, written
in Perl over the Perl test support ('support/test_writing/perl'). Its GOOD
files are the Python demonstration's, by '.link' ('hwut.good.link.show
GOOD'): the Perl programs print the same text. Where a run names its own
file, it has a GOOD of its own ('../RATIONALE.txt', DEMO-PERL-2).

Every test application is a file whose header ('@hwut { }') is its whole
configuration; 'hwut.conf' is what the directory says. A file's comment
says what each of its choices shows. Where a run is seeded by the clock or
the scheduler its output differs from run to run, and every choice passes
anyway.

FILE              WHAT IT SHOWS
------------------------------------------------------------------------------
demo.pl           THE COMPARISON'S TOLERANCES, one per choice
                  plain        exact, line by line
                  tolerance    'eq_pattern', 'numeric_ratio'
                  constraints  '((name: value))' judged by laws
                  analogies    '((handle))' consistent throughout
                  race         '##! potpourri': lines in any order
                  pool         '##! potpourri subset duplicates'
                  progress     'nothing': lines that count as none
                  lisp         'analogy' markers of one's own
                  clusters     '##! point-cloud ... pair dist=Linf'

chamber.pl        REGIONS, UNITS, LAWS: '##! verbatim', '##! table',
                  '##! point-cloud', '##! ignore'; '((settle: 201 s))'
                  against 'settle <= 4 min'; a string law; a 'tolerance'
                  for every choice; '##' notes

protocol.sh       AN ORDER LAW AS A PYPE, fed live by a Perl producer (five
                  client processes): clean, broken (the violation report
                  as GOOD), slow ('tick:' and a wait guard over
                  'pype.time()')
door.pl           A PYPE THAT BINDS ITS VERDICT: the door's log, fired by
door.pype         'door.pype' into a state machine; a known-broken story
                  whose GOOD is its breach report

garage.pl         CASES GENERATED, NOT WRITTEN: 'Hwut::SpaceIterator',
garage-space.hocon 'Hwut::Hocon', 'Hwut::DeterministicStream',
                  'Hwut::TriggerDispatcher' (races drawn as strings);
                  'Hwut::Runner' as front end, 'interactive = true'

shop.pl           THE DIRECTORY'S WORD -- read 'hwut.conf' with it:
delivery.json     'on_entry'/'on_exit', 'on_before_test'/'on_after_test',
fixture.pl        'script_caps', 'ignore', 'admit', 'app_defaults',
ShopDb.pm         'collision', 'dependency', 'apps' (a test without a
hwut.conf         header), 'execute', a choice-less test, 'target'
                  ('hwut.execute fixture open'); 'output' files;
                  'stderr_ignored'; '##! table unordered sep={;}'.
                  SQLite through FFI::Platypus ('ShopDb.pm').

screen.pl         A TERMINAL PROGRAM'S SCREEN: Hwut::Vterm runs 'viewer.pl'
viewer.pl         on a pseudo-terminal and presses its keys; the screen is
                  compared as seen -- 'regions', 'comment', 'whitespace'
                  off. Needs libvterm and FFI::Platypus ('apt install
                  libvterm0 libffi-platypus-perl').

build.pl          A PYPE NAMED IN THE HEADER, 'pype = "build.pypes"': a
build.pypes       system of two scripts; push/pop over nested
normalise.pype    directories, '<exit>', 'import:', a repeat group,
build.pype        'quantity(s)', '<bol>'/'<eol>', globs, 'flush';
compiler.pype     'same = true' -- serial and parallel share one GOOD;
                  'choices' as a list

SupportPath.pm    WHERE THE PERL SUPPORT STANDS, named once (the line
                  marked 'HWUT-SUPPORT-PATH'); 'garage.pl' and 'screen.pl'
                  load it. PERL5LIB wins over it.

MAKE IT IMPORTABLE
------------------------------------------------------------------------------
With the support written to '<dir>' (the Perl port at '<dir>/perl'), one
line makes it importable for a test of one's own:

    export PERL5LIB="<dir>/perl${PERL5LIB:+:$PERL5LIB}"

and the test then writes

    use Hwut::Runner;          # and Hwut::Hocon, Hwut::SpaceIterator, ...

Perl itself, 5.26 or later, and its core modules are all else a test
needs; 'Hwut::Vterm' (and 'ShopDb.pm' here) want FFI::Platypus as well.

NOT HERE, ON PURPOSE
------------------------------------------------------------------------------
'language-setup', 'variant_group', 'procsitter', 'free_disk_min_mb'
                  the root's alone ('hwut-root.conf')
'build'           a compiled test application's word: Perl is run as it
                  stands, no Makefile
'##! unaccepted', '##! constraint-violation'
                  written by hwut itself, into a recording or a GOOD
'diff_display_parameters'
                  how a difference is shown, not what passes
==============================================================================
