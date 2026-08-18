#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: The provider seam of provision -- one interface per stage role,
         refused at the door, indistinguishable behind it.

CHOICES: roles, door, foreign, cadence, scheme;

DESCRIPTION:

roles     every local stage derives from its role's interface, and the
          canonicalise role alone declares a predecessor argument -- the
          arity asymmetry is out loud, per role, never hidden in one
          signature.

door      a provider in the WRONG slot is refused at construction, by
          name; the right provider in the right slot passes the same
          door.

foreign   a provider that is NOT a local stage -- a stand-in for an
          orchestrator's proxy -- fills the execute slot by deriving the
          interface alone; downstream, its delivery is indistinguishable,
          and the planner-declared 'kind' is what observation reports.

cadence   the cadence rides IN the delivery: a measuring provider hands
          a dict, one that cannot measure hands None -- absence is data,
          and nothing ever asks the provider's person.

scheme    the general scheme: every role roots in I_Provider; a
          multi-provider holds ONE shared means and sets up
          I_ProxyProviders that name it -- and a QUEUE consumes plain
          providers and proxies uniformly, never learning which it got.
______________________________________________________________________________
"""
import os
import sys
import asyncio
import inspect
import tempfile
import config                                                       # noqa: F401

from   vut.language_support.python.hwut_runner import HwutRunner    # noqa: E402
from   vut.engine.operations.run.provider  import (             # noqa: E402
                                               I_Provider,
                                               I_ProxyProvider,
                                               I_MultiProvider,
                                               I_ExecuteProvider,
                                               I_CanonicaliseProvider)
from   vut.engine.operations.run.core import (Provision,        # noqa: E402
                                                  Supply,
                                                  Run)
from   vut.engine.operations.run.stage_execute \
                                          import StageExecute       # noqa: E402
from   vut.engine.operations.run.stage_canonicalise \
                                          import StageCanonicalise  # noqa: E402
from   vut.engine.operations.configuration import (TestConfiguration, # noqa: E402
                                                 TestChoiceConfiguration,
                                                 E_SourceKind)
from   vut.engine.procsitter.procsitter  import ProcsitterConfig    # noqa: E402


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


def _interpreted():
    """RETURN: TestConfiguration, a tiny interpreted test in a fresh
    temporary directory: one line on stdout."""
    directory = tempfile.mkdtemp(prefix="vut_provider_")
    path = os.path.join(directory, "app.py")
    with open(path, "w") as fh:
        fh.write("print('one line')\n")
    return TestConfiguration(
        source_file    = "app.py",
        source_kind    = E_SourceKind.INTERPRETED,
        interpreter    = [sys.executable],
        test_directory = directory,
        caps           = ProcsitterConfig(max_wall_clock_sec=20.0),
        choice_db      = {None: TestChoiceConfiguration()})


class SinkReaderStandIn(I_ExecuteProvider):
    """A stand-in for an orchestrator's proxy: derives the interface,
    delivers raw text as if it had run -- here, as a filled sink would
    be read. It measures no cadence, and says so by None."""

    def __init__(self, stdout_text):
        self.stdout_text = stdout_text

    async def supply(self, stop_event=None):
        """
        RETURN: Supply, product = ({'stdout': ..., 'stderr': ''}, None).
        """
        return Supply(product=({"stdout": self.stdout_text,
                                "stderr": ""}, None))


def test_roles():
    """One interface per role; the local stages derive; the arity
    asymmetry is declared per role."""
    pairs = ((StageExecute,      I_ExecuteProvider),
             (StageCanonicalise, I_CanonicaliseProvider))
    print("INSPECT: stage -> its role interface")
    for stage, interface in pairs:
        print("         %-17s is %s: %s"
              % (stage.__name__, interface.__name__,
                 issubclass(stage, interface)))
    fed  = list(inspect.signature(
                    I_CanonicaliseProvider.supply).parameters)
    lone = list(inspect.signature(I_ExecuteProvider.supply).parameters)
    print("         canonicalise supply(%s)" % ", ".join(fed[1:]))
    print("         execute      supply(%s)" % ", ".join(lone[1:]))
    ok = _check([
        (all(issubclass(s, i) for s, i in pairs),
         "every local stage derives from its role's interface"),
        ("raw_db" in fed and "raw_db" not in lone,
         "the one role fed by its predecessor declares that, alone"),
    ])
    _verdict(ok, "the role is the type, and each role speaks for itself.")


def test_door():
    """A provider in the wrong slot is refused at construction, by
    name; the right one passes the same door."""
    configuration = _interpreted()
    canonicalise = StageCanonicalise(configuration, None)
    execute      = StageExecute(configuration)
    try:
        Provision(stage_execute=canonicalise,
                  stage_canonicalise=canonicalise)
        refusal = "nothing"
    except AssertionError as x:
        refusal = str(x)
    passed = Provision(stage_execute=execute,
                       stage_canonicalise=canonicalise)
    print("INSPECT: a canonicaliser knocks at the execute slot")
    print("         refused: %r" % refusal)
    print("         the execute provider passes: %s"
          % (passed.stage_execute is execute))
    ok = _check([
        ("I_ExecuteProvider" in refusal
         and "StageCanonicalise" in refusal,
         "the refusal names the required role and the received type"),
        (passed.stage_execute is execute,
         "the right provider passes the same door"),
    ])
    _verdict(ok, "a wrong plug is refused at the door, never downstream.")


def test_foreign():
    """A foreign provider -- the shape of an orchestrator's proxy --
    fills the slot by deriving the interface alone; the planner declares
    what observation reports."""
    provision = Provision(
        stage_execute      = SinkReaderStandIn("as if it had run\n"),
        stage_canonicalise = StageCanonicalise(_interpreted()),
        kind               = "Run")
    subjects = asyncio.run(provision.provide())
    print("INSPECT: a stand-in proxy fills the execute slot")
    print("         delivered subjects = %s" % subjects.names())
    print("         stdout             = %r"
          % subjects["stdout"].open().read())
    print("         kind (declared)    = %r" % provision.kind)
    ok = _check([
        (subjects["stdout"].open().read() == "as if it had run\n",
         "downstream, the delivery is indistinguishable"),
        (provision.kind == "Run",
         "observation reports what the planner declared"),
    ])
    _verdict(ok, "behind the interface, local and proxy are one kind.")


def test_cadence():
    """The cadence rides IN the delivery: dict where measured, None
    where not -- nothing asks the provider's person."""
    configuration = _interpreted()

    async def one(provision):
        """RETURN: Subjects, the delivery of 'provision'."""
        return await provision.provide()

    measured   = asyncio.run(one(Run(configuration, keep_timing=True)))
    unmeasured = asyncio.run(one(Run(configuration, keep_timing=False)))
    proxied    = asyncio.run(one(Provision(
        stage_execute      = SinkReaderStandIn("one line\n"),
        stage_canonicalise = StageCanonicalise(configuration),
        kind               = "Run")))
    print("INSPECT: measuring run   -> timing_db is a dict: %s, "
          "'stdout' measured: %s"
          % (isinstance(measured.timing_db, dict),
             "stdout" in (measured.timing_db or {})))
    print("         non-measuring   -> timing_db = %s"
          % unmeasured.timing_db)
    print("         proxy delivery  -> timing_db = %s" % proxied.timing_db)
    ok = _check([
        (isinstance(measured.timing_db, dict)
         and "stdout" in measured.timing_db,
         "a measuring provider hands the cadence in the delivery"),
        (unmeasured.timing_db is None,
         "a non-measuring one hands None -- absent, not empty"),
        (proxied.timing_db is None,
         "a provider that cannot measure says so the same way"),
    ])
    _verdict(ok, "the cadence is read from the delivery, never from the "
                 "provider's person.")


