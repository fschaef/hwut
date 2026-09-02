#! /usr/bin/env python3
#
# @hwut {
#     title      = "The coverage provision chain"
#     choices    = ["harvested", "incomplete", "no_target", "not_asked",
#                   "nothing_borne"]
#     tolerance { eq_pattern = ["SUCCESS.*"] }
#     interactive = true
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

THE COVERAGE PROVISION CHAIN.

    UNIT     'coverage_action' inside the session's ceremony, and the
             adapter's build-side half: the call is WRAPPED by the
             elected reader, the run's closing act HARVESTS, the record
             is SEATED with the run id and stored in the store's own
             ground, and the book entry carries one 'E_CoverageResult'.

    CAUSAL CONTRACT
             coverage asked + artefacts left  ->  '.cover' + 'ok'
             coverage asked + nothing left    ->  no file  + 'no-data-provided'
             coverage not asked               ->  no key on the entry
             the application did not testify  ->  nothing READ,
                                                  'run-incomplete'
             compiled, language names no 'coverage_target' -> 'no-coverage-target',
                                                  executable built as ever

    CONSISTENCY CONTRACT
             a record is never written without a run id; an empty
             record is never written for a run that bore nothing; the
             subjects are judged exactly as without coverage.

    THE WITNESS READER stands in for a tool: it is registered here, in
    this test, and reads an artefact the fixture application writes when
    -- and only when -- the wrapped call asks it to. The chain is the
    unit; the real readers are tested against witnessed artefacts in
    'coverage/TEST/test-readers.py'.
______________________________________________________________________________
"""
import asyncio
import io
from   dataclasses import replace
import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

from   config import HwutRunner                                  # noqa F401,E402

from   vut.engine.procsitter.api    import ProcsitterConfig # noqa E402
from   vut.engine.operations.configuration   import (              # noqa E402
                                                   TestConfiguration,
                                                   TestChoiceConfiguration,
                                                   E_SourceKind)
from   vut.engine.operations.session         import (run_test_held, # noqa E402
                                                   Request)
from   vut.engine.operations.coverage_action import (CoverageSetup, # noqa E402
                                                   E_CoverageResult,
                                                   uncapped)
from   vut.engine.bookkeeper.api      import Bookkeeper     # noqa E402
from   vut.engine.bookkeeper.api    import StoreConfig    # noqa E402
from   vut.engine.bookkeeper.api     import TestRunId      # noqa E402
from   vut.engine.coverage.api     import CoverageConfig # noqa E402
from   vut.engine.coverage.api            import (CCoverageFramework,
                                                  CCoverageFormat,     # noqa E402
                                                   record_of,
                                                   artifact_directory_of)
from   vut.engine.coverage.api            import unpack_record  # noqa E402
from   vut.engine.coverage.api            import format_record  # noqa E402

WITNESS_FILE = "witness.json"

#  The fixture application: prints its subject; with '--witness' it
#  ALSO writes which of its lines ran, where a tool would leave them.
APPLICATION = '''\
import json, os, sys
print("behaviour one")
if "--witness" in sys.argv:
    os.makedirs(os.path.join("OUT", "COVERAGE"), exist_ok=True)
    with open(os.path.join("OUT", "COVERAGE", "%s"), "w") as fh:
        json.dump({"demo.py": {"executable": [1, 2, 3, 4, 5, 6],
                               "covered":    [1, 2, 3, 4, 5, 6]}}, fh)
''' % WITNESS_FILE


class WitnessFormat(CCoverageFormat):
    """The witness file: which lines ran."""
    name = "witness-json"

    def read(self, work_dir, source_root, config=None):
        """RETURN: CoverageRecord of the witness file; None where the
        application left none."""
        path = os.path.join(artifact_directory_of(work_dir), WITNESS_FILE)
        if not os.path.isfile(path): return None
        with io.open(path, encoding="utf-8") as fh:
            entry_db = json.load(fh)
        return record_of(self, "python",
                         ((p, e["executable"], e["covered"], None)
                          for p, e in entry_db.items()))


class WitnessFramework(CCoverageFramework):
    """A tool that measures by being asked to."""
    name   = "witness"
    format = WitnessFormat()

    def wrap(self, argv, config, work_dir):
        """RETURN: list of str, the call with '--witness' appended."""
        return list(argv) + ["--witness"]

    def report_argv(self, config, work_dir):
        """RETURN: None: no second call."""
        return None


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


def _place(setup, body=APPLICATION):
    """RETURN: (TestConfiguration, Bookkeeper, str), a ready test whose
    configuration carries 'setup' as its coverage."""
    directory = tempfile.mkdtemp(prefix="vut_cov_")
    with open(os.path.join(directory, "demo.py"), "w") as fh:
        fh.write(body)
    configuration = TestConfiguration(
        source_file    = "demo.py",
        source_kind    = E_SourceKind.INTERPRETED,
        test_directory = directory,
        caps           = ProcsitterConfig(max_wall_clock_sec=20.0),
        interpreter    = ["python3", "-u"],
        store          = StoreConfig(directory=directory),
        choice_db      = {None: TestChoiceConfiguration()},
        coverage       = setup)
    return configuration, Bookkeeper(directory), directory


def _run(configuration, bookkeeper, run_id):
    """RETURN: Outcome of the held entry, the run id handed in."""
    return asyncio.run(run_test_held(configuration, Request(),
                                     bookkeeper=bookkeeper, run_id=run_id))


def _show(outcome, bookkeeper, directory):
    """RETURN: None. Prints the entry's coverage token and the record."""
    print("INSPECT: verdict %-5s report %s" % (outcome.verdict,
                                                outcome.report.value))
    print("         coverage on the entry: %s"
          % outcome.entry.get("coverage", "<absent>"))
    path = bookkeeper.coverage_path("demo.py", None)
    if not path.is_file():
        print("         record: <none>")
        return
    print("         record: %s  (binary; shown converted)"
          % os.path.relpath(path, directory))
    for line in format_record(unpack_record(path.read_bytes())) \
                    .splitlines()[:8]:
        print("           | %s" % line)


