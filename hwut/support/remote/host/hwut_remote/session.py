"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE HUB -- Hub, the base of every hub, and LinkHub, the session
         over an agent's map: hello, reset, vector, read, write, contract,
         and the ladder (README 11, 18; PROTOCOL.txt 4, 5; MAP.txt).

    with hub:                    opens the link, says hello (PROTOCOL 4)
        hub.reset()              'w 3f 01': the UUT reset; then vectors
        hub.vector(stim)         'x <stim>' -> int, or TIMEOUT
    hub.flash(image, image_id)   the loader named by 'loader' (README 14)
    hub.reset_bench()            the bench reset (README 15)

A session is one choice. The writer never sees a token, a CRC, a byte order
or a recovery; a recovery is one '##' line through 'note'.
______________________________________________________________________________
"""
import random
import subprocess
import sys
import time

from .     import line as line_
from .link import DeviceAbsent, LinkError

MAGIC       = b"hwut"
HELLO_N     = 0x1a
A_RESET     = 0x3f
A_LAST      = 0x18
A_BUS       = 0x100
TOKEN_START = 0xff


class _Timeout:
    """Outcome 02: the UUT gave no done within 'timeout' -- data, a row.
    Formats as 'timeout' under any format spec."""

    def __format__(self, spec):
        """RETURN: str, 'timeout' whatever 'spec' asks."""
        return "timeout"

    def __repr__(self):
        """RETURN: str, 'TIMEOUT'."""
        return "TIMEOUT"

    __str__ = __repr__


TIMEOUT = _Timeout()


class HubError(Exception):
    """A failure of the session: the choice fails, its text a '##' line."""


class NoAgent(HubError):
    """No hello reply within 'boot'."""


class AgentRestarted(HubError):
    """The agent restarted since the session's reset."""


class AgentSilent(HubError):
    """The agent stopped answering: end of file, or three failures."""


class Refused(HubError):
    """'! unknown', '! syntax' or '! limit': the command did not act."""


class Expired(HubError):
    """Outcome 03: no done within 'timeout' ticks -- a failure."""


def absent(text):
    """
    RETURN: never. 'text' to stderr as the last line, then exit status 77:
            the infrastructure this case needs is absent (README 16).
    """
    sys.stdout.flush()
    sys.stderr.write("%s\n" % text)
    sys.stderr.flush()
    raise SystemExit(77)


class Hub:
    """The base of every hub: a context manager, the loader and the bench
    reset. A subclass gives '_open' and '_close'."""

    def __init__(self, values, note=None, transport=None):
        """RETURN: None. A hub over the checked 'values'; 'note' (str ->
        None) receives the '##' lines; the factory sets 'transport'."""
        self.transport = transport
        self.values    = dict(values)
        self.note      = note or (lambda text: None)
        self.image_id  = None
        self.image     = None
        self.failure_n = 3
        self.open_f    = False

    def expect(self, image_id=None, image=None, failures=3):
        """RETURN: Hub, self, with the image the session expects and the
        failures before 'silent' (create_hub's arguments)."""
        self.image_id  = image_id
        self.image     = image
        self.failure_n = failures
        return self

    def __enter__(self):
        """RETURN: Hub, self, opened; exit 77 where the device is absent."""
        try:
            self.open()
        except DeviceAbsent as error:
            absent("%s: %s" % (self.transport, error))
        return self

    def __exit__(self, *_):
        """RETURN: False. The hub closed; an exception passes on."""
        self.close()
        return False

    def open(self):
        """RETURN: None. The link opened and greeted."""
        self._open()
        self.open_f = True

    def close(self):
        """RETURN: None. The link closed; closing twice is harmless."""
        if self.open_f: self._close()
        self.open_f = False

    def _open(self):
        """RETURN: None. The subclass's opening."""
        raise NotImplementedError

    def _close(self):
        """RETURN: None. The subclass's closing."""
        raise NotImplementedError

    def flash(self, image, image_id):
        """
        RETURN: str, what happened, if 'image' runs on the target
                afterwards ('already on the board', 'nothing to flash');
                HubError, else; exit 77 where the device is absent.
        """
        from . import loader
        return loader.flash(self, image, image_id)

    def reset_bench(self, image=None):
        """
        RETURN: str, the bench reset done (README 15), with the link
                closed; the hub is closed afterwards.
        """
        from . import loader
        return loader.reset(self, image or self.image)


