"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE
       THE FEED SESSION -- carrying a comparison out to a consumer.

DESCRIPTION
       Two hubs, two halves (README 11.1). DOWN carries the comparison
       out; UP carries a human's resolution back. DISPLAY uses DOWN only;
       MERGE uses DOWN then UP.

       DOWN IS COMPARE'S -- it is not invented here. 'compare/feeder/ui.py'
       runs the association inside and yields immutable DisplayInst items.
       This module carries them; it does not interpret them.

       ONE INTERFACE TO ANY TARGET: a DisplayAdapter states a required
       SEQUENCE, and a DRIVER implements it for one tool. The driver owns
       its connection mechanics entirely -- a socket, a pipe, files on
       disk -- so there is NO shared connection type to constrain the next
       tool.

           open -> present each DOWN item -> (merge: yield an UP) -> close

       THE SIGNATURE VERSIONS THE PROTOCOL STRUCTURE, not the run, the
       content or the process. A hub checks it BEFORE parsing, so it never
       reads a message with the wrong parser: on mismatch it REFUSES
       rather than mis-read.

       UP IS THE ARTIFACT, NOT THE VIEW. A resolution is the plain
       canonicalised nominal stream plus an intent -- never a view
       unparsed back into bytes. Compare tokenises and may normalise, so
       reconstructing a nominal from the projection is lossy-risk, and a
       wrong nominal poisons every future comparison.
______________________________________________________________________________
"""
from   dataclasses import dataclass
from   pathlib     import Path
from   enum        import Enum
from   typing      import Optional

import vut.engine.compare.feeder.ui as compare_feeder


PROTOCOL_SIGNATURE = "vut-feed/1"

#  THE ROUND CAP of a merge session. A merge is a human activity and no
#  author edits one file a thousand times; a session that reaches this
#  number is a DRIVER answering REALIGN unconditionally. Reaching it ends
#  the session as a CANCEL -- bounded, and the nominal is left untouched.
#  A caller may name its own ('merge_session(..., max_round_n=...)').
MERGE_ROUND_MAX = 1000


class E_DisplayTarget(Enum):
    """Which driver carries the session."""
    NONE     = "none"       # collect nothing; the verdict is enough
    CONSOLE  = "console"    # the always-available tier
    TUI      = "tui"        # the terminal, interactively (tui.py)
    RICH     = "rich"       # a client speaking our protocol

    def __str__(self):
        """RETURN: str, the target's token."""
        return self.value


class E_Intent(Enum):
    """What an UP resolution asks for."""
    REALIGN = "realign"     # the nominal changed; show me again
    COMMIT  = "commit"      # store this as the nominal
    CANCEL  = "cancel"      # store nothing

    def __str__(self):
        """RETURN: str, the intent's token."""
        return self.value


@dataclass(frozen=True)
class Resolution:
    """An UP message: the ARTIFACT and what to do with it.

    'nominal_text' is the plain canonicalised nominal stream -- the
    material a merge produced, not a rendering of it.
    """
    intent:       E_Intent
    nominal_text: Optional[str] = None
    signature:    str           = PROTOCOL_SIGNATURE


class ProtocolMismatch(Exception):
    """A message arrived under a signature this hub cannot parse. Raised
    BEFORE parsing, so nothing is ever read with the wrong parser."""
    pass


def check_signature(signature):
    """
    RETURN: None, the signature is one this hub parses.

    Raises ProtocolMismatch otherwise. REFUSING is the point: a hub that
    guessed would mis-read a message rather than decline it.
    """
    if signature != PROTOCOL_SIGNATURE:
        raise ProtocolMismatch(
            "feed protocol %r cannot be parsed by %r -- refusing rather "
            "than mis-reading" % (signature, PROTOCOL_SIGNATURE))


def envelope(resolution):
    """
    RETURN: dict, an UP message ready to be written as JSON.

    THE ENVELOPE IS SIGNED AND VERSIONED like DOWN, and it carries the
    ARTIFACT: the plain canonicalised nominal stream, never a rendering
    of it. A view unparsed back into bytes would be lossy-risk, and a
    wrong nominal poisons every future comparison.
    """
    return {"signature": PROTOCOL_SIGNATURE,
            "intent":    str(resolution.intent),
            "nominal":   resolution.nominal_text}


