"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE
       THE OBSERVER -- the progress seam of every operation.

DESCRIPTION
       Orthogonal to the display TARGET: an observer WATCHES a run
       unfold; a target RECEIVES the comparison. One is a console log or
       a database of record, the other is what a person reads a
       difference in.

       DUCK-TYPED, every method optional. An operation calls through
       'notify()', so an observer implements what it cares about and
       ignores the rest -- and a new call site never breaks an existing
       observer.

       OBSERVERS ADD, exactly as consumers do in procsitter's 'tee()':
       fanning out to several is a composite, not a special case.

       AN OBSERVER MAY NEVER CHANGE A VERDICT. It watches. So an
       exception raised inside one is swallowed at the seam: a broken log
       must not turn a passing test into a failing one.
______________________________________________________________________________
"""


def notify(observer, method_name, *argument_list):
    """
    RETURN: None. Calls 'method_name' on 'observer' when it has one.

    Silent when the observer is None, when it lacks the method, and when
    the method raises: an observer WATCHES, and nothing it does may reach
    the verdict.
    """
    if observer is None: return
    method = getattr(observer, method_name, None)
    if method is None:   return
    try:
        method(*argument_list)
    except Exception:
        pass


class NullObserver:
    """Watches nothing. The default, so no operation has to test for
    'None' at every call site."""
    pass


class ConsoleObserver:
    """Writes progress as it happens. Deliberately terse: it exists to
    show that something is moving, not to report -- the report is the
    TestResult."""

    def __init__(self, write=None):
        self._write = write if write is not None else self._to_stdout

    @staticmethod
    def _to_stdout(text):
        """RETURN: None. Writes one line, unbuffered."""
        import sys
        sys.stdout.write(text + "\n")
        sys.stdout.flush()

    def started(self, name, groundwork_kind):
        """RETURN: None. Announces the operation's start."""
        self._write("... %s [%s]" % (name, groundwork_kind))

    def built(self, build_report):
        """RETURN: None. Announces the build's outcome (COMPILED only)."""
        self._write("    build: %s" % build_report)

    def verdict(self, subject_name, ok):
        """RETURN: None. Announces one subject's verdict as it lands."""
        self._write("    %-8s %s" % (subject_name, "ok" if ok else "DIFFERS"))

    def finished(self, result):
        """RETURN: None. Announces the derived result."""
        self._write("=== %s: %s" % (result.name, result.report))


class ObserverGroup:
    """Several observers as one. They ADD: each gets every notification,
    in the order given, and one that raises does not stop the next."""

    def __init__(self, *observer_list):
        self.observer_list = tuple(o for o in observer_list if o is not None)

    def __getattr__(self, method_name):
        """
        RETURN: a callable that forwards to every member that has
                'method_name'.

        Raises AttributeError for private names, so the group does not
        pretend to implement the object protocol.
        """
        if method_name.startswith("_"): raise AttributeError(method_name)

        def forward(*argument_list):
            """RETURN: None. Notifies every member, in order."""
            for observer in self.observer_list:
                notify(observer, method_name, *argument_list)
        return forward
