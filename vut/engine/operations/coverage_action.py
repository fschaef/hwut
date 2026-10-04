"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE
       COVERAGE -- the chain of ONE coverage run, for the coverage
       dispatcher ('orchestrator/run/coverage_dispatcher.py').

DESCRIPTION
       THE CHAIN (coverage RATIONALE D-19, D-38). The configuration
       handed in is already the coverage run's: it builds the coverage
       target and its call carries the tool.

           prepare   'OUT/COVERAGE' emptied
           run       the provision executes the call; NOTHING IS
                     COMPARED with any nominal
           testify   the run ended by itself AND its stdout ends in
                     '<hwut-end>' -- else nothing is read (D-21)
           report    the tool's second call, where it has one,
                     supervised
           harvest   the reader reads 'OUT/COVERAGE', the record is
                     seated with the run id and stored as '.cover' in
                     its BINARY spelling (D-20)

       IT JUDGES NOTHING AND BOOKS NOTHING. What the run came to is
       one token, 'E_CoverageResult', handed back to the caller. A run
       whose tree bore nothing yields NO record and 'NO_DATA_PROVIDED';
       an empty record is never written for it.

       COVERAGE RIDES ON TESTIMONY (coverage RATIONALE D-21). "These
       lines are covered" means "a test that testified executed them".
       A run that did not testify -- killed, stalled, contained, not
       launched, ended without '<hwut-end>' -- supports no such claim,
       and its artefacts are NOT READ: the check stands BEFORE the
       harvest, so nothing is parsed and then discarded.

       ONE ARTEFACT DIRECTORY PER TEST DIRECTORY (D-22): every tool
       writes into 'OUT/COVERAGE', so two runs of one directory at once
       would write over each other. The coverage dispatcher runs ONE
       TEST AT A TIME per directory, and 'prepare' empties the
       directory before each; other directories proceed in parallel.

       CAPS UNDER COVERAGE (D-19): 'uncapped' lifts the caps that guard
       the author's patience ('timeout_sec', 'cpu_sec') -- instrumented
       code is slower and a plain run's timeout is a false miss -- and
       keeps the ones that keep the machine alive.

       THE RECORD LIVES IN THE STORE'S OWN GROUND, 'TMP/store/
       <test>--<choice>.cover': it is a measurement of the LAST
       coverage run of that choice, kept per run (D-8), never a
       nominal, never a subject.
______________________________________________________________________________
"""
from   dataclasses import dataclass
from   enum        import Enum
from   pathlib     import Path

from   ..procsitter.api import Procsitter, E_Containment
from   .consume.terminal       import ends_in_terminal
from   .result                 import E_TestRunResult
from   .                       import subject_provision
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
    NOT_REGISTERED     = "not-registered"       # the register names no
                                                # such run: no id to seat
                                                # a record with (D-18)

    def __str__(self):
        """RETURN: str, the token, as the book holds it."""
        return self.value


@dataclass(frozen=True)
class CoverageSetup:
    """The coverage step's OWN struct, one per test application of a
    coverage run.

    'reader' is the elected tool's framework (coverage
    'CCoverageFramework');
    'config' its 'CoverageConfig'; 'note' is what was already
    concluded before any run -- 'NO_COVERAGE_TARGET' where a compiled
    test declares none -- or None where nothing stands against it.
    """
    reader: object
    config: object
    note:   E_CoverageResult | None = None


def prepare(test_directory):
    """
    RETURN: None. Empties the artefact directory of 'test_directory':
            what the tool leaves there is THIS run's and nobody's
            inheritance (D-22).
    """
    import shutil
    shutil.rmtree(artifact_directory_of(str(test_directory)),
                  ignore_errors=True)


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


async def harvest(setup, configuration, bookkeeper, test, choice, run_id,
                  report=E_TestRunResult.OK):
    """
    RETURN: E_CoverageResult, what the step concluded -- 'OK' with a
            record written to 'bookkeeper.coverage_path(test, choice)',
            else the token naming why none was.

    'setup' is the run's CoverageSetup: the elected tool and what the
    run gathers. 'report' is the run's own E_TestRunResult; where it
    says the application did not testify, NOTHING IS READ and the
    answer is 'RUN_INCOMPLETE' (D-21). Else the reader's second call
    runs under procsitter where the tool has one, then the artifact
    under 'OUT/COVERAGE' is read. The record is seated with 'run_id'
    before it is written: a record without a run is a record nobody
    can attribute (D-18).
    """
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



async def measured(setup, configuration, store, choice, run_id):
    """
    RETURN: E_CoverageResult, what ONE coverage run of '(test, choice)'
            came to: 'OK' with the record written, else the token
            naming why none was.

    'configuration' is the coverage run's own -- coverage target and
    wrapped call in place. The application is executed afresh and
    NOTHING IS COMPARED: the run's only statement is its testimony
    (D-21), which is the provision's report and the terminal token at
    the end of its stdout. The caller holds the directory and lets no
    second run of it proceed meanwhile (D-22).
    """
    prepare(configuration.test_directory)
    provision, _ = subject_provision.provider_of(configuration, store,
                                                 choice, force_run=True)
    subjects = await provision.provide()
    report   = subjects.provision.report
    #  THE TERMINAL TOKEN IS THE STATEMENT (D-21, R-70): a stream that
    #  does not end in it never completed, whatever the process said
    #  on its way out.
    if testified_f(report) \
       and ("stdout" not in subjects
            or not ends_in_terminal(subjects["stdout"].open())):
        report = E_TestRunResult.TERMINATED_WITHOUT_END
    return await harvest(setup, configuration, store.bookkeeper,
                         configuration.key_name, choice, run_id, report)