def test_scheme():
    """The general scheme: one root, proxies handed out by a multi, one
    queue for both shapes."""
    import dataclasses
    from vut.engine.operations.run.multi_execute import MultiExecute
    configuration = dataclasses.replace(_interpreted(), interactive=True)
    m       = MultiExecute(configuration)
    proxy   = m.provider("a")
    local   = StageExecute(configuration)
    queue   = [local, proxy]
    role_db = (I_ExecuteProvider, I_CanonicaliseProvider)
    print("INSPECT: every role roots in I_Provider: %s"
          % all(issubclass(r, I_Provider) for r in role_db))
    print("         MultiExecute  is an I_MultiProvider: %s"
          % isinstance(m, I_MultiProvider))
    print("         its hand-out  is I_ProxyProvider and I_ExecuteProvider: "
          "%s, %s" % (isinstance(proxy, I_ProxyProvider),
                      isinstance(proxy, I_ExecuteProvider)))
    print("         the proxy names its multi: %s" % (proxy.multi is m))
    print("         the queue sees I_Provider, uniformly: %s"
          % all(isinstance(p, I_Provider) for p in queue))
    print("         a local stage is NO proxy: %s"
          % (not isinstance(local, I_ProxyProvider)))
    ok = _check([
        (all(issubclass(r, I_Provider) for r in role_db),
         "one root under every role"),
        (isinstance(m, I_MultiProvider)
         and not isinstance(m, I_Provider),
         "a multi-provider holds the means -- its PROXIES fill slots, "
         "not itself"),
        (isinstance(proxy, I_ProxyProvider)
         and isinstance(proxy, I_ExecuteProvider)
         and proxy.multi is m,
         "a hand-out is a proxy IN a role, and names its multi"),
        (all(isinstance(p, I_Provider) for p in queue)
         and not isinstance(local, I_ProxyProvider),
         "one queue consumes both shapes, and provenance stays visible "
         "only to who asks"),
    ])
    _verdict(ok, "queue a provider, or a multi's proxies -- the seam "
                 "carries both.")


HwutRunner(
    argv       = sys.argv,
    title      = "The provider seam: one interface per role, refused at the door",
    choice_map = {
        "roles":   test_roles,
        "door":    test_door,
        "foreign": test_foreign,
        "cadence": test_cadence,
        "scheme":  test_scheme,
    },
).run()
