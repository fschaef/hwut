#! /usr/bin/env python3
#
# @hwut {
#     title      = "The coverage provision chain"
#     choices    = ["harvested", "incomplete", "no_target",
#                   "nothing_borne"]
#     tolerance { eq_pattern = ["SUCCESS.*"] }
#     interactive = true
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

THE COVERAGE PROVISION CHAIN.

    UNIT     'coverage_action.measured' -- one coverage run -- and
             'coverage_dispatcher.coverage_configuration_of', which
             makes the configuration it runs: the call is the elected tool's
             COMMAND LINE (D-39), the application is executed, a
             testified run is HARVESTED, the record is SEATED with the
             run id and stored in the store's own ground. NOTHING IS
             COMPARED AND NOTHING IS BOOKED (coverage D-38).

    CAUSAL CONTRACT
             artefacts left                   ->  '.cover' + 'ok'
             nothing left                     ->  no file  + 'no-data-provided'
             the application did not testify  ->  nothing READ,
                                                  'run-incomplete'
             compiled, language names no 'coverage_target' -> 'no-coverage-target',
                                                  the case is not run

    CONSISTENCY CONTRACT
             a record is never written without a run id; an empty
             record is never written for a run that bore nothing; the
             book holds no entry of a coverage run.

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
from   vut.engine.operations.session         import store_of  # noqa E402
from   vut.engine.operations.run.core        import application_argv  # noqa E402
from   vut.engine.operations.coverage_action import (CoverageSetup, # noqa E402
                                                   E_CoverageResult,
                                                   measured, uncapped)
from   vut.engine.orchestrator.run.coverage_dispatcher import (  # noqa E402
                                                   coverage_configuration_of,
                                                   run_configuration_of)
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
print("<hwut-end>")
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

    call_scheme = "python3 -u {test} --witness {choice}"

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
    configuration is the coverage run's under 'setup'."""
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
        choice_db      = {None: TestChoiceConfiguration()})
    print("INSPECT: the call, plain:     %s"
          % " ".join(application_argv(configuration, None)))
    configuration = run_configuration_of(
                        coverage_configuration_of(configuration, setup,
                                                  None),
                        setup, None)
    print("         under the tool:      %s"
          % " ".join(application_argv(configuration, None)))
    return configuration, Bookkeeper(directory), directory


def _run(setup, configuration, bookkeeper, run_id):
    """RETURN: E_CoverageResult of the one coverage run."""
    return asyncio.run(measured(setup, configuration,
                                store_of(configuration, bookkeeper),
                                None, run_id))


def _show(token, bookkeeper, directory):
    """RETURN: None. Prints the token, the record, and what the book
    holds of the run."""
    print("INSPECT: the run came to: %s" % token)
    print("         book entry: %s"
          % (bookkeeper.result("demo.py", None) or "<none>"))
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
    """The tree bore fruit: a record, seated, stored; nothing booked."""
    setup = CoverageSetup(reader=WitnessFramework(), config=CoverageConfig())
    configuration, bookkeeper, directory = _place(setup)
    token = _run(setup, configuration, bookkeeper, TestRunId(0, 0))
    _show(token, bookkeeper, directory)

    path   = bookkeeper.coverage_path("demo.py", None)
    record = unpack_record(path.read_bytes())
    ok = _check([
        (token is E_CoverageResult.OK,
         "the step concluded OK"),
        (str(path).endswith(os.path.join("TMP/store", "demo.py.cover")),
         "the record lives in the store's own ground, never in OUT/"),
        (record.run == frozenset([TestRunId(0, 0)]),
         "the record is SEATED with the run id handed in"),
        (record.tool == "witness"
         and record.file_db["demo.py"].covered == ((1, 7),),
         "and carries what the reader read"),
        (not bookkeeper.result("demo.py", None),
         "the book holds no entry of the run: nothing was judged"),
    ])
    shutil.rmtree(directory)
    _verdict(ok, "one coverage run harvests, seats and stores; the "
                 "record is the whole product.")


def test_nothing_borne():
    """The application left nothing: no record, and the token says
    why."""
    setup = CoverageSetup(reader=WitnessFramework(), config=CoverageConfig())
    mute  = APPLICATION.replace('"--witness" in sys.argv', "False")
    configuration, bookkeeper, directory = _place(setup, mute)
    token = _run(setup, configuration, bookkeeper, TestRunId(0, 0))
    _show(token, bookkeeper, directory)

    ok = _check([
        (token is E_CoverageResult.NO_DATA_PROVIDED,
         "a tree that did not grow makes the harvest trivial: "
         "NO_DATA_PROVIDED"),
        (not bookkeeper.coverage_path("demo.py", None).exists(),
         "and NO record is written -- absent, never empty"),
    ])
    shutil.rmtree(directory)
    _verdict(ok, "absence is answered with its cause, and stored "
                 "nowhere.")


