#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PROVISION: THE TWO WAYS SUBJECTS COME TO EXIST.

    UNIT     ONE 'Provision', its STAGES as members (build, execute,
             canonicalise | load); 'Run' and 'Replay' are PLANNERS that
             wire it -- disjoint configuration keys, one product.

    CAUSAL CONTRACT
             the source kind fixes the argv and the choice name selects
             the scenario; stdout, stderr and every file under OUT/ are
             subjects; a declared canonicaliser rewrites a subject before
             anyone compares it.

    CONSISTENCY CONTRACT
             Run and Replay return the SAME shape, so nothing above can
             tell them apart; a failed build ends provision; a failing
             canonicaliser leaves the text UNCHANGED and says so; an
             absent recording is reported, never invented as empty.

    STAGE CONTRACT
             the wiring is DATA (None marks an absent stage) and its law
             lives at construction; a shared StageBuild builds ONCE,
             however many provisions hold it.
______________________________________________________________________________
"""
import asyncio
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

from   config import HwutRunner                                  # noqa F401,E402

from   vut.engine.test_run.result     import E_TestRunResult  # noqa E402
from   vut.engine.procsitter.procsitter  import ProcsitterConfig # noqa E402
from   vut.engine.test_run.provision.build import (BuildConfig,    # noqa E402
                                                   E_BuildSystem)
from   vut.engine.test_run.configuration import (               # noqa E402
                                                 TestConfiguration,
                                                 TestChoiceConfiguration,
                                                 E_SourceKind)
from   vut.engine.test_run.provision.core import (Run, Replay,   # noqa E402
                                                  Provision,
                                                  Supply,
                                                  application_argv)
from   vut.engine.test_run.provision.stage_acquire      import (  # noqa E402
                                                  AcquireItem,
                                                  StageAcquire)
from   vut.engine.test_run.provision.stage_build        import \
                                                  StageBuild      # noqa E402
from   vut.engine.test_run.provision.stage_execute      import \
                                                  StageExecute    # noqa E402
from   vut.engine.test_run.provision.stage_canonicalise import \
                                                  StageCanonicalise  # noqa E402
from   vut.engine.orchestrator.bookkeeper.bookkeeper import (    # noqa E402
                                                 Bookkeeper)
from   vut.engine.test_run.store         import Store            # noqa E402

#  ASKED OF config.py, NOT COUNTED IN '..'. The walk in config.py is
#  the one place that knows where 'vut' is; a hop count here is a
#  silent hostage to the layout -- this test moved one level deeper
#  once, and the counted path went on pointing into the void.
from   config import VUT_DIRECTORY                               # noqa E402

PYPE = os.path.join(VUT_DIRECTORY, "engine", "hwut_pype", "hwut_pype.py")

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


def _interpreted(directory, canonicaliser_db=None, choice_db=None):
    """RETURN: TestConfiguration, an INTERPRETED test in 'directory'."""
    entry = TestChoiceConfiguration(canonicalisers=canonicaliser_db or {})
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
    """stdout, stderr and every file the run leaves under OUT/ are
    subjects, provided as readers of one kind."""
    directory = _place(
        "import sys, os\n"
        "print('to stdout')\n"
        "sys.stderr.write('to stderr\\n')\n"
        "os.makedirs('OUT', exist_ok=True)\n"
        "open(os.path.join('OUT','emitted.txt'),'w').write('to a file\\n')\n")
    provided = asyncio.run(Run(_interpreted(directory)).provide())

    print("INSPECT: report   = %s" % provided.provision.report)
    print("         subjects = %s" % provided.names())
    for name in provided.names():
        print("           %-12s %r" % (name, provided[name].open().read()))
    ok = _check([
        (provided.names() == ["emitted.txt", "stderr", "stdout"],
         "three subjects: two channels and one output file"),
        (provided.provision.report is E_TestRunResult.OK,
         "provision reports OK"),
        (len(provided.provision.records) == 1,
         "one attribution record: one supervised call happened"),
    ])
    shutil.rmtree(directory, ignore_errors=True)
    _verdict(ok, "channels and output files alike are subjects.")


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
    """A canonicaliser that cannot run leaves the text UNCHANGED and says
    so. Half a stream would be compared and called a difference in the
    subject -- blaming the code for the tool's fault."""
    directory = _place("print('alpha')\n")
    provided  = asyncio.run(Run(_interpreted(
        directory, {"stdout": ["no-such-canonicaliser-anywhere"]})).provide())

    print("INSPECT: report = %s" % provided.provision.report)
    print("         stdout = %r" % provided["stdout"].open().read())
    ok = _check([
        (provided.provision.report
             is E_TestRunResult.PYPE_INTERPRETER_NOT_FOUND,
         "the report names the canonicaliser, not the application"),
        (provided["stdout"].open().read() == "alpha\n",
         "the text is UNCHANGED -- never half a stream"),
    ])
    shutil.rmtree(directory, ignore_errors=True)
    _verdict(ok, "a broken canonicaliser blames itself, not the code.")


