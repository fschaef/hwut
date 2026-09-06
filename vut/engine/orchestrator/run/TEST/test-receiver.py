#! /usr/bin/env python3
#
# @hwut {
#     title      = "Vocabulary and receiver: format, dispatch, misfit"
#     choices    = ["dispatch", "emitter", "format", "misfit"]
#     interactive = true
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE VOCABULARY AND THE RECEIVER -- the format description an
         outside consumer reads, the emitter's assertions, and the
         receiver's dispatch: named handlers, the catch-alls, misfit.

CHOICES: format, emitter, dispatch, misfit;

DESCRIPTION:

format    'format_text()', verbatim -- the promise and every kind.

emitter   'event(...)' refuses a wrong event at emission: unknown
          kind, missing field, wrong type, unknown field.

dispatch  a derived receiver: named parameters arrive on the specific
          handlers; a NEWER stream's extra field is dropped there and
          still visible to 'on_any'; an unknown kind reaches
          'on_unknown'.

misfit    a known kind missing a required field, one with a wrong
          type, and a thing that is no event at all: 'on_misfit'.
______________________________________________________________________________
"""
import asyncio
import sys
from config import HwutRunner                                # noqa: F401

from vut.engine.protocol.receiver   import CRunReportReceiver
from vut.engine.protocol.vocabulary import event, format_text


def banner(label):
    """RETURN: None. Section heading."""
    print()
    print("--- %s ---" % label)


class Shown(CRunReportReceiver):
    """A receiver that prints what reaches it -- the face of the
    dispatch."""

    def on_any(self, kind, **fields):
        """RETURN: None. The tap: kind and field names alone."""
        print("    any      %-10s fields: %s"
              % (kind, ", ".join(sorted(fields))))

    def on_unknown(self, kind, **fields):
        """RETURN: None."""
        print("    unknown  %-10s fields: %s"
              % (kind, ", ".join(sorted(fields))))

    def on_misfit(self, kind, **fields):
        """RETURN: None."""
        print("    misfit   %-10s fields: %s"
              % (kind, ", ".join(sorted(fields))))

    def on_run_ended(self, when, directory, node, node_kind, good,
                     verdict, cause=None, report=None, detail=None):
        """RETURN: None. The named surface, shown."""
        print("    run-ended when=%s directory=%s node=%s good=%s "
              "verdict=%s cause=%s report=%s detail=%s"
              % (when, directory, node, good, verdict, cause, report,
                 detail))

    def on_tree_done(self, when, good, fail_n, meta_n=0, skip_n=0):
        """RETURN: None."""
        print("    tree-done when=%s good=%s fail_n=%d"
              % (when, good, fail_n))


def received(item_list):
    """RETURN: None. Drives a Shown receiver over the items and the
    closing 'None'."""
    async def main():
        queue = asyncio.Queue()
        for item in item_list: queue.put_nowait(item)
        queue.put_nowait(None)
        await Shown().receive(queue)
    asyncio.run(main())


def test_format():
    """RETURN: None. The description, verbatim."""
    print(format_text())


def test_emitter():
    """RETURN: None. A wrong event is the emitter's defect, named."""
    for label, build in (
        ("unknown kind",
         lambda: event("tree-gone", "T01", good=True, fail_n=0)),
        ("missing field",
         lambda: event("tree-done", "T01", good=True)),
        ("wrong type",
         lambda: event("tree-done", "T01", good=True, fail_n="0")),
        ("unknown field",
         lambda: event("tree-done", "T01", good=True, fail_n=0,
                       colour="red")),
    ):
        banner(label)
        try:
            build()
            print("NOT REFUSED -- a law is broken")
        except AssertionError as error:
            print("REFUSED: %s" % error)


def test_dispatch():
    """RETURN: None. Named handlers, growth, unknown kinds."""
    banner("a run-ended with a cause")
    received([event("run-ended", "T01", directory="alpha/TEST",
                    node="test-a.py", node_kind="TEST", good=False,
                    verdict="unsupported", cause="build[make]")])

    banner("a NEWER stream's extra field: on_any sees it, the named "
           "handler does not")
    newer = event("tree-done", "T02", good=True, fail_n=0)
    newer["walltime_sec"] = 12.5              # a field of tomorrow
    received([newer])

    banner("an unknown kind")
    received([{"format": 1, "kind": "coffee-break", "when": "T03",
               "minutes": 5}])


def test_misfit():
    """RETURN: None. Known kind, unfit structure."""
    banner("a required field missing")
    received([{"format": 1, "kind": "tree-done", "when": "T01",
               "good": True}])

    banner("a required field of the wrong type")
    received([{"format": 1, "kind": "tree-done", "when": "T01",
               "good": True, "fail_n": "three"}])

    banner("no event at all")
    received(["forty-two"])


if __name__ == "__main__":
    HwutRunner(sys.argv,
               "Vocabulary and receiver: format, dispatch, misfit;", {
        "format":   test_format,
        "emitter":  test_emitter,
        "dispatch": test_dispatch,
        "misfit":   test_misfit,
    }).run()
