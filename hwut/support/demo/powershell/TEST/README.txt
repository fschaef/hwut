==============================================================================
THE DEMONSTRATION OVER POWERSHELL 7 -- one test directory, everything a
test directory can say, each thing shown once
==============================================================================

    hwut --plain                    every test here: 27 ok
    hwut.report.features            every feature, and the run that proves
                                    it -- this port's one is 'demo-powershell'
    hwut.play <file> <choice>       one choice, run and shown
    hwut.config.show <file>         what hwut read, and from where

The same demonstration as '../../python/TEST', choice for choice, over the
PowerShell test support ('support/test_writing/powershell'). Every test
application is a file whose header ('@hwut { }') is its whole
configuration; 'hwut.conf' is what the directory says. A file's comment
says what each of its choices shows. Where a run is seeded by the clock or
the scheduler its output differs from run to run, and every choice passes
anyway.

THE GOOD FILES ARE THE PYTHON DEMO'S: 'GOOD/<file>--<choice>.link' names
'../../python/TEST/GOOD/<file.py>--<choice>.txt' -- the same choice prints
the same text. Three stand on their own, because they name this
directory's own files ('RATIONALE.txt', DEMO-POWERSHELL-5):
'screen.ps1--open', 'screen.ps1--scroll' ('> viewer.ps1 race.txt') and
'shop.ps1--report' (the frame log names 'shop.ps1'), with its
'stock.csv' (only stdout links).

FILE              WHAT IT SHOWS
------------------------------------------------------------------------------
demo.ps1          THE COMPARISON'S TOLERANCES, one per choice
                  plain        exact, line by line
                  tolerance    'eq_pattern', 'numeric_ratio'
                  constraints  '((name: value))' judged by laws
                  analogies    '((handle))' consistent throughout
                  race         '##! potpourri': lines in any order
                  pool         '##! potpourri subset duplicates'
                  progress     'nothing': lines that count as none
                  lisp         'analogy' markers of one's own
                  clusters     '##! point-cloud ... pair dist=Linf'

chamber.ps1       REGIONS, UNITS, LAWS: '##! verbatim', '##! table',
                  '##! point-cloud', '##! ignore'; '((settle: 201 s))'
                  against 'settle <= 4 min'; a string law; a 'tolerance'
                  for every choice; '##' notes

protocol.sh       AN ORDER LAW AS A PYPE, fed live by a PowerShell
                  producer: clean, broken (the violation report as
                  GOOD), slow ('tick:' and a wait guard over
                  'pype.time()')
door.ps1          A PYPE THAT BINDS ITS VERDICT, '((breaches: N))', judged
door.pype         by the header; modes inheriting two bases; 'caps'; a
                  known-broken version whose GOOD is its violation
                  report; potpourri against pype; analogies in a region

garage.ps1        CASES GENERATED, NOT WRITTEN: 'SpaceIterator',
garage-space.hocon 'hwut_hocon', 'DeterministicStream',
                  'deterministic_timeline' (races drawn as strings);
                  'HwutRunner' as front end, 'interactive = true'

shop.ps1          THE DIRECTORY'S WORD -- read 'hwut.conf' with it:
delivery.json     'on_entry'/'on_exit', 'on_before_test'/'on_after_test',
fixture.ps1       'script_caps', 'ignore', 'admit', 'app_defaults',
shop_db.ps1       'collision', 'dependency', 'apps' (a test without a
hwut.conf         header), 'execute', a choice-less test, 'target'
                  ('hwut.execute fixture open'); 'output' files;
                  'stderr_ignored'; '##! table unordered sep={;}'.
                  SQLite through 'shop_db.ps1' (libsqlite3 by P/Invoke)

screen.ps1        A TERMINAL PROGRAM'S SCREEN: hwut_vterm runs 'viewer.ps1'
viewer.ps1        on a pseudo-terminal and presses its keys; the screen is
                  compared as seen -- 'regions', 'comment', 'whitespace'
                  off. Needs libvterm ('apt install libvterm0').

build.ps1         A PYPE NAMED IN THE HEADER, 'pype = "build.pypes"': a
build.pypes       system of two scripts; push/pop over nested
normalise.pype    directories, '<exit>', 'import:', a repeat group,
build.pype        'quantity(s)', '<bol>'/'<eol>', globs, 'flush';
compiler.pype     'same = true' -- serial and parallel share one GOOD;
                  'choices' as a list

hwut_support.ps1  WHERE THE SUPPORT STANDS -- no test: every test
                  dot-sources it, naming the modules it uses. Its
                  marked line is the one place that names
                  the port: HWUT_SUPPORT_POWERSHELL, else the port in
                  hwut's own tree.

The pypes are written in hwut.pype's own language -- Python, whatever
language the application is in: 'door.pype' fires its events into
Python's 'hwut_fsm'.

PWSH UNDER hwut's CAPS: .NET maps a 2 TiB memory file as pwsh starts,
which hwut's 10 MB per-file cap kills; 'hwut.conf' raises 'file_size_mb'
for the tests ('app_defaults') and for its scripts ('script_caps').

MAKE IT IMPORTABLE
------------------------------------------------------------------------------
Where the support was written to '<dir>' (the port at '<dir>/powershell'),
one shell line makes it found -- by this demonstration's tests and by a
test of one's own:

    export HWUT_SUPPORT_POWERSHELL=<dir>/powershell

A test of one's own then writes, at its top (one line per module it uses;
the classes are known when the file is parsed, a class may derive from
them):

    using module <dir>/powershell/hwut_runner.psm1

-- 'using module' takes a literal path, no variable. A test that is to
find the support through HWUT_SUPPORT_POWERSHELL does as these do, with
'hwut_support.ps1' beside it:

    . "$PSScriptRoot/hwut_support.ps1" hwut_runner deterministic_random

PowerShell's own mechanism, PSModulePath, finds a module only in a folder
of its name ('<path>/hwut_runner/hwut_runner.psm1'); the support's modules
stand flat in one directory, so it cannot find them ('RATIONALE.txt',
DEMO-POWERSHELL-2).

NOT HERE, ON PURPOSE
------------------------------------------------------------------------------
'language-setup', 'variant_group', 'procsitter', 'free_disk_min_mb'
                  the root's alone ('hwut-root.conf')
'build'           a compiled test application's word: pwsh runs a
                  '.ps1' as it stands
'##! unaccepted', '##! constraint-violation'
                  written by hwut itself, into a recording or a GOOD
'diff_display_parameters'
                  how a difference is shown, not what passes
script_runner     a fixture for hwut's own tests of its faces
==============================================================================
