#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Test ArtifactHandling registry and the Filepath worked example.

CHOICES: registry, canonicalise, resolve;

DESCRIPTION:

ArtifactHandling subclasses provide the per-type translation between
descriptions in three forms: raw (from the user/recipe), normalised
(used by the workflow internally), and local (used at task execution).

This file verifies:

    registry      - register, lookup, duplicate-rejection, missing-type.

    canonicalise  - FilepathHandling reduces equivalent path strings to
                    the same canonical form, regardless of whether they
                    are absolute, relative, contain '..', or have
                    redundant separators.

    resolve       - FilepathHandling decanonicalises a canonical path
                    back into a local filesystem-style path under a
                    given host_root.
______________________________________________________________________________
"""
import sys
from   config import HwutRunner           

from vut.engine.workflow.artifact import (E_Artifact,
                                          ArtifactHandling,
                                          ArtifactHandlingRegistry,
                                          FilepathHandling)


def banner(label):
    """RETURN: None.

    Prints a section heading.
    """
    print()
    print("--- %s ---" % label)


def run_registry():
    """RETURN: None.

    Demonstrates the registration contract: empty registry; fresh
    registration is accepted; duplicate registration is silently
    refused via False return and does NOT overwrite the existing
    handler; lookup of an unregistered type returns None.

    The registry is mechanism only - it never raises and never
    overwrites. The caller decides how to react to a False return
    or a None lookup (typically: report a configuration error).
    """
    reg = ArtifactHandlingRegistry()

    banner("empty registry")
    print("FILEPATH in reg:    %s" % (E_Artifact.FILEPATH in reg))
    print("get(FILEPATH):      %s" % reg.get(E_Artifact.FILEPATH))

    banner("first registration is accepted")
    accepted = reg.register(E_Artifact.FILEPATH, FilepathHandling)
    print("accepted:           %s" % accepted)
    print("FILEPATH in reg:    %s" % (E_Artifact.FILEPATH in reg))
    print("get is Filepath:    %s"
          % (reg.get(E_Artifact.FILEPATH) is FilepathHandling))

    banner("duplicate registration is refused; existing handler preserved")

    class _OtherHandler(ArtifactHandling):
        @classmethod
        def canonicalise(cls, description, conventions): return description
        @classmethod
        def resolve     (cls, normalized_description, local_context): return None

    accepted = reg.register(E_Artifact.FILEPATH, _OtherHandler)
    print("accepted:           %s" % accepted)
    print("get is Filepath:    %s  (still the original)"
          % (reg.get(E_Artifact.FILEPATH) is FilepathHandling))
    print("get is _Other:      %s"
          % (reg.get(E_Artifact.FILEPATH) is _OtherHandler))

    banner("lookup of unregistered type returns None")
    fresh_reg = ArtifactHandlingRegistry()
    print("get(FILEPATH):      %s" % fresh_reg.get(E_Artifact.FILEPATH))


def run_canonicalise():
    """RETURN: None.

    Exercises FilepathHandling.canonicalise() across a range of input
    forms (absolute under root, absolute outside root, relative, with
    '.', with '..', with trailing slash, with double separator) and
    prints the canonical form for each.
    """
    conventions = {"test_root": "/home/user/test_42"}

    cases = [
        ("absolute path under test_root",
            {"path": "/home/user/test_42/build/main.o"}),
        ("absolute path NOT under test_root (kept as-is)",
            {"path": "/usr/lib/libc.so"}),
        ("relative path",
            {"path": "build/main.o"}),
        ("relative path with redundant '.'",
            {"path": "./build/./main.o"}),
        ("relative path with '..' segments",
            {"path": "build/sub/../main.o"}),
        ("relative path with trailing slash",
            {"path": "build/sub/"}),
        ("relative path with double separator",
            {"path": "build//main.o"}),
        ("equivalent forms produce same canonical",
            {"path": "build/sub/../main.o"}),
    ]

    for label, descr in cases:
        banner(label)
        canon = FilepathHandling.canonicalise(descr, conventions)
        print("input:     %s" % descr)
        print("canonical: %s" % canon)


def run_resolve():
    """RETURN: None.

    Demonstrates that FilepathHandling.resolve() recovers a usable local
    path from a canonical form, that two different host_root values
    produce two different local paths from the same canonical form, and
    that omitting host_root returns the canonical path as-is.
    """
    canon = {"path": "build/main.o"}

    banner("local handle on machine A")
    h_a = FilepathHandling.resolve(canon, {"host_root": "/home/alice/test"})
    print("canonical: %s" % canon)
    print("host_root: /home/alice/test")
    print("local:     %s" % h_a)

    banner("local handle on machine B")
    h_b = FilepathHandling.resolve(canon, {"host_root": "/srv/runner3/test"})
    print("canonical: %s" % canon)
    print("host_root: /srv/runner3/test")
    print("local:     %s" % h_b)

    banner("no host_root: canonical path returned as-is")
    h_c = FilepathHandling.resolve(canon, {})
    print("canonical: %s" % canon)
    print("local:     %s" % h_c)

    banner("the same canonical decanonicalises differently per host")
    print("h_a == h_b: %s" % (h_a == h_b))
    print("h_a == h_c: %s" % (h_a == h_c))


HwutRunner(
    argv       = sys.argv,
    title      = "ArtifactHandling registry and Filepath handler",
    choice_map = {
        "registry":     run_registry,
        "canonicalise": run_canonicalise,
        "resolve":      run_resolve,
    },
).run()
