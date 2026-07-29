"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE
       PROVISION -- how the subjects of a test come to exist.

DESCRIPTION
       Two ways, one product:

           Run      execute, contain, record   -> the subjects
           Replay   read what was stored       -> the subjects

       They read DISJOINT configuration keys and return the SAME thing,
       so no operation above ever branches on which one it got -- which
       is what keeps comparison blind to provenance (README 2.4).

       A SUBJECT IS A NOMINAL-KIND OBJECT. Subject and nominal are the
       same kind of thing (README 2.3); a comparison merely aligns two
       readers. So provision hands back 'subject name -> Nominal', and
       nothing downstream can tell a subject from a nominal by its type.

       CANONICALISATION IS PROVISION, not comparison: a pype stage is HOW
       a raw stream becomes the comparable stream. It happens here, per
       subject, and what is stored and compared is its result. A subject
       with no canonicaliser declared is comparable raw -- raw IS
       canonical for it.

       PROVISION JUDGES NOTHING. It reports what happened as one token of
       the brief vocabulary and hands over readers. Whether the test
       passes is decided above.
______________________________________________________________________________
"""
import asyncio
from   dataclasses import dataclass
from   pathlib     import Path

from   vut.auxiliary.test_run_result     import E_TestRunResult
from   vut.engine.procsitter.procsitter  import Procsitter, E_Containment
from   vut.engine.procsitter.construction import Link, chain
from   vut.engine.test_run.build         import build
from   vut.engine.test_run.configuration import E_SourceKind
from   vut.engine.test_run.nominal       import BytesNominal
from   vut.engine.test_run.observer      import notify
from   vut.engine.test_run.report        import Provision


STDOUT = "stdout"
STDERR = "stderr"


def application_argv(configuration, choice_name):
    """
    RETURN: list[str], the command line of ONE call of the test
            application: the source kind decides the prefix, and the
            CHOICE NAME is appended as the argument that selects it.

    A test without choices is keyed by 'None' and gets no such argument.
    """
    kind = configuration.source_kind
    if   kind is E_SourceKind.INTERPRETED:
        argv = [str(x) for x in configuration.interpreter]
        argv.append(str(configuration.source_file))
    elif kind is E_SourceKind.COMPILED:
        target_list = list(configuration.build.target_list)
        artifact    = target_list[0] if target_list \
                                     else configuration.stem
        argv = [str(configuration.build_directory / artifact)]
    else:
        argv = [str(Path(configuration.test_directory)
                    / configuration.source_file)]
    if choice_name is not None:
        argv.append(str(choice_name))
    return argv


async def _read_all(reader):
    """RETURN: str, everything the reader yields, to EOF."""
    chunk_list = []
    while not reader.at_eof():
        data = await reader.read(4096)
        if data: chunk_list.append(data)
    return b"".join(chunk_list).decode("utf-8", errors="replace")


async def _read_all_timed(reader):
    """
    RETURN: (str, tuple), everything the reader yields, and the DELTA
            time before each line, in seconds.

    The cadence is a property of the RAW stream, measured as the lines
    ARRIVE -- which is why it is taken here and not reconstructed later.
    The first delta is measured from the first read, so it is the gap
    before the first line, not the process's start-up.
    """
    import time
    line_list, delta_list = [], []
    mark = time.monotonic()
    while not reader.at_eof():
        raw = await reader.readline()
        if not raw: break
        now = time.monotonic()
        delta_list.append(round(now - mark, 6))
        mark = now
        line_list.append(raw)
    return (b"".join(line_list).decode("utf-8", errors="replace"),
            tuple(delta_list))


async def canonicalise(text, pype_argv, procsitter):
    """
    RETURN: (str, E_TestRunResult), the canonicalised text and the report.

    The canonicaliser is a supervised call like any other: its own caps,
    its own attribution. A canonicaliser that fails leaves the text
    UNCHANGED and says so -- it never silently returns half a stream,
    which would be compared and called a difference in the subject.
    """
    source = Link()
    await source.feed(text.encode("utf-8"))
    source.close()

    c      = chain([(procsitter, list(pype_argv))],
                   stdin_reader=source.reader)
    record = (await asyncio.gather(*c.task_tuple))[0]
    result = await _read_all(c.tail.reader)

    if record.containment is E_Containment.FAIL_LAUNCH:
        return text, E_TestRunResult.PYPE_INTERPRETER_NOT_FOUND
    if record.containment is E_Containment.FAIL_COMPLETED:
        return text, E_TestRunResult.PYPE_FAILED
    if record.containment is not E_Containment.OK_COMPLETED:
        return text, E_TestRunResult.PYPE_CONTAINED
    return result, E_TestRunResult.OK


@dataclass(frozen=True)
class Subjects:
    """What provision delivered: readers by subject name, and the record
    of how they came to be.

    'raw_db' and 'timing_db' are the material for RECORDING (README 4).
    They are kept only when asked for, since the raw content of a noisy
    run can be large where its cadence never is.
    """
    reader_db: dict
    provision: Provision
    raw_db:    dict = None
    timing_db: dict = None

    def __contains__(self, subject_name):
        """RETURN: True, that subject was provided."""
        return subject_name in self.reader_db

    def __getitem__(self, subject_name):
        """RETURN: Nominal, the reader of that subject."""
        return self.reader_db[subject_name]

    def names(self):
        """RETURN: list[str], the provided subject names, sorted."""
        return sorted(self.reader_db)


class Run:
    """PROVISION BY EXECUTION: build if COMPILED, launch, contain,
    canonicalise, and hand over readers.

    Reads the source, build, place, caps, canonicaliser and store keys of
    the configuration -- and none of the stored-data keys.
    """

    kind = "Run"

    def __init__(self, configuration, choice_name=None, observer=None,
                 keep_raw=False, keep_timing=False):
        self.configuration = configuration
        self.choice_name   = choice_name
        self.observer      = observer
        self.keep_raw      = keep_raw
        self.keep_timing   = keep_timing
        self.last_provided = None    # what 'provide()' last produced, so
                                     # a caller may RECORD it without
                                     # provisioning a second time

    async def provide(self, stop_event=None):
        """
        RETURN: Subjects, the readers and the record of provision.

        REMEMBERS the product, so a caller that must both compare and
        record does not provision twice -- which for a Run would mean
        running the application a second time and recording a DIFFERENT
        execution than the one that was judged.
        """
        self.last_provided = await self._provide(stop_event=stop_event)
        return self.last_provided

    async def _provide(self, stop_event=None):
        """
        RETURN: Subjects, the readers and the record of provision.

        The build's failure ENDS provision: there is nothing to launch,
        so no subject is provided and the report names the build.
        """
        configuration = self.configuration
        record_list   = []

        if configuration.source_kind is E_SourceKind.COMPILED:
            outcome = await build(configuration, stop_event=stop_event,
                                  observer=self.observer)
            record_list.append(outcome.record)
            if not outcome.succeeded:
                return Subjects({}, Provision(report  = outcome.report,
                                              records = tuple(record_list)))

        procsitter = Procsitter(configuration.caps,
                                work_dir=str(configuration.test_directory))
        error_link = Link()
        c = chain([(procsitter,
                    application_argv(configuration, self.choice_name),
                    {"stderr_handler": error_link.feed})])
        timing_db = {}
        try:
            if self.keep_timing:
                stdout_text, delta_tuple = await _read_all_timed(c.tail.reader)
                timing_db[STDOUT] = delta_tuple
            else:
                stdout_text = await _read_all(c.tail.reader)
            record = (await asyncio.gather(*c.task_tuple))[0]
        finally:
            error_link.close()                 # not an edge: ours to close
        stderr_text = await _read_all(error_link.reader)
        record_list.append(record)

        if record.containment is E_Containment.FAIL_LAUNCH:
            return Subjects({}, Provision(
                report  = E_TestRunResult.TEST_APP_LAUNCH_FAILED,
                records = tuple(record_list)))

        raw_db = {STDOUT: stdout_text, STDERR: stderr_text}
        raw_db.update(self._output_files())

        report    = E_TestRunResult.OK
        if record.containment is E_Containment.FAIL_STALLED:
            report = E_TestRunResult.TEST_APP_STALLED
        elif record.containment is not E_Containment.OK_COMPLETED \
             and record.containment is not E_Containment.FAIL_COMPLETED:
            report = E_TestRunResult.TEST_APP_CONTAINED

        reader_db = {}
        entry     = configuration.choice_configuration(self.choice_name)
        for name, text in raw_db.items():
            pype_argv = entry.canonicalisers.get(name)
            if pype_argv is not None:
                text, pype_report = await canonicalise(text, pype_argv,
                                                       procsitter)
                if pype_report is not E_TestRunResult.OK \
                   and report is E_TestRunResult.OK:
                    report = pype_report
            reader_db[name] = BytesNominal(text, name=name)

        return Subjects(reader_db,
                        Provision(report  = report,
                                  records = tuple(record_list)),
                        raw_db    = dict(raw_db) if self.keep_raw else None,
                        timing_db = timing_db if self.keep_timing else None)

    def _output_files(self):
        """
        RETURN: dict, subject name -> text, for every file the run left
                under 'OUT/'. A file subject is named by its file name.
        """
        directory = self.configuration.output_directory
        file_db   = {}
        if not directory.is_dir(): return file_db
        for path in sorted(directory.iterdir()):
            if not path.is_file(): continue
            try:
                file_db[path.name] = path.read_text(encoding="utf-8",
                                                    errors="replace")
            except OSError:
                pass
        return file_db


class Replay:
    """PROVISION BY STORED DATA: read the recorded subjects back.

    Reads the store keys and NONE of the source, build, place or caps
    keys. Nothing is executed, so there is nothing to contain and no
    attribution to make -- which is why its Provision carries no records.
    """

    kind = "Replay"

    def __init__(self, store, test_name, choice_name=None,
                 subject_name_list=None, observer=None):
        self.store             = store
        self.test_name         = test_name
        self.choice_name       = choice_name
        self.subject_name_list = subject_name_list
        self.observer          = observer
        self.last_provided     = None

    async def provide(self, stop_event=None):
        """
        RETURN: Subjects, the readers and the record of provision.

        REMEMBERS the product, so a caller that must both compare and
        record does not provision twice -- which for a Run would mean
        running the application a second time and recording a DIFFERENT
        execution than the one that was judged.
        """
        self.last_provided = await self._provide(stop_event=stop_event)
        return self.last_provided

    async def _provide(self, stop_event=None):
        """
        RETURN: Subjects, readers over the stored candidates.

        A recording that is not there is REPORTED, never invented: an
        absent record must not read as an empty subject, which would be
        compared and called a difference.
        """
        name_list = self.subject_name_list
        if name_list is None:
            name_list = [STDOUT, STDERR]

        reader_db, missing = {}, []
        for name in name_list:
            candidate = self.store.candidate(self.test_name,
                                             self.choice_name, name)
            if not candidate.exists():
                missing.append(name)
                continue
            with candidate.open() as reader:
                reader_db[name] = BytesNominal(reader.read(), name=name)

        if not reader_db:
            return Subjects({}, Provision(
                report=E_TestRunResult.RECORDING_MISSING))
        return Subjects(reader_db, Provision(report=E_TestRunResult.OK))
