"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE
       ACCEPT -- write the nominal.

DESCRIPTION
       THIN, DELIBERATELY. Acceptance's content production -- authoring,
       merging, editing -- is BEYOND scope: an external tool, an editor or
       a person does that. What happens here is the last step only: a
       COMPLETE DUMP that this component did not construct is stored,
       WHOLESALE, per subject, in the canonicalised domain.

       A dump is the same KIND of thing as a nominal: a subject record.
       So acceptance is a PROMOTION, and README 2.3's one-artifact-three-
       roles becomes an operation rather than a remark.

       TO ACCEPT IS TO DECLARE THE POLE, not to freeze a run (PHILOSOPHY
       1.1). A nominal is the designated CENTRE of the good descriptions
       with the tolerance band around it -- what the word means in
       engineering -- and that is why the band need only reach the RADIUS
       of the spread rather than its whole diameter. Accepting a run that
       sits near the EDGE of what is good is a mistake even though the
       run is good; it shows up later as a test that fails on another
       machine, and the answer is then to move the nominal toward the
       centre or to widen the canonicaliser until the spread vanishes.

       TWO MODES, and the distinctions of the outside world -- copy,
       write, merge, manual merge -- are distinctions THERE, not here:

           TAKE_DUMP   a complete dump is handed over  -> store it
           INITIATE    launch an external session, eat its final plain
                       nominal stream                  -> store it

       IT PULLS PROVISION WHEN IT NEEDS IT. Finding no dump and no stored
       subject, Accept activates provision -- an unmet precondition like
       any other, not a special case (README 2.5).

       PARTIAL ACCEPTANCE IS REFUSED. Either every named subject is
       stored, or none is. A half-accepted test would hold new behaviour
       against old nominals on the subjects that were missed, and report
       the difference as a fault of the code.
______________________________________________________________________________
"""
from   dataclasses import dataclass, field
from   enum        import Enum
from   typing      import Mapping, Optional
from ...bookkeeper.api import E_StderrNote

from   ..result           import E_TestRunResult
from   ..interaction.feed import E_Intent, merge_session
from   ..nominal          import (NominalNotAvailable,
                                             RecordNominal)
from   ..observer         import notify


class E_AcceptMode(Enum):
    """Where the complete dump comes from."""
    TAKE_DUMP = "take-dump"   # handed over, ready to store
    INITIATE  = "initiate"    # an external session produces it

    def __str__(self):
        """RETURN: str, the mode's token."""
        return self.value


@dataclass(frozen=True)
class AcceptStep:
    """What to store for ONE subject, and where it comes from."""
    mode:        E_AcceptMode        = E_AcceptMode.TAKE_DUMP
    dump:        Optional[object]    = None   # TAKE_DUMP: a Nominal-kind
    interaction: Optional[object]    = None   # INITIATE: how to launch


@dataclass(frozen=True)
class AcceptConfig:
    """What this operation is ASKED for: which subjects to accept, and
    from where. A groundwork is optional -- given, it is what Accept
    pulls when a step names no dump."""
    name:       str
    subjects:   Mapping[str, AcceptStep] = field(default_factory=dict)
    choice:     Optional[str]            = None
    groundwork: Optional[object]         = None
    compare:    Optional[object]          = None
    stderr:     Optional[E_StderrNote]   = None
                            # THE SECOND QUESTION: which NOTE to write
                            # in the book for stderr. None means it was
                            # not asked -- and acceptance REFUSES
                            # rather than decide on the author's behalf
                            # ('--stderr-nominal' / '--stderr-ignored'
                            # / '--stderr-forbidden' at the face).


@dataclass(frozen=True)
class AcceptResult:
    """What acceptance did."""
    name:            str
    report:          E_TestRunResult
    accepted_db:     Mapping[str, str] = field(default_factory=dict)
    provision:       Optional[object]  = None

    @property
    def verdict(self):
        """
        RETURN: True,  every named subject was stored.
                False, nothing was -- acceptance is all or nothing.
        """
        return self.report is E_TestRunResult.OK


