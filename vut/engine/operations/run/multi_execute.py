"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE
       THE MULTI-EXECUTOR -- many choices through ONE application call.

DESCRIPTION
       'MultiExecute' is to the execute role what a multi-builder is to
       the build role: ONE supervised call of the test application
       serves MANY choices. It exists only for an application whose
       configuration REGISTERS the capability ('interactive', a
       configuration key -- never probed): the app is launched once
       with '--interactive' and driven over its control port
       (hwut_runner, README-hwut_runner.txt).

       THE SCHEME OF OPERATION.

            MultiExecute (holds THE SESSION)
                |
                |  launch ONCE, under procsitter:
                |      argv(configuration) + '--interactive'
                |      cwd = test_directory, caps enforced
                |
                |  DOWN (app stdin):   run <choice> <sink-out> <sink-err>
                |                      quit           . . . at close()
                |  UP   (app stdout):  done <choice> <status>
                |                      fail <choice> <reason>
                |                      bye
                |
                |          .-------------------------------------.
                +--------> | provider(choice) -> ChoiceExecute   |
                           |   an I_ExecuteProvider: PARKS on    |
                           |   the choice's ticket, triggers     |
                           |   when the session says 'done',     |
                           |   reads the sinks, delivers         |
                           '-------------------------------------'
                                            |
                              Supply((raw_db, None), report)
                              raw_db = {stdout, stderr}, the sinks
                              cadence None: sinks have no arrival

       THE TICKET. 'submit(choice)' registers one future per choice and
       writes ONE 'run' line; it is idempotent -- a choice runs once
       per session, however many ask. The session's reader resolves the
       ticket on the matching 'done'/'fail' -- by TOKEN, so the
       "process" scheme of the app (done in COMPLETION order) is served
       by the same mechanism as the sequential one. A provider's
       'supply()' submits when nobody has, then parks on the ticket:
       standalone use and an orchestrator running ahead are the same
       machinery.

       THE SINKS are the transport of the two channel subjects. They
       live under the test directory in a session sub directory
       ('.hwut-session/'), are named RELATIVE on the wire (the app's
       cwd is the test directory; no machine-chosen absolute path
       crosses it), are read on 'done' and deleted -- the sub directory
       leaves with the session.

       WHAT A STATUS MEANS follows the classic run: the application
       exiting non-zero is BEHAVIOR, not provision failure -- the
       streams are delivered and compared, report OK. A NEGATIVE status
       is a terminating signal: delivered, report 'test-app-contained'.
       'fail <choice> <reason>' delivers nothing: product None, report
       'test-app-launch-failed' -- the command did not execute. A
       session that ends before a ticket resolves fails that ticket the
       same way, with the session's own record beside it.

       THE ATTRIBUTION (ruled). The record of the process that
       produced a result is PART of that result, in every mode. So
       EVERY choice's Supply carries the session's ProcsitterResult in
       its 'record_list' -- the same record for each, since the same
       one process produced them all.

       That record exists only once the session closed, so the session
       PRODUCES FIRST and is read afterwards: 'run(choice_list)' runs
       every choice and closes; the sinks hold the products meanwhile,
       which is what a file transport is for. 'supply()' on a session
       that has not produced runs it for that one choice. The sinks
       outlive 'close()' and leave with the visit ('discard()',
       'async with').

       CURRENT LAW OF THE FILE SUBJECTS: a session delivers the two
       CHANNEL subjects only. Output-file subjects share one 'OUT/'
       across the session's choices and would cross-pollute; a test
       with file subjects takes the classic one-call run
       (DISCUSSIONS todo-23).

       THE WIRE IS BLANK-SEPARATED (one command per line), so a choice
       name containing whitespace cannot travel it: refused at
       'submit', by name.
