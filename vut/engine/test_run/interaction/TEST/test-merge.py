#! /usr/bin/env python3
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

THE MERGE SESSION -- THE UP HALF.

    UNIT     the UP envelope, 'merge_session', and 'MergeToolDisplay' --
             the first driver, which needs no IDE.

    CAUSAL CONTRACT
             DOWN presents the comparison, the driver is handed its
             MATERIAL (plain subject, plain nominal), and returns plain
             merged bytes which become the nominal.

    CONSISTENCY CONTRACT
             a CANCEL stores nothing; a COMMIT carrying no artifact is
             treated as a CANCEL; a foreign signature is refused before
             parsing; what is stored is never a rendering of the view.
______________________________________________________________________________
"""
import asyncio
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

from   config import HwutRunner                                  # noqa F401,E402

from   vut.engine.test_run.result       import E_TestRunResult  # noqa E402
from   vut.engine.procsitter.procsitter    import ProcsitterConfig # noqa E402
from   vut.engine.test_run.operations.accept import (Accept,       # noqa E402
                                                     AcceptConfig,
                                                     AcceptStep,
                                                     E_AcceptMode)
from   vut.engine.test_run.configuration   import (              # noqa E402
                                                   TestConfiguration,
                                                   TestChoiceConfiguration,
                                                   E_SourceKind)
from   vut.engine.test_run.interaction.feed import (              # noqa E402
                                                    E_Intent,
                                                    MergeToolDisplay,
                                                    PROTOCOL_SIGNATURE,
                                                    ProtocolMismatch,
                                                    Resolution,
                                                    down_message,
                                                    envelope,
                                                    merge_session,
                                                    resolution_of)
from   vut.engine.test_run.interaction.feed import RemoteDisplay  # noqa E402
from   vut.engine.test_run.provision.core  import Run            # noqa E402
from   vut.engine.orchestrator.bookkeeper.bookkeeper import (    # noqa E402
                                                   Bookkeeper)
from   vut.engine.test_run.store           import Store          # noqa E402


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


def _place(tool_body):
    """
    RETURN: (TestConfiguration, Store, str, str), a ready test and the
            path of a merge tool with 'tool_body'.
    """
    directory = tempfile.mkdtemp(prefix="vut_merge_")
    with open(os.path.join(directory, "demo.py"), "w") as fh:
        fh.write("print('subject line')\n")
    tool = os.path.join(directory, "tool.py")
    with open(tool, "w") as fh:
        fh.write(tool_body)
    configuration = TestConfiguration(
        source_file    = "demo.py",
        source_kind    = E_SourceKind.INTERPRETED,
        test_directory = directory,
        caps           = ProcsitterConfig(max_wall_clock_sec=20.0),
        interpreter    = ["python3", "-u"],
        choice_db      = {None: TestChoiceConfiguration()})
    return configuration, Store(Bookkeeper(directory)), directory, tool


def _accept_through(configuration, store, directory, tool, work):
    """RETURN: AcceptResult, of one INITIATE through the merge tool."""
    driver = MergeToolDisplay(["python3", tool, "{subject}", "{nominal}",
                               "{merged}"],
                              os.path.join(directory, work))
    return asyncio.run(Accept(AcceptConfig(
        "demo",
        {"stdout": AcceptStep(mode=E_AcceptMode.INITIATE,
                              interaction=driver)},
        groundwork=Run(configuration)), store).run())


def test_envelope():
    """The UP envelope is SIGNED and VERSIONED like DOWN, and it carries
    the ARTIFACT -- plain nominal bytes, never a rendering."""
    message = envelope(Resolution(intent=E_Intent.COMMIT,
                                  nominal_text="merged bytes\n"))
    back    = resolution_of(message)
    refused = None
    try:
        resolution_of({"signature": "some-other/9", "intent": "commit"})
    except ProtocolMismatch as error:
        refused = str(error).split("--")[0].strip()

    print("INSPECT: envelope   = %s" % sorted(message))
    print("         signature  = %s, intent = %s"
          % (message["signature"], message["intent"]))
    print("         round trip = %r" % back.nominal_text)
    print("         foreign    -> %s" % (refused or "NOT REFUSED"))
    ok = _check([
        (message["signature"] == PROTOCOL_SIGNATURE,
         "the envelope is signed"),
        (message["nominal"] == "merged bytes\n",
         "and carries the plain artifact, not a view"),
        (back.intent is E_Intent.COMMIT
             and back.nominal_text == "merged bytes\n",
         "it round-trips"),
        (refused is not None,
         "a foreign signature is REFUSED before anything is parsed"),
    ])
    _verdict(ok, "signed, versioned, and carrying the artifact.")


def test_merge_commits():
    """A tool that produces a merged file COMMITS: its plain bytes become
    the nominal. What is stored came from the tool, not from the feed."""
    configuration, store, directory, tool = _place(
        "import sys\n"
        "subject = open(sys.argv[1]).read().strip()\n"
        "open(sys.argv[3],'w').write('MERGED from %s\\n' % subject)\n")
    store.accept("demo", None, "stdout", "the old nominal\n")
    result = _accept_through(configuration, store, directory, tool, "m1")
    stored = store.nominal("demo", None, "stdout").open().read()

    print("INSPECT: report = %s" % result.report)
    print("         stored = %r" % stored)
    ok = _check([
        (result.verdict is True,
         "acceptance succeeded"),
        (stored == "MERGED from subject line\n",
         "the tool's plain bytes became the nominal"),
        ("subject line" in stored,
         "and the tool saw the real subject as its material"),
    ])
    shutil.rmtree(directory, ignore_errors=True)
    _verdict(ok, "the merge tool's artifact becomes the nominal.")


def test_cancel_stores_nothing():
    """A tool that fails, or leaves no merged file, CANCELS -- and an
    abandoned merge must never become a nominal."""
    configuration, store, directory, tool = _place(
        "import sys\nsys.exit(1)\n")
    store.accept("demo", None, "stdout", "the old nominal\n")
    result = _accept_through(configuration, store, directory, tool, "m2")
    after  = store.nominal("demo", None, "stdout").open().read()

    silent_dir = tempfile.mkdtemp(prefix="vut_merge_")
    quiet = os.path.join(silent_dir, "quiet.py")
    with open(quiet, "w") as fh:
        fh.write("pass\n")            # exits 0, writes nothing
    result2 = _accept_through(configuration, store, directory, quiet, "m3")
    after2  = store.nominal("demo", None, "stdout").open().read()

    print("INSPECT: tool failed      -> %s" % result.report)
    print("         nominal after    -> %r" % after)
    print("         tool wrote none  -> %s" % result2.report)
    print("         nominal after    -> %r" % after2)
    ok = _check([
        (result.verdict is False,
         "a failing tool cancels the acceptance"),
        (after == "the old nominal\n",
         "and the nominal is UNTOUCHED"),
        (result2.verdict is False,
         "a tool that exits cleanly but writes nothing also cancels"),
        (after2 == "the old nominal\n",
         "the nominal survives that too"),
    ])
    for d in (directory, silent_dir): shutil.rmtree(d, ignore_errors=True)
    _verdict(ok, "an abandoned merge never becomes a nominal.")


def test_empty_commit_is_a_cancel():
    """A COMMIT carrying no artifact is treated as a CANCEL: committing
    an absent stream would store emptiness as the accepted behaviour."""
    class Hollow:
        async def open(self, name):    pass
        async def present(self, item): pass
        async def close(self):         pass
        async def resolve(self, name, subject_text, nominal_text):
            """RETURN: Resolution, COMMIT with nothing in it."""
            return Resolution(intent=E_Intent.COMMIT, nominal_text=None)

    text, intent = asyncio.run(merge_session(
        None, "subject\n", "nominal\n", Hollow(), "stdout"))
    print("INSPECT: driver said COMMIT with no artifact")
    print("         hub resolved to -> %s, text %r" % (intent, text))
    ok = _check([
        (intent is E_Intent.CANCEL,
         "the hub downgrades it to CANCEL"),
        (text is None,
         "and carries nothing forward"),
    ])
    _verdict(ok, "an empty commit is refused, not stored.")


def test_driver_without_resolve():
    """A DISPLAY driver has no 'resolve'. Handed to a merge session it
    cancels rather than failing -- half-duplex is not an error."""
    class DisplayOnly:
        def __init__(self): self.count = 0
        async def open(self, name):    pass
        async def present(self, item): self.count += 1
        async def close(self):         pass

    driver = DisplayOnly()
    text, intent = asyncio.run(merge_session(
        None, "subject\n", "different\n", driver, "stdout"))
    print("INSPECT: the driver presented %i DOWN items" % driver.count)
    print("         and the session resolved to %s" % intent)
    ok = _check([
        (driver.count > 0,
         "DOWN was still presented in full"),
        (intent is E_Intent.CANCEL,
         "and a driver that cannot merge simply cancels"),
        (text is None,
         "storing nothing"),
    ])
    _verdict(ok, "half-duplex is a driver's choice, not a fault.")


MOCK_IDE = os.path.join(os.path.dirname(__file__), "mock", "mock_ide.py")


def test_a_client_over_a_pipe():
    """THE RICH TIER, against a client that imports NOTHING from vut. It
    dispatches on the message 'kind' and checks the signature before
    parsing -- which is what makes the protocol implementable in any
    language."""
    committing = RemoteDisplay(["python3", MOCK_IDE, "commit"])
    text, intent = asyncio.run(merge_session(
        None, "subject line\n", "nominal line\n", committing, "stdout"))

    cancelling = RemoteDisplay(["python3", MOCK_IDE, "cancel"])
    text2, intent2 = asyncio.run(merge_session(
        None, "subject line\n", "nominal line\n", cancelling, "stdout"))

    print("INSPECT: DOWN items serialised to the client = %i"
          % committing.sent_count)
    print("         client committed -> %s, %r" % (intent, text))
    print("         client cancelled -> %s, %r" % (intent2, text2))
    ok = _check([
        (committing.sent_count > 0,
         "DOWN crossed a real boundary as JSON, one message per line"),
        (intent is E_Intent.COMMIT and text is not None,
         "the client's UP envelope was parsed back into a resolution"),
        (str(committing.sent_count) in (text or ""),
         "and the client had really SEEN the items it answers about"),
        (intent2 is E_Intent.CANCEL and text2 is None,
         "a client that cancels stores nothing"),
    ])
    _verdict(ok, "a client in any language can speak this protocol.")


def test_the_merge_loop():
    """THE LOOP (README 11.6). A REALIGN is answered with a FRESH
    association of the fixed subject against the WORKING nominal, and the
    author is shown it again -- because the alignment is compare's, not
    the editor's. 'open' and 'close' happen ONCE, outside the loop: a
    driver whose connection IS the session has nothing to answer on once
    it is closed.

    TWO GUARDS, both ending the session as a CANCEL so the nominal is
    left exactly as it was. NO PROGRESS catches the ordinary bug -- a
    driver echoing its input -- on the very next round, and never touches
    an author, since every real edit progresses. THE CAP is the backstop
    for a driver that OSCILLATES (A, B, A, B ...) and so progresses for
    ever without ever deciding."""
    round_list = []

    class Scripted:
        """Answers one scripted Resolution per round, recording what the
        hub showed it each time."""
        def __init__(self, answer_list):
            self.answer_list = list(answer_list)
            self.opened = self.closed = 0
            self._item_list = []

        async def open(self, name):    self.opened += 1
        async def present(self, item): self._item_list.append(item)
        async def close(self):         self.closed += 1

        async def resolve(self, name, subject_text, nominal_text):
            """RETURN: Resolution, the next scripted answer."""
            round_list.append((nominal_text, self._item_list))
            self._item_list = []
            if not self.answer_list:
                return Resolution(intent=E_Intent.CANCEL)
            return self.answer_list.pop(0)

    subject = "alpha\nbeta\ngamma\n"
    nominal = "alpha\nBETA\ngamma\n"
    edited  = "alpha\nbeta\ndelta\ngamma\n"

    looping = Scripted([Resolution(intent=E_Intent.REALIGN,
                                   nominal_text=edited),
                        Resolution(intent=E_Intent.COMMIT,
                                   nominal_text=edited)])
    text, intent = asyncio.run(merge_session(None, subject, nominal,
                                             looping, "stdout"))

    del round_list[:]
    stuck = Scripted([Resolution(intent=E_Intent.REALIGN,
                                 nominal_text=nominal)])   # NO edit
    text2, intent2 = asyncio.run(merge_session(None, subject, nominal,
                                               stuck, "stdout"))
    stuck_rounds = len(round_list)

    del round_list[:]
    patient = Scripted([Resolution(intent=E_Intent.REALIGN,
                                   nominal_text="alpha\n" + "x" * i + "\n")
                        for i in range(1, 21)]
                       + [Resolution(intent=E_Intent.COMMIT,
                                     nominal_text="alpha\n")])
    _, intent3 = asyncio.run(merge_session(None, subject, nominal,
                                           patient, "stdout"))
    patient_rounds = len(round_list)

    del round_list[:]
    oscillating = Scripted([Resolution(intent=E_Intent.REALIGN,
                                       nominal_text=(nominal if i % 2
                                                     else edited))
                            for i in range(200)])
    text4, intent4 = asyncio.run(merge_session(None, subject, nominal,
                                               oscillating, "stdout",
                                               max_round_n=5))
    oscillating_rounds = len(round_list)

    print("INSPECT: looping  -> %s, %r" % (intent, text))
    print("         stuck    -> %s, %r after %i round(s)"
          % (intent2, text2, stuck_rounds))
    print("         patient  -> %s after %i round(s)"
          % (intent3, patient_rounds))
    print("         capped   -> %s after %i round(s) (cap 5)"
          % (intent4, oscillating_rounds))
    ok = _check([
        (looping.opened == 1 and looping.closed == 1,
         "open and close happen ONCE -- the loop is inside the session"),
        (intent is E_Intent.COMMIT and text == edited,
         "the loop ends on COMMIT, carrying the final artifact"),
        (intent2 is E_Intent.CANCEL and text2 is None,
         "a REALIGN that changed nothing is refused as a CANCEL"),
        (stuck_rounds == 1,
         "and it is refused AT ONCE -- no second round is computed"),
        (intent3 is E_Intent.COMMIT and patient_rounds == 21,
         "twenty progressing rounds are not cut off: only the bug is"),
        (intent4 is E_Intent.CANCEL and text4 is None,
         "an OSCILLATING driver -- always progressing, never deciding "
         "-- is ended by the cap, as a CANCEL"),
        (oscillating_rounds == 5,
         "and exactly at the cap, not one round beyond it"),
    ])
    _verdict(ok, "the merge loop loops, and stops for a reason.")


def test_the_loop_realigns():
    """THE POINT OF THE LOOP: the second DOWN is not the first one again.
    The subject is FIXED and the nominal gained a line, so the association
    compare computes for round 2 differs from round 1's -- which is the
    whole reason an edit must be answered with a fresh feed rather than
    with the old projection."""
    generation_list = []

    class TwoRounds:
        def __init__(self): self._item_list = []; self._done = False
        async def open(self, name): pass
        async def present(self, item): self._item_list.append(item)
        async def close(self): pass
        async def resolve(self, name, subject_text, nominal_text):
            """RETURN: Resolution, REALIGN once with an edit, then COMMIT."""
            generation_list.append(self._item_list)
            self._item_list = []
            if self._done:
                return Resolution(intent=E_Intent.COMMIT,
                                  nominal_text="alpha\nbeta\ndelta\ngamma\n")
            self._done = True
            return Resolution(intent=E_Intent.REALIGN,
                              nominal_text="alpha\nbeta\ndelta\ngamma\n")

    def rows(item_list):
        """RETURN: list, the (subject, nominal) line numbers of the pairs."""
        return [(i.line_n_s, i.line_n_n) for i in item_list
                if type(i).__name__ == "LinePairInst"]

    asyncio.run(merge_session(None, "alpha\nbeta\ngamma\n",
                              "alpha\nBETA\ngamma\n", TwoRounds(), "stdout"))
    first, second = rows(generation_list[0]), rows(generation_list[1])
    print("INSPECT: round 1 pairs = %s" % first)
    print("         round 2 pairs = %s" % second)
    ok = _check([
        (len(generation_list) == 2,
         "two DOWN generations were produced, one per round"),
        (first != second,
         "the second is a DIFFERENT association -- the edit re-aligned it"),
        (len(second) > len(first),
         "the added nominal line appears as an added pair"),
    ])
    _verdict(ok, "an edit changes the alignment, and the author sees it.")


def test_the_loop_over_a_real_pipe():
    """THE LOOP AGAINST A REAL CLIENT, in another process, importing
    nothing from vut. It answers REALIGN once with an edited nominal, then
    COMMIT -- so a second DOWN generation must cross the pipe.

    This is what pins 'RemoteDisplay.resolve' NOT closing the client's
    stdin: a REALIGN is answered on that same pipe, and a driver that shut
    it after the first answer would make the loop impossible."""
    one_round = RemoteDisplay(["python3", MOCK_IDE, "commit"])
    text, intent = asyncio.run(merge_session(
        None, "subject line\n", "nominal line\n", one_round, "stdout"))

    looping = RemoteDisplay(["python3", MOCK_IDE, "realign", "commit"])
    text2, intent2 = asyncio.run(merge_session(
        None, "subject line\n", "nominal line\n", looping, "stdout"))

    print("INSPECT: one round  -> %s after %i DOWN items"
          % (intent, one_round.sent_count))
    print("         two rounds -> %s after %i DOWN items"
          % (intent2, looping.sent_count))
    ok = _check([
        (intent is E_Intent.COMMIT and text is not None,
         "the single-round client still commits, unchanged"),
        (intent2 is E_Intent.COMMIT and text2 is not None,
         "the looping client reaches its COMMIT through a REALIGN"),
        (looping.sent_count > one_round.sent_count,
         "a SECOND DOWN generation crossed the pipe"),
        (looping.sent_count == 2 * one_round.sent_count + 1,
         "one extra MaterialInst and one full generation, exactly"),
    ])
    _verdict(ok, "the loop survives a real process boundary.")


def test_resolve_is_inside_the_session():
    """THE SEQUENCE: open -> present -> resolve -> close. 'resolve' is
    INSIDE the open session, because a driver whose connection IS the
    session has nothing to answer on once it is closed."""
    trace = []

    class Tracer:
        async def open(self, name):    trace.append("open")
        async def present(self, item): trace.append("item")
        async def close(self):         trace.append("close")
        async def resolve(self, name, subject_text, nominal_text):
            """RETURN: Resolution, recording WHEN it was asked."""
            trace.append("resolve")
            return Resolution(intent=E_Intent.COMMIT, nominal_text="ok\n")

    asyncio.run(merge_session(None, "a\n", "b\n", Tracer(), "stdout"))
    shape = [step for step in trace if step != "item"]
    print("INSPECT: sequence = %s" % shape)
    print("         (%i DOWN items elided)" % trace.count("item"))
    ok = _check([
        (shape == ["open", "resolve", "close"],
         "resolve happens between open and close, never after"),
        (trace.index("resolve") > trace.index("item"),
         "and after every DOWN item has been presented"),
    ])
    _verdict(ok, "open, present, resolve, close -- in that order.")


def test_unknown_intent_and_target():
    """An UP message with an intent this hub does not know, and a display
    target with no driver: both are REFUSED. Guessing would act on a
    message nobody sent."""
    from vut.engine.test_run.interaction.feed import driver_for, E_DisplayTarget
    unknown_intent = unknown_target = None
    try:
        resolution_of({"signature": PROTOCOL_SIGNATURE,
                       "intent": "obliterate", "nominal": "x"})
    except ValueError as error:
        unknown_intent = str(error)
    try:
        driver_for("not-a-target")
    except ValueError as error:
        unknown_target = str(error)

    print("INSPECT: unknown intent -> %s" % (unknown_intent or "ACCEPTED"))
    print("         unknown target -> %s" % (unknown_target or "ACCEPTED"))
    ok = _check([
        (unknown_intent is not None,
         "an intent this hub does not know is refused"),
        (unknown_target is not None,
         "and so is a target with no driver"),
    ])
    _verdict(ok, "refuse the unknown; never guess an action.")


def test_a_widened_down_stream():
    """A DESIGN TEST, not a behaviour one: how easily does this component
    react when COMPARE changes what its association emits?

    Nothing here NAMES a DOWN item's kind or any of its fields -- the
    hub carries, it does not interpret. So a new kind with new fields
    reaches a client untouched and fully named, with no edit here.

    What it will NOT do is guess: an item whose fields cannot be read is
    REFUSED, because a kind with an empty body is indistinguishable from
    an item that genuinely has none, and the client would show nothing
    while nobody complained.
    """
    import dataclasses, collections

    @dataclasses.dataclass(frozen=True)
    class NewKindOfInst:                       # compare invents one
        subject_span: str   = "3..7"
        confidence:   float = 0.91
        origin:       str   = "analogy-db"

    class PlainClassInst:                      # compare drops dataclasses
        def __init__(self): self.left, self.right = "a", "b"

    NamedTupleInst = collections.namedtuple("NamedTupleInst", "left right")

    @dataclasses.dataclass(frozen=True)
    class NoFieldInst:                         # a kind with NO fields --
        pass                                   #   readable, and empty

    carried = [(what, down_message(item))
               for item, what in ((NewKindOfInst(),         "a new kind"),
                                  (PlainClassInst(),        "a plain class"),
                                  (NamedTupleInst("a","b"), "a namedtuple"))]
    empty_body = down_message(NoFieldInst())["field_db"]
    refused    = None
    try:
        down_message(object())                 # nothing to read at all
    except TypeError as error:
        refused = str(error).split(":")[0]

    for what, message in carried:
        print("INSPECT: %-14s -> kind %-14s fields %s"
              % (what, message["kind"], sorted(message["field_db"])))
    print("         no fields      -> readable, and empty: %s" % (empty_body == {}))
    print("         unreadable     -> %s" % (refused or "NOT REFUSED"))
    ok = _check([
        (sorted(carried[0][1]["field_db"])
             == ["confidence", "origin", "subject_span"],
         "a NEW kind's NEW fields arrive named, with no edit here"),
        (all(sorted(m["field_db"]) == ["left", "right"]
             for _, m in carried[1:]),
         "and the shape compare chooses -- dataclass, class, tuple -- "
         "does not matter"),
        (all(m["signature"] == PROTOCOL_SIGNATURE for _, m in carried),
         "every message still carries the signature a client checks"),
        (empty_body == {},
         "a kind with NO fields is readable and empty -- absent is not "
         "empty, and this is where they are hardest to tell apart"),
        (refused is not None,
         "an item whose fields cannot be READ AT ALL is refused"),
    ])
    _verdict(ok, "the hub carries what compare emits; it never guesses.")


if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "The merge session: the UP half",
        choice_map = {
            "envelope":      test_envelope,
            "commit":        test_merge_commits,
            "cancel":        test_cancel_stores_nothing,
            "empty_commit":  test_empty_commit_is_a_cancel,
            "display_only":  test_driver_without_resolve,
            "loop":          test_the_merge_loop,
            "loop_realigns": test_the_loop_realigns,
            "loop_pipe":     test_the_loop_over_a_real_pipe,
            "rich_client":   test_a_client_over_a_pipe,
            "sequence":      test_resolve_is_inside_the_session,
            "unknown":       test_unknown_intent_and_target,
            "widened_down":  test_a_widened_down_stream,
        },
        happy      = "SUCCESS.*",
    ).run()
