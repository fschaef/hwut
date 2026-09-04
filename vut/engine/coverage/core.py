"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE COMPONENT'S FACE -- three calls, and nothing above needs to
         know that a coverage tool exists.

DESCRIPTION
       CONTRACT   CoverageConfig            what is gathered
       WRAPPING   'Coverage.wrap(argv)'     the tool's own call form
       HARVEST    'Coverage.harvest(dir)'   artifact -> homogeneous record

       The four seams in the rest of the tree stay ONE LINE each:

           StoreConfig.record_coverage      the run is asked for it
           StageExecute                     asks THIS for the argv
           store.write_coverage()           stores what harvest returned
           services/report.py               renders it

       ELECTION HAPPENS ONCE, at construction, and the elected tool is
       remembered -- because the record's header must name the tool that
       ACTUALLY served (RATIONALE D-7), and a second election could
       answer differently.

       A COVERAGE RUN IS ITS OWN ANIMAL (D-4). This face states the
       consequences it owns; the caller enforces them:
           -- caps named in 'disabled_caps' are not enforced
           -- no cadence is measured
           -- the interactive road is never taken
       Asked for two of these at once, it REFUSES at the door rather than
       silently preferring one.
______________________________________________________________________________
"""
from .configuration  import CoverageConfig, CoverageRefused
from .readers.api    import ARTIFACT_DIRECTORY, elect, language_of
#  'reader_of' is NOT on the door: 'readers/reader.py' has never
#  defined it (pre-existing, see the session's report). Reaching
#  straight into the submodule reproduces the standing bug unchanged
#  rather than silently repairing it in the course of a house move.
from .readers.reader import reader_of


class Coverage:
    """ONE TEST'S coverage gathering: the elected tool, and its reader.

    Constructed where a run is wired, from the coverage configuration and
    the test's source file. Construction ELECTS -- so a machine without
    any candidate is refused before the run starts, not after it.
    """

    def __init__(self, config, source_file, tool_db=None):
        """
        RETURN: Coverage, with its language derived or stated, its tool
                elected, and its reader resolved.

        Raises CoverageRefused where the language derives nothing, where
        no tool is configured for it, where no candidate is available on
        this machine, or where the elected tool has no reader in this
        build. Every one of those is named at the door.
        """
        self.config      = config
        self.source_file = source_file
        self.language    = language_of(source_file, config.language)
        self.tool        = elect(self.language, tool_db)
        self.reader      = reader_of(self.tool)

    @property
    def artifact_directory(self):
        """RETURN: str, where the tool's own artifact is left, relative
        to the test directory: 'OUT/COVERAGE'."""
        return ARTIFACT_DIRECTORY

    def report_argv(self, work_dir):
        """
        RETURN: list[str], the SECOND supervised call this tool needs to
                turn its raw state into a readable artifact.
                None, where it needs none.

        The component NAMES it; the execute stage MAKES it, under the
        procsitter like every other process. A reader spawns nothing.
        """
        return self.reader.report_argv(self.config, work_dir)

    def wrap(self, argv, work_dir):
        """
        RETURN: list[str], 'argv' as it runs UNDER the elected tool --
                the ONE change a coverage run makes to the execute stage.
        """
        return self.reader.wrap(argv, self.config, work_dir)

    def harvest(self, work_dir, source_root):
        """
        RETURN: CoverageRecord, this run's coverage, homogeneous, its
                header naming the language, the tool and the artifact's
                own format.
                None, where the tool left no artifact -- ABSENT, and the
                caller must report it as absent, never as an empty
                measurement.
        """
        return self.reader.harvest(work_dir, source_root, self.config)


def verify(config, record_timing_f=False, interactive_f=False):
    """
    RETURN: None, the coverage request is servable.

    Raises CoverageRefused naming the ONE first fault. Checked where the
    request is HANDED IN, before a single process runs -- never at step
    seven.

    A coverage run produces no cadence, and never takes the interactive
    road: both are RATIONALE D-4, and both are refused here rather than
    resolved by a preference the caller did not state.
    """
    if not isinstance(config, CoverageConfig):
        raise CoverageRefused("a CoverageConfig was expected, %s given"
                              % type(config).__name__)
    if record_timing_f:
        raise CoverageRefused(
            "'record_timing' stands beside 'record_coverage': a coverage "
            "run produces no cadence. Ask for one or the other.")
    if interactive_f:
        raise CoverageRefused(
            "'interactive' stands beside 'record_coverage': a coverage "
            "run never takes the session road, because a session measures "
            "one process across many choices and the record is keyed per "
            "choice.")