______________________________________________________________________________
"""
import asyncio
from   dataclasses import replace
import shutil
from   pathlib import Path

from   ..result                   import E_TestRunResult
from   .stage_execute             import read_declared_files
from   ...procsitter.procsitter   import Procsitter
from   ...procsitter.construction import Link, chain
from   .core                      import (Supply, STDOUT, STDERR,
                                          application_argv)
from   .provider                  import (I_ExecuteProvider,
                                          I_ProxyProvider,
                                          I_MultiProvider)


SESSION_DIRECTORY_NAME = ".hwut-session"


class MultiExecute(I_MultiProvider):
    """ONE interactive session of ONE test application, serving its
    choices through per-choice execute providers.

    Use as an async context manager, or 'start()'/'close()' by hand;
    'provider(choice)' hands out the pluggable I_ExecuteProvider. The
    session launches lazily upon the first need.
    """

    def __init__(self, configuration):
        """
        RETURN: MultiExecute, not yet launched.

        Raises AssertionError when the configuration does not register
        the 'interactive' capability: without it, driving choices over
        the control port makes no sense -- refused at the door.
        """
        assert configuration.interactive, \
               "MultiExecute requires a configuration that registers " \
               "'interactive'; '%s' does not" % configuration.source_file
        self.configuration = configuration
        self.record        = None    # the session's ProcsitterResult,
                                     # present after close()
        self._down         = None    # Link into the app's stdin
        self._up           = None    # reader of the app's stdout
        self._stderr       = None    # Link off the app's stderr
        self._task_tuple   = None
        self._reader_task  = None
        self._ticket_db    = {}      # token -> asyncio.Future
        self._started      = False
        self._closed       = False

    # -- the session ---------------------------------------------------
    async def start(self):
        """
        RETURN: None. Launches the ONE application call, supervised,
                and starts the UP reader. Idempotent.
        """
        if self._started: return
        self._started = True
        configuration = self.configuration
        self._session_directory().mkdir(parents=True, exist_ok=True)
        #  THE TERMINAL TOKEN (R-70, t-6): where a pype owns any
        #  choice's stdout, the SESSION application must not emit
        #  '<hwut-end>' -- per-choice suppression cannot exist on one
        #  process, so any pype silences the app for the whole
        #  session; the pype's '<eof>' provides, and the nominal
        #  (recorded through the same road) decides consistently.
        pype_owned_f = any("stdout" in c.canonicalisers
                           for c in configuration.choice_db.values()
                           if c is not None)
        caps = configuration.caps
        if pype_owned_f:
            caps = replace(caps, env={**(caps.env or {}),
                                      "HWUT_NO_TERMINAL": "1"})
        procsitter = Procsitter(caps,
                                work_dir=str(configuration.test_directory))
        self._down   = Link()
        self._stderr = Link()
        argv = application_argv(configuration, None) + ["--interactive"]
        c = chain([(procsitter, argv,
                    {"stderr_handler": self._stderr.feed})],
                  stdin_reader=self._down.reader)
        self._up          = c.tail.reader
        self._task_tuple  = c.task_tuple
        self._reader_task = asyncio.ensure_future(self._read_up())

    async def _read_up(self):
        """
        RETURN: None; returns at the UP channel's end.

        Resolves tickets by TOKEN on 'done'/'fail' -- completion order,
        not submission order, so the app's "process" scheme is served
        by the same reading as the sequential one. Lines matching no UP
        message are skipped (output written before the session).
        """
        while True:
            raw = await self._up.readline()
            if not raw: break
            fields = raw.decode("utf-8", errors="replace").split()
            match fields:
                case ["done", token, status] if _is_int(status):
                    self._resolve(token, int(status))
                case ["fail", token, *_]:
                    self._resolve(token, "fail")
                case ["bye"]:
                    break
                case _:
                    pass                       # pre-session line: skipped
        self._fail_leftovers()

    def _resolve(self, token, answer):
        """RETURN: None. Resolves the token's ticket; an unknown token
        is skipped -- the wire owes no answer it was never asked."""
        ticket = self._ticket_db.get(token)
        if ticket is not None and not ticket.done():
            ticket.set_result(answer)

    def _fail_leftovers(self):
        """RETURN: None. The session ended: every unresolved ticket is
        failed -- an absent answer is REPORTED, never invented."""
        for ticket in self._ticket_db.values():
            if not ticket.done():
                ticket.set_result("session-ended")

    async def close(self):
        """
        RETURN: ProcsitterResult, the session's attribution -- ONE
                record for the ONE call; also kept as '.record'.
                None, the session never launched.

        Sends 'quit', lets the app drain and say 'bye', awaits the
        supervised call's end, fails leftover tickets, removes the
        session sub directory. Idempotent.
        """
        if self._closed:      return self.record
        self._closed = True
        if not self._started: return None
        await self._down.feed(b"quit\n")
        self._down.close()
        record_list = await asyncio.gather(*self._task_tuple)
        self.record = record_list[0]
        await self._reader_task
        self._stderr.close()
        return self.record

    def discard(self):
        """RETURN: None. Removes the sink directory. Separate from
        'close': the sinks must OUTLIVE the quit, since deliveries are
        read after the session's record exists (ruling C)."""
        shutil.rmtree(self._session_directory(), ignore_errors=True)

    async def run(self, choice_name_list):
        """
        RETURN: ProcsitterResult, the session's attribution -- the
                session ran every named choice AND CLOSED, so every
                delivery afterwards can carry the record of the process
                that produced it.

        THE PRODUCTION PHASE. The sinks hold the products meanwhile:
        that is what a file transport is for.
        """
        await self.start()
        ticket_list = [self.submit(c) for c in choice_name_list]
        if ticket_list: await asyncio.wait(ticket_list)
        return await self.close()

    async def __aexit__(self, *_):
        """RETURN: False, exceptions propagate. Closes, then discards
        the sinks -- the transport leaves with the VISIT, after the
        deliveries were read."""
        await self.close()
        self.discard()
        return False

    # -- the tickets ---------------------------------------------------
    def submit(self, choice_name):
        """
        RETURN: asyncio.Future, the choice's ticket: an int status, or
                'fail' / 'session-ended'. IDEMPOTENT -- a choice runs
                once per session, however many ask.

        Raises AssertionError for a choice name the blank-separated
        wire cannot carry.
        """
        token = self._token(choice_name)
        if token in self._ticket_db: return self._ticket_db[token]
        assert not self._closed, \
               "the session is closed: choice %r cannot be produced by " \
               "it" % choice_name
        assert not any(x.isspace() for x in token), \
               "the wire is blank-separated: choice %r cannot travel it" \
               % choice_name
        ticket = asyncio.get_event_loop().create_future()
        self._ticket_db[token] = ticket
        if self._reader_task is not None and self._reader_task.done():
            #  The session already ENDED: an absent answer is REPORTED,
            #  never awaited forever -- the leftover law, applied to a
            #  ticket that arrives after the wire fell silent.
            ticket.set_result("session-ended")
            return ticket
        out, err = self._sink_pair(token)
        asyncio.ensure_future(self._down.feed(
            ("run %s %s %s\n" % (token, out, err)).encode()))
        return ticket

    def provider(self, choice_name):
        """RETURN: I_ExecuteProvider, this choice's proxy into the
        session -- pluggable wherever a local StageExecute is."""
        return ChoiceExecute(self, choice_name)

    # -- the places ----------------------------------------------------
    def _session_directory(self):
        """RETURN: Path, the session's sink directory, absolute."""
        return Path(self.configuration.test_directory) \
               / SESSION_DIRECTORY_NAME

    def _token(self, choice_name):
        """RETURN: str, the choice's token on the wire: its name, or
        '-' for the choice-less test."""
        return "-" if choice_name is None else str(choice_name)

    def _sink_pair(self, token):
        """RETURN: (str, str), the RELATIVE sink paths of that token --
        relative, so no machine-chosen absolute path crosses the wire;
        the app's working directory is the test directory."""
        stem = "no-choice" if token == "-" else token
        base = "%s/%s" % (SESSION_DIRECTORY_NAME, stem)
        return base + ".out", base + ".err"

    def _read_sinks(self, token):
        """
        RETURN: dict, {stdout, stderr} -- the sinks' texts; the files
                are deleted after reading, the transport leaves no
                residue.
        """
        out_rel, err_rel = self._sink_pair(token)
        directory = Path(self.configuration.test_directory)
        raw_db = {}
        for name, rel in ((STDOUT, out_rel), (STDERR, err_rel)):
            path = directory / rel
            raw_db[name] = path.read_text(encoding="utf-8",
                                          errors="replace")
            path.unlink()
        return raw_db


