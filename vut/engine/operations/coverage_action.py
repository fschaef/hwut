"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE
       COVERAGE -- a step inside provision, for a run asked to measure
       what it reaches.

DESCRIPTION
       THE CHAIN (coverage RATIONALE D-19). 'hwut.run.cov' -- or 'hwut.run
       --coverage' -- is the DEMAND, and the demand shapes the run:

           build  cov-target      the author's build rules instrument
                                  THAT target; hwut asks for it by name
           run    wrapped argv    the elected reader's 'wrap' puts the
                                  tool around the call, where the tool
                                  needs it (interpreted languages)
           report second call     'report_argv', where the tool turns
                                  raw state into a readable artifact
           harvest -> record      the reader reads, this seats the run
                                  id, the bookkeeper stores '.cover'
                                  in its BINARY spelling (D-20)

       THIS MODULE IS THE RUN-SIDE HALF. The build-side half is one
       line in the adapter: 'target_list' names the coverage target
       instead of the executable. Everything else the run does is
       unchanged -- the subjects are judged exactly as without coverage.

       IT JUDGES NOTHING. Like the build, it reports what happened as
       one token, 'E_CoverageResult', and the token goes into the book
       entry beside the verdict. A run whose tree bore nothing yields
       NO record and 'NO_DATA_PROVIDED'; an empty record is never
       written for it.

       COVERAGE RIDES ON TESTIMONY (coverage RATIONALE D-21). "These
       lines are covered" means "a test that testified executed them".
       A run that did not testify -- killed, stalled, contained, not
       launched, ended without '<hwut-end>' -- supports no such claim,
       and its artefacts are NOT READ: the check stands BEFORE the
       harvest, so nothing is parsed and then discarded.

       ONE ARTEFACT DIRECTORY PER TEST DIRECTORY (D-22): every tool
       writes into 'OUT/COVERAGE', so two runs of one directory at once
       would write over each other. Under coverage the dispatcher runs
       ONE TEST AT A TIME per directory, and 'prepare' empties the
       directory before each; other directories proceed in parallel.

       CAPS UNDER COVERAGE (D-19): the adapter drops the caps that guard
       the author's patience ('timeout_sec', 'cpu_sec') -- instrumented
       code is slower and a plain run's timeout is a false failure --
       and keeps the ones that keep the machine alive; 'OUT/COVERAGE'
       is admitted to the write sandbox.

       THE RECORD LIVES IN THE STORE'S OWN GROUND, 'TMP/store/
       <test>--<choice>.cover': it is a measurement of the LAST run of
       that choice, kept per run (D-8), never a nominal, never a
       subject.
