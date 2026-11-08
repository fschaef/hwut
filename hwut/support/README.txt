support -- WHAT HELPS A USER, BESIDE WHAT HWUT IS
==============================================================================

    test_writing/   the test writing support: the Python modules a test
                    imports ('hwut.support.test_writing.python'), and the
                    same in sixteen more languages. 'LANGUAGES.conf' says
                    which port lives with hwut ('home = "hwut"') and which
                    may leave for a repository of its own ('home =
                    "support"'); 'adm/support_layout.py' checks it.
    remote/         remote execution: a test application drives a board,
                    a simulator or an emulator through an agent beside the
                    UUT -- 'hwut_remote' (host/), the agents (target/), one
                    directory per target kind (model/, iverilog/); its own
                    README.txt.
    demo/           '<language>/', the demonstration in each language,
                    which 'hwut.support <language> <dir>' writes out with
                    the support; 'showcase/', worked examples, a root of
                    its own (not in the package).

'hwut.support <language> <dir>' writes '<dir>/<language>' (the support),
'<dir>/TEST' (the demonstration) and '<dir>/hwut-root.conf', and says how
to make the support importable for a test of your own (services E-217).

EXIT 77, in every language: a test application exits 77 where the device
it talks to -- a board, a simulator -- is not reachable; hwut fails the case
without comparing its output, the last line of stderr beside it (engine/
operations RATIONALE O-36). Every other exit status is behaviour.

Nothing of hwut stands on a 'home = "support"' port; hwut's engine and
faces import the Python port alone (services RATIONALE E-216).