#  ------------------------------------------------------------- choices

def test_harvested():
    """Coverage asked, the tree bore fruit: a record, seated, stored."""
    setup = CoverageSetup(reader=WitnessFramework(), config=CoverageConfig())
    configuration, bookkeeper, directory = _place(setup)
    outcome = _run(configuration, bookkeeper, TestRunId(0, 0))
    _show(outcome, bookkeeper, directory)

    path   = bookkeeper.coverage_path("demo.py", None)
    record = unpack_record(path.read_bytes())
    ok = _check([
        (outcome.coverage is E_CoverageResult.OK
         and outcome.entry["coverage"] == "ok",
         "the step concluded OK, and the book entry says so"),
        (str(path).endswith(os.path.join("TMP/store", "demo.py.cover")),
         "the record lives in the store's own ground, never in OUT/"),
        (record.run == frozenset([TestRunId(0, 0)]),
         "the record is SEATED with the run id handed in"),
        (record.tool == "witness"
         and record.file_db["demo.py"].covered == ((1, 7),),
         "and carries what the reader read"),
        (bookkeeper.candidate_path("demo.py", None, "stdout")
                   .read_text(encoding="utf-8").startswith("behaviour one"),
         "the subject is what the application printed -- the wrapper "
         "added nothing to what is judged"),
    ])
    shutil.rmtree(directory)
    _verdict(ok, "the run's closing act harvests, seats, stores, "
                 "and the book says 'ok'.")


def test_nothing_borne():
    """Coverage asked, the application left nothing: no record, and the
    book says why."""
    setup = CoverageSetup(reader=WitnessFramework(), config=CoverageConfig())
    mute  = APPLICATION.replace('"--witness" in sys.argv', "False")
    configuration, bookkeeper, directory = _place(setup, mute)
    outcome = _run(configuration, bookkeeper, TestRunId(0, 0))
    _show(outcome, bookkeeper, directory)

    ok = _check([
        (outcome.coverage is E_CoverageResult.NO_DATA_PROVIDED,
         "a tree that did not grow makes the harvest trivial: "
         "NO_DATA_PROVIDED"),
        (not bookkeeper.coverage_path("demo.py", None).exists(),
         "and NO record is written -- absent, never empty"),
        (outcome.entry["coverage"] == "no-data-provided",
         "the book entry carries the cause beside the absence"),
    ])
    shutil.rmtree(directory)
    _verdict(ok, "absence and its cause travel together, in the book.")


