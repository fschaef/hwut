"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE
       COVERAGE -- a step inside provision, for a run asked to measure
       what it reaches.

DESCRIPTION
       THE CHAIN (coverage RATIONALE D-19). 'hwut.cov' -- or 'hwut.run
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

       THIS MODULE IS THE RUN-SIDE HALF. The build-side half is one
       line in the adapter: 'target_list' names the coverage target
       instead of the executable. Everything else the run does is
       unchanged -- the subjects are judged exactly as without coverage.

       IT JUDGES NOTHING. Like the build, it reports what happened as
       one token, 'E_CoverageResult', and the token goes into the book
       entry beside the verdict. A run whose tree bore nothing yields
       NO record and 'NO_DATA_PROVIDED'; an empty record is never
       written for it.

       THE RECORD LIVES IN THE STORE'S OWN GROUND, '.hwut-store/
       <test>--<choice>.cover': it is a measurement of the LAST run of
       that choice, kept per run (D-8), never a nominal, never a
       subject.
______________________________________________________________________________
"""
import io
from   dataclasses import dataclass
from   enum        import Enum
from   pathlib     import Path

from   ..procsitter.procsitter import Procsitter, E_Containment
from   ..coverage.record       import seated, format_record


class E_CoverageResult(Enum):
    """WHAT THE COVERAGE STEP CONCLUDED about one run -- one token per
    run, because a run is one stimulus applied once."""
    OK                 = "ok"                   # a record stands
    NO_COVERAGE_TARGET = "no-coverage-target"   # COMPILED, and the
                                                # configuration names no
                                                # 'build.coverage_target'
    NO_DATA_PROVIDED   = "no-data-provided"     # the run left nothing to
                                                # harvest
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

    'reader' is the elected tool's reader (coverage 'I_Reader');
    'config' its 'CoverageConfig'; 'note' is what the ADAPTER already
    concluded before any run -- 'NO_COVERAGE_TARGET' where a compiled
    test declares none -- or None where nothing stands against it.
    """
    reader: object
    config: object
    note:   E_CoverageResult | None = None


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


async def harvest(configuration, bookkeeper, test, choice, run_id):
    """
    RETURN: E_CoverageResult, what the step concluded -- 'OK' with a
            record written to 'bookkeeper.coverage_path(test, choice)',
            else the token naming why none was.

    Runs the reader's second call under procsitter where the tool has
    one, then reads the artifact under 'OUT/COVERAGE' of the test
    directory. The record is seated with 'run_id' before it is written:
    a record without a run is a record nobody can attribute (D-18).
    """
    setup = configuration.coverage
    if setup is None:                         return E_CoverageResult.NOT_ASKED
    if setup.note is not None:                return setup.note

    work_dir = str(configuration.test_directory)
    argv     = setup.reader.report_argv(setup.config, work_dir)
    if argv is not None:
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
    with io.open(path, "w", encoding="utf-8") as handle:
        handle.write(format_record(seated(record, run_id)))
    return E_CoverageResult.OK

