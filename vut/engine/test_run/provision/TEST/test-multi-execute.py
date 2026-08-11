#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: The multi-executor -- many choices of one test application
         through ONE supervised call, driven interactively.

CHOICES: session, plugged, status, unknown, refused;

DESCRIPTION:

session   two choices are served by ONE application call: the fixture
          counts its launches; both deliveries are correct; the session
          leaves no residue and its close hands the one attribution.

plugged   a ChoiceExecute fills the execute slot of a Provision beside
          the local canonicalise stage; 'provide()' delivers
          canonicalised subjects; the cadence is None -- a sink has no
          arrival, absence is data.

status    the application exiting non-zero is BEHAVIOR: the streams are
          delivered, the report stays OK -- exactly the classic run's
          law.

unknown   a choice the application does not know 'fail's: product None,
          named report -- and the session survives to serve the next
          real choice.

refused   a configuration that does not register 'interactive' is
          refused at the door, by name; so is a choice name the
          blank-separated wire cannot carry.
______________________________________________________________________________
"""
import os
import sys
import asyncio
import tempfile
import config                                                       # noqa: F401

from   vut.language_support.python.hwut_runner import HwutRunner    # noqa: E402
from   vut.engine.test_run.provision.multi_execute \
                                          import MultiExecute       # noqa: E402
from   vut.engine.test_run.provision.provider \
                                          import I_ExecuteProvider  # noqa: E402
from   vut.engine.test_run.provision.core import Provision          # noqa: E402
from   vut.engine.test_run.result         import E_TestRunResult    # noqa: E402
from   vut.engine.test_run.provision.stage_canonicalise \
                                          import StageCanonicalise  # noqa: E402
from   vut.engine.test_run.configuration import (TestConfiguration, # noqa: E402
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


import vut                                                          # noqa: E402
_REPO_ROOT = os.path.dirname(os.path.abspath(list(vut.__path__)[0]))

_FIXTURE = """\
import sys
sys.path.insert(0, %(root)r)
with open('launch.log', 'a') as fh: fh.write('launched\\n')
from vut.language_support.python.hwut_runner import HwutRunner

def run_alpha():
    print('alpha speaks')
    print('   zebra')
    print('   apple')

def run_beta():
    print('beta speaks')
    print('on stderr, too', file=sys.stderr)

def run_gamma():
    print('gamma speaks, then leaves with 3')
    sys.exit(3)

HwutRunner(sys.argv, 'Fixture;',
           {'alpha': run_alpha, 'beta': run_beta, 'gamma': run_gamma}).run()
"""


def _interactive_configuration(canonicalisers=None):
    """RETURN: TestConfiguration, the interactive fixture in a fresh
    temporary directory."""
    directory = tempfile.mkdtemp(prefix="vut_multi_")
    with open(os.path.join(directory, "app.py"), "w") as fh:
        fh.write(_FIXTURE % {"root": _REPO_ROOT})
    choice = TestChoiceConfiguration(canonicalisers=canonicalisers or {})
    return TestConfiguration(
        source_file    = "app.py",
        source_kind    = E_SourceKind.INTERPRETED,
        interpreter    = [sys.executable],
        test_directory = directory,
        caps           = ProcsitterConfig(max_wall_clock_sec=20.0),
        choice_db      = {"alpha": choice, "beta": choice, "gamma": choice},
        interactive    = True)


def _launch_count(configuration):
    """RETURN: int, how often the fixture application was launched."""
    path = os.path.join(configuration.test_directory, "launch.log")
    if not os.path.isfile(path): return 0
    with open(path) as fh:
        return len(fh.read().splitlines())


def test_session():
    """ONE call, many choices; residue-free; one attribution."""
    configuration = _interactive_configuration()

    async def scene():
        """RETURN: (Supply, Supply, record), two served choices and the
        session's attribution."""
        async with MultiExecute(configuration) as m:
            await m.run(["alpha", "beta"])          # produce first
            a = await m.provider("alpha").supply()
            b = await m.provider("beta").supply()
        return a, b, m.record

    a, b, record = asyncio.run(scene())
    session_dir = os.path.join(configuration.test_directory,
                               ".hwut-session")
    print("INSPECT: the application was launched %i time(s) for 2 choices"
          % _launch_count(configuration))
    print("         alpha stdout = %r" % a.product[0]["stdout"])
    print("         beta  stdout = %r" % b.product[0]["stdout"])
    print("         beta  stderr = %r" % b.product[0]["stderr"])
    ok = _check([
        (_launch_count(configuration) == 1,
         "ONE call served both choices"),
        (a.product[0]["stdout"] == "alpha speaks\n   zebra\n   apple\n",
         "the first choice's channels are its own"),
        (b.product[0]["stdout"] == "beta speaks\n"
         and b.product[0]["stderr"] == "on stderr, too\n",
         "and the second's are its own -- no bleed between choices"),
        (not os.path.isdir(session_dir),
         "the transport leaves with the session"),
        (record is not None,
         "close hands the ONE attribution of the one call"),
        (a.record_list == (record,) and b.record_list == (record,),
         "and EVERY choice carries it: the record of the process that "
         "produced a result is part of that result"),
    ])
    _verdict(ok, "many choices, one application call.")