def resolution_of(message):
    """
    RETURN: Resolution, parsed from an UP message.

    Raises ProtocolMismatch when the signature is not one this hub
    parses -- checked BEFORE anything else is read, so a foreign message
    is never interpreted under the wrong grammar.
    Raises ValueError on an intent this hub does not know.
    """
    check_signature(message.get("signature"))
    intent_text = message.get("intent")
    for intent in E_Intent:
        if str(intent) == intent_text:
            return Resolution(intent=intent,
                              nominal_text=message.get("nominal"))
    raise ValueError("unknown UP intent %r" % intent_text)


class DisplayAdapter:
    """THE ONE INTERFACE to any target. A driver implements this sequence
    for one tool and owns its own connection mechanics.

    Every method is optional in a driver; the session calls what exists.
    """

    async def open(self, subject_name):
        """RETURN: None. The session for one subject begins."""

    async def present(self, item):
        """RETURN: None. One DOWN item arrives, in order."""

    async def resolve(self, subject_name, subject_text, nominal_text):
        """
        RETURN: Resolution, what the human decided.
                None,       this driver does not merge.

        The MATERIAL is handed over -- the plain subject and the plain
        nominal -- so a merge is made FROM the artifacts, never from the
        projection.
        """
        return None

    async def close(self):
        """RETURN: None. The session ends, however it ended."""


class NullDisplay(DisplayAdapter):
    """Presents nothing. The default, so DifferenceDisplay needs no
    special case for 'no target'."""
    pass


class CollectingDisplay(DisplayAdapter):
    """Keeps every DOWN item. The always-available tier, and what a test
    inspects."""

    def __init__(self):
        self.item_list    = []
        self.opened_list  = []
        self.closed       = False

    async def open(self, subject_name):
        """RETURN: None. Records that a subject's session began."""
        self.opened_list.append(subject_name)

    async def present(self, item):
        """RETURN: None. Keeps the item, in arrival order."""
        self.item_list.append(item)

    async def close(self):
        """RETURN: None. Records that the session ended."""
        self.closed = True


