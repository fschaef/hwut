"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________
PURPOSE
       THE VIEWERS -- every INTERPRETER of an alignment, in one family.

DESCRIPTION
       An alignment is the association run's product: the immutable
       DisplayInst stream of compare's door. The port
       ('engine/operations/interaction/port.py') states the contract a
       viewer answers; THIS family holds the viewers themselves -- the
       TUI and whichever client comes next (a VS Code integration would
       live here). Down in the engine live only the
       contract and the merge dialogue, both compare-blind; up here
       lives everything that renders FOR A PERSON IN A SESSION. What
       renders the run's own testimony ('engine/display') stays down --
       driven-by-the-run against driven-by-a-someone is the line.

       'driver_for' is THE ONLY PLACE a target becomes a driver, moved
       here whole: the engine must not construct a services class, and
       a face names an outcome, never a mechanism.
______________________________________________________________________________
"""
from enum import Enum

from vut.engine.operations.interaction.port import (NullDisplay,
                                                    CollectingDisplay,
                                                    RemoteDisplay)


class E_DisplayTarget(Enum):
    """Which driver carries the session."""
    NONE     = "none"       # collect nothing; the verdict is enough
    CONSOLE  = "console"    # the always-available tier
    TUI      = "tui"        # the terminal, interactively (tui.py)
    RICH     = "rich"       # a client speaking our protocol
    KEYS     = "keys"       # the keyed session: point, mark, take

    def __str__(self):
        """RETURN: str, the target's token."""
        return self.value


def keyed_absent_reason(stream_tuple):
    """
    RETURN: str, why the keyed screen cannot run -- no terminal on one of
            'stream_tuple', or 'prompt_toolkit' not importable -- worded
            for a NOTE line.
            None, where it can run.
    """
    for stream in stream_tuple:
        if not getattr(stream, "isatty", lambda: False)():
            return "no terminal"
    try:
        import prompt_toolkit  # noqa: F401
    except ImportError:
        return "'prompt_toolkit' is not installed"
    return None


def fallback_note(reason):
    """RETURN: str, the ONE line a face writes where the keyed screen was
               wanted and the text display is used instead (services
               E-79) -- the fallback is never silent."""
    return ("NOTE: %s -- the text display is used "
            "('--console' asks for it outright)" % reason)


def driver_for(target, **argument_db):
    """
    RETURN: DisplayAdapter, the driver that carries a session to 'target'.

    THE ONLY PLACE a target becomes a driver. A caller names an outcome
    -- where to show this -- and never constructs a driver itself, so
    adding a viewer touches this function and nothing else.

    Raises ValueError for a target with no driver: guessing one would
    send a session somewhere nobody asked for.
    """
    if target is E_DisplayTarget.NONE:
        return NullDisplay()
    if target is E_DisplayTarget.CONSOLE:
        return CollectingDisplay()
    if target is E_DisplayTarget.TUI:
        from .tui import TuiDisplay
        return TuiDisplay(**argument_db)
    if target is E_DisplayTarget.KEYS:
        #  THE KEYED TIER NEEDS 'prompt_toolkit'. Where it will not
        #  import, the TUI tier stands in and today's line-based session
        #  runs: a merge is NEVER hard-failed for lack of an import.
        #  The import is tried HERE, once, so a tree without the module
        #  still imports this package cleanly.
        try:
            import prompt_toolkit  # noqa: F401
        except ImportError:
            from .tui import TuiDisplay
            return TuiDisplay(**argument_db)
        from .keyed.driver import KeyedDisplay
        return KeyedDisplay(**argument_db)
    if target is E_DisplayTarget.RICH:
        argv = argument_db.get("argv")
        if not argv:
            raise ValueError("E_DisplayTarget.RICH needs the client's "
                             "'argv' -- there is no default client")
        return RemoteDisplay(argv,
                             resolve_f=argument_db.get("resolve_f", True))
    raise ValueError("no driver for display target %r" % target)
