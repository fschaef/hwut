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
import config                                                       # noqa: F401

from vut.language_support.python.hwut_runner    import HwutRunner
from vut.engine.workflow.artifact               import (E_Artifact,
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

    Demonstrates the registration contract: empty registry; register a
    handler; look it up; reject duplicate registration with a clear
    message; reject lookup of an unregistered type with a clear message.
    """
    reg = ArtifactHandlingRegistry()

    banner("empty registry")
    print("FILEPATH in reg: %s" % (E_Artifact.FILEPATH in reg))

    banner("register FilepathHandling for FILEPATH")
    reg.register(E_Artifact.FILEPATH, FilepathHandling)
    print("FILEPATH in reg: %s" % (E_Artifact.FILEPATH in reg))
    print("get(FILEPATH) is FilepathHandling: %s"
          % (reg.get(E_Artifact.FILEPATH) is FilepathHandling))

    banner("duplicate registration is rejected")

    class _OtherHandler(ArtifactHandling):
        @classmethod
        def canonicalise(cls, description, conventions): return description
        @classmethod
        def resolve     (cls, normalized_description, local_context): return None

    try:
        reg.register(E_Artifact.FILEPATH, _OtherHandler)
        print("UNEXPECTED: duplicate registration succeeded")
    except ArtifactHandlingRegistry.DuplicateRegistration as e:
        print("DuplicateRegistration raised (expected)")
        print("message: %s" % e)

    banner("lookup of unregistered type raises KeyError")
    fresh_reg = ArtifactHandlingRegistry()
    try:
        fresh_reg.get(E_Artifact.FILEPATH)
        print("UNEXPECTED: lookup succeeded")
    except KeyError as e:
        print("KeyError raised (expected)")
        print("message: %s" % e)


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