async def merge_session(compare_options, subject_text, nominal_text,
                        adapter, subject_name,
                        max_round_n=MERGE_ROUND_MAX):
    """
    RETURN: (str, E_Intent), the resolved nominal stream and the intent
            that ended the loop.
            (None, E_Intent.CANCEL) when the driver resolved nothing, or
            when a round made no progress (below).

    THE FULL-DUPLEX HALF: DOWN presents the comparison, then the driver is
    handed its MATERIAL -- the plain subject and the plain nominal -- and
    returns the plain merged stream. This hub never reconstructs a nominal
    from the projection it just sent.

    THE LOOP (README 11.6). Editing the nominal changes the ALIGNMENT, and
    the alignment is COMPARE's -- so a REALIGN is answered with a FRESH
    association of the same subject against the working nominal, and the
    author is shown it again. The SUBJECT IS FIXED throughout; only the
    nominal evolves.

        HUB (this function)                          DRIVER (adapter)
         |                                              |
         |------------ open(subject_name) ------------->|         ONCE
         |                                               |
         |  .--------------- ROUND ---------------------.
         |  |                                            |
         |  |  compare.feed(subject, working)             |
         |  |  yields DOWN items ...                      |
         |  |----------- present(item) * ----------------->|   * once per item
         |  |                                              |
         |  |----------- resolve(subject, working) -------->|
         |  |<---------- Resolution(intent, text) ----------|
         |  |                                              |
         |  |  intent is COMMIT or CANCEL?  ---------------------> break, keep intent
         |  |  text is None or == working?  -> NO-PROGRESS GUARD -> CANCEL, break
         |  |  round_n >= max_round_n?      -> THE CAP          -> CANCEL, break
         |  |  else: working = text, round_n += 1               -> another ROUND
         |  '--------------------------------------------.
         |                                                |
         |------------ close() -------------------------->|         ONCE
         |
        returns (working or None, intent) to the CALLER

    'open' and 'close' stay OUTSIDE the loop: a driver whose connection IS
    the session -- a pipe, a socket -- has nothing to answer on once it is
    closed. That is also why 'resolve' sits inside the open session, and
    why the half-duplex door 'feed_down' cannot be the body of this one.

    ONE COMPARE RUN PER ROUND: each round is an independent, exact
    'feed(subject, working nominal)'. Nothing carries over between rounds
    and nothing needs to -- the streams are held here as TEXT, so a round
    costs a fresh StringIO and no re-reading of anything.

    A COMMIT that carries no text is refused as a CANCEL: committing an
    absent artifact would store emptiness as the accepted behaviour.

    TWO GUARDS AGAINST A SESSION THAT NEVER ENDS, and both end it as a
    CANCEL -- the nominal is left exactly as it was:

        NO PROGRESS   a REALIGN with no artifact, or one byte-identical
                      to the round before it, cannot align to anything
                      new. Refused at once. This catches the ordinary
                      bug -- a driver echoing its input -- on the very
                      next round, and it never touches an author, since
                      every real edit progresses.

        THE CAP       'max_round_n' rounds, then the session ends anyway.
                      The backstop for a driver that oscillates (A, B,
                      A, B ...) and so progresses for ever without ever
                      deciding. The default is deliberately far above
                      any human merge.
    """
    import io
    from vut.engine.compare.configuration import Configuration
    if compare_options is None: compare_options = Configuration()

    working    = nominal_text
    resolution = None
    round_n    = 0
    await _call(adapter, "open", subject_name)
    try:
        resolve = getattr(adapter, "resolve", None)
        while True:
            async for item in compare_feeder.feed(compare_options,
                                                  io.StringIO(subject_text),
                                                  io.StringIO(working)):
                await _call(adapter, "present", item)

            #  A driver with no 'resolve' is half-duplex by its own
            #  choice, not by fault: one round, then out.
            if resolve is None: break

            resolution = await resolve(subject_name, subject_text, working)
            if resolution is None: break
            round_n += 1
            #  BEFORE the message is read, never after.
            check_signature(resolution.signature)
            if resolution.intent is not E_Intent.REALIGN: break

            if resolution.nominal_text is None \
               or resolution.nominal_text == working:
                #  No progress: nothing to align differently. Ending here
                #  bounds the driver's bug without bounding the author.
                resolution = Resolution(intent=E_Intent.CANCEL)
                break
            if round_n >= max_round_n:
                #  Progressing, but never deciding. Ended, not raised:
                #  a hung driver must not take the caller down with it.
                resolution = Resolution(intent=E_Intent.CANCEL)
                break
            working = resolution.nominal_text
    finally:
        await _call(adapter, "close")

    if resolution is None:
        return None, E_Intent.CANCEL
    if resolution.intent is E_Intent.COMMIT and resolution.nominal_text is None:
        return None, E_Intent.CANCEL
    return resolution.nominal_text, resolution.intent


async def feed_down(compare_options, subject_reader, nominal_reader, adapter,
                    subject_name):
    """
    RETURN: int, how many DOWN items were carried.

    The session's DOWN half for one subject: open, present every item
    compare yields, close. 'close' runs however the body ended, so a
    driver's resources are released even when presentation raised.
    """
    await _call(adapter, "open", subject_name)
    count = 0
    try:
        async for item in compare_feeder.feed(compare_options,
                                              subject_reader,
                                              nominal_reader):
            await _call(adapter, "present", item)
            count += 1
    finally:
        await _call(adapter, "close")
    return count


async def _call(adapter, method_name, *argument_list):
    """
    RETURN: whatever the adapter's method returns, or None when it has
            none.

    A driver implements what it needs; a method it lacks is not a fault.
    Unlike an observer's, a driver's exception PROPAGATES: a display that
    failed must not be reported as a display that happened.
    """
    method = getattr(adapter, method_name, None)
    if method is None: return None
    return await method(*argument_list)