def test_build_ends_provision():
    """A failed build ENDS provision: there is nothing to launch, so no
    subject is provided and the report names the build."""
    directory = tempfile.mkdtemp(prefix="vut_prov_")
    os.makedirs(os.path.join(directory, "BUILD", "demo"))
    with open(os.path.join(directory, "BUILD", "demo", "Makefile"), "w") as fh:
        fh.write("app:\n\tfalse\n")
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
    print("         records  = %i" % len(provided.provision.records))
    ok = _check([
        (provided.provision.report is E_TestRunResult.BUILD_FAILED,
         "the report names the build"),
        (provided.names() == [],
         "NO subject is provided -- nothing was launched"),
        (len(provided.provision.records) == 1,
         "the build's own attribution record is kept"),
    ])
    shutil.rmtree(directory, ignore_errors=True)
    _verdict(ok, "a failed build ends provision, with its evidence.")


def test_replay():
    """Replay reads what was stored. It executes nothing, so it carries
    no attribution records -- and an absent recording is REPORTED, never
    invented as an empty subject."""
    directory = tempfile.mkdtemp(prefix="vut_prov_")
    store     = Store(Bookkeeper(directory))
    store.write_candidate("demo", None, "stdout", "recorded line\n")
    store.write_candidate("demo", None, "stderr", "")

    present = asyncio.run(Replay(store, "demo").provide())
    absent  = asyncio.run(Replay(store, "never-recorded").provide())

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
    """Run and Replay read DISJOINT configuration keys and return the
    SAME thing, so nothing above ever branches on which one it got."""
    directory = _place("print('same')\n")
    executed  = asyncio.run(Run(_interpreted(directory)).provide())

    store = Store(Bookkeeper(directory))
    for name in ("stdout", "stderr"):
        store.write_candidate("demo", None, name,
                              executed[name].open().read())
    replayed = asyncio.run(Replay(store, "demo").provide())

    print("INSPECT: Run    -> %s, type %s"
          % (executed.names(), type(executed).__name__))
    print("         Replay -> %s, type %s"
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
        (Run.kind != Replay.kind,
         "they differ only in what they are CALLED, for the observer"),
    ])
    shutil.rmtree(directory, ignore_errors=True)
    _verdict(ok, "one product, two provenances, indistinguishable above.")


def test_source_kinds():
    """ALL THREE source kinds, each launched for real. COMPILED builds an
    artifact and then RUNS it; EXECUTABLE runs the file itself."""
    directory = tempfile.mkdtemp(prefix="vut_prov_")
    build_dir = os.path.join(directory, "BUILD", "app")
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
        (len(compiled_out.provision.records) == 2,
         "two records: the build's and the run's"),
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
        (timed_out.provision.report is E_TestRunResult.TEST_APP_CONTAINED,
         "any other cap becomes TEST_APP_CONTAINED"),
        ("one line" in stalled["stdout"].open().read(),
         "and what the run DID produce is still handed over"),
    ])
    for d in (directory, directory2): shutil.rmtree(d, ignore_errors=True)
    _verdict(ok, "a cap that ended the run reaches the report.")


