#! /usr/bin/env python3
#
# @hwut {
#     title      = "Provision: execute, canonicalise, and the loaded read"
#     choices    = ["absent_application", "argv", "canonicalisation",
#                   "canonicaliser_broken", "containment", "loaded",
#                   "same_shape", "source_kinds", "stages", "subjects"]
#     tolerance { eq_pattern = ["SUCCESS.*"] }
#     interactive = true
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PROVISION: HOW A SUBJECT COMES TO EXIST -- execute, then canonicalise.

    UNIT     ONE 'Provision', its STAGES as members (execute,
             canonicalise); 'Run' is the PLANNER that wires it. The
             application is ALREADY PROVIDED: building is the plan's
             (BUILD nodes; 'build_action.py' is one action), and a
             stored run is read back by 'consume/loaded.py' -- the
             SAME 'Subjects' shape, so nothing above can tell them
             apart.

    CAUSAL CONTRACT
             the source kind fixes the argv and the choice name selects
             the scenario; stdout, stderr and every file under OUT/ are
             subjects; a declared canonicaliser rewrites a subject before
             anyone compares it.

    CONSISTENCY CONTRACT
             an ABSENT application is the launch's failure, named by
             execution; a failing canonicaliser leaves the text
             UNCHANGED and says so; an absent recording is reported,
             never invented as empty.

    STAGE CONTRACT
             the wiring is DATA and its law lives at construction.