def test_incomplete():
    """The application did not testify: nothing is read (D-21)."""
    setup = CoverageSetup(reader=WitnessFramework(), config=CoverageConfig())
    #  Writes its witness file, then stalls without the terminal token
    #  being the point: it is killed by the (tiny) wall clock.
    stalling = APPLICATION + "import time\nsys.stdout.flush()\ntime.sleep(30)\n"
    configuration, bookkeeper, directory = _place(setup, stalling)
    configuration = replace(configuration,
                            caps=ProcsitterConfig(max_wall_clock_sec=2.0,
                                                  max_output_gap_sec=1.0))
    outcome = _run(configuration, bookkeeper, TestRunId(0, 0))
    _show(outcome, bookkeeper, directory)
    witness_left = os.path.isfile(os.path.join(
        artifact_directory_of(directory), WITNESS_FILE))

    ok = _check([
        (outcome.report.value in ("test-app-stalled", "test-app-contained"),
         "the run did not end by itself"),
        (witness_left,
         "the tool DID leave an artefact -- lines were touched"),
        (outcome.coverage is E_CoverageResult.RUN_INCOMPLETE,
         "and it is NOT harvested: a killed process testifies to "
         "nothing, so the lines it touched are a claim of nothing"),
        (not bookkeeper.coverage_path("demo.py", None).exists(),
         "no record is written"),
        (outcome.entry["coverage"] == "run-incomplete",
         "the book says why"),
    ])
    shutil.rmtree(directory)
    _verdict(ok, "coverage rides on testimony; no testimony, no coverage.")


def test_not_asked():
    """No coverage asked: the call is not wrapped, the entry has no key."""
    configuration, bookkeeper, directory = _place(None)
    outcome = _run(configuration, bookkeeper, None)
    _show(outcome, bookkeeper, directory)

    ok = _check([
        (outcome.coverage is None and "coverage" not in outcome.entry,
         "no key on the entry -- absence is data"),
        (not os.path.isdir(artifact_directory_of(directory)),
         "the call was not wrapped: the application left no artefact"),
    ])
    shutil.rmtree(directory)
    _verdict(ok, "a plain run is a plain run.")


def test_no_target():
    """The build-side half: a compiled test whose LANGUAGE declares no
    'coverage_target' is noted, and builds its executable as ever. The
    target is the language's word (exploration R-73), '%' its stem
    (R-74)."""
    from vut.engine.orchestrator.run.adapter import _build_of
    from vut.engine.orchestrator.exploration.configuration_tree import (
                                     Build, LanguageSetup, TestParameters)

    parameters = TestParameters(build=Build(framework="make",
                                            executable="%.exe"))
    declared   = LanguageSetup(coverage=("witness",),
                               coverage_target="%.cov.exe")
    undeclared = LanguageSetup(coverage=("witness",))
    plain      = CoverageSetup(reader=WitnessFramework(),
                               config=CoverageConfig())
    noted      = CoverageSetup(reader=WitnessFramework(),
                               config=CoverageConfig(),
                               note=E_CoverageResult.NO_COVERAGE_TARGET)
    source     = "test-app.c"
    for label, entry, setup in (
            ("no coverage asked",         declared,   None),
            ("asked, target declared",    declared,   plain),
            ("asked, NO target declared", undeclared, noted)):
        build = _build_of(parameters, source, setup, entry)
        print("INSPECT: %-26s -> target %s" % (label, build.target_list))

    plain_caps = ProcsitterConfig(max_wall_clock_sec=30.0,
                                  max_cpu_time_sec=20, max_memory_mb=256)
    cov_caps   = uncapped(plain_caps)
    print("INSPECT: caps under coverage: wall %s cpu %s memory %s MB"
          % ("lifted" if cov_caps.max_wall_clock_sec > 1e8 else "kept",
             "lifted" if cov_caps.max_cpu_time_sec  > 1e8 else "kept",
             cov_caps.max_memory_mb))

    ok = _check([
        (cov_caps.max_wall_clock_sec > 1e8 and cov_caps.max_cpu_time_sec > 1e8
         and cov_caps.max_memory_mb == 256,
         "time is luxury under coverage and is lifted; memory keeps "
         "the machine alive and stands"),
        (_build_of(parameters, source, None, declared).target_list
         == ["test-app.exe"],
         "without coverage the executable is the one target, '%' the "
         "stem"),
        (_build_of(parameters, source, plain, declared).target_list
         == ["test-app.cov.exe"],
         "under coverage the language's COVERAGE TARGET is built and "
         "run in its place -- the name is the whole communication"),
        (_build_of(parameters, source, noted, undeclared).target_list
         == ["test-app.exe"],
         "a language declaring none builds the executable as ever; "
         "the note NO_COVERAGE_TARGET rides on the entry"),
    ])
    _verdict(ok, "the demand shapes the build; a missing declaration is "
                 "noted, not fatal.")


if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "The coverage provision chain",
        choice_map = {
            "harvested":     test_harvested,
            "nothing_borne": test_nothing_borne,
            "incomplete":    test_incomplete,
            "not_asked":     test_not_asked,
            "no_target":     test_no_target,
        },
        happy      = "SUCCESS.*",
    ).run()
