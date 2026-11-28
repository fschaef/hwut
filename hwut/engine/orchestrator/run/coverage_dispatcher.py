"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE COVERAGE DISPATCHER -- what 'hwut.cov.run' plugs into the
         orchestrator in place of the test run's dispatcher (coverage
         D-38).

    run_script, run_build   as the test run's: the frame and the
                            build are the directory's, whoever asks
    open_session            stands up NOTHING: a coverage run takes
                            one process per choice (coverage D-4)
    run_test                the tool runs the application; where the
                            application testified (D-21) its artefact
                            is harvested into a record. NOTHING IS
                            COMPARED and NOTHING IS BOOKED

THE ANSWER OF 'run_test' IS NO VERDICT. True says 'a record stands',
False 'none does', and 'report_of' names why in one token of
'E_CoverageResult'. The record is the whole product. What each case
came to is also left as a LOCAL TRACE ('TMP/hwut-traces-coverage.csv',
coverage D-41), for 'hwut.help' and for nothing else.

THE REGISTER IS READ, NEVER WRITTEN. The record is seated with the
run id the register holds (D-18); a case the register does not name
is not measured and is answered 'not-registered'.

ONE RUN AT A TIME PER DIRECTORY (D-22): every tool leaves its artefact
in the directory's 'OUT/COVERAGE', emptied before each run.
______________________________________________________________________________
"""
import asyncio
import os
import shlex
from   dataclasses import replace

from ...operations.build_action       import BuildConfig, build
from ...operations.configuration      import E_SourceKind
from ...operations.coverage_action    import (CoverageSetup,
                                              E_CoverageResult, measured,
                                              uncapped)
from ...operations.run.core           import application_argv
from ...coverage.api                  import (OUTCOME_OK, CoverageConfig,
                                              CoverageRefused,
                                              CoverageTraceDb,
                                              serving_framework)
from .adapter                         import stem_expanded
from .dispatcher                      import TestRunDispatcher


def coverage_setup_of(app, configuration, demand, entry):
    """
    RETURN: CoverageSetup: the framework of the ONE tool the language
            entry 'entry' names and the format it writes (coverage
            D-46), what the run gathers, and the note
            'NO_COVERAGE_TARGET' where the test is COMPILED and its
            language states no 'coverage_target'; else no note.

    Raises CoverageRefused where the test has no language, where no
    entry stands for it, where the entry names no tool, or where the
    tool is absent here -- each named at the door; no other tool is
    tried.
    """
    if app.language is None:
        raise CoverageRefused(
            "'%s' has no language: coverage needs one to know its tool. "
            "State 'language' in its header, or claim its extension in "
            "'language-setup' of 'HWUT_ROOT/setup.conf'." % app.source_file)
    if entry is None:
        raise CoverageRefused(
            "no 'language-setup' entry stands for language '%s' of '%s' "
            "in 'HWUT_ROOT/setup.conf'" % (app.language, app.source_file))
    reader, format_name = serving_framework(app.language, entry.coverage,
                                            entry.coverage_format)
    note   = None
    if configuration.build is not None and entry.coverage_target is None:
        note = E_CoverageResult.NO_COVERAGE_TARGET
    return CoverageSetup(reader=reader, config=demand, note=note,
                         format_name=format_name)


def coverage_configuration_of(configuration, setup, entry):
    """
    RETURN: TestConfiguration, 'configuration' as a coverage run needs
            it (coverage D-19):

                build    the language entry's 'coverage_target' ('%'
                         the stem) in place of the executable
                caps     the time caps lifted; the others as they stand

            The CALL is made per run ('run_configuration_of'): it
            carries the choice.

            'configuration' itself, where the setup carries a note:
            such a case is not run.
    """
    if setup.note is not None: return configuration
    build = configuration.build
    if build is not None:
        build = BuildConfig(build.build_system,
                            [stem_expanded(entry.coverage_target,
                                           configuration.source_file)],
                            build.argument_list, build.tool)
    result = replace(configuration, build=build,
                     caps=uncapped(configuration.caps),
                     choice_db={choice: stated if stated.caps is None
                                        else replace(
                                            stated,
                                            caps=uncapped(stated.caps))
                                for choice, stated
                                in configuration.choice_db.items()},
                     interactive=False)
    return result


def test_app_of(configuration):
    """
    RETURN: str, the test application as a coverage tool is handed it
            ('specify_command_line'): the source file of an
            interpreted test -- WITHOUT its interpreter, which is the
            tool's to choose -- the built target of a compiled one, the
            file itself of an executable one. A STATED CALL (R-68) is
            handed over as stated, '$file' and '$filestem' expanded
            (G-4); '$choice' expands EMPTY here -- the tool's call
            scheme places the choice itself.
    """
    if configuration.execute is not None:
        return shlex.join(application_argv(configuration, None))
    if configuration.source_kind is E_SourceKind.INTERPRETED:
        return str(configuration.source_file)
    return application_argv(configuration, None)[0]


def run_configuration_of(configuration, setup, choice):
    """
    RETURN: TestConfiguration of ONE coverage run: 'configuration' with
            the tool's command line ('specify_command_line', D-39) as
            THE CALL (R-68).
            'configuration' itself, where the tool is not on the
            command line.

    Raises CoverageRefused where the tool's command line does not end
    in the choice: the run appends the choice to the call, and a call
    that carries it elsewhere cannot be stated.
    """
    argv = setup.reader.specify_command_line(setup.config.include,
                                             setup.config.omit,
                                             test_app_of(configuration),
                                             choice, setup.format_name)
    if argv is None: return configuration
    argv = list(argv)
    if choice is not None:
        if not argv or argv[-1] != str(choice):
            raise CoverageRefused(
                "the call scheme of '%s' does not end in '{choice}': %s"
                % (setup.reader.name, " ".join(argv)))
        argv.pop()
    return replace(configuration, execute=tuple(argv))


class CoverageRunDispatcher(TestRunDispatcher):
    """Drives one directory's plan for coverage: every test case is run
    under its tool and harvested; none is judged, none is booked."""

    def __init__(self, directory, entry, demand=None, variant_tuple=(),
                 relative_directory=None, run_list=None):
        """
        RETURN: CoverageRunDispatcher holding 'directory', its lock
                taken as the test run's dispatcher takes it.

        'demand' the CoverageConfig: what this run gathers. None reads
                 as the default demand.
        'run_list'
                 where every test run that left a record is noted for
                 the run's final gathering (coverage D-42), as
                 '(directory, test, choice, record path)' --
                 'directory' being 'relative_directory', this
                 directory's path from the run's root. None: nobody
                 gathers.

        An application no tool serves does not refuse the directory: its
        cases are answered 'not-measurable', and the sentence naming
        why is a notice once per application run (coverage D-47). Raises
        DirectoryBusy where another live process holds the directory.
        """
        super().__init__(directory, entry, record=False,
                         variant_tuple=variant_tuple)
        demand         = demand if demand is not None else CoverageConfig()
        directory_spec = getattr(getattr(entry, "app_set", None),
                                 "directory_spec", None)
        language_setup = getattr(directory_spec, "language_setup",
                                 None) or {}
        self.setup_db  = {}
        for app in entry.app_set:
            configuration  = self.config_db[app.source_file]
            language_entry = language_setup.get(app.language)
            try:
                setup = coverage_setup_of(app, configuration, demand,
                                          language_entry)
            except CoverageRefused as refusal:
                #  NOT MEASURABLE IS PER CASE (D-47): the rest of the
                #  directory is measured.
                setup = CoverageSetup(
                            reader=None, config=demand,
                            note=E_CoverageResult.NOT_MEASURABLE,
                            refusal=str(refusal))
            self.setup_db[app.source_file]  = setup
            self.config_db[app.source_file] = \
                coverage_configuration_of(configuration, setup,
                                          language_entry)
        #  THE BUILD ACTIONS name configurations; they must name the
        #  coverage run's.
        self.build_db = {action: self.config_db[configuration.source_file]
                         for action, configuration
                         in self.build_db.items()}
        self.cov_lock = asyncio.Lock()
        #  (test, choice) -> outcome, for the LOCAL TRACE of this run
        #  (coverage D-41), written at 'close()'.
        self.outcome_db = {}
        self.relative_directory = relative_directory
        self.run_list           = run_list
        self.unmeasurable_set   = set()        # applications noticed
        #  node name -> (book's verdict token or None, deviates_f): the
        #  LABEL of each case (coverage D-48); never written anywhere.
        self.label_db           = {}

    async def close(self):
        """RETURN: None. The trace of this run written under 'TMP/',
        then the directory released as the test run's dispatcher
        releases it."""
        CoverageTraceDb(self.directory).note(self.outcome_db)
        await super().close()

    async def open_session(self, node):
        """RETURN: True. No session stands up: under coverage every
        choice is its own process (coverage D-4)."""
        return True

    async def run_test(self, node):
        """
        RETURN: bool, True where a record of that run stands now.
                False where none does; 'report_of' names why.
        """
        configuration = self.config_db[node.file]
        book    = self.bookkeeper.result(configuration.key_name, node.choice)
        book    = None if book is None else str(book["verdict"])
        self.label_db[node.name()] = (book, False)
        try:
            async with self.cov_lock:
                token, verdict = await self._measured(node)
        except CoverageRefused as refusal:
            self.report_db[node.name()] = str(refusal)
            return False
        #  DEVIATION (D-48): the run under the tool came out otherwise
        #  than the book's last word. No book verdict: no information.
        if verdict is not None and book in ("true", "false"):
            self.label_db[node.name()] = (book,
                                          verdict != (book == "true"))
        key = (self.config_db[node.file].key_name, node.choice)
        if token is E_CoverageResult.OK:
            self.outcome_db[key] = OUTCOME_OK
            if self.run_list is not None:
                self.run_list.append(
                    (self.relative_directory, key[0], key[1],
                     str(self.bookkeeper.coverage_path(*key))))
            return True
        self.outcome_db[key]        = str(token)
        self.report_db[node.name()] = str(token)
        return False

    async def run_build(self, node):
        """
        RETURN: bool, the coverage target built -- as the test run's
                build, with the STAGE NAMED where it failed (ruled
                2026-11-26): the detail names the coverage target the
                language entry asks for and the last line the build
                tool wrote to stderr, so 'build failed' is never said
                without what and why.
        """
        configuration = self.build_db.get(node.action)
        if configuration is None or configuration.build is None:
            return await super().run_build(node)
        outcome = await build(configuration)
        if not outcome.succeeded:
            self.report_db[node.name()] = outcome.report.value
            target = ", ".join(configuration.build.target_list)
            self.detail_db[node.name()] = (
                "coverage target '%s'%s" % (target, ": %s" % outcome.detail
                                            if outcome.detail else ""))
        return outcome.succeeded

    def label_of(self, node_name):
        """
        RETURN: (str | None, bool), the case's LABEL (coverage D-48): the
                book's last verdict token ('true', 'false', None where it
                has none) and whether the coverage run's verdict
                contradicts it; a case never run cannot deviate.
        """
        return self.label_db.get(node_name, (None, False))

    async def _measured(self, node):
        """
        RETURN: (E_CoverageResult, bool | None), what the one run came
                to: 'OK' with the record written, else the token naming
                why none was; and its verdict against 'GOOD/', None
                where the case was not run (it cannot deviate).
        """
        configuration = self.config_db[node.file]
        setup         = self.setup_db[node.file]
        if setup.refusal is not None \
           and node.file not in self.unmeasurable_set:
            self.unmeasurable_set.add(node.file)
            self.notice_list.append("NOT MEASURABLE %s: %s"
                                    % (configuration.key_name,
                                       setup.refusal))
        if setup.note is not None: return setup.note, None
        run_id = self.bookkeeper.run_id_of(configuration.key_name,
                                           node.choice)
        if run_id is None: return E_CoverageResult.NOT_REGISTERED, None

        return await measured(setup,
                              run_configuration_of(configuration, setup,
                                                   node.choice),
                              self.store,
                              node.choice, run_id)


def coverage_run_dispatcher_factory(demand=None, variant_tuple=(),
                                    root=None, run_list=None):
    """
    RETURN: callable(directory, entry) -> CoverageRunDispatcher -- the
            factory 'orchestrator()' consumes, the demand and the
            variant selection bound.

    'run_list' collects, over every directory, the test runs that left
    a record -- each with its directory's path from 'root' -- for the
    run's final gathering (D-42); None collects nothing.
    """
    def made(directory, entry):
        relative = os.path.relpath(directory, root or directory) \
                     .replace(os.sep, "/")
        return CoverageRunDispatcher(directory, entry, demand=demand,
                                     variant_tuple=variant_tuple,
                                     relative_directory=relative,
                                     run_list=run_list)
    return made