def test_plugged():
    """The proxy in a Provision, beside the local canonicalise stage."""
    configuration = _interactive_configuration(
        canonicalisers={"stdout": [sys.executable, "-c",
                                   "import sys;"
                                   "print(''.join(sorted("
                                   "sys.stdin.readlines())), end='')"]})

    async def scene():
        """RETURN: Subjects, a full provide() through the session."""
        async with MultiExecute(configuration) as m:
            provision = Provision(
                stage_execute      = m.provider("alpha"),
                stage_canonicalise = StageCanonicalise(configuration,
                                                       "alpha"),
                kind               = "Run")
            return await provision.provide()

    subjects = asyncio.run(scene())
    print("INSPECT: the proxy is an I_ExecuteProvider: %s"
          % isinstance(MultiExecute(configuration).provider("alpha"),
                       I_ExecuteProvider))
    print("         canonicalised stdout = %r"
          % subjects["stdout"].open().read())
    print("         cadence              = %s" % subjects.timing_db)
    ok = _check([
        (subjects["stdout"].open().read()
         == "   apple\n   zebra\nalpha speaks\n",
         "provide() delivers the canonicalised subject"),
        (subjects.timing_db is None,
         "a sink has no arrival: the cadence is absent, never empty"),
    ])
    _verdict(ok, "behind the seam, the session is just an execute "
                 "provider.")


def test_status():
    """A non-zero exit is behavior: delivered, report OK."""
    configuration = _interactive_configuration()

    async def scene():
        """RETURN: Supply, the exiting choice's delivery."""
        async with MultiExecute(configuration) as m:
            return await m.provider("gamma").supply()

    supply = asyncio.run(scene())
    print("INSPECT: the choice leaves with sys.exit(3)")
    print("         stdout = %r" % supply.product[0]["stdout"])
    print("         report = %s" % supply.report)
    ok = _check([
        (supply.product is not None,
         "the exit of the application is behavior: the streams are "
         "delivered"),
        (supply.product[0]["stdout"]
         == "gamma speaks, then leaves with 3\n",
         "and they are the choice's own"),
        (supply.report is E_TestRunResult.OK,
         "the report stays OK -- the classic run's law"),
    ])
    _verdict(ok, "a non-zero status delivers; behavior is judged by "
                 "compare, not here.")


def test_unknown():
    """An unknown choice 'fail's, named; the session survives."""
    configuration = _interactive_configuration()

    async def scene():
        """RETURN: (Supply, Supply), the refused and the served."""
        async with MultiExecute(configuration) as m:
            await m.run(["no-such-choice", "beta"])
            bogus = await m.provider("no-such-choice").supply()
            real  = await m.provider("beta").supply()
        return bogus, real

    bogus, real = asyncio.run(scene())
    print("INSPECT: bogus -> product None: %s, report = %s"
          % (bogus.product is None, bogus.report))
    print("         beta afterwards -> %r" % real.product[0]["stdout"])
    ok = _check([
        (bogus.product is None,
         "an unexecuted command delivers nothing -- never an empty "
         "subject"),
        (bogus.report is E_TestRunResult.TEST_APP_LAUNCH_FAILED,
         "and the report names it"),
        (real.product[0]["stdout"] == "beta speaks\n",
         "the session serves the other choice of the same call"),
        (len(bogus.record_list) == 1,
         "even a refusal carries the producing process's record"),
    ])
    _verdict(ok, "a refusal is named; the session runs on.")


def test_refused():
    """Refusals at the door: no registered capability, no travelable
    name."""
    plain = _interactive_configuration()
    unregistered = TestConfiguration(
        source_file    = plain.source_file,
        source_kind    = plain.source_kind,
        interpreter    = plain.interpreter,
        test_directory = plain.test_directory,
        caps           = plain.caps,
        choice_db      = plain.choice_db)          # interactive: default
    try:
        MultiExecute(unregistered)
        capability = "nothing"
    except AssertionError as x:
        capability = str(x)

    async def scene():
        """RETURN: str, the wire's refusal of a blank-carrying name."""
        async with MultiExecute(plain) as m:
            try:
                m.submit("two words")
                return "nothing"
            except AssertionError as x:
                return str(x)
    wire = asyncio.run(scene())
    print("INSPECT: unregistered capability -> %r" % capability)
    print("         a name with a blank    -> %r" % wire)
    ok = _check([
        ("interactive" in capability,
         "a configuration without the registered capability is refused, "
         "by name"),
        ("blank-separated" in wire,
         "a name the wire cannot carry is refused before it travels"),
    ])
    _verdict(ok, "what cannot make sense is refused at the door.")


HwutRunner(
    argv       = sys.argv,
    title      = "The multi-executor: one application call, many choices",
    choice_map = {
        "session": test_session,
        "plugged": test_plugged,
        "status":  test_status,
        "unknown": test_unknown,
        "refused": test_refused,
    },
).run()