class MergeToolDisplay(DisplayAdapter):
    """A DRIVER for any external merge tool that works on FILES.

    Its connection mechanics -- three paths and a subprocess -- are its
    OWN concern; nothing here is shared with the next driver, which is
    the point of there being no common 'connection' type.

        subject  ->  <work>/subject
        nominal  ->  <work>/nominal
        merged   <-  <work>/merged      what the tool leaves behind

    The tool's command is a template: '{subject}', '{nominal}' and
    '{merged}' are substituted. A tool that exits non-zero, or leaves no
    merged file, CANCELS -- an unfinished merge must never be stored.
    """

    def __init__(self, command_template, work_directory, present_f=False):
        self.command_template = list(command_template)
        self.work_directory   = Path(work_directory)
        self.present_f        = present_f
        self.item_list        = []

    async def open(self, subject_name):
        """RETURN: None. A session for one subject begins."""
        self.work_directory.mkdir(parents=True, exist_ok=True)

    async def present(self, item):
        """RETURN: None. DOWN items are kept only if asked for: a merge
        tool reads files, not a projection."""
        if self.present_f: self.item_list.append(item)

    async def resolve(self, subject_name, subject_text, nominal_text):
        """
        RETURN: Resolution, COMMIT with the merged stream when the tool
                succeeded; CANCEL otherwise.

        The tool is handed the MATERIAL and gives back plain bytes, so
        what is stored is never a rendering.
        """
        import asyncio as _asyncio
        path_db = {"subject": self.work_directory / ("%s.subject" % subject_name),
                   "nominal": self.work_directory / ("%s.nominal" % subject_name),
                   "merged":  self.work_directory / ("%s.merged"  % subject_name)}
        path_db["subject"].write_text(subject_text, encoding="utf-8")
        path_db["nominal"].write_text(nominal_text, encoding="utf-8")
        if path_db["merged"].exists(): path_db["merged"].unlink()

        argv = [part.format(**{k: str(v) for k, v in path_db.items()})
                for part in self.command_template]
        process = await _asyncio.create_subprocess_exec(*argv)
        code    = await process.wait()

        if code != 0 or not path_db["merged"].exists():
            return Resolution(intent=E_Intent.CANCEL)
        return Resolution(intent=E_Intent.COMMIT,
                          nominal_text=path_db["merged"].read_text(
                                                          encoding="utf-8"))

    async def close(self):
        """RETURN: None. The session ends."""


def down_message(item):
    """
    RETURN: dict, one DOWN item as a transport-neutral message.

    The kind is named explicitly, so a client dispatches on a STRING and
    never on a Python class it would have to import. This is what makes
    the protocol implementable by a client in any language.
    """
    #  ABSENT IS NOT EMPTY, and this is where the two are hardest to tell
    #  apart: an item with NO fields is readable and empty, while an item
    #  whose fields cannot be found is unreadable. Only the second is
    #  refused, so the test is 'is not None' and never truthiness.
    name_list = None
    for attribute in ("__dataclass_fields__", "_fields", "__slots__"):
        found = getattr(item, attribute, None)
        if found is not None:
            name_list = list(found)
            break
    if name_list is None and hasattr(item, "__dict__"):
        name_list = list(vars(item))
    if name_list is None:
        #  REFUSE RATHER THAN GUESS. An item whose fields cannot be read
        #  would serialise to a kind with an EMPTY body -- indistinguish-
        #  able from an item that genuinely has none, and the client
        #  would display nothing while nobody complained.
        raise TypeError(
            "cannot read the fields of a %s: the DOWN stream carries an "
            "item shape this hub does not know how to serialise"
            % type(item).__name__)

    return {"signature": PROTOCOL_SIGNATURE,
            "kind":      type(item).__name__,
            "field_db":  {name: _carry(getattr(item, name))
                          for name in name_list}}


def _carry(value, depth=0):
    """
    RETURN: the value in a form ANY language can read -- scalars as
            themselves, sequences as lists, mappings and objects as
            nested maps.

    A repr is NOT portable. A Python reader can squint at
    "[SubjectCell(subject='alpha', ...)]"; a Lua one cannot, and neither
    can any other, so a client could carry a comparison and never render
    one. Structure is carried AS STRUCTURE.

    NOTHING IS INTERPRETED. No field is renamed, invented or flattened:
    whatever compare names its parts is what a client reads. Depth is
    capped, since a cycle would otherwise carry forever.
    """
    #  Enum FIRST: an IntEnum is also an int, and would otherwise arrive
    #  as '1' where a client wants 'STRING'.
    if isinstance(value, Enum): return value.name      # a LEAF, by its name
    if isinstance(value, (str, int, float, bool, type(None))): return value
    if depth >= 6: return repr(value)
    if isinstance(value, (list, tuple, set)):
        return [_carry(v, depth + 1) for v in value]
    if isinstance(value, dict):
        return {str(k): _carry(v, depth + 1) for k, v in value.items()}

    name_list = getattr(value, "__dataclass_fields__", None) \
                or getattr(value, "_fields", None) \
                or getattr(value, "__slots__", None) \
                or (vars(value).keys() if hasattr(value, "__dict__") else None)
    if name_list:
        carried = {}
        for name in name_list:
            if name.startswith("_"): continue
            try:    carried[name] = _carry(getattr(value, name), depth + 1)
            except Exception:  pass       # a property that computes, and
        if carried: return carried        #   raises: not part of the message
    return repr(value)                    # a sentinel with nothing to read


