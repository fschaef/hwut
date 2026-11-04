"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: 'local' -- the machine this hwut runs on (ruling 16). Always
         available; nothing to start or stop; never handed a bubble:
         the orchestrator runs a local bubble itself.
______________________________________________________________________________
"""
KEY_TUPLE = ()


def check(name, spec):
    """RETURN: (), always: 'local' takes no keys, and its reader refuses
    any before asking."""
    return ()


def is_available(name, spec):
    """RETURN: (True, ""), always: the local machine is where we are."""
    return (True, "")


def start(name, spec, write, log=None):
    """RETURN: (True, ""), always: nothing to make ready."""
    return (True, "")


def run(name, spec, bubble, wish, sink, root=None):
    """
    RETURN: never. Raises AssertionError: a local bubble is run by the
            orchestrator itself, never handed over.
    """
    raise AssertionError("platform 'local' is never handed a bubble")


def relay(name, spec, bubble_path, directory, argv, write):
    """
    RETURN: never. Raises AssertionError: a local face runs itself.
    """
    raise AssertionError("platform 'local' is never handed a face")


def stop(name, spec):
    """RETURN: None. Nothing was started."""
    return None