______________________________________________________________________________
"""
from   dataclasses import dataclass
from   enum        import Enum
from   pathlib     import Path

from   ..procsitter.api import Procsitter, E_Containment
from   .result                 import E_TestRunResult
from   ..coverage.api       import artifact_directory_of
from   ..coverage.api       import seated
from   ..coverage.api       import pack_record


#  THE CAPS THAT ARE LUXURY (D-19): a time cap guards the author's
#  patience, not the machine. Under coverage they are lifted to this --
#  thirty years, which procsitter's rlimit and watchdog both take as a
#  number, where None they would not.
UNCAPPED_SEC = 10 ** 9


def uncapped(caps):
    """
    RETURN: ProcsitterConfig, 'caps' with the time caps lifted --
            wall clock and CPU -- and every other cap as it stands.
    """
    from dataclasses import replace
    return replace(caps, max_wall_clock_sec=float(UNCAPPED_SEC),
                         max_cpu_time_sec=UNCAPPED_SEC)


class E_CoverageResult(Enum):
    """WHAT THE COVERAGE STEP CONCLUDED about one run -- one token per
    run, because a run is one stimulus applied once."""
    OK                 = "ok"                   # a record stands
    NO_COVERAGE_TARGET = "no-coverage-target"   # COMPILED, and the
                                                # configuration names no
                                                # 'build.coverage_target'
    NO_DATA_PROVIDED   = "no-data-provided"     # the run left nothing to
                                                # harvest
    RUN_INCOMPLETE     = "run-incomplete"       # the application did not
                                                # testify: killed, stalled,
                                                # contained, not launched,
                                                # or ended without the
                                                # terminal token -- NOT
                                                # harvested (D-21)
    REPORT_FAILED      = "report-failed"        # the tool's second call
                                                # did not end well
    NOT_ASKED          = "not-asked"            # no coverage was asked

    def __str__(self):
        """RETURN: str, the token, as the book holds it."""
        return self.value


@dataclass(frozen=True)
class CoverageSetup:
    """The coverage step's OWN struct, held verbatim by the test's
    configuration. None there means: coverage was not asked.

    'reader' is the elected tool's framework (coverage
    'CCoverageFramework');
    'config' its 'CoverageConfig'; 'note' is what the ADAPTER already
    concluded before any run -- 'NO_COVERAGE_TARGET' where a compiled
    test declares none -- or None where nothing stands against it.
    """
    reader: object
    config: object
    note:   E_CoverageResult | None = None


def prepare(configuration):
    """
    RETURN: None. Empties the artefact directory of the test directory
            where coverage is asked: what the tool leaves there is
            THIS run's and nobody's inheritance (D-22).
    """
    if configuration.coverage is None: return
    import shutil
    directory = artifact_directory_of(str(configuration.test_directory))
    shutil.rmtree(directory, ignore_errors=True)


def wrapped_argv(configuration, argv):
    """
    RETURN: list of str, 'argv' run UNDER the coverage tool where the
            configuration asks for coverage; 'argv' itself else.

    The one change coverage makes to the execute stage. A reader whose
    tool needs no wrapping (the instrumented binary measures itself)
    returns the argv unchanged.
    """
    setup = configuration.coverage
    if setup is None: return argv
    return list(setup.reader.wrap(list(argv), setup.config,
                                  str(configuration.test_directory)))


#  A run that ended with one of these did NOT testify (D-21). Every
#  other report -- OK, a judgement against the nominal, a missing file
#  -- came from an application that ran to its own end.
_NOT_TESTIFIED = frozenset((
    E_TestRunResult.SOURCE_NOT_FOUND,
    E_TestRunResult.INTERPRETER_NOT_FOUND,
    E_TestRunResult.TEST_APP_LAUNCH_FAILED,
    E_TestRunResult.TEST_APP_CONTAINED,
    E_TestRunResult.TEST_APP_SESSION_GONE,       # O-21: never served
    E_TestRunResult.TEST_APP_WALL_CLOCK_EXCEEDED,
    E_TestRunResult.TEST_APP_CPU_TIME_EXCEEDED,
    E_TestRunResult.TEST_APP_MEMORY_EXCEEDED,
    E_TestRunResult.TEST_APP_FILE_SIZE_EXCEEDED,
    E_TestRunResult.TEST_APP_PIDS_EXCEEDED,
    E_TestRunResult.TEST_APP_DISK_EXCEEDED,
    E_TestRunResult.TEST_APP_STALLED,
    E_TestRunResult.TEST_APP_NO_OUTPUT,
    E_TestRunResult.TERMINATED_WITHOUT_END,
))


def testified_f(report):
    """
    RETURN: True,  the application ran to its own end and made its
                   statement -- its lines may be claimed as covered.
            False, it did not; nothing it touched is a claim.
    """
    return report not in _NOT_TESTIFIED


async def harvest(configuration, bookkeeper, test, choice, run_id,
                  report=E_TestRunResult.OK):
    """
    RETURN: E_CoverageResult, what the step concluded -- 'OK' with a
            record written to 'bookkeeper.coverage_path(test, choice)',
            else the token naming why none was.

    'report' is the run's own E_TestRunResult; where it says the
    application did not testify, NOTHING IS READ and the answer is
    'RUN_INCOMPLETE' (D-21). Else the reader's second call runs under
    procsitter where the tool has one, then the artifact under
    'OUT/COVERAGE' is read. The record is seated with 'run_id' before
    it is written: a record without a run is a record nobody can
    attribute (D-18).
    """
    setup = configuration.coverage
    if setup is None:                         return E_CoverageResult.NOT_ASKED
    if setup.note is not None:                return setup.note
    if not testified_f(report):               return E_CoverageResult.RUN_INCOMPLETE

    work_dir = str(configuration.test_directory)
    argv     = setup.reader.report_argv(setup.config, work_dir)
    if argv is not None:
        #  THE APPLICATION'S CAPS (O-20): the harvest is the
        #  application's, made once for every choice together.
        record = await Procsitter(configuration.caps,
                                  work_dir=work_dir).run(list(argv))
        if record.containment not in (E_Containment.OK_COMPLETED,
                                      E_Containment.FAIL_COMPLETED):
            return E_CoverageResult.REPORT_FAILED

    record = setup.reader.harvest(work_dir, work_dir, setup.config)
    if record is None:
        return E_CoverageResult.NO_DATA_PROVIDED

    path = Path(bookkeeper.coverage_path(test, choice))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(pack_record(seated(record, run_id)))
    return E_CoverageResult.OK