def test_incomplete():
    """The application did not testify: nothing is read (D-21)."""
    setup = CoverageSetup(reader=WitnessFramework(), config=CoverageConfig())
    #  Writes its witness file, then stalls: it is killed by the (tiny)
    #  wall clock, set AFTER the coverage configuration lifted it.
    stalling = APPLICATION + "import time\nsys.stdout.flush()\ntime.sleep(30)\n"
    configuration, bookkeeper, directory = _place(setup, stalling)
    tiny = ProcsitterConfig(max_wall_clock_sec=2.0, max_output_gap_sec=1.0)
    configuration = replace(configuration, caps=tiny,
                            choice_db={None: TestChoiceConfiguration(
                                                 caps=tiny)})
    token = _run(setup, configuration, bookkeeper, TestRunId(0, 0))
    _show(token, bookkeeper, directory)
    witness_left = os.path.isfile(os.path.join(
        artifact_directory_of(directory), WITNESS_FILE))

    #  A SECOND APPLICATION leaves its witness and ends by itself, but
    #  never says the terminal token.
    silent = APPLICATION.replace('print("<hwut-end>")\n', "")
    configuration, bookkeeper_2, directory_2 = _place(setup, silent)
    token_2 = _run(setup, configuration, bookkeeper_2, TestRunId(0, 0))
    _show(token_2, bookkeeper_2, directory_2)

    ok = _check([
        (witness_left,
         "the tool DID leave an artefact -- lines were touched"),
        (token is E_CoverageResult.RUN_INCOMPLETE,
         "a killed run is NOT harvested: it testifies to nothing, so "
         "the lines it touched are a claim of nothing"),
        (not bookkeeper.coverage_path("demo.py", None).exists(),
         "no record is written"),
        (token_2 is E_CoverageResult.RUN_INCOMPLETE
         and not bookkeeper_2.coverage_path("demo.py", None).exists(),
         "a run that ends by itself WITHOUT '<hwut-end>' did not "
         "testify either -- no nominal is consulted for that"),
    ])
    shutil.rmtree(directory)
    shutil.rmtree(directory_2)
    _verdict(ok, "coverage rides on testimony; no testimony, no coverage.")


def test_no_target():
    """The build-side half: under coverage the LANGUAGE's
    'coverage_target' is built in place of the executable, '%' its stem
    (R-73, R-74); a compiled test whose language declares none is not
    run and is answered 'no-coverage-target'."""
    from vut.engine.operations.build_action import BuildConfig, E_BuildSystem
    from vut.engine.orchestrator.exploration.configuration_tree import (
                                                          LanguageSetup)

    plain_caps = ProcsitterConfig(max_wall_clock_sec=30.0,
                                  max_cpu_time_sec=20, max_memory_mb=256)
    compiled   = TestConfiguration(
        source_file    = "test-app.c",
        source_kind    = E_SourceKind.COMPILED,
        test_directory = "/tmp",
        caps           = plain_caps,
        build          = BuildConfig(E_BuildSystem.MAKE, ["test-app.exe"]),
        choice_db      = {None: TestChoiceConfiguration(caps=plain_caps)})
    declared   = LanguageSetup(coverage=("witness",),
                               coverage_target="%.cov.exe")
    undeclared = LanguageSetup(coverage=("witness",))
    plain      = CoverageSetup(reader=WitnessFramework(),
                               config=CoverageConfig())
    noted      = CoverageSetup(reader=WitnessFramework(),
                               config=CoverageConfig(),
                               note=E_CoverageResult.NO_COVERAGE_TARGET)
    made_db = {}
    for label, entry, setup in (
            ("target declared",    declared,   plain),
            ("NO target declared", undeclared, noted)):
        made = coverage_configuration_of(compiled, setup, entry)
        made_db[label] = made
        print("INSPECT: %-19s -> target %s" % (label,
                                               list(made.build.target_list)))

    cov_caps = made_db["target declared"].caps
    print("INSPECT: caps under coverage: wall %s cpu %s memory %s MB"
          % ("lifted" if cov_caps.max_wall_clock_sec > 1e8 else "kept",
             "lifted" if cov_caps.max_cpu_time_sec  > 1e8 else "kept",
             cov_caps.max_memory_mb))
    choice_caps = made_db["target declared"].choice_db[None].caps

    ok = _check([
        (cov_caps.max_wall_clock_sec > 1e8 and cov_caps.max_cpu_time_sec > 1e8
         and cov_caps.max_memory_mb == 256,
         "time is luxury under coverage and is lifted; memory keeps "
         "the machine alive and stands"),
        (choice_caps.max_wall_clock_sec > 1e8,
         "for every choice, not only for the application"),
        (list(made_db["target declared"].build.target_list)
         == ["test-app.cov.exe"],
         "under coverage the language's COVERAGE TARGET is built and "
         "run in its place -- the name is the whole communication"),
        (made_db["NO target declared"] is compiled,
         "a language declaring none leaves the configuration as it "
         "stands; the note NO_COVERAGE_TARGET answers for the case"),
    ])
    _verdict(ok, "the coverage run shapes the build; a missing "
                 "declaration is answered, not guessed around.")


if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "The coverage provision chain",
        choice_map = {
            "harvested":     test_harvested,
            "nothing_borne": test_nothing_borne,
            "incomplete":    test_incomplete,
            "no_target":     test_no_target,
        },
        happy      = "SUCCESS.*",
    ).run()