class Accept:
    """WRITE THE NOMINAL."""

    def __init__(self, config, store, observer=None):
        self.config    = config
        self.store     = store
        self.observer  = observer
        self._provided = None      # the subjects delivery, kept for
                                   # the stderr question

    async def run(self, stop_event=None):
        """
        RETURN: AcceptResult, what was stored and under which report.

        Every dump is GATHERED first and only then written: a dump that
        cannot be read must not leave the test half accepted.
        """
        config = self.config
        notify(self.observer, "started", config.name, "Accept")

        text_db, report, provision = await self._gather(stop_event)

        #  THE SECOND QUESTION, at the door: a stderr that has words in
        #  it and no decision about it stops the ceremony. Accepting
        #  stdout while silently discarding a stream the test produced
        #  would bless a half-truth.
        if report is E_TestRunResult.OK:
            report = self._stderr_refusal(self._provided)

        if report is not E_TestRunResult.OK:
            result = AcceptResult(config.name, report, {}, provision)
            notify(self.observer, "finished", result)
            return result

        for name, text in sorted(text_db.items()):
            self.store.accept(config.name, config.choice, name, text)
            notify(self.observer, "verdict", name, True)

        #  THE NOTE IS THE DECISION: written verbatim into the book.
        #  STDERR IS NEVER SUBJECT TO TESTING (E-5) -- unlike every
        #  other subject, its stream is never itself accepted; only
        #  the note is.
        match config.stderr:
            case E_StderrNote.IGNORED | E_StderrNote.FORBIDDEN:
                self.store.note_stderr(config.name, config.choice,
                                       config.stderr)
                notify(self.observer, "verdict", "stderr", True)
            case _:
                pass

        result = AcceptResult(config.name, E_TestRunResult.OK,
                              dict(text_db), provision)
        notify(self.observer, "finished", result)
        return result

    def _stderr_text(self, provided):
        """
        RETURN: str, what the run wrote on stderr; '' where the
                provision delivered no such subject.

        'provided' is the SUBJECTS delivery ('None' where provision
        failed), not the provision record.
        """
        if provided is None or "stderr" not in provided: return ""
        with provided["stderr"].open() as reader:
            return reader.read()

    def _stderr_refusal(self, provided):
        """
        RETURN: E_TestRunResult.STDERR_UNDECIDED where the run wrote on
                stderr and NO note about it was ever taken -- neither
                handed to this ceremony nor standing in the book;
                E_TestRunResult.OK otherwise.

        REFUSE RATHER THAN GUESS, AT THE DOOR: the three notes say
        different things about the same stream, and only the author
        knows which is meant.
        """
        config = self.config
        if config.stderr is not None:            return E_TestRunResult.OK
        #  STDERR IS NEVER A SUBJECT (E-5): 'config.subjects' can no
        #  longer name it, so the earlier "asked for by name" escape
        #  is gone -- there is no second way to have decided.
        if not _has_words(self._stderr_text(provided)):
            return E_TestRunResult.OK
        if self.store.stderr_note(config.name, config.choice) \
                is not E_StderrNote.FORBIDDEN:
            return E_TestRunResult.OK          # the book already says
        return E_TestRunResult.STDERR_UNDECIDED

    async def _initiate(self, subject_name, step):
        """
        RETURN: (str, E_TestRunResult), the session's final plain nominal
                stream, or the reason there is none.

        The session presents the comparison and hands the driver its
        MATERIAL; what comes back is plain bytes. A CANCEL stores
        nothing -- an abandoned merge must never become a nominal.
        """
        session = step.interaction
        if session is None:
            return None, E_TestRunResult.RECORDING_MISSING

        collect = getattr(session, "collect", None)
        if collect is not None:                      # a plain producer
            return await collect(subject_name), E_TestRunResult.OK

        subject_text, nominal_text = await self._material(subject_name)
        if subject_text is None:
            return None, E_TestRunResult.RECORDING_MISSING
        text, intent = await merge_session(self.config.compare,
                                           subject_text, nominal_text,
                                           session, subject_name)
        if intent is not E_Intent.COMMIT:
            return None, E_TestRunResult.RECORDING_MISSING
        return text, E_TestRunResult.OK

    async def _material(self, subject_name):
        """
        RETURN: (str, str), the plain subject and the plain nominal a
                merge is made FROM. Either may be '' when absent.
                (None, None) when no subject can be had at all.
        """
        provided = None
        if self.config.groundwork is not None:
            provided = await self.config.groundwork.provide()
        if provided is None or subject_name not in provided:
            return None, None
        with provided[subject_name].open() as reader:
            subject_text = reader.read()

        #  A FIRST acceptance has no nominal yet, and a merge tool must
        #  still be given something on that side. The empty string is
        #  handed over DELIBERATELY and only here -- everywhere else an
        #  absent nominal is a fault, never an empty one.
        nominal = RecordNominal(self.store.nominal_path(
                                    self.config.name, self.config.choice,
                                     subject_name))
        try:
            with nominal.open() as reader:
                nominal_text = reader.read()
        except NominalNotAvailable:
            nominal_text = ""              # no nominal YET, not an empty one
        return subject_text, nominal_text

    async def _gather(self, stop_event):
        """
        RETURN: (dict, E_TestRunResult, provision), the complete dump per
                subject, the report, and the provision product if one was
                pulled.

        Nothing is written from here: gathering either yields every named
        subject or it fails, and the caller writes only in the first case.
        """
        config     = self.config
        text_db    = {}
        provided   = None

        for name, step in sorted(config.subjects.items()):
            if step.mode is E_AcceptMode.INITIATE:
                text, report = await self._initiate(name, step)
                if report is not E_TestRunResult.OK:
                    return {}, report, None
                text_db[name] = text
                continue

            if step.dump is not None:
                try:
                    with step.dump.open() as reader:
                        text_db[name] = reader.read()
                except NominalNotAvailable:
                    return {}, E_TestRunResult.RECORDING_MISSING, None
                continue

            #  No dump named: the precondition is unmet, so provision
            #  activates -- once, however many subjects need it.
            if provided is None:
                if config.groundwork is None:
                    return {}, E_TestRunResult.RECORDING_MISSING, None
                provided       = await config.groundwork.provide(
                                                   stop_event=stop_event)
                self._provided = provided
                if not provided.provision.delivered:
                    return {}, provided.provision.report, provided.provision
            if name not in provided:
                return {}, E_TestRunResult.OUTPUT_FILE_NOT_FOUND, \
                       provided.provision
            with provided[name].open() as reader:
                text_db[name] = reader.read()

        return text_db, E_TestRunResult.OK, \
               (provided.provision if provided is not None else None)


def _has_words(text):
    """RETURN: True, 'text' holds anything but whitespace; False else."""
    return bool(text) and bool(text.strip())
