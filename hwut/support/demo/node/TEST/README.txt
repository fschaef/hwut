==============================================================================
THE DEMONSTRATION OVER JAVASCRIPT (NODE.JS) -- one test directory,
everything a test directory can say, each thing shown once
==============================================================================

    hwut --plain                    every test here: 27 ok
    hwut.report.features            every feature, and the run that proves
                                    it -- this port's one is 'demo-node'
    hwut.play <file> <choice>       one choice, run and shown
    hwut.config.show <file>         what hwut read, and from where

The same demonstration as '../../python/TEST', choice for choice, written
in JavaScript for node (22 or later) over the node test support
('support/test_writing/node'). Nothing is built: 'node' runs each '.js' as
it stands (the 'javascript' interpreter of 'hwut-root.conf').

Every test application is a file whose header ('// @hwut { }') is its
whole configuration; 'hwut.conf' is what the directory says. A file's
comment says what each of its choices shows. Where a run is seeded by the
clock or the event loop's timers its output differs from run to run, and
every choice passes anyway.

THE GOOD FILES ARE THE PYTHON DEMO'S: 'GOOD/<file>.js--<choice>.link'
names '../../python/TEST/GOOD/<file>.py--<choice>.txt' -- the same choice
prints the same text in either language. Three stand on their own, since
their text names the node file itself ('RATIONALE.txt', DEMO-NODE-3):
'screen.js--open', 'screen.js--scroll', 'shop.js--report' (and its
'stock.csv', an output file: only stdout links). 'hwut.good.link.show
GOOD' lists the links.

FILE              WHAT IT SHOWS
------------------------------------------------------------------------------
demo.js           THE COMPARISON'S TOLERANCES, one per choice
                  plain        exact, line by line
                  tolerance    'eq_pattern', 'numeric_ratio'
                  constraints  '((name: value))' judged by laws
                  analogies    '((handle))' consistent throughout
                  race         '##! potpourri': lines in any order
                  pool         '##! potpourri subset duplicates'
                  progress     'nothing': lines that count as none
                  lisp         'analogy' markers of one's own
                  clusters     '##! point-cloud ... pair dist=Linf'

chamber.js        REGIONS, UNITS, LAWS: '##! verbatim', '##! table',
                  '##! point-cloud', '##! ignore'; '((settle: 201 s))'
                  against 'settle <= 4 min'; a string law; a 'tolerance'
                  for every choice; '##' notes

protocol.sh       AN ORDER LAW AS A PYPE, fed live by a node producer:
                  clean, broken (the violation report as GOOD), slow
                  ('tick:' and a wait guard over 'pype.time()')
door.js           A PYPE THAT BINDS ITS VERDICT, '((breaches: N))', judged
door.pype         by the header; a state machine the pype fires the log's
                  events into; a known-broken door whose GOOD is its
                  breach report

garage.js         CASES GENERATED, NOT WRITTEN: 'space_iterator',
garage-space.hocon 'hwut_hocon', 'DeterministicStream',
                  'deterministic_timeline' (races drawn as strings);
                  'HwutRunner' as front end, 'interactive = true'

shop.js           THE DIRECTORY'S WORD -- read 'hwut.conf' with it:
delivery.json     'on_entry'/'on_exit', 'on_before_test'/'on_after_test',
fixture.js        'script_caps', 'ignore', 'admit', 'app_defaults',
hwut.conf         'collision', 'dependency', 'apps' (a test without a
                  header), 'execute', a choice-less test, 'target'
                  ('hwut.execute fixture open'); 'output' files;
                  'stderr_ignored'; '##! table unordered sep={;}'.
                  The database is node's own 'node:sqlite'; the clerks
                  are worker threads.

screen.js         A TERMINAL PROGRAM'S SCREEN: hwut_vterm runs 'viewer.js'
viewer.js         on a pseudo-terminal and presses its keys; the screen is
                  compared as seen -- 'regions', 'comment', 'whitespace'
                  off. Needs libvterm ('apt install libvterm0') and koffi
                  ('npm install' in the support's directory).

build.js          A PYPE NAMED IN THE HEADER, 'pype = "build.pypes"': a
build.pypes       system of two scripts; push/pop over nested
normalise.pype    directories, '<exit>', 'import:', a repeat group,
build.pype        'quantity(s)', '<bol>'/'<eol>', globs, 'flush';
compiler.pype     'same = true' -- serial and parallel share one GOOD;
                  'choices' as a list

hwut_support.js   no test: WHERE THE NODE SUPPORT STANDS, named on its one
                  line marked 'HWUT-SUPPORT-PATH'. NODE_PATH wins; the
                  marked path is the fallback.

MAKE IT IMPORTABLE
------------------------------------------------------------------------------
Where the support was written to '<dir>' (the port at '<dir>/node'), these
lines make it a node test's own, in the shell that runs hwut:

    export NODE_PATH=<dir>/node${NODE_PATH:+:$NODE_PATH}
    (cd <dir>/node && npm install)      # koffi -- for 'hwut_vterm' alone

and a test of one's own then writes

    const { HwutRunner } = require('hwut_runner');

-- likewise 'space_iterator', 'hwut_hocon', 'deterministic_random',
'deterministic_timeline', 'hwut_fsm', 'hwut_vterm', 'pytext'.

NOT HERE, ON PURPOSE
------------------------------------------------------------------------------
'language-setup', 'variant_group', 'procsitter', 'free_disk_min_mb'
                  the root's alone ('hwut-root.conf')
'build'           a compiled test application's word: node builds nothing
                  (no Makefile)
'##! unaccepted', '##! constraint-violation'
                  written by hwut itself, into a recording or a GOOD
'diff_display_parameters'
                  how a difference is shown, not what passes
a node pype       a pype script's actions are Python, in every language:
                  'door.pype' fires into the Python 'hwut_fsm'
                  ('RATIONALE.txt', DEMO-NODE-4)
==============================================================================
