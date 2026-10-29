"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE DIRECTORY'S HANDLERS, CALLED ONE WAY -- by 'hwut.run' (the
         dispatcher) and by 'hwut.play' alike (services E-204).

    on_entry, on_exit               before the directory's tests / after
    on_before_test, on_after_test   around each test run, told which by
                                    'HWUT_TEST' and 'HWUT_CHOICE' ('' for
                                    none)

Each runs as 'bash -c <command>' in the directory: the command line is
the author's, and the two variables expand in it where it names them --
'on_before_test = "./check.sh $HWUT_TEST $HWUT_CHOICE"'.

EVERY HANDLER IS SUPERVISED (B-17): under the directory's 'script_caps'
('adapter.script_config_of'). An end other than exit 0 is no verdict
(E-158): the caller says it, and the tests run.
______________________________________________________________________________
"""
from ...procsitter.api import Procsitter
from .adapter          import script_config_of

FRAME_ROLE_TUPLE  = ("on_entry", "on_exit")
HELPER_ROLE_TUPLE = ("on_before_test", "on_after_test")


def helper_env(app, choice):
    """
    RETURN: dict, the environment that tells 'on_before_test' and
            'on_after_test' which test run they stand around: 'HWUT_TEST'
            the test application's file name, 'HWUT_CHOICE' the choice,
            '' for a test without choices.
    """
    return {"HWUT_TEST": app, "HWUT_CHOICE": choice or ""}


async def run(directory_spec, directory, command, env=None):
    """
    RETURN: None, the handler 'command' ran to exit 0 -- 'bash -c' in
                  'directory', supervised, 'env' overlaid;
            str, how it ended else -- 'exited <n>', or 'ended: <how>'
                 where the supervisor ended it.
    """
    procsitter = Procsitter(script_config_of(directory_spec, env),
                            work_dir=directory)
    record = await procsitter.run(["bash", "-c", command])
    name   = record.containment.name
    if name == "OK_COMPLETED" and record.exit_code == 0: return None
    if name in ("OK_COMPLETED", "FAIL_COMPLETED"):
        return "exited %s" % record.exit_code
    return "ended: %s" % name[len("FAIL_"):].lower().replace("_", " ")