class LinkHub(Hub):
    """A Hub over an agent's map, through a Link (line, CRC, token and the
    ladder are LinkHub's)."""

    def __init__(self, link, values, note=None, transport=None):
        """RETURN: None. A hub over 'link' (a Link, not yet opened)."""
        Hub.__init__(self, values, note, transport)
        self.link         = link
        self.reader       = line_.Reader()
        self.pending      = []
        self.failure_run  = 0
        self.token        = random.randrange(16)
        self.agent_last   = TOKEN_START
        self.reset_f      = False
        self.sw = self.rw = None
        self.mode         = None
        self.clock        = None
        self.timeout      = None

    # ---------------------------------------------------------- opening ---
    def _open(self):
        """RETURN: None. The link opened, the hello answered and noted
        (PROTOCOL 4); NoAgent, HubError else."""
        self.reader  = line_.Reader()
        self.pending = []
        self.reset_f = False
        self.failure_run = 0
        self.link.open()
        try:
            self._hello()
        except BaseException:
            self.link.close()
            raise

    def _close(self):
        """RETURN: None."""
        self.link.close()

    def _hello(self):
        """RETURN: None. 'r 0 1a' answered within 'boot': identity, lengths
        and contract read, noted."""
        boot      = float(self.values["boot"])
        margin    = self._margin()
        self.link.send(b"\n")
        self.token = random.randrange(16)
        sent       = line_.encode(self.token, "r 0 %x" % HELLO_N)
        start      = time.monotonic()
        echo_n     = 0
        reply      = None
        while reply is None:
            self.link.send(sent)
            until = start + boot if not self.link.repeat_hello_f \
                    else min(start + boot, time.monotonic() + margin)
            try:
                reply, echo = self._await(self.token, until, echo_of=sent)
            except EOFError:
                raise NoAgent("no agent: the link ended")
            echo_n += echo
            if reply is None and time.monotonic() >= start + boot:
                raise NoAgent("no agent: link echoes" if echo_n
                              else "no agent within %s s" % boot)
            if reply is None and not self.link.repeat_hello_f:
                raise NoAgent("no agent within %s s" % boot)
        data = self._bytes(reply, "r 0 %x" % HELLO_N)
        if len(data) != HELLO_N or data[0:4] != MAGIC:
            raise NoAgent("no agent: the reply to the hello is no 'hwut' map")
        self._identity(data)

    def _identity(self, data):
        """RETURN: None. The hello's bytes read into the session, checked
        against the expected image, noted."""
        proto = int.from_bytes(data[4:8], "little")
        image = int.from_bytes(data[8:12], "little")
        if proto != 1: raise HubError("protocol %i" % proto)
        if self.image_id is not None and image != self.image_id:
            raise HubError("stale agent: image %08x, built %08x"
                           % (image, self.image_id))
        self.sw, self.rw  = data[0x0c], data[0x0d]
        self.mode         = data[0x0e]
        discarded_n       = data[0x0f]
        self.clock        = int.from_bytes(data[0x10:0x14], "little")
        self.timeout      = int.from_bytes(data[0x14:0x18], "little")
        self.agent_last   = data[0x18]
        self.note("agent: proto %i  image %08x  stim %i  report %i  %s"
                  % (proto, image, self.sw, self.rw, _hz(self.clock)))
        self.note("discarded %i bytes, %i lines"
                  % (self.reader.discarded_byte_n, discarded_n))

    # ------------------------------------------------------- the writer ---
    def reset(self):
        """RETURN: None. The UUT reset through the map ('w 3f 01'); vectors
        and writes are allowed from here."""
        self._require_open()
        status = self._command("w", "%x %s" % (A_RESET, "01"), wait_f=True)
        self.reset_f = True
        self._check_status(status[0])

    def vector(self, stim):
        """
        RETURN: int, the report (little-endian), if the UUT answered
                (outcome 01);
                TIMEOUT, on outcome 02 (no done within 'timeout' cycles);
                Expired, on outcome 03; HubError, else.
        """
        self._require_reset()
        data   = int(stim).to_bytes(self.sw, "little")
        reply  = self._command("x", line_.hex_bytes(data), wait_f=True)
        status = reply[0]
        self._check_status(status)
        outcome = status & 0x03
        if outcome == 0x01: return int.from_bytes(reply[1:], "little")
        if outcome == 0x02: return TIMEOUT
        if outcome == 0x03:
            self.note("outcome 03: no done within %i ticks" % self.timeout)
            raise Expired("expired: no done within %i ticks" % self.timeout)
        raise HubError("outcome 00 after 'x'")

    def read(self, address, n):
        """RETURN: bytes, the 'n' bytes of the map at 'address'; a read at
        the bus is followed by 'r 19 1' and checked for fresh."""
        self._require_open()
        data = self._command("r", "%x %x" % (address, n))
        if address >= A_BUS and self.reset_f:
            self._check_status(self._command("r", "19 1")[0])
        return data

    def write(self, address, data):
        """RETURN: None. 'data' (bytes) written at 'address'."""
        self._require_reset()
        status = self._command("w", "%x %s" % (address, line_.hex_bytes(data)),
                               wait_f=(address == A_RESET))
        self._check_status(status[0])

    def contract(self):
        """
        RETURN: str, the wait contract as the writer prints it, a row:
                'contract: sample 1 cycle after apply, timeout 10000000
                counts at 50 MHz' or 'contract: wait for done, ...'.
        """
        self._require_open()
        latency = self.mode >> 2
        if self.mode & 0x01:
            how = "sample %i cycle%s after apply" \
                  % (latency, "" if latency == 1 else "s")
        else:
            how = "wait for done"
        return "contract: %s, timeout %i counts at %s" \
               % (how, self.timeout, _hz(self.clock))

    # ------------------------------------------------------- the ladder ---
    def _command(self, verb, body=None, wait_f=False):
        """
        RETURN: bytes, the reply's bytes to 'verb body' -- after the ladder
                of PROTOCOL 5 where a line was lost;
                Refused, AgentRestarted, AgentSilent, HubError, else.
        """
        while True:
            token = self._next_token(verb)
            deadline = self._deadline(wait_f)
            try:
                text = verb if body is None else "%s %s" % (verb, body)
                self.link.send(line_.encode(token, text))
                reply, _ = self._await(token, time.monotonic() + deadline)
            except EOFError:
                self._fail(AgentSilent("agent silent: the link ended"))
            if reply is None:
                self.failure_run += 1
                if self.failure_run >= self.failure_n:
                    self._fail(AgentSilent("agent silent: %i failures in a "
                                           "row" % self.failure_run))
                if verb == "r":
                    self.note("recovered: no reply to 'r %s', resent" % body)
                    continue
                acted = self._reconcile(token, verb)
                if acted is None:
                    self.note("recovered: '%s' was lost, resent" % verb)
                    continue
                self.note("recovered: the reply to '%s' was lost; it acted"
                          % verb)
                self.agent_last = token
                return acted
            if reply.startswith("! "):
                word = reply[2:]
                if word == "busy":
                    self.failure_run += 1
                    self.note("busy: waited one deadline, resent")
                    if self.failure_run >= self.failure_n:
                        self._fail(AgentSilent("agent silent: %i failures in "
                                               "a row" % self.failure_run))
                    time.sleep(min(deadline, 60.0))
                    continue
                raise Refused("! %s: '%s%s'" % (word, verb,
                                                "" if body is None
                                                else " " + body))
            self.failure_run = 0           # a reply with the command's token
            data = self._bytes(reply, "%s %s" % (verb, body))
            if verb in ("w", "x"): self.agent_last = token
            return data

    def _reconcile(self, token, verb):
        """
        RETURN: bytes, the reply the lost one would have been, if the
                command acted ('last' = its token);
                None, if it did not ('last' = the previous last);
                AgentRestarted, else.
        """
        previous = self.agent_last
        data = self._command("r", "%x %x" % (A_LAST, 2 + self.rw))
        last, status = data[0], data[1]
        if last == token:
            self._check_status(status)
            return data[1:] if verb == "x" else data[1:2]
        if last == previous:
            return None
        self._fail(AgentRestarted("agent restarted: last %02x, expected %02x "
                                  "or %02x" % (last, token, previous)))

    def _check_status(self, status):
        """RETURN: None; AgentRestarted where 'fresh' is set after the
        session's reset."""
        if self.reset_f and status & 0x80:
            self._fail(AgentRestarted("agent restarted: fresh after the "
                                      "session's reset"))

    def _fail(self, error):
        """RETURN: never. The link closed, the bench reset, reopened and
        greeted; then 'error' raised: the choice fails."""
        self.note(str(error))
        try:
            self.reset_bench()
            self.open()
            self.note("bench reset; the agent answers again")
        except (HubError, LinkError, DeviceAbsent) as other:
            self.note("bench reset failed: %s" % other)
        raise error

    # ------------------------------------------------------ the wire ---
    def _next_token(self, verb):
        """RETURN: int, a token other than the previous one and, for 'w' and
        'x', other than the agent's 'last' (a duplicate never acts)."""
        token = (self.token + 1) % 16
        while token == self.token or (verb in ("w", "x")
                                      and token == self.agent_last):
            token = (token + 1) % 16
        self.token = token
        return token

    def _await(self, token, deadline, echo_of=None):
        """
        RETURN: (str | None, int), the body of the verified line with
                'token' before 'deadline', or None; and the echoes of
                'echo_of' seen. A verified line with another token is a
                late reply, noted and discarded.
                EOFError, at the link's end.
        """
        echo_n = 0
        while True:
            while self.pending:
                tok, body = self.pending.pop(0)
                if echo_of is not None and line_.encode(tok, body) == echo_of:
                    echo_n += 1
                    continue
                if tok == token and not body.startswith(("r ", "w ", "x ")):
                    return body, echo_n
                self.note("late reply %x discarded: %s" % (tok, body))
            data = self.link.recv(deadline)
            if not data and time.monotonic() >= deadline: return None, echo_n
            if self.link.datagram_f and data and not data.endswith(b"\n"):
                data += b"\n"
            self.pending.extend(self.reader.feed(data))
            if echo_of is not None:
                echo_n += sum(1 for raw in self.reader.noise_list
                              if raw == echo_of)
                self.reader.noise_list = []

    def _bytes(self, reply, command):
        """RETURN: bytes, the hex of 'reply'; HubError if it is none."""
        data = line_.parse_bytes(reply)
        if data is None:
            raise HubError("reply to '%s' is no bytes: %s" % (command, reply))
        return data

    def _deadline(self, wait_f):
        """RETURN: float, seconds: waits + line_time + link_margin
        (PROTOCOL 5)."""
        margin = self._margin()
        waits  = self.timeout / self.clock if wait_f and self.clock else 0.0
        baud   = self.values.get("baud")
        line_time = 2 * 80 * 10 / baud if baud else 0.0
        return waits + line_time + margin

    def _margin(self):
        """RETURN: float, the link margin in seconds (inf: virtual)."""
        return float(self.values["link_margin"])

    def _require_open(self):
        """RETURN: None; HubError unless the hub is open."""
        if not self.open_f: raise HubError("the hub is not open: 'with hub:'")

    def _require_reset(self):
        """RETURN: None; HubError unless this hub has reset."""
        self._require_open()
        if not self.reset_f:
            raise HubError("vector and write need hub.reset() first")


def _hz(clock):
    """RETURN: str, 'clock' in Hz as '50 MHz', '32768 Hz', ..."""
    for unit, scale in (("GHz", 10**9), ("MHz", 10**6), ("kHz", 10**3)):
        if clock >= scale and clock % scale == 0:
            return "%i %s" % (clock // scale, unit)
    return "%i Hz" % clock


def run_command(text):
    """RETURN: None. 'text' run by the shell; HubError where it fails."""
    status = subprocess.call(text, shell=True)
    if status != 0: raise HubError("'%s' exited %i" % (text, status))
