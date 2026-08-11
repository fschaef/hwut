#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: The multi-builder -- many targets through few tool
         invocations, wave knowledge behind an interface per build
         system.

CHOICES: waves, order, broken;

DESCRIPTION:

waves     three targets, partitioned [(a, b), (c,)] by the fixture
          build system: TWO invocations serve them; every proxy is an
          I_ProxyProvider and an I_BuildProvider naming its multi;
          every delivery carries its wave's record; artifacts exist.

order     waves build IN ORDER: the second wave's invocation sees the
          first wave's artifacts already standing.

broken    a wave whose invocation ends non-zero fails ITS targets by
          name ('build-failed', the record beside it) -- and every
          LATER wave answers 'target-not-built' with NO record and NO
          invocation: nothing pretends to have run.
______________________________________________________________________________
"""
import os
import sys
import asyncio
import tempfile
import config                                                       # noqa: F401

from   vut.language_support.python.hwut_runner import HwutRunner    # noqa: E402
from   vut.engine.test_run.provision.multi_build import (           # noqa: E402
                                               I_BuildSystem,
                                               MultiBuild)
from   vut.engine.test_run.provision.provider import (              # noqa: E402
                                               I_BuildProvider,
                                               I_ProxyProvider)
from   vut.engine.test_run.result import E_TestRunResult            # noqa: E402
from   vut.engine.procsitter.procsitter import ProcsitterConfig     # noqa: E402


def _check(pair_list):
    """
    RETURN: True,  every claim held.
            False, at least one did not.
    """
    ok = True
    for holds, claim in pair_list:
        print("  %s: %s" % ("OK  " if holds else "FAIL", claim))
        if not holds: ok = False
    return ok


def _verdict(ok, sentence):
    """RETURN: None. Prints the one closing line HWUT greps for."""
    print("%s: %s" % ("SUCCESS" if ok else "FAILURE", sentence))


class ToyBuildSystem(I_BuildSystem):
    """The fixture's knowledge: 'a', 'b' and the breaking 'x' share the
    first wave, 'c' stands on them. One invocation per wave: it logs
    itself once, then 'builds' every target by writing '<target>.built'
    -- and 'c' records whether 'a.built' already stood."""

    def waves(self, target_list):
        """RETURN: the fixed partition of the fixture's world."""
        first  = tuple(t for t in target_list if t in ("a", "b", "x"))
        second = tuple(t for t in target_list if t not in ("a", "b", "x"))
        return tuple(w for w in (first, second) if w)

    def argv(self, target_tuple):
        """RETURN: one python invocation building the whole wave."""
        code = (
            "import os\n"
            "open('build.log','a').write('invocation\\n')\n"
            "for t in %r:\n"
            "    if t == 'c':\n"
            "        open('c.saw','w').write("
            "str(os.path.exists('a.built')))\n"
            "    if t == 'x':\n"
            "        raise SystemExit(1)\n"
            "    open(t + '.built','w').write('yes')\n"
            % (list(target_tuple),))
        return [sys.executable, "-c", code]


def _build(target_list):
    """
    RETURN: (dict, MultiBuild, str) -- Supply per target, the closed
            multi, and the build directory.
    """
    directory = tempfile.mkdtemp(prefix="vut_mbuild_")

    async def scene():
        """RETURN: dict, target -> Supply."""
        async with MultiBuild(ToyBuildSystem(), target_list, directory,
                              ProcsitterConfig(max_wall_clock_sec=20.0)
                              ) as multi:
            supply_db = {t: await multi.provider(t).supply()
                         for t in target_list}
        return supply_db, multi

    supply_db, multi = asyncio.run(scene())
    return supply_db, multi, directory


def _invocations(directory):
    """RETURN: int, how many invocations the fixture logged."""
    path = os.path.join(directory, "build.log")
    if not os.path.isfile(path): return 0
    with open(path) as fh:
        return len(fh.read().splitlines())


def test_waves():
    """Two invocations for three targets; proxies in role; records
    beside every delivery."""
    supply_db, multi, directory = _build(("a", "b", "c"))
    proxy = multi.provider("a")
    print("INSPECT: 3 targets, partition [(a, b), (c,)] "
          "-> %i invocation(s)" % _invocations(directory))
    print("         deliveries = %s"
          % {t: s.product for t, s in supply_db.items()})
    print("         proxy roles: I_ProxyProvider %s, I_BuildProvider %s, "
          "names its multi %s"
          % (isinstance(proxy, I_ProxyProvider),
             isinstance(proxy, I_BuildProvider), proxy.multi is multi))
    ok = _check([
        (_invocations(directory) == 2,
         "one invocation per WAVE, not per target"),
        (all(supply_db[t].product == t for t in ("a", "b", "c")),
         "every target is delivered by name"),
        (all(len(s.record_list) == 1 for s in supply_db.values()),
         "every delivery carries its wave's ONE record"),
        (all(os.path.isfile(os.path.join(directory, t + ".built"))
             for t in ("a", "b", "c")),
         "and the artifacts stand"),
        (len(multi.record) == 2,
         "close keeps one attribution per invocation"),
    ])
    _verdict(ok, "many targets, few invocations -- the wave is the "
                 "unit.")


def test_order():
    """The second wave sees the first wave's artifacts standing."""
    supply_db, _, directory = _build(("a", "b", "c"))
    with open(os.path.join(directory, "c.saw")) as fh:
        saw = fh.read()
    print("INSPECT: at c's build, 'a.built' stood: %s" % saw)
    ok = _check([
        (saw == "True",
         "waves build IN ORDER: what 'c' stands on, stands first"),
        (supply_db["c"].report is E_TestRunResult.OK,
         "and 'c' is delivered"),
    ])
    _verdict(ok, "the partition's order is the build's order.")


def test_broken():
    """A broken wave fails its targets; later waves never run."""
    supply_db, multi, directory = _build(("a", "x", "c"))
    print("INSPECT: 'x' breaks its wave; %i invocation(s) ran"
          % _invocations(directory))
    for t in ("a", "x", "c"):
        print("         %s -> product %s, report %s, records %i"
              % (t, supply_db[t].product, supply_db[t].report,
                 len(supply_db[t].record_list)))
    ok = _check([
        (supply_db["x"].product is None
         and supply_db["x"].report is E_TestRunResult.BUILD_FAILED,
         "the breaking target answers 'build-failed'"),
        (supply_db["a"].report is E_TestRunResult.BUILD_FAILED
         and len(supply_db["a"].record_list) == 1,
         "its wave-mates share the verdict, the record beside it"),
        (supply_db["c"].report is E_TestRunResult.TARGET_NOT_BUILT
         and len(supply_db["c"].record_list) == 0,
         "a later wave answers 'target-not-built' -- no record "
         "pretends a run"),
        (_invocations(directory) == 1,
         "and its invocation never happened"),
    ])
    _verdict(ok, "a broken wave breaks what stands on it, and says so.")


HwutRunner(
    argv       = sys.argv,
    title      = "The multi-builder: waves in order, one invocation each",
    choice_map = {
        "waves":  test_waves,
        "order":  test_order,
        "broken": test_broken,
    },
).run()
