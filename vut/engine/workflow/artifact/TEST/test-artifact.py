#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Test the Artifact frozen-record contract.

CHOICES: frozen, fields;

DESCRIPTION:

The Artifact class is a passive frozen record. Instances are minted by
ArtifactManager (tested elsewhere); here we verify only the record's own
contract:

    -- the three fields are accessible
    -- __repr__ produces a stable, readable form
    -- the instance refuses mutation
______________________________________________________________________________
"""
import sys
import config                                                       # noqa: F401

from dataclasses                                import FrozenInstanceError
from vut.language_support.python.hwut_runner    import HwutRunner
from vut.engine.workflow.artifact               import (ArtifactManager,
                                                        E_Artifact)


def banner(label):
    """RETURN: None.

    Prints a section heading. Used by every test choice for consistent output.
    """
    print()
    print("--- %s ---" % label)


def run_fields():
    """RETURN: None.

    Prints the three fields of constructed Artifacts and demonstrates that
    __repr__ is stable, and dict-key order in the input does not affect
    the result.
    """
    mgr = ArtifactManager()

    banner("simple artifact: one key")
    a = mgr.generate(E_Artifact.FILEPATH, {"path": "build/main.o"})
    print("type:        %s" % a.type.name)
    print("description: %s" % a.normalized_description)
    print("artifact_id: %d" % a.artifact_id)
    print("repr:        %s" % repr(a))

    banner("multi-key description")
    b = mgr.generate(E_Artifact.FILEPATH, {"path": "lib.so", "variant": "debug"})
    print("description: %s" % b.normalized_description)
    print("repr:        %s" % repr(b))

    banner("dict-key order does not matter")
    c1 = mgr.generate(E_Artifact.FILEPATH, {"path": "x.o", "variant": "rel"})
    c2 = mgr.generate(E_Artifact.FILEPATH, {"variant": "rel", "path": "x.o"})
    print("c1 descr:    %s" % c1.normalized_description)
    print("c2 descr:    %s" % c2.normalized_description)
    print("same id:     %s" % (c1.artifact_id == c2.artifact_id))


def run_frozen():
    """RETURN: None.

    Demonstrates that an Artifact instance refuses every flavour of mutation:
    field assignment on each of the three fields, and field deletion. All
    must raise FrozenInstanceError.
    """
    mgr = ArtifactManager()
    a   = mgr.generate(E_Artifact.FILEPATH, {"path": "main.o"})

    banner("attempt to assign .type")
    try:
        a.type = E_Artifact.FILEPATH
        print("UNEXPECTED: assignment succeeded")
    except FrozenInstanceError:
        print("FrozenInstanceError raised (expected)")

    banner("attempt to assign .artifact_id")
    try:
        a.artifact_id = 999
        print("UNEXPECTED: assignment succeeded")
    except FrozenInstanceError:
        print("FrozenInstanceError raised (expected)")

    banner("attempt to assign .normalized_description")
    try:
        a.normalized_description = {}
        print("UNEXPECTED: assignment succeeded")
    except FrozenInstanceError:
        print("FrozenInstanceError raised (expected)")

    banner("attempt to delete a field")
    try:
        del a.type
        print("UNEXPECTED: deletion succeeded")
    except FrozenInstanceError:
        print("FrozenInstanceError raised (expected)")


HwutRunner(
    argv       = sys.argv,
    title      = "Artifact frozen record",
    choice_map = {
        "fields": run_fields,
        "frozen": run_frozen,
    },
).run()
