#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Test the ArtifactManager factory and registry.

CHOICES: minting, interning, lookup;

DESCRIPTION:

The ArtifactManager is the only legal source of Artifact instances.
This file verifies:

    minting    - fresh artifact_ids are assigned monotonically from 0;
                 different (type, description) pairs get different ids.

    interning  - asking for the same (type, description) twice returns
                 the very same object instance, not just an equal one.

    lookup     - by_id() recovers the Artifact; unknown ids raise
                 KeyError; __contains__ and __len__ behave as expected.
______________________________________________________________________________
"""
import sys
import config                                                       # noqa: F401

from vut.language_support.python.hwut_runner    import HwutRunner
from vut.engine.workflow.artifact               import (ArtifactManager,
                                                        E_Artifact)


def banner(label):
    """RETURN: None.

    Prints a section heading.
    """
    print()
    print("--- %s ---" % label)


def run_minting():
    """RETURN: None.

    Demonstrates that .make() assigns artifact_ids monotonically from 0,
    that distinct descriptions produce distinct ids, and that __len__
    reports the number of distinct artifacts seen.
    """
    mgr = ArtifactManager()

    banner("ids assigned monotonically from 0")
    a = mgr.make(E_Artifact.FILEPATH, {"path": "a.o"})
    b = mgr.make(E_Artifact.FILEPATH, {"path": "b.o"})
    c = mgr.make(E_Artifact.FILEPATH, {"path": "c.o"})
    print("a.id = %d" % a.artifact_id)
    print("b.id = %d" % b.artifact_id)
    print("c.id = %d" % c.artifact_id)

    banner("count after three distinct artifacts")
    print("len(mgr) = %d" % len(mgr))

    banner("different descriptions yield different ids")
    print("a.id != b.id: %s" % (a.artifact_id != b.artifact_id))
    print("b.id != c.id: %s" % (b.artifact_id != c.artifact_id))
    print("a.id != c.id: %s" % (a.artifact_id != c.artifact_id))


def run_interning():
    """RETURN: None.

    Demonstrates that .make() returns the very same Artifact instance for
    repeated requests with the same (type, description), and that this
    holds regardless of dict-key order in the description.
    """
    mgr = ArtifactManager()

    banner("same (type, description) twice -> same instance")
    a1 = mgr.make(E_Artifact.FILEPATH, {"path": "main.o"})
    a2 = mgr.make(E_Artifact.FILEPATH, {"path": "main.o"})
    print("a1.id    == a2.id:    %s" % (a1.artifact_id == a2.artifact_id))
    print("a1 is a2:             %s" % (a1 is a2))

    banner("same description, different dict-key order -> same instance")
    b1 = mgr.make(E_Artifact.FILEPATH, {"path": "x.o", "variant": "debug"})
    b2 = mgr.make(E_Artifact.FILEPATH, {"variant": "debug", "path": "x.o"})
    print("b1.id    == b2.id:    %s" % (b1.artifact_id == b2.artifact_id))
    print("b1 is b2:             %s" % (b1 is b2))

    banner("count is unaffected by repeated requests")
    print("len(mgr) = %d  (expected 2)" % len(mgr))

    banner("different description -> new artifact, fresh id")
    c = mgr.make(E_Artifact.FILEPATH, {"path": "y.o"})
    print("c.id     = %d  (expected 2)" % c.artifact_id)
    print("len(mgr) = %d  (expected 3)" % len(mgr))


def run_lookup():
    """RETURN: None.

    Demonstrates the reverse-lookup contract: by_id() recovers the Artifact
    by its id; unknown ids raise KeyError; __contains__ behaves as expected;
    a fresh manager has length 0 and contains no ids.
    """
    mgr = ArtifactManager()

    banner("by_id() recovers the same instance")
    a   = mgr.make(E_Artifact.FILEPATH, {"path": "main.o"})
    got = mgr.by_id(a.artifact_id)
    print("by_id(a.id) is a:     %s" % (got is a))
    print("got.descr_dict():     %s" % got.description_dict())

    banner("__contains__")
    print("a.id in mgr:          %s" % (a.artifact_id in mgr))
    print("999  in mgr:          %s" % (999          in mgr))

    banner("by_id() on unknown id -> KeyError")
    try:
        mgr.by_id(999)
        print("UNEXPECTED: lookup succeeded")
    except KeyError:
        print("KeyError raised (expected)")

    banner("empty manager")
    empty = ArtifactManager()
    print("len(empty) = %d" % len(empty))
    print("0 in empty: %s" % (0 in empty))


HwutRunner(
    argv       = sys.argv,
    title      = "ArtifactManager factory and registry",
    choice_map = {
        "minting":   run_minting,
        "interning": run_interning,
        "lookup":    run_lookup,
    },
).run()
