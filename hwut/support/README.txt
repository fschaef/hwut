support -- WHAT HELPS A USER, BESIDE WHAT HWUT IS
==============================================================================

    test_writing/   the test writing support: the Python modules a test
                    imports ('hwut.support.test_writing.python'), and the
                    same in sixteen more languages. 'LANGUAGES.conf' says
                    which port lives with hwut ('home = "hwut"') and which
                    may leave for a repository of its own ('home =
                    "support"'); 'adm/support_layout.py' checks it.
    demo/           'python/', the demonstration 'hwut.demo.python' writes
                    out; 'showcase/', worked examples, a root of its own.

Nothing of hwut stands on a 'home = "support"' port; hwut's engine and
faces import the Python port alone (services RATIONALE E-216).