def test_stages():
    """A Provision holds its stages as MEMBERS -- the wiring is DATA,
    'None' for a stage this provision does not have. Exactly one path
    exists, and that law lives at CONSTRUCTION, where the wiring is
    written."""
    directory = _place("print('hi')\n")
    store_dir = tempfile.mkdtemp(prefix="vut_prov_")
    executed  = Run(_interpreted(directory))
    loaded    = Replay(Store(Bookkeeper(store_dir)), "demo")

    def picture(p):
        """RETURN: str, one mark per stage member, 'X' present, '-' absent."""
        return " ".join("X" if s is not None else "-"
                        for s in (p.stage_acquire, p.stage_build,
                                  p.stage_execute, p.stage_canonicalise,
                                  p.stage_load))
    print("INSPECT: wiring  [acquire build execute canonicalise load]")
    print("         Run    -> %s   kind %r" % (picture(executed),
                                               executed.kind))
    print("         Replay -> %s   kind %r" % (picture(loaded),
                                               loaded.kind))

    refused = []
    for label, kwargs in (
            ("both paths",       {"stage_execute": executed.stage_execute,
                                  "stage_load":    loaded.stage_load}),
            ("no path",          {}),
            ("build beside load",
             {"stage_load":  loaded.stage_load,
              "stage_build": StageBuild(_interpreted(directory))}),
            ("acquire beside load -- replay is OFFLINE",
             {"stage_load":    loaded.stage_load,
              "stage_acquire": StageAcquire(_interpreted(directory), [])})):
        try:
            Provision(**kwargs)
            refused.append(False)
        except AssertionError:
            refused.append(True)

    ok = _check([
        (executed.stage_execute is not None
         and executed.stage_canonicalise is not None
         and executed.stage_load is None,
         "an executing provision: execute and canonicalise, no load"),
        (loaded.stage_load is not None
         and loaded.stage_build is None
         and loaded.stage_execute is None
         and loaded.stage_canonicalise is None,
         "a loading provision: ONLY its load stage"),
        (type(executed) is type(loaded),
         "ONE Provision type -- provenance is wiring, never subclass"),
        (all(refused),
         "both paths, no path, build-beside-load, acquire-beside-load: "
         "refused at construction"),
    ])
    shutil.rmtree(directory, ignore_errors=True)
    shutil.rmtree(store_dir, ignore_errors=True)
    _verdict(ok, "the wiring is data, and its law lives at construction.")


def test_acquire():
    """DEPENDENCIES come to exist -- once, and only where absent. An
    acquisition is A SUPERVISED CALL guarded by a SATISFACTION CHECK
    (the make semantics): satisfied is SKIPPED, absent is acquired, a
    failure ENDS provision with 'acquisition-failed' -- and the run
    stage never starts. A LYING command -- ran fine, check still absent
    -- is the same failure. Shared across provisions, the world is
    asked ONCE."""
    directory = _place("print('app ran')\n")
    marker    = os.path.join(directory, "dep.marker")
    log_path  = os.path.join(directory, "acquire.log")

    #  One satisfied item whose command WOULD fail if it ever ran; one
    #  absent item whose command acquires and logs.
    item_list = [
        AcquireItem("already-there", lambda: True, ("sh", "-c", "exit 7")),
        AcquireItem("fetched-dep",
                    lambda: os.path.exists(marker),
                    ("sh", "-c",
                     "echo got-it > dep.marker && echo fetched >> acquire.log")),
    ]
    configuration = _interpreted(directory)
    shared        = StageAcquire(configuration, item_list)

    async def both():
        """RETURN: (Subjects, Subjects), two provisions, one acquisition."""
        first  = Run(configuration, stage_acquire=shared)
        second = Run(configuration, stage_acquire=shared)
        return await first.provide(), await second.provide()
    out_a, out_b = asyncio.run(both())

    with open(log_path) as fh:
        fetch_n = len(fh.read().splitlines())

    #  The failing acquisition: provision ENDS, the app never runs.
    failing = Run(_interpreted(_place("print('never')\n")),
                  stage_acquire=StageAcquire(
                      configuration,
                      [AcquireItem("unreachable", lambda: False,
                                   ("sh", "-c", "exit 3"))]))
    out_c = asyncio.run(failing.provide())

    #  The LIAR: the command succeeds, the check still says absent.
    lying = Run(_interpreted(_place("print('never')\n")),
                stage_acquire=StageAcquire(
                    configuration,
                    [AcquireItem("claimed", lambda: False, ("true",))]))
    out_d = asyncio.run(lying.provide())

    supply = asyncio.run(shared.supply())
    print("INSPECT: acquired = %s; the fetch command ran %i time(s)"
          % (list(supply.product), fetch_n))
    print("         failing -> %s, subjects %s"
          % (out_c.provision.report, out_c.names()))
    print("         lying   -> %s" % out_d.provision.report)
    ok = _check([
        (out_a.provision.report is E_TestRunResult.OK
         and out_b.provision.report is E_TestRunResult.OK,
         "with dependencies satisfied, provision delivers as ever"),
        (os.path.exists(marker) and fetch_n == 1,
         "the absent dependency was acquired ONCE -- shared stage, "
         "one ask of the world"),
        (isinstance(supply, Supply) and supply.record_list,
         "the answer is the ONE SHAPE, and the call is attributed"),
        (out_c.provision.report is E_TestRunResult.ACQUISITION_FAILED
         and out_c.names() == [],
         "a failing acquisition ends provision -- the app NEVER ran"),
        (out_d.provision.report is E_TestRunResult.ACQUISITION_FAILED,
         "a command that 'succeeded' past an unsatisfied check failed"),
    ])
    shutil.rmtree(directory, ignore_errors=True)
    _verdict(ok, "the world is asked once, refused loudly, never trusted.")