______________________________________________________________________________
"""
import asyncio
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

from   config import HwutRunner                                  # noqa F401,E402

from   vut.engine.operations.result     import E_TestRunResult  # noqa E402
from   vut.engine.procsitter.api  import ProcsitterConfig # noqa E402
from   vut.engine.operations.build_action import (BuildConfig,    # noqa E402
                                                   E_BuildSystem,
                                                   build)
from   vut.engine.operations.configuration import (               # noqa E402
                                                 TestConfiguration,
                                                 TestChoiceConfiguration,
                                                 E_SourceKind)
from   vut.engine.operations.run.core import (Run,           # noqa E402
                                                  Provision,
                                                  Supply,
                                                  application_argv)
from   vut.engine.operations.consume.loaded import loaded     # noqa E402
from   vut.engine.operations.run.stage_execute      import \
                                                  StageExecute    # noqa E402
from   vut.engine.operations.run.stage_canonicalise import \
                                                  StageCanonicalise  # noqa E402
from   vut.engine.bookkeeper.api import (    # noqa E402
                                                 Bookkeeper)
from   vut.engine.bookkeeper.api         import Store            # noqa E402

#  ASKED OF config.py, NOT COUNTED IN '..'. The walk in config.py is
#  the one place that knows where 'vut' is; a hop count here is a
#  silent hostage to the layout -- this test moved one level deeper
#  once, and the counted path went on pointing into the void.
from   config import VUT_DIRECTORY                               # noqa E402

PYPE = os.path.join(VUT_DIRECTORY, "test_writing_support", "hwut_pype", "hwut_pype.py")

_SORT_SCRIPT = ("on: <bof> => {\n"
                "    collected = []\n"
                "}\n"
                "on: <else> => {\n"
                "    collected.append(pype.line())\n"
                "}\n"
                "on: <eof> => {\n"
                "    for one in sorted(collected):\n"
                "        print(one)\n"
                "}\n")


def _check(pair_list):
    """RETURN: True, every claim held; False, at least one did not."""
    ok = True
    for holds, claim in pair_list:
        print("  %s: %s" % ("OK  " if holds else "FAIL", claim))
        if not holds: ok = False
    return ok


def _verdict(ok, sentence):
    """RETURN: None. Prints the one closing line HWUT greps for."""
    print("%s: %s" % ("SUCCESS" if ok else "FAILURE", sentence))


def _place(application_text, extra_db=None):
    """
    RETURN: str, a fresh test directory holding 'demo.py' and whatever
            'extra_db' names (file name -> content).
    """
    directory = tempfile.mkdtemp(prefix="vut_prov_")
    with open(os.path.join(directory, "demo.py"), "w") as fh:
        fh.write(application_text)
    for name, content in (extra_db or {}).items():
        with open(os.path.join(directory, name), "w") as fh:
            fh.write(content)
    return directory


def _interpreted_capped(directory, **cap_db):
    """RETURN: TestConfiguration, an INTERPRETED test under given caps."""
    return TestConfiguration(
        source_file    = "demo.py",
        source_kind    = E_SourceKind.INTERPRETED,
        test_directory = directory,
        caps           = ProcsitterConfig(**{"max_wall_clock_sec": 30.0,
                                             **cap_db}),
        interpreter    = ["python3", "-u"],
        choice_db      = {None: TestChoiceConfiguration()})


def _interpreted(directory, canonicaliser_db=None, choice_db=None,
                 output=None):
    """RETURN: TestConfiguration, an INTERPRETED test in 'directory'.

    'output' states the subjects (R-71). None leaves the default --
    the stdout channel alone.
    """
    entry = TestChoiceConfiguration(canonicalisers=canonicaliser_db or {},
                                    output=output)
    return TestConfiguration(
        source_file    = "demo.py",
        source_kind    = E_SourceKind.INTERPRETED,
        test_directory = directory,
        caps           = ProcsitterConfig(max_wall_clock_sec=20.0),
        interpreter    = ["python3", "-u"],
        choice_db      = choice_db or {None: entry})


def test_argv():
    """The source kind fixes the prefix; the CHOICE NAME is the argument
    that selects the scenario. A test without choices gets none."""
    directory = _place("print('x')\n")
    with_choice = _interpreted(directory,
                               choice_db={"basic": TestChoiceConfiguration()})
    without     = _interpreted(directory)

    a = application_argv(with_choice, "basic")
    b = application_argv(without, None)
    print("INSPECT: INTERPRETED, choice 'basic' -> %s" % (a[:2] + [a[-1]]))
    print("         INTERPRETED, no choice      -> %s" % b[:2])
    ok = _check([
        (a[0:2] == ["python3", "-u"],
         "the interpreter prefix leads the argv"),
        (a[-1] == "basic",
         "the choice name is appended as the selecting argument"),
        (b[-1].endswith("demo.py"),
         "a test without choices ends at the source file"),
        (len(b) == len(a) - 1,
         "and carries exactly one argument fewer"),
    ])
    shutil.rmtree(directory, ignore_errors=True)
    _verdict(ok, "the source kind fixes the argv; the choice selects.")


def test_subjects():
    """SUBJECTS ARE DECLARED, NEVER DISCOVERED (R-71). A file becomes a
    subject because 'output' NAMES it -- not because the run happened
    to leave it behind. Both channels are provided regardless; what is
    JUDGED is decided above (stderr never is, E-5).

    The file is read AFTER termination, hence no race, and REMOVED:
    a lingering file would be explored as a test application by the
    next walk, and a stale one would green a run that stopped
    producing it."""
    directory = _place(
        "import sys\n"
        "print('to stdout')\n"
        "sys.stderr.write('to stderr\\n')\n"
        "open('emitted.txt','w').write('to a file\\n')\n")
    configuration = _interpreted(directory,
                                 output=("stdout", "emitted.txt"))
    provided = asyncio.run(Run(configuration).provide())

    print("INSPECT: declared = %s"
          % (configuration.choice_db[None].output,))
    print("         report   = %s" % provided.provision.report)
    print("         subjects = %s" % provided.names())
    for name in provided.names():
        print("           %-12s %r" % (name, provided[name].open().read()))
    print("         residue  = %s"
          % os.path.exists(os.path.join(directory, "emitted.txt")))
    ok = _check([
        (provided.names() == ["emitted.txt", "stderr", "stdout"],
         "the DECLARED file is a subject, beside both channels"),
        (provided.provision.report is E_TestRunResult.OK,
         "provision reports OK"),
        (len(provided.provision.records) == 1,
         "one attribution record: one supervised call happened"),
        (not os.path.exists(os.path.join(directory, "emitted.txt")),
         "read AND REMOVED: the carrier leaves no residue"),
    ])
    shutil.rmtree(directory, ignore_errors=True)
    _verdict(ok, "a declared file is a subject; the channels always are.")


def test_canonicalisation():
    """Canonicalisation is PROVISION: the subject handed over is already
    the comparable stream. Here a run whose line ORDER is arbitrary
    becomes one canonical form."""
    directory = _place("print('zebra'); print('apple'); print('mango')\n",
                       {"sort.pype": _SORT_SCRIPT})
    raw = asyncio.run(Run(_interpreted(directory)).provide())
    can = asyncio.run(Run(_interpreted(
              directory,
              {"stdout": ["python3", PYPE,
                          os.path.join(directory, "sort.pype")]})).provide())

    print("INSPECT: raw           = %r" % raw["stdout"].open().read())
    print("         canonicalised = %r" % can["stdout"].open().read())
    print("         report        = %s" % can.provision.report)
    ok = _check([
        (raw["stdout"].open().read() == "zebra\napple\nmango\n",
         "raw keeps the order the application happened to emit"),
        (can["stdout"].open().read() == "apple\nmango\nzebra\n",
         "the canonicalised subject is in canonical order"),
        (can.provision.report is E_TestRunResult.OK,
         "and provision reports OK"),
        ("stderr" in can and can["stderr"].open().read() == "",
         "a subject with no canonicaliser is passed through raw"),
    ])
    shutil.rmtree(directory, ignore_errors=True)
    _verdict(ok, "what provision hands over is already comparable.")


def test_canonicaliser_failure():
    """A canonicaliser that cannot run ENDS PROVISION: nothing is
    handed over, and the report names the canonicaliser. Handing the
    RAW text over would deliver a stream nobody ever meant to compare
    -- and where the nominal was blessed from an equally unfiltered
    run, the test would pass for the wrong reason with nothing to say
    so."""
    directory = _place("print('alpha')\n")
    provided  = asyncio.run(Run(_interpreted(
        directory, {"stdout": ["no-such-canonicaliser-anywhere"]})).provide())

    print("INSPECT: report   = %s" % provided.provision.report)
    print("         provided = %s" % provided.names())
    print("         'stdout' in provided = %s" % ("stdout" in provided))
    print("         records  = %d (execution, canonicalisation)"
          % len(provided.provision.records))
    ok = _check([
        (provided.provision.report
             is E_TestRunResult.PYPE_INTERPRETER_NOT_FOUND,
         "the report names the canonicaliser, not the application"),
        (provided.names() == [],
         "NOTHING is handed over -- never a stream the filter did not "
         "touch"),
        ("stdout" not in provided,
         "and asking for one answers 'no', never an exception"),
        (len(provided.provision.records) == 2,
         "the attribution carries both calls: the application's and "
         "the canonicaliser's"),
    ])
    shutil.rmtree(directory, ignore_errors=True)
    _verdict(ok, "a broken canonicaliser ends provision and blames "
                 "itself, not the code.")


def test_absent_application():
    """The application is ALREADY PROVIDED (building is the plan's): a
    COMPILED test whose artifact does not stand is the LAUNCH's
    failure, named by execution -- nothing is built here."""
    directory = tempfile.mkdtemp(prefix="vut_prov_")
    configuration = TestConfiguration(
        source_file    = "demo.c",
        source_kind    = E_SourceKind.COMPILED,
        test_directory = directory,
        caps           = ProcsitterConfig(max_wall_clock_sec=20.0),
        build          = BuildConfig(E_BuildSystem.MAKE, ["app"]),
        choice_db      = {None: TestChoiceConfiguration()})
    provided = asyncio.run(Run(configuration).provide())

    print("INSPECT: report   = %s" % provided.provision.report)
    print("         subjects = %s" % provided.names())
    ok = _check([
        (provided.provision.report
             is E_TestRunResult.TEST_APP_LAUNCH_FAILED,
         "the launch names the absence -- nothing was built here"),
        (provided.names() == [],
         "NO subject is provided"),
    ])
    shutil.rmtree(directory, ignore_errors=True)
    _verdict(ok, "an unprovided application is the launch's failure.")


def test_loaded():
    """'consume/loaded.py' reads what was stored. Nothing executes, so
    there is no attribution to make -- and an absent recording is
    REPORTED, never invented as an empty subject."""
    directory = tempfile.mkdtemp(prefix="vut_prov_")
    store     = Store(Bookkeeper(directory))
    store.write_candidate("demo", None, "stdout", "recorded line\n")
    store.write_candidate("demo", None, "stderr", "")

    present = loaded(store, "demo")
    absent  = loaded(store, "never-recorded")

    print("INSPECT: stored    -> report %s, subjects %s"
          % (present.provision.report, present.names()))
    print("         stdout    -> %r" % present["stdout"].open().read())
    print("         unstored  -> report %s, subjects %s"
          % (absent.provision.report, absent.names()))
    ok = _check([
        (present.provision.report is E_TestRunResult.OK,
         "a stored recording is provided"),
        (present["stdout"].open().read() == "recorded line\n",
         "and reads back what was written"),
        (present.provision.records == (),
         "nothing ran, so there is no attribution to make"),
        (absent.provision.report is E_TestRunResult.RECORDING_MISSING,
         "an absent recording is REPORTED"),
        (absent.names() == [],
         "and not invented as an empty subject"),
    ])
    shutil.rmtree(directory, ignore_errors=True)
    _verdict(ok, "stored data provides subjects; absence says so.")


def test_same_shape():
    """Run and 'loaded' return the SAME thing, so nothing above ever
    branches on which one it got."""
    directory = _place("print('same')\n")
    executed  = asyncio.run(Run(_interpreted(directory)).provide())

    store = Store(Bookkeeper(directory))
    for name in ("stdout", "stderr"):
        store.write_candidate("demo", None, name,
                              executed[name].open().read())
    replayed = loaded(store, "demo")

    print("INSPECT: Run    -> %s, type %s"
          % (executed.names(), type(executed).__name__))
    print("         loaded -> %s, type %s"
          % (replayed.names(), type(replayed).__name__))
    print("         stdout matches: %s"
          % (executed["stdout"].open().read()
             == replayed["stdout"].open().read()))
    ok = _check([
        (type(executed) is type(replayed),
         "both return the same type"),
        (executed.names() == replayed.names(),
         "with the same subject names"),
        (executed["stdout"].open().read()
             == replayed["stdout"].open().read(),
         "and the same bytes"),

    ])
    shutil.rmtree(directory, ignore_errors=True)
    _verdict(ok, "one product, two provenances, indistinguishable above.")


def test_source_kinds():
    """ALL THREE source kinds, each launched for real. COMPILED runs
    the artifact BUILT ABOVE (the plan's order, replayed by hand with
    'build_action'); EXECUTABLE runs the file itself."""
    directory = tempfile.mkdtemp(prefix="vut_prov_")
    build_dir = os.path.join(directory, "BUILD", "app.c")
    os.makedirs(build_dir)
    with open(os.path.join(build_dir, "Makefile"), "w") as fh:
        fh.write("built:\n"
                 "\tprintf '#! /bin/sh\\necho compiled artifact ran\\n' "
                 "> built\n"
                 "\tchmod +x built\n")
    compiled = TestConfiguration(
        source_file    = "app.c",
        source_kind    = E_SourceKind.COMPILED,
        test_directory = directory,
        caps           = ProcsitterConfig(max_wall_clock_sec=20.0),
        build          = BuildConfig(E_BuildSystem.MAKE, ["built"]),
        choice_db      = {None: TestChoiceConfiguration()})
    #  BUILT ABOVE, run here: the plan's order, replayed by hand.
    asyncio.run(build(compiled))
    compiled_out = asyncio.run(Run(compiled).provide())

    script = os.path.join(directory, "direct.sh")
    with open(script, "w") as fh:
        fh.write('#! /bin/sh\necho executable ran with "$1"\n')
    os.chmod(script, 0o755)
    executable = TestConfiguration(
        source_file    = "direct.sh",
        source_kind    = E_SourceKind.EXECUTABLE,
        test_directory = directory,
        caps           = ProcsitterConfig(max_wall_clock_sec=20.0),
        choice_db      = {"basic": TestChoiceConfiguration()})
    executable_out = asyncio.run(Run(executable, "basic").provide())

    print("INSPECT: COMPILED argv   = %s"
          % [os.path.basename(a) for a in application_argv(compiled, None)])
    print("         COMPILED stdout = %r"
          % compiled_out["stdout"].open().read())
    print("         EXECUTABLE argv = %s"
          % [os.path.basename(a) for a in application_argv(executable,
                                                           "basic")])
    print("         EXECUTABLE out  = %r"
          % executable_out["stdout"].open().read())
    ok = _check([
        (compiled_out.provision.report is E_TestRunResult.OK,
         "the COMPILED test built AND ran"),
        (compiled_out["stdout"].open().read() == "compiled artifact ran\n",
         "and its ARTIFACT produced the output, not its source"),
        (len(compiled_out.provision.records) == 1,
         "one record: the run's -- the build's own attribution is the "
         "BUILD node's, above"),
        (executable_out["stdout"].open().read()
             == "executable ran with basic\n",
         "the EXECUTABLE ran directly, with the choice as its argument"),
    ])
    shutil.rmtree(directory, ignore_errors=True)
    _verdict(ok, "all three source kinds launch what they should.")


def test_containment_reaches_the_report():
    """A run ended by a CAP is reported as such. The silence cap in
    particular: procsitter attributes FAIL_STALLED, and provision must
    render that as TEST_APP_STALLED rather than losing it."""
    directory = _place("import time\n"
                       "print('one line, then silence')\n"
                       "time.sleep(30)\n")
    stalled = asyncio.run(Run(_interpreted_capped(
        directory, max_output_gap_sec=1.0)).provide())

    directory2 = _place("import time\ntime.sleep(30)\n")
    timed_out  = asyncio.run(Run(_interpreted_capped(
        directory2, max_wall_clock_sec=1.0)).provide())

    print("INSPECT: silent run  -> containment %s, report %s"
          % (stalled.provision.records[0].containment.name,
             stalled.provision.report))
    print("         long run    -> containment %s, report %s"
          % (timed_out.provision.records[0].containment.name,
             timed_out.provision.report))
    ok = _check([
        (stalled.provision.report is E_TestRunResult.TEST_APP_STALLED,
         "FAIL_STALLED becomes TEST_APP_STALLED"),
        (timed_out.provision.report
             is E_TestRunResult.TEST_APP_WALL_CLOCK_EXCEEDED,
         "a cap names itself (O-19): the wall clock, here"),
        ("one line" in stalled["stdout"].open().read(),
         "and what the run DID produce is still handed over"),
    ])
    for d in (directory, directory2): shutil.rmtree(d, ignore_errors=True)
    _verdict(ok, "a cap that ended the run reaches the report.")


def test_stages():
    """A Provision holds its stages as MEMBERS -- the wiring is DATA,
    and its law lives at CONSTRUCTION, where the wiring is written:
    both stages stand, or the provision is refused by name."""
    directory = _place("print('hi')\n")
    executed  = Run(_interpreted(directory))

    def picture(p):
        """RETURN: str, one mark per stage member, 'X' present."""
        return " ".join("X" if s is not None else "-"
                        for s in (p.stage_execute,
                                  p.stage_canonicalise))
    print("INSPECT: wiring  [execute canonicalise]")
    print("         Run -> %s   kind %r" % (picture(executed),
                                            executed.kind))

    refused = []
    for label, kwargs in (
            ("no execute",      {"stage_canonicalise":
                                     executed.stage_canonicalise}),
            ("no canonicalise", {"stage_execute":
                                     executed.stage_execute})):
        try:
            Provision(**kwargs)
            refused.append(False)
        except AssertionError:
            refused.append(True)
    print("         no execute refused: %s" % refused[0])
    print("         no canonicalise refused: %s" % refused[1])

    ok = _check([
        (executed.stage_execute is not None
         and executed.stage_canonicalise is not None,
         "an executing provision: execute and canonicalise"),
        (all(refused),
         "a missing stage is refused at construction, by name"),
    ])
    shutil.rmtree(directory, ignore_errors=True)
    _verdict(ok, "the wiring is data, and its law lives at the door.")

#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PROVISION: HOW A SUBJECT COMES TO EXIST -- execute, then canonicalise.

    UNIT     ONE 'Provision', its STAGES as members (execute,
             canonicalise); 'Run' is the PLANNER that wires it. The
             application is ALREADY PROVIDED: building is the plan's
             (BUILD nodes; 'build_action.py' is one action), and a
             stored run is read back by 'consume/loaded.py' -- the
             SAME 'Subjects' shape, so nothing above can tell them
             apart.

    CAUSAL CONTRACT
             the source kind fixes the argv and the choice name selects
             the scenario; stdout, stderr and every file under OUT/ are
             subjects; a declared canonicaliser rewrites a subject before
             anyone compares it.

    CONSISTENCY CONTRACT
             an ABSENT application is the launch's failure, named by
             execution; a failing canonicaliser leaves the text
             UNCHANGED and says so; an absent recording is reported,
             never invented as empty.

    STAGE CONTRACT
             the wiring is DATA and its law lives at construction.
______________________________________________________________________________
"""
import asyncio
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

from   config import HwutRunner                                  # noqa F401,E402

from   vut.engine.operations.result     import E_TestRunResult  # noqa E402
from   vut.engine.procsitter.api  import ProcsitterConfig # noqa E402
from   vut.engine.operations.build_action import (BuildConfig,    # noqa E402
                                                   E_BuildSystem,
                                                   build)
from   vut.engine.operations.configuration import (               # noqa E402
                                                 TestConfiguration,
                                                 TestChoiceConfiguration,
                                                 E_SourceKind)
from   vut.engine.operations.run.core import (Run,           # noqa E402
                                                  Provision,
                                                  Supply,
                                                  application_argv)
from   vut.engine.operations.consume.loaded import loaded     # noqa E402
from   vut.engine.operations.run.stage_execute      import \
                                                  StageExecute    # noqa E402
from   vut.engine.operations.run.stage_canonicalise import \
                                                  StageCanonicalise  # noqa E402
from   vut.engine.bookkeeper.api import (    # noqa E402
                                                 Bookkeeper)
from   vut.engine.bookkeeper.api         import Store            # noqa E402

#  ASKED OF config.py, NOT COUNTED IN '..'. The walk in config.py is
#  the one place that knows where 'vut' is; a hop count here is a
#  silent hostage to the layout -- this test moved one level deeper
#  once, and the counted path went on pointing into the void.
from   config import VUT_DIRECTORY                               # noqa E402

PYPE = os.path.join(VUT_DIRECTORY, "test_writing_support", "hwut_pype", "hwut_pype.py")

_SORT_SCRIPT = ("on: <bof> => {\n"
                "    collected = []\n"
                "}\n"
                "on: <else> => {\n"
                "    collected.append(pype.line())\n"
                "}\n"
                "on: <eof> => {\n"
                "    for one in sorted(collected):\n"
                "        print(one)\n"
                "}\n")


def _check(pair_list):
    """RETURN: True, every claim held; False, at least one did not."""
    ok = True
    for holds, claim in pair_list:
        print("  %s: %s" % ("OK  " if holds else "FAIL", claim))
        if not holds: ok = False
    return ok


def _verdict(ok, sentence):
    """RETURN: None. Prints the one closing line HWUT greps for."""
    print("%s: %s" % ("SUCCESS" if ok else "FAILURE", sentence))


def _place(application_text, extra_db=None):
    """
    RETURN: str, a fresh test directory holding 'demo.py' and whatever
            'extra_db' names (file name -> content).
    """
    directory = tempfile.mkdtemp(prefix="vut_prov_")
    with open(os.path.join(directory, "demo.py"), "w") as fh:
        fh.write(application_text)
    for name, content in (extra_db or {}).items():
        with open(os.path.join(directory, name), "w") as fh:
            fh.write(content)
    return directory


def _interpreted_capped(directory, **cap_db):
    """RETURN: TestConfiguration, an INTERPRETED test under given caps."""
    return TestConfiguration(
        source_file    = "demo.py",
        source_kind    = E_SourceKind.INTERPRETED,
        test_directory = directory,
        caps           = ProcsitterConfig(**{"max_wall_clock_sec": 30.0,
                                             **cap_db}),
        interpreter    = ["python3", "-u"],
        choice_db      = {None: TestChoiceConfiguration()})


def _interpreted(directory, canonicaliser_db=None, choice_db=None,
                 output=None):
    """RETURN: TestConfiguration, an INTERPRETED test in 'directory'.

    'output' states the subjects (R-71). None leaves the default --
    the stdout channel alone.
    """
    entry = TestChoiceConfiguration(canonicalisers=canonicaliser_db or {},
                                    output=output)
    return TestConfiguration(
        source_file    = "demo.py",
        source_kind    = E_SourceKind.INTERPRETED,
        test_directory = directory,
        caps           = ProcsitterConfig(max_wall_clock_sec=20.0),
        interpreter    = ["python3", "-u"],
        choice_db      = choice_db or {None: entry})


def test_argv():
    """The source kind fixes the prefix; the CHOICE NAME is the argument
    that selects the scenario. A test without choices gets none."""
    directory = _place("print('x')\n")
    with_choice = _interpreted(directory,
                               choice_db={"basic": TestChoiceConfiguration()})
    without     = _interpreted(directory)

    a = application_argv(with_choice, "basic")
    b = application_argv(without, None)
    print("INSPECT: INTERPRETED, choice 'basic' -> %s" % (a[:2] + [a[-1]]))
    print("         INTERPRETED, no choice      -> %s" % b[:2])
    ok = _check([
        (a[0:2] == ["python3", "-u"],
         "the interpreter prefix leads the argv"),
        (a[-1] == "basic",
         "the choice name is appended as the selecting argument"),
        (b[-1].endswith("demo.py"),
         "a test without choices ends at the source file"),
        (len(b) == len(a) - 1,
         "and carries exactly one argument fewer"),
    ])
    shutil.rmtree(directory, ignore_errors=True)
    _verdict(ok, "the source kind fixes the argv; the choice selects.")


def test_subjects():
    """SUBJECTS ARE DECLARED, NEVER DISCOVERED (R-71). A file becomes a
    subject because 'output' NAMES it -- not because the run happened
    to leave it behind. Both channels are provided regardless; what is
    JUDGED is decided above (stderr never is, E-5).

    The file is read AFTER termination, hence no race, and REMOVED:
    a lingering file would be explored as a test application by the
    next walk, and a stale one would green a run that stopped
    producing it."""
    directory = _place(
        "import sys\n"
        "print('to stdout')\n"
        "sys.stderr.write('to stderr\\n')\n"
        "open('emitted.txt','w').write('to a file\\n')\n")
    configuration = _interpreted(directory,
                                 output=("stdout", "emitted.txt"))
    provided = asyncio.run(Run(configuration).provide())

    print("INSPECT: declared = %s"
          % (configuration.choice_db[None].output,))
    print("         report   = %s" % provided.provision.report)
    print("         subjects = %s" % provided.names())
    for name in provided.names():
        print("           %-12s %r" % (name, provided[name].open().read()))
    print("         residue  = %s"
          % os.path.exists(os.path.join(directory, "emitted.txt")))
    ok = _check([
        (provided.names() == ["emitted.txt", "stderr", "stdout"],
         "the DECLARED file is a subject, beside both channels"),
        (provided.provision.report is E_TestRunResult.OK,
         "provision reports OK"),
        (len(provided.provision.records) == 1,
         "one attribution record: one supervised call happened"),
        (not os.path.exists(os.path.join(directory, "emitted.txt")),
         "read AND REMOVED: the carrier leaves no residue"),
    ])
    shutil.rmtree(directory, ignore_errors=True)
    _verdict(ok, "a declared file is a subject; the channels always are.")


def test_canonicalisation():
    """Canonicalisation is PROVISION: the subject handed over is already
    the comparable stream. Here a run whose line ORDER is arbitrary
    becomes one canonical form."""
    directory = _place("print('zebra'); print('apple'); print('mango')\n",
                       {"sort.pype": _SORT_SCRIPT})
    raw = asyncio.run(Run(_interpreted(directory)).provide())
    can = asyncio.run(Run(_interpreted(
              directory,
              {"stdout": ["python3", PYPE,
                          os.path.join(directory, "sort.pype")]})).provide())

    print("INSPECT: raw           = %r" % raw["stdout"].open().read())
    print("         canonicalised = %r" % can["stdout"].open().read())
    print("         report        = %s" % can.provision.report)
    ok = _check([
        (raw["stdout"].open().read() == "zebra\napple\nmango\n",
         "raw keeps the order the application happened to emit"),
        (can["stdout"].open().read() == "apple\nmango\nzebra\n",
         "the canonicalised subject is in canonical order"),
        (can.provision.report is E_TestRunResult.OK,
         "and provision reports OK"),
        ("stderr" in can and can["stderr"].open().read() == "",
         "a subject with no canonicaliser is passed through raw"),
    ])
    shutil.rmtree(directory, ignore_errors=True)
    _verdict(ok, "what provision hands over is already comparable.")


def test_canonicaliser_failure():
    """A canonicaliser that cannot run ENDS PROVISION: nothing is
    handed over, and the report names the canonicaliser. Handing the
    RAW text over would deliver a stream nobody ever meant to compare
    -- and where the nominal was blessed from an equally unfiltered
    run, the test would pass for the wrong reason with nothing to say
    so."""
    directory = _place("print('alpha')\n")
    provided  = asyncio.run(Run(_interpreted(
        directory, {"stdout": ["no-such-canonicaliser-anywhere"]})).provide())

    print("INSPECT: report   = %s" % provided.provision.report)
    print("         provided = %s" % provided.names())
    print("         'stdout' in provided = %s" % ("stdout" in provided))
    print("         records  = %d (execution, canonicalisation)"
          % len(provided.provision.records))
    ok = _check([
        (provided.provision.report
             is E_TestRunResult.PYPE_INTERPRETER_NOT_FOUND,
         "the report names the canonicaliser, not the application"),
        (provided.names() == [],
         "NOTHING is handed over -- never a stream the filter did not "
         "touch"),
        ("stdout" not in provided,
         "and asking for one answers 'no', never an exception"),
        (len(provided.provision.records) == 2,
         "the attribution carries both calls: the application's and "
         "the canonicaliser's"),
    ])
    shutil.rmtree(directory, ignore_errors=True)
    _verdict(ok, "a broken canonicaliser ends provision and blames "
                 "itself, not the code.")


def test_absent_application():
    """The application is ALREADY PROVIDED (building is the plan's): a
    COMPILED test whose artifact does not stand is the LAUNCH's
    failure, named by execution -- nothing is built here."""
    directory = tempfile.mkdtemp(prefix="vut_prov_")
    configuration = TestConfiguration(
        source_file    = "demo.c",
        source_kind    = E_SourceKind.COMPILED,
        test_directory = directory,
        caps           = ProcsitterConfig(max_wall_clock_sec=20.0),
        build          = BuildConfig(E_BuildSystem.MAKE, ["app"]),
        choice_db      = {None: TestChoiceConfiguration()})
    provided = asyncio.run(Run(configuration).provide())

    print("INSPECT: report   = %s" % provided.provision.report)
    print("         subjects = %s" % provided.names())
    ok = _check([
        (provided.provision.report
             is E_TestRunResult.TEST_APP_LAUNCH_FAILED,
         "the launch names the absence -- nothing was built here"),
        (provided.names() == [],
         "NO subject is provided"),
    ])
    shutil.rmtree(directory, ignore_errors=True)
    _verdict(ok, "an unprovided application is the launch's failure.")


def test_loaded():
    """'consume/loaded.py' reads what was stored. Nothing executes, so
    there is no attribution to make -- and an absent recording is
    REPORTED, never invented as an empty subject."""
    directory = tempfile.mkdtemp(prefix="vut_prov_")
    store     = Store(Bookkeeper(directory))
    store.write_candidate("demo", None, "stdout", "recorded line\n")
    store.write_candidate("demo", None, "stderr", "")

    present = loaded(store, "demo")
    absent  = loaded(store, "never-recorded")

    print("INSPECT: stored    -> report %s, subjects %s"
          % (present.provision.report, present.names()))
    print("         stdout    -> %r" % present["stdout"].open().read())
    print("         unstored  -> report %s, subjects %s"
          % (absent.provision.report, absent.names()))
    ok = _check([
        (present.provision.report is E_TestRunResult.OK,
         "a stored recording is provided"),
        (present["stdout"].open().read() == "recorded line\n",
         "and reads back what was written"),
        (present.provision.records == (),
         "nothing ran, so there is no attribution to make"),
        (absent.provision.report is E_TestRunResult.RECORDING_MISSING,
         "an absent recording is REPORTED"),
        (absent.names() == [],
         "and not invented as an empty subject"),
    ])
    shutil.rmtree(directory, ignore_errors=True)
    _verdict(ok, "stored data provides subjects; absence says so.")


def test_same_shape():
    """Run and 'loaded' return the SAME thing, so nothing above ever
    branches on which one it got."""
    directory = _place("print('same')\n")
    executed  = asyncio.run(Run(_interpreted(directory)).provide())

    store = Store(Bookkeeper(directory))
    for name in ("stdout", "stderr"):
        store.write_candidate("demo", None, name,
                              executed[name].open().read())
    replayed = loaded(store, "demo")

    print("INSPECT: Run    -> %s, type %s"
          % (executed.names(), type(executed).__name__))
    print("         loaded -> %s, type %s"
          % (replayed.names(), type(replayed).__name__))
    print("         stdout matches: %s"
          % (executed["stdout"].open().read()
             == replayed["stdout"].open().read()))
    ok = _check([
        (type(executed) is type(replayed),
         "both return the same type"),
        (executed.names() == replayed.names(),
         "with the same subject names"),
        (executed["stdout"].open().read()
             == replayed["stdout"].open().read(),
         "and the same bytes"),

    ])
    shutil.rmtree(directory, ignore_errors=True)
    _verdict(ok, "one product, two provenances, indistinguishable above.")


def test_source_kinds():
    """ALL THREE source kinds, each launched for real. COMPILED runs
    the artifact BUILT ABOVE (the plan's order, replayed by hand with
    'build_action'); EXECUTABLE runs the file itself."""
    directory = tempfile.mkdtemp(prefix="vut_prov_")
    build_dir = os.path.join(directory, "BUILD", "app.c")
    os.makedirs(build_dir)
    with open(os.path.join(build_dir, "Makefile"), "w") as fh:
        fh.write("built:\n"
                 "\tprintf '#! /bin/sh\\necho compiled artifact ran\\n' "
                 "> built\n"
                 "\tchmod +x built\n")
    compiled = TestConfiguration(
        source_file    = "app.c",
        source_kind    = E_SourceKind.COMPILED,
        test_directory = directory,
        caps           = ProcsitterConfig(max_wall_clock_sec=20.0),
        build          = BuildConfig(E_BuildSystem.MAKE, ["built"]),
        choice_db      = {None: TestChoiceConfiguration()})
    #  BUILT ABOVE, run here: the plan's order, replayed by hand.
    asyncio.run(build(compiled))
    compiled_out = asyncio.run(Run(compiled).provide())

    script = os.path.join(directory, "direct.sh")
    with open(script, "w") as fh:
        fh.write('#! /bin/sh\necho executable ran with "$1"\n')
    os.chmod(script, 0o755)
    executable = TestConfiguration(
        source_file    = "direct.sh",
        source_kind    = E_SourceKind.EXECUTABLE,
        test_directory = directory,
        caps           = ProcsitterConfig(max_wall_clock_sec=20.0),
        choice_db      = {"basic": TestChoiceConfiguration()})
    executable_out = asyncio.run(Run(executable, "basic").provide())

    print("INSPECT: COMPILED argv   = %s"
          % [os.path.basename(a) for a in application_argv(compiled, None)])
    print("         COMPILED stdout = %r"
          % compiled_out["stdout"].open().read())
    print("         EXECUTABLE argv = %s"
          % [os.path.basename(a) for a in application_argv(executable,
                                                           "basic")])
    print("         EXECUTABLE out  = %r"
          % executable_out["stdout"].open().read())
    ok = _check([
        (compiled_out.provision.report is E_TestRunResult.OK,
         "the COMPILED test built AND ran"),
        (compiled_out["stdout"].open().read() == "compiled artifact ran\n",
         "and its ARTIFACT produced the output, not its source"),
        (len(compiled_out.provision.records) == 1,
         "one record: the run's -- the build's own attribution is the "
         "BUILD node's, above"),
        (executable_out["stdout"].open().read()
             == "executable ran with basic\n",
         "the EXECUTABLE ran directly, with the choice as its argument"),
    ])
    shutil.rmtree(directory, ignore_errors=True)
    _verdict(ok, "all three source kinds launch what they should.")


def test_containment_reaches_the_report():
    """A run ended by a CAP is reported as such. The silence cap in
    particular: procsitter attributes FAIL_STALLED, and provision must
    render that as TEST_APP_STALLED rather than losing it."""
    directory = _place("import time\n"
                       "print('one line, then silence')\n"
                       "time.sleep(30)\n")
    stalled = asyncio.run(Run(_interpreted_capped(
        directory, max_output_gap_sec=1.0)).provide())

    directory2 = _place("import time\ntime.sleep(30)\n")
    timed_out  = asyncio.run(Run(_interpreted_capped(
        directory2, max_wall_clock_sec=1.0)).provide())

    print("INSPECT: silent run  -> containment %s, report %s"
          % (stalled.provision.records[0].containment.name,
             stalled.provision.report))
    print("         long run    -> containment %s, report %s"
          % (timed_out.provision.records[0].containment.name,
             timed_out.provision.report))
    ok = _check([
        (stalled.provision.report is E_TestRunResult.TEST_APP_STALLED,
         "FAIL_STALLED becomes TEST_APP_STALLED"),
        (timed_out.provision.report
             is E_TestRunResult.TEST_APP_WALL_CLOCK_EXCEEDED,
         "a cap names itself (O-19): the wall clock, here"),
        ("one line" in stalled["stdout"].open().read(),
         "and what the run DID produce is still handed over"),
    ])
    for d in (directory, directory2): shutil.rmtree(d, ignore_errors=True)
    _verdict(ok, "a cap that ended the run reaches the report.")


if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "Provision: execute, canonicalise, and the loaded read",
        choice_map = {
            "argv":                 test_argv,
            "subjects":             test_subjects,
            "canonicalisation":     test_canonicalisation,
            "canonicaliser_broken": test_canonicaliser_failure,
            "absent_application":   test_absent_application,
            "loaded":               test_loaded,
            "same_shape":           test_same_shape,
            "source_kinds":         test_source_kinds,
            "stages":               test_stages,
            "containment":          test_containment_reaches_the_report,
        },
        happy      = "SUCCESS.*",
    ).run()