class ChoiceExecute(I_ProxyProvider, I_ExecuteProvider):
    """ONE choice's proxy into the session: acts as if it executed,
    parks on the ticket, triggers when its multi says 'done'. Behind
    the interface, indistinguishable from a local StageExecute --
    which is the point."""

    def __init__(self, multi, choice_name):
        self._multi      = multi
        self.choice_name = choice_name

    @property
    def multi(self):
        """RETURN: MultiExecute, the session this proxy triggers on."""
        return self._multi

    async def supply(self, stop_event=None):
        """
        RETURN: Supply, product = (raw_db, None): the two channel
                subjects read from the sinks; the cadence is None --
                a sink has no arrival, and an unmeasured cadence is
                absent, never empty. Product None when the command did
                not execute or the session ended first; the report
                token speaks. A NON-ZERO status DELIVERS: the exit of
                the application is behavior, not provision failure.
        """
        session = self.multi
        if not session._started:
            #  THE ONE-SHOT MODE: nobody holds the session -- run it
            #  for this one choice and spend it (the standalone law).
            await session.run([self.choice_name])
            ticket = session.submit(self.choice_name)
            answer = ticket.result()
        else:
            #  THE HELD MODE: an orchestrator opened the session and
            #  will close it; this choice submits its ticket and
            #  WAITS -- the session stays standing for its siblings.
            ticket = session.submit(self.choice_name)
            answer = await ticket
        record = (session.record,) if session.record is not None else ()
        match answer:
            case "fail":
                #  The application refused the choice, by name.
                return Supply(
                        product     = None,
                        report      = E_TestRunResult.TEST_APP_LAUNCH_FAILED,
                        record_list = record)
            case "session-ended":
                #  The wire fell silent before this ticket was served.
                return Supply(
                        product     = None,
                        report      = E_TestRunResult.TEST_APP_CONTAINED,
                        record_list = record)
            case _:
                raw_db  = session._read_sinks(
                                    session._token(self.choice_name))
                #  THE CHOICE'S declared files, read NOW -- after this
                #  choice's 'done', which the token precedes; the
                #  process lives on for its siblings, so the process
                #  end can never be the reading point here
                #  (todo-1-judgement-timing). Read-and-remove PER
                #  CHOICE: B never reads A's leftover.
                missing = read_declared_files(session.configuration,
                                              self.choice_name, raw_db)
                report = E_TestRunResult.OK if answer >= 0 \
                         else E_TestRunResult.TEST_APP_CONTAINED
                if report is E_TestRunResult.OK and missing is not None:
                    #  Containment speaks first: a contained run
                    #  explains a missing file better than the file's
                    #  absence does.
                    report = missing
                return Supply(product     = (raw_db, None),
                              report      = report,
                              record_list = record)


def _is_int(text):
    """RETURN: True, 'text' parses as an int (sign admitted)."""
    try:
        int(text)
        return True
    except ValueError:
        return False