class RemoteDisplay(DisplayAdapter):
    """A DRIVER for a client that speaks the protocol over a PIPE -- the
    RICH tier, and the reference implementation of it.

    DOWN goes out as one JSON message per line; UP comes back as one JSON
    envelope. The client may be written in any language: it dispatches on
    'kind', and it checks 'signature' before parsing anything.

    Transport-neutral by construction: this driver owns a pipe, and the
    next driver may own a socket without either knowing of the other.
    """

    def __init__(self, argv, resolve_f=True):
        self.argv       = list(argv)
        self.resolve_f  = resolve_f
        self._process   = None
        self.sent_count = 0

    async def open(self, subject_name):
        """RETURN: None. Launches the client and begins its session."""
        import asyncio as _asyncio
        self._process = await _asyncio.create_subprocess_exec(
            *self.argv,
            stdin=_asyncio.subprocess.PIPE,
            stdout=_asyncio.subprocess.PIPE)

    async def present(self, item):
        """RETURN: None. Sends one DOWN message, newline-framed."""
        import json as _json
        line = _json.dumps(down_message(item)) + "\n"
        self._process.stdin.write(line.encode("utf-8"))
        await self._process.stdin.drain()
        self.sent_count += 1

    async def resolve(self, subject_name, subject_text, nominal_text):
        """
        RETURN: Resolution, parsed from the client's UP envelope.
                None,       this driver was told not to merge.

        Raises ProtocolMismatch when the client answers under a signature
        this hub cannot parse -- checked before the message is read.

        STDIN STAYS OPEN. A REALIGN is answered with a fresh DOWN on this
        same pipe, so closing the client's input here would end the
        session after one round and make the loop impossible. 'close()'
        closes it, once, when the session is really over.
        """
        import json as _json
        if not self.resolve_f: return None

        self._process.stdin.write(
            (_json.dumps({"signature": PROTOCOL_SIGNATURE,
                          "kind":      "MaterialInst",
                          "field_db":  {"subject": subject_text,
                                        "nominal": nominal_text}}) + "\n")
            .encode("utf-8"))
        await self._process.stdin.drain()

        raw = await self._process.stdout.readline()
        if not raw.strip(): return Resolution(intent=E_Intent.CANCEL)
        return resolution_of(_json.loads(raw.decode("utf-8")))

    async def close(self):
        """RETURN: None. Waits for the client, whatever it did."""
        if self._process is None: return
        if self._process.stdin is not None and \
           not self._process.stdin.is_closing():
            self._process.stdin.close()
        await self._process.wait()


def driver_for(target, **argument_db):
    """
    RETURN: DisplayAdapter, the driver that carries a session to 'target'.

    THE ONLY PLACE a target becomes a driver. A caller names an outcome
    -- where to show this -- and never constructs a driver itself, so
    adding a tier touches this function and nothing else.

    Raises ValueError for a target with no driver: guessing one would
    send a session somewhere nobody asked for.
    """
    if target is E_DisplayTarget.NONE:
        return NullDisplay()
    if target is E_DisplayTarget.CONSOLE:
        return CollectingDisplay()
    if target is E_DisplayTarget.TUI:
        #  Imported lazily: tui.py imports THIS module for the adapter
        #  interface, and a driver is compare-side rendering machinery a
        #  verdict-only run never needs loaded.
        from vut.engine.test_run.tui import TuiDisplay
        return TuiDisplay(**argument_db)
    if target is E_DisplayTarget.RICH:
        argv = argument_db.get("argv")
        if not argv:
            raise ValueError("E_DisplayTarget.RICH needs the client's "
                             "'argv' -- there is no default client")
        return RemoteDisplay(argv, resolve_f=argument_db.get("resolve_f", True))
    raise ValueError("no driver for display target %r" % target)