def test_shared_build():
    """SHARING IS INSTANCE IDENTITY: the SAME StageBuild wired into two
    Provisions builds ONCE -- the memoized outcome serves both. That is
    'build if necessary' at suite scale, and it is the PLANNER's choice:
    fresh stages (the default) still build per provision."""
    directory = tempfile.mkdtemp(prefix="vut_prov_")
    build_dir = os.path.join(directory, "BUILD", "app")
    os.makedirs(build_dir)
    with open(os.path.join(build_dir, "Makefile"), "w") as fh:
        fh.write("built:\n"
                 "\techo one-build >> build.log\n"
                 "\tprintf '#! /bin/sh\\necho artifact ran\\n' > built\n"
                 "\tchmod +x built\n")
    compiled = TestConfiguration(
        source_file    = "app.c",
        source_kind    = E_SourceKind.COMPILED,
        test_directory = directory,
        caps           = ProcsitterConfig(max_wall_clock_sec=20.0),
        build          = BuildConfig(E_BuildSystem.MAKE, ["built"]),
        choice_db      = {None: TestChoiceConfiguration()})

    shared = StageBuild(compiled)
    def provision():
        """RETURN: Provision, execution-wired around the SHARED build."""
        return Provision(
            stage_build        = shared,
            stage_execute      = StageExecute(compiled),
            stage_canonicalise = StageCanonicalise(compiled))

    async def both():
        """RETURN: (Subjects, Subjects), two provisions, one build."""
        first, second = provision(), provision()
        return await first.provide(), await second.provide()
    out_a, out_b = asyncio.run(both())

    log_path = os.path.join(build_dir, "build.log")
    with open(log_path) as fh:
        build_n = len(fh.read().splitlines())
    print("INSPECT: reports = %s, %s; the build tool ran %i time(s)"
          % (out_a.provision.report, out_b.provision.report, build_n))
    print("         stdout  = %r == %r"
          % (out_a["stdout"].open().read(),
             out_b["stdout"].open().read()))
    ok = _check([
        (out_a.provision.report is E_TestRunResult.OK
         and out_b.provision.report is E_TestRunResult.OK,
         "both provisions deliver"),
        (build_n == 1,
         "the build tool ran ONCE -- the shared stage remembers"),
        (out_a["stdout"].open().read() == "artifact ran\n"
         and out_b["stdout"].open().read() == "artifact ran\n",
         "and both ran the one artifact it built"),
    ])
    shutil.rmtree(directory, ignore_errors=True)
    _verdict(ok, "one shared stage, one build, two provisions served.")


if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "Provision: Run, Replay, and canonicalisation",
        choice_map = {
            "argv":                 test_argv,
            "subjects":             test_subjects,
            "canonicalisation":     test_canonicalisation,
            "canonicaliser_broken": test_canonicaliser_failure,
            "build_ends_it":        test_build_ends_provision,
            "replay":               test_replay,
            "same_shape":           test_same_shape,
            "source_kinds":         test_source_kinds,
            "stages":               test_stages,
            "acquire":              test_acquire,
            "shared_build":         test_shared_build,
            "containment":          test_containment_reaches_the_report,
        },
        happy      = "SUCCESS.*",
    ).run()
