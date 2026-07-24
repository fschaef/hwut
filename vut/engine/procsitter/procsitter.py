"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE
       THE SUPERVISED SYSTEM CALL -- platform-independent containment
       of unintentional misbehavior of trusted subprocesses, with
       attribution.

DESCRIPTION
       Every subprocess HWUT launches goes through the procsitter: test
       applications, build and helper tools ('make', 'scp', scripts),
       and pype filters. It replaces direct 'subprocess' usage. The
       procsitter is THE GROUND; everything else -- pipelines, the judged
       test -- is lightweight composition on top (see judged.py).

       The procsitter protects the RUN from the subprocess's BUGS: disk
       flooding, fork bombs, runaway memory growth, endless loops,
       hangs. A violation is reported as the failure of the call that
       caused it, with the exhausted resource named (ProcsitterResult).

       It does NOT defend against malice, does not isolate, and does
       not pin execution environments. Those concerns are resolved
       independently at the outer boundary (container, VM, dedicated
       runner) by the administrator. See SPEC-procsitter.txt.

       Dependencies: stdlib + psutil. Degradable: without psutil the
       memory and pid-count caps cannot be enforced and are REPORTED
       in ProcsitterResult.unenforced -- never silently ignored. On
       platforms without the 'resource' module (Windows) the CPU-time
       and file-size caps are likewise reported as unenforced; the
       wall-clock cap works everywhere.

MECHANISMS
       preexec hook     os.setsid (own process group) + rlimits for
                        CPU time and file size.
       watchdog task    polls beside the stream readers: enforces
                        wall-clock and RSS caps over the whole process
                        group, counts group members against max_pids
                        (THE process-count cap -- per-call, own group),
                        records peaks for attribution, and reaps
                        stragglers that outlive the test process.
       kill ladder      SIGTERM -> grace -> SIGKILL, applied to the
                        process GROUP; post-mortem sweep of any
                        observed descendant that escaped the group.
       anti-leak        cleanup is CANCELLATION-PROOF: an interrupted
                        run (Ctrl-C, logout) still kills and sweeps its
                        group; a module-level atexit backstop killpg's
                        any group a dying harness left behind.

       RLIMIT_AS is deliberately NOT used: it breaks interpreters that
       reserve large virtual address spaces. Memory containment is
       watchdog-based (RSS) -- adequate against accidents; adversaries
       are out of scope.

       RLIMIT_NPROC is deliberately NOT used: it caps processes per
       REAL USER ID -- system-wide, not per-call. Derived from a
       point-in-time snapshot it STARVES a legitimate build the moment
       unrelated processes of the same user push the global count past
       the snapshot (a busy desktop: build fork -> EAGAIN, "Resource
       temporarily unavailable"). The per-call process-count cap is the
       watchdog's group-member count, which is correctly scoped.
______________________________________________________________________________
"""
import asyncio
import atexit
import os
import shutil
import signal
import time
from   collections import deque
from   contextlib  import suppress
from   dataclasses import dataclass
from   enum        import Enum, auto
from   pathlib     import Path
from   typing      import Awaitable, Callable, Optional, Sequence

try:                import resource
except ImportError: resource = None      # e.g. Windows

try:                import psutil
except ImportError: psutil = None        # degradable, reported


_WATCHDOG_PERIOD_SEC  = 0.25   # poll period: RSS, pid count, wall clock
_DISK_POLL_EVERY      = 4      # disk checked every Nth tick (~1 s): a
                               # directory walk is heavier than a poll
_KILL_GRACE_SEC       = 2.0    # SIGTERM -> SIGKILL escalation delay
_STRAGGLER_GRACE_SEC  = 1.0    # children outliving the exited test process

_STDERR_TAIL_LINES    = 100    # stderr kept as its LAST N lines (the field
                               # name 'stderr_last_100_lines' states N)
_STDERR_LINE_MAX      = 4096   # one line trimmed to its tail: a line
                               # without newlines cannot flood memory

_SIGKILL              = getattr(signal, "SIGKILL", signal.SIGTERM)

# THE ANTI-LEAK BACKSTOP. Every live supervised call registers its
# process-group id (== the child pid: it setsid'd) here, and clears it
# on cleanup. A child that setsid'd into its own session would NOT die
# with the harness -- so if the harness exits with groups still live
# (an unhandled exception, sys.exit, an interpreter teardown), this
# atexit hook killpg's them. It cannot fire on SIGKILL of the harness
# (no process can); that residue is the outer boundary's concern.
_ACTIVE_GROUP_PIDS: set = set()


def _reap_active_groups():
    """
    RETURN: None. Best-effort SIGKILL of every still-registered process
            group -- the harness is exiting; nothing else would reap a
            setsid'd child.
    """
    if os.name != "posix":
        return
    for pid in list(_ACTIVE_GROUP_PIDS):
        with suppress(ProcessLookupError, PermissionError, OSError):
            os.killpg(pid, _SIGKILL)
    _ACTIVE_GROUP_PIDS.clear()


atexit.register(_reap_active_groups)


class Link:
    """RETURN: --. THE DIRECTED EDGE of the byte world: it carries a
                   stream from a PRODUCTION port to a CONTROL port.

    THE TWO AXES. Every component spans the same two orthogonal
    directions:

        PRODUCTION  what flows OUT   (stdout; stderr is a second,
                                      diagnostic production channel)
        CONTROL     what flows IN    (stdin: the component obeys it)

    A Link connects one production to one control: its '.feed' is
    given as a producer's 'stdout_handler' (or 'stderr_handler'); its
    '.reader' is given as a consumer's 'stdin_reader'. '.close()'
    propagates end-of-stream. The law of the axes: production may be
    LISTENED to by many ('tee', below -- consumers add); a control
    port obeys ONE voice (byte streams do not merge
    deterministically).

    Every process on a wired graph runs in its OWN procsitter: own
    caps, own attribution -- supervised at every link.
    """
    def __init__(self):
        self.reader = asyncio.StreamReader()

    async def feed(self, data: bytes):
        """RETURN: None. Upstream stdout handler: pass one chunk on."""
        self.reader.feed_data(data)

    def close(self):
        """RETURN: None. Upstream ended: downstream sees EOF."""
        with suppress(Exception):
            self.reader.feed_eof()


def tee(*consumer_list):
    """
    RETURN: async handler, feeding every consumer in 'consumer_list'
            with each chunk -- THE CONSUMER SUM.

    Fan-out is NOT a building block: a consumer is a plain async
    function, and functions ADD. 'tee(judge_link.feed, observer.feed)'
    is the sum of two consumers -- anyone may LISTEN to a production
    port. (The reverse does not exist: two productions cannot merge
    into one control port deterministically -- ONE VOICE COMMANDS.)
    """
    async def handler(data: bytes):
        for consume in consumer_list:
            await consume(data)
    return handler


# ---------------------------------------------------------------------------
# THE WIRING IDIOMS -- everything above the two building blocks is
# composition; no further class is needed.
#
# CHAIN (a pipeline A | B), with THE THREE RULES every chain obeys:
#   (1) EOF ONWARD: when a stage ends, close its outgoing Link
#       ('finally: link.close()') -- downstream sees end-of-stream.
#   (2) STOP ON EARLY DEATH: a stage that ends while an UPSTREAM stage
#       still runs sets the shared stop_event -- SIGPIPE semantics,
#       supervised; this is also what BOUNDS MEMORY (an in-memory
#       'feed' never blocks; without the rule an upstream would fill
#       a dead chain's buffer without limit).
#   (3) EVERY STAGE ACCOUNTED: gather ALL stage tasks; one
#       ProcsitterResult per stage, nothing disappears.
#
#     stop = asyncio.Event()
#     link = Link()
#     async def stage_a():
#         try:     return await a.run(argv_a, stdout_handler=link.feed,
#                                     stop_event=stop)
#         finally: link.close()                              # rule 1
#     async def stage_b():
#         try:     return await b.run(argv_b, stdin_reader=link.reader,
#                                     stdout_handler=consume,
#                                     stop_event=stop)
#         finally:
#             if not task_a.done(): stop.set()               # rule 2
#     record_a, record_b = await asyncio.gather(stage_a(), stage_b())
#                                                            # rule 3
#
# MAN IN THE MIDDLE (controller C rides subject A, consumer B keeps
# listening undisturbed): production is TEE'D, control is answered --
#
#     to_b, to_c, back = Link(), Link(), Link()   # B and C listen; C answers
#     A.run(argv, stdout_handler=tee(to_b.feed, to_c.feed),
#           stdin_reader=back.reader)             # finally: to_b/to_c.close()
#     C.run(ctrl_argv, stdin_reader=to_c.reader,
#           stdout_handler=back.feed)             # finally: back.close()
#     B consumes to_b.reader (a judge, a pype link, a log)
#
# A dialogue where both ends wait is an accident like any other: the
# wall clocks contain it. A supervised answerer must be UNBUFFERED
# (e.g. 'python3 -u') -- a buffered answer never arrives.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ChainRun:
    """RETURN: --. PLAIN DATA handed back by 'launch_chain()': the
                   chain's production end ('.tail', a Link), the shared
                   stop_event, and ONE TASK PER STAGE. No behavior --
                   the chain's rules live in 'launch_chain'; the data
                   is dumb:

        records  = await asyncio.gather(*chain.task_tuple)
        running  = any(not t.done() for t in chain.task_tuple)
        stop     = chain.stop_event.set()
    """
    tail:       "Link"
    stop_event: "asyncio.Event"
    task_tuple: tuple


def launch_chain(stage_list, stop_event=None, stdin_reader=None):
    """
    RETURN: ChainRun, the LAUNCHED chain: every stage runs; the last
            stage's production feeds '.tail'.

    THE POLICY FUNCTION of the chain idiom -- the three rules, encoded
    once (see the idiom block above): (1) EOF onward -- a stage that
    ends closes its outgoing Link; (2) stop on early death -- a stage
    ending while an UPSTREAM stage still runs sets the shared
    stop_event (SIGPIPE semantics, supervised; bounds the in-memory
    buffers); (3) every stage accounted -- one task per stage, gather
    them for the records.

    'stage_list' entries are (procsitter, argv) or (procsitter, argv,
    extra_run_kwargs) -- the extra kwargs go verbatim into that
    stage's 'run()' (e.g. {'stderr_handler': err_link.feed} to wire a
    stage's diagnostic production). ONE exception: a 'stdout_handler'
    in the extra kwargs is not a replacement but a LISTENER -- it is
    TEE'D with the chain edge, so the stage's production reaches both
    the next stage AND the listener (a log tap, a mirror); anyone may
    LISTEN to a production, the pipeline still flows. 'stdin_reader'
    feeds the FIRST stage's control port (recorded input, or a
    dialogue's back edge).
    """
    stop      = stop_event if stop_event is not None else asyncio.Event()
    tail      = Link()
    task_list = []
    last_i    = len(stage_list) - 1
    upstream  = stdin_reader
    for i, stage in enumerate(stage_list):
        procsitter, argv = stage[0], stage[1]
        extra    = dict(stage[2]) if len(stage) > 2 else {}
        listener = extra.pop("stdout_handler", None)   # a production tap
        out_link = tail if i == last_i else Link()
        # chain edge FIRST: a chunk reaches the next stage before the
        # listener runs, so a failing tap (e.g. an unwritable log) never
        # starves the pipeline of that chunk -- it surfaces afterwards
        # as a loud harness fault, the chain already fed.
        handler  = out_link.feed if listener is None \
                   else tee(out_link.feed, listener)

        async def run_stage(ps=procsitter, av=argv, up=upstream,
                            out=out_link, idx=i, kw=extra, h=handler):
            try:
                return await ps.run(av, stdin_reader=up,
                                    stdout_handler=h,
                                    stop_event=stop, **kw)
            finally:
                out.close()                                   # rule 1
                if any(not t.done() for t in task_list[:idx]):
                    stop.set()                                # rule 2

        task_list.append(asyncio.create_task(run_stage()))
        upstream = out_link.reader
    return ChainRun(tail=tail, stop_event=stop,
                    task_tuple=tuple(task_list))               # rule 3


class E_Containment(Enum):
    """How the supervised call ended. THE PREFIX IS THE VERDICT: 'OK_'
    is the one success (ran to its own end, exit 0); every 'FAIL_' is a
    way it went wrong -- so success is readable from the containment
    alone, no separate flag.
    """
    OK_COMPLETED             = auto()   # exited by itself, exit code 0
    FAIL_COMPLETED           = auto()   # exited by itself, NONZERO code
                                        # (incl. death by signal, e.g.
                                        # SIGSEGV -> negative exit_code)
    FAIL_WALL_CLOCK_EXCEEDED = auto()   # watchdog: max_wall_clock_sec
    FAIL_CPU_TIME_EXCEEDED   = auto()   # RLIMIT_CPU (SIGXCPU)
    FAIL_MEMORY_EXCEEDED     = auto()   # watchdog: group RSS over cap
    FAIL_FILE_SIZE_EXCEEDED  = auto()   # RLIMIT_FSIZE (SIGXFSZ death).
                                        # NOTE: an app that ignores
                                        # SIGXFSZ -- CPython does -- gets
                                        # EFBIG from write() and fails by
                                        # its own exception: the cap
                                        # still holds, but the run
                                        # reports FAIL_COMPLETED with the
                                        # app's exit code.
    FAIL_PIDS_EXCEEDED       = auto()   # watchdog: group members over cap
    FAIL_DISK_USAGE_EXCEEDED = auto()   # watchdog: allocated bytes under
                                        # the work dir over max_disk_mb --
                                        # catches the many-files loop that
                                        # RLIMIT_FSIZE (per file) cannot
    FAIL_DISK_SPACE_LOW      = auto()   # watchdog: free space of the work
                                        # dir's filesystem fell below
                                        # min_free_disk_mb WHILE this call
                                        # ran -- terminated to keep the
                                        # OPERATING SYSTEM operable; the
                                        # shortage is not proof that THIS
                                        # call caused it
    FAIL_STOPPED             = auto()   # external stop_event
    FAIL_LAUNCH              = auto()   # command not found / not executable


@dataclass
class ProcsitterConfig:
    """THE PER-CALL CONTRACT: every field is a CAP the procsitter
    ENFORCES. A call's ENVIRONMENTAL needs -- network reach, bound
    ports, writable paths beyond the work dir -- are NOT here: ensuring
    them is the ORCHESTRATOR's job (it owns the environment), ABOVE
    this level. The procsitter neither records nor enforces them.
    """
    max_wall_clock_sec: float = 300.0
    max_cpu_time_sec:   int   = 300
    max_memory_mb:      int   = 512     # watchdog RSS, whole process group
    max_pids:           int   = 32
    max_file_size_mb:   int   = 10      # PER FILE (RLIMIT_FSIZE)
    max_disk_mb:        int   = 100     # TOTAL allocation under work_dir
                                        # (watchdog walk, st_blocks): the
                                        # many-files loop cap
    min_free_disk_mb:   int   = 128     # free-space FLOOR of work_dir's
                                        # filesystem: below it the call is
                                        # terminated so the OS stays
                                        # operable, whoever caused the
                                        # shortage


@dataclass
class ProcsitterResult:
    """THE ATTRIBUTION RECORD of one procsittered execution."""
    containment:    E_Containment        # THE VERDICT: OK_ vs FAIL_
    exit_code:      Optional[int]        # set for OK_/FAIL_COMPLETED;
                                         # None when the procsitter ended it
    wall_clock_sec: float
    cpu_time_sec:   Optional[float]      # None if not measurable
    peak_memory_mb: Optional[float]      # None without psutil
    unenforced:     tuple[str, ...]      # caps the platform cannot enforce
    stderr_last_100_lines: str = ""      # last 100 lines of stderr,
                                         # captured when NO stderr_handler
                                         # was given -- the WHY for the
                                         # report (a nonzero exit without
                                         # it is a riddle); bounded by
                                         # LINE COUNT, so it informs
                                         # without risking a flood; "" when
                                         # a handler consumed the channel
    peak_pids:      Optional[int] = None # peak process-group member count
                                         # observed (None without psutil);
                                         # the WHY beside FAIL_PIDS_EXCEEDED
    peak_disk_mb:   Optional[float] = None
                                         # peak allocation observed under
                                         # the work dir (watchdog walk);
                                         # the WHY beside
                                         # FAIL_DISK_USAGE_EXCEEDED
                                         #
                                         # SUCCESS is 'containment is
                                         # E_Containment.OK_COMPLETED' --
                                         # no separate '.ok' flag (the
                                         # prefix already says it).


class _RunState:
    """Shared mutable state between run(), watchdog, and stop watcher."""
    __slots__ = ("cause", "peak_memory_mb", "peak_pids", "peak_disk_mb",
                 "cpu_time_sec", "descendants")

    def __init__(self):
        self.cause          = None    # first containment cause wins
        self.peak_memory_mb = None
        self.peak_pids      = None
        self.peak_disk_mb   = None
        self.cpu_time_sec   = None
        self.descendants    = {}      # pid -> create_time, ever observed

    def set_cause(self, cause):
        """
        RETURN: True,  cause was recorded (first one wins).
                False, a cause was already present.
        """
        if self.cause is None:
            self.cause = cause
            return True
        return False


class Procsitter:
    def __init__(self, config: ProcsitterConfig, work_dir: str):
        self.config   = config
        self.work_dir = Path(work_dir).resolve()

    # ------------------------------------------------------------------ API

    async def run(self,
                  command:        Sequence[str],
                  stdout_handler: None | Callable[[bytes], Awaitable[None]] = None,
                  stderr_handler: None | Callable[[bytes], Awaitable[None]] = None,
                  stdin_reader:   None | asyncio.StreamReader = None,
                  stop_event:     None | asyncio.Event = None) -> ProcsitterResult:
        """
        RETURN: ProcsitterResult, the attribution record of the completed (or
                contained) run: what ended it, exit code, wall clock, cpu
                time, peak memory, and any caps the platform could not
                enforce.

        'command' is the argv SEQUENCE -- [program, arg, ...] -- executed
        DIRECTLY, no shell: nothing to quote or escape, a path with
        spaces is simply one element.

        Handlers, if given, receive output
        chunks as they arrive; otherwise the channels are drained. Never
        raises on TEST misbehavior -- misbehavior is a RESULT, not an
        exception. Raises only on harness-level faults (a handler raising,
        bad configuration).
        """
        # A bare str is iterable -- it would spread into single CHARACTERS
        # and fail cryptically (program 'c', 'm', ...). Catch the mistake
        # loudly: 'command' is the argv list, e.g. ["make", "-j4", "all"].
        assert not isinstance(command, (str, bytes)), \
               "command must be an argv sequence, e.g. ['make', 'all'], " \
               "not a string"

        state              = _RunState()
        preexec, unenforced = self._make_preexec()
        rusage_before      = self._rusage_children()
        t0                 = time.monotonic()

        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdin  = asyncio.subprocess.PIPE,
                stdout = asyncio.subprocess.PIPE,
                stderr = asyncio.subprocess.PIPE,
                cwd    = self.work_dir,
                **self._spawn_kwargs(preexec))
        except (FileNotFoundError, PermissionError, NotADirectoryError):
            return ProcsitterResult(E_Containment.FAIL_LAUNCH, None,
                                 time.monotonic() - t0, None, None,
                                 unenforced)
        except OSError:
            # e.g. EAGAIN ("Resource temporarily unavailable"): the
            # per-user process table is full -- the SYSTEM is out of
            # processes, not a fault of THIS call. A clean, attributed
            # result, never a raw traceback out of the harness.
            return ProcsitterResult(E_Containment.FAIL_LAUNCH, None,
                                 time.monotonic() - t0, None, None,
                                 unenforced)

        # Register the group for the anti-leak backstop (POSIX: the child
        # setsid'd, so its group id equals its pid).
        if os.name == "posix":
            _ACTIVE_GROUP_PIDS.add(process.pid)

        # Without a caller handler, stderr is CAPTURED (last 100 lines)
        # instead of blindly drained: a nonzero exit without its stderr
        # is a riddle; it lands in ProcsitterResult.stderr_last_100_lines.
        # The cap is by LINE COUNT -- informative, and a runaway process
        # cannot flood it. A pathological single line without newlines is
        # itself trimmed to its tail so it cannot flood memory either.
        stderr_lines   = deque(maxlen=_STDERR_TAIL_LINES)
        stderr_pending = bytearray()
        if stderr_handler is None:
            async def stderr_handler(data):
                stderr_pending.extend(data)
                while True:
                    i = stderr_pending.find(b"\n")
                    if i < 0:
                        if len(stderr_pending) > _STDERR_LINE_MAX:
                            del stderr_pending[:-_STDERR_LINE_MAX]
                        break
                    line, del_to = bytes(stderr_pending[:i + 1]), i + 1
                    del stderr_pending[:del_to]
                    stderr_lines.append(line[-_STDERR_LINE_MAX:])

        out_task  = asyncio.create_task(
            self._pump(process.stdout, stdout_handler))
        err_task  = asyncio.create_task(
            self._pump(process.stderr, stderr_handler))
        in_task   = asyncio.create_task(
            self._pump_stdin(process.stdin, stdin_reader))
        dog_task  = asyncio.create_task(
            self._watchdog(process, state, t0))
        stop_task = asyncio.create_task(
            self._watch_stop(process, state, stop_event))
        exit_task = asyncio.create_task(process.wait())

        harness_error = None
        cancelled     = False
        try:
            # Completes when (a) process exited AND both output pipes hit
            # EOF, or (b) a pump raised (harness fault in a handler).
            await asyncio.wait({exit_task, out_task, err_task},
                               return_when=asyncio.FIRST_EXCEPTION)
        except asyncio.CancelledError:
            cancelled = True          # interrupt: still clean up below
        finally:
            # THE ANTI-LEAK GUARANTEE. A run interrupted at ANY point still
            # kills its process group and sweeps -- a cancelled run must
            # NEVER orphan its children (they setsid into their own group,
            # so nobody else would reap them).
            all_tasks = (out_task, err_task, in_task, dog_task,
                         stop_task, exit_task)
            if cancelled:
                # Interrupted (Ctrl-C, logout): no graceful shutdown owed,
                # only a guarantee of no leak. Kill the group AND the
                # leader directly, SYNCHRONOUSLY -- no await can be stolen,
                # and the direct kill covers the pre-setsid window where
                # the group id does not yet exist.
                self._hard_kill(process)
            elif process.returncode is None:
                await self._kill_ladder(process)      # normal: be graceful
            for task in all_tasks:
                if not task.done(): task.cancel()
            results = []
            with suppress(asyncio.CancelledError, Exception):
                results = await asyncio.gather(*all_tasks,
                                               return_exceptions=True)
            harness_error = next(
                (r for r in results[:2]
                 if isinstance(r, Exception)
                 and not isinstance(r, asyncio.CancelledError)),
                None)
            with suppress(asyncio.CancelledError, Exception):
                await self._close_stdin_transport(process)
            self._sweep(state)                        # synchronous: always
            _ACTIVE_GROUP_PIDS.discard(process.pid)

        if cancelled:
            # Group is dead and swept; now honour the cancellation.
            raise asyncio.CancelledError
        if harness_error is not None:
            raise harness_error

        wall = time.monotonic() - t0
        cpu  = self._cpu_time(rusage_before, state)
        if stderr_pending:                     # the final unterminated line
            stderr_lines.append(bytes(stderr_pending)[-_STDERR_LINE_MAX:])
        stderr_text = b"".join(stderr_lines).decode("utf-8", errors="replace")
        return self._make_result(process.returncode, state, wall, cpu,
                                 unenforced, stderr_text)

    # ------------------------------------------------------- result shaping

    def _make_result(self, returncode, state, wall, cpu, unenforced,
                     stderr_last_100_lines):
        """
        RETURN: ProcsitterResult, the verdict derived from the recorded
                watchdog/stop cause first, else the death signal
                (SIGXCPU/SIGXFSZ -> rlimit containment), else the
                process's own exit: OK_COMPLETED (0) or FAIL_COMPLETED
                (nonzero, incl. death by signal).
        """
        if state.cause is not None:
            containment, exit_code = state.cause, None
        elif resource is not None and returncode == -signal.SIGXCPU:
            containment, exit_code = E_Containment.FAIL_CPU_TIME_EXCEEDED, None
        elif resource is not None and returncode == -signal.SIGXFSZ:
            containment, exit_code = E_Containment.FAIL_FILE_SIZE_EXCEEDED, None
        elif returncode == 0:
            containment, exit_code = E_Containment.OK_COMPLETED, 0
        else:
            containment, exit_code = E_Containment.FAIL_COMPLETED, returncode

        return ProcsitterResult(containment    = containment,
                             exit_code      = exit_code,
                             wall_clock_sec = wall,
                             cpu_time_sec   = cpu,
                             peak_memory_mb = state.peak_memory_mb,
                             unenforced     = unenforced,
                             stderr_last_100_lines = stderr_last_100_lines,
                             peak_pids      = state.peak_pids,
                             peak_disk_mb   = state.peak_disk_mb)

    def _cpu_time(self, rusage_before, state):
        """
        RETURN: float, cpu seconds attributed to the run: preferred source
                       is the getrusage(RUSAGE_CHILDREN) delta (exact for
                       the reaped child incl. its waited-for descendants);
                       fallback is the watchdog's last group sample.
                None,  if neither source is available.
        """
        if rusage_before is not None:
            after = self._rusage_children()
            delta = (after[0] - rusage_before[0]) \
                  + (after[1] - rusage_before[1])
            if delta >= 0.0:
                return delta
        return state.cpu_time_sec

    @staticmethod
    def _rusage_children():
        """
        RETURN: (float, float), user and system cpu time of reaped children.
                None,            if 'resource' is unavailable.
        """
        if resource is None: return None
        usage = resource.getrusage(resource.RUSAGE_CHILDREN)
        return usage.ru_utime, usage.ru_stime

    # ------------------------------------------------------------- spawning

    def _spawn_kwargs(self, preexec):
        """
        RETURN: dict, platform-appropriate spawn keywords: on POSIX a new
                      session (own process group) plus the rlimit preexec
                      hook; empty elsewhere.
        """
        if os.name != "posix":
            return {}
        kwargs = {"start_new_session": True}
        if preexec is not None:
            kwargs["preexec_fn"] = preexec
        return kwargs

    def _make_preexec(self):
        """
        RETURN: [0] callable, pre-exec hook applying rlimits in the child.
                    None,     if the 'resource' module is unavailable.
                [1] tuple[str, ...], names of caps the platform cannot
                    enforce (honest-reporting; surfaces in ProcsitterResult).
        """
        unenforced = []
        if psutil is None:
            # No watchdog: no RSS cap, and no process-count cap either
            # (max_pids is the watchdog's group-member count).
            unenforced += ["max_memory_mb", "max_pids"]
        if resource is None:
            unenforced += ["max_cpu_time_sec", "max_file_size_mb"]
            return None, tuple(unenforced)

        cpu_sec    = self.config.max_cpu_time_sec
        fsize_byte = self.config.max_file_size_mb * 1024 * 1024

        def preexec():
            # Child context, post-fork pre-exec: keep it minimal; a cap
            # the kernel refuses is skipped (kernel ceilings vary).
            # NOTE: RLIMIT_NPROC is NOT set here -- it is a per-REAL-USER
            # cap, not per-call, and starves legitimate builds on a busy
            # machine (module header). max_pids is the watchdog's job.
            with suppress(ValueError, OSError):
                resource.setrlimit(resource.RLIMIT_CPU,
                                   (cpu_sec, cpu_sec + 1))
            with suppress(ValueError, OSError):
                resource.setrlimit(resource.RLIMIT_FSIZE,
                                   (fsize_byte, fsize_byte))

        return preexec, tuple(unenforced)

    # ------------------------------------------------------------- watchdog

    async def _watchdog(self, process, state, t0):
        """
        RETURN: None.

        Enforces, at _WATCHDOG_PERIOD_SEC resolution:
          -- max_wall_clock_sec over the whole run,
          -- max_memory_mb as summed RSS over the process group,
          -- max_pids as the group member count,
        and, every _DISK_POLL_EVERY ticks (~1 s; stdlib, no psutil
        needed):
          -- max_disk_mb as allocated bytes under the work dir
             (st_blocks: sparse files count what they CLAIM),
          -- min_free_disk_mb as the free-space floor of the work
             dir's filesystem -- the call is terminated below it so
             the OPERATING SYSTEM stays operable, whoever caused the
             shortage.
        Records peaks and observed descendants for attribution and the
        post-mortem sweep, and reaps stragglers: descendants that outlive
        the exited test process beyond _STRAGGLER_GRACE_SEC.
        """
        main = None
        if psutil is not None:
            with suppress(Exception):
                main = psutil.Process(process.pid)
        exited_at = None
        tick      = 0

        while True:
            now = time.monotonic()

            if process.returncode is not None:
                # Test process is gone; only stragglers can remain.
                if exited_at is None: exited_at = now
                if not self._group_alive(process.pid):
                    return
                if now - exited_at >= _STRAGGLER_GRACE_SEC:
                    await self._kill_ladder(process)
                    return
            else:
                if now - t0 >= self.config.max_wall_clock_sec:
                    state.set_cause(E_Containment.FAIL_WALL_CLOCK_EXCEEDED)
                    await self._kill_ladder(process)
                    return
                if main is not None:
                    self._sample(main, state)
                    if state.peak_memory_mb is not None \
                       and state.peak_memory_mb > self.config.max_memory_mb \
                       and self._current_memory_mb(main) \
                           > self.config.max_memory_mb:
                        state.set_cause(E_Containment.FAIL_MEMORY_EXCEEDED)
                        await self._kill_ladder(process)
                        return
                    if state.peak_pids is not None \
                       and state.peak_pids > self.config.max_pids:
                        state.set_cause(E_Containment.FAIL_PIDS_EXCEEDED)
                        await self._kill_ladder(process)
                        return
                if tick % _DISK_POLL_EVERY == 0:
                    usage_mb = self._disk_usage_mb()
                    if usage_mb is not None:
                        state.peak_disk_mb = max(state.peak_disk_mb or 0.0,
                                                 usage_mb)
                        if usage_mb > self.config.max_disk_mb:
                            state.set_cause(
                                E_Containment.FAIL_DISK_USAGE_EXCEEDED)
                            await self._kill_ladder(process)
                            return
                    free_mb = self._disk_free_mb()
                    if free_mb is not None \
                       and free_mb < self.config.min_free_disk_mb:
                        state.set_cause(E_Containment.FAIL_DISK_SPACE_LOW)
                        await self._kill_ladder(process)
                        return

            tick += 1
            await asyncio.sleep(_WATCHDOG_PERIOD_SEC)

    def _sample(self, main, state):
        """
        RETURN: None. One watchdog sample over the process group: updates
                peak RSS (MB), peak member count, summed cpu time, and the
                descendant registry (pid -> create_time) for the sweep.
        """
        try:
            procs = [main] + main.children(recursive=True)
        except psutil.NoSuchProcess:
            return
        rss_byte = 0
        cpu_sec  = 0.0
        count    = 0
        for proc in procs:
            with suppress(psutil.NoSuchProcess, psutil.AccessDenied):
                with proc.oneshot():
                    rss_byte += proc.memory_info().rss
                    times     = proc.cpu_times()
                    cpu_sec  += times.user + times.system
                    state.descendants[proc.pid] = proc.create_time()
                    count += 1
        if count == 0: return
        rss_mb = rss_byte / (1024.0 * 1024.0)
        state.peak_memory_mb = max(state.peak_memory_mb or 0.0, rss_mb)
        state.peak_pids      = max(state.peak_pids or 0, count)
        state.cpu_time_sec   = max(state.cpu_time_sec or 0.0, cpu_sec)

    @staticmethod
    def _current_memory_mb(main):
        """
        RETURN: float, current (re-sampled) group RSS in MB -- confirms a
                       peak before a MEMORY_EXCEEDED kill, so a spike that
                       already receded does not kill.
        """
        rss_byte = 0
        with suppress(psutil.NoSuchProcess, psutil.AccessDenied):
            rss_byte += main.memory_info().rss
            for proc in main.children(recursive=True):
                with suppress(psutil.NoSuchProcess, psutil.AccessDenied):
                    rss_byte += proc.memory_info().rss
        return rss_byte / (1024.0 * 1024.0)

    def _disk_usage_mb(self):
        """
        RETURN: float, allocated megabytes under the work dir -- summed
                       st_blocks (actual disk claim; a sparse file
                       counts what it allocates, not what it
                       addresses). Platforms without st_blocks
                       (Windows) fall back to st_size.
                None,  if the work dir cannot be walked.
        """
        total_byte = 0
        try:
            stack = [str(self.work_dir)]
            while stack:
                path = stack.pop()
                with os.scandir(path) as entry_iter:
                    for entry in entry_iter:
                        with suppress(OSError):
                            st = entry.stat(follow_symlinks=False)
                            blocks = getattr(st, "st_blocks", None)
                            total_byte += (blocks * 512
                                           if blocks is not None
                                           else st.st_size)
                            if entry.is_dir(follow_symlinks=False):
                                stack.append(entry.path)
        except OSError:
            return None
        return total_byte / (1024.0 * 1024.0)

    def _disk_free_mb(self):
        """
        RETURN: float, free megabytes on the filesystem holding the
                       work dir (shutil.disk_usage: platform-
                       independent).
                None,  if not determinable.
        """
        try:
            return shutil.disk_usage(str(self.work_dir)).free \
                   / (1024.0 * 1024.0)
        except OSError:
            return None

    async def _watch_stop(self, process, state, stop_event):
        """
        RETURN: None. Waits on 'stop_event'; on set, records STOPPED and
                runs the kill ladder. Completes immediately if no event.
        """
        if stop_event is None: return
        await stop_event.wait()
        if process.returncode is None:
            state.set_cause(E_Containment.FAIL_STOPPED)
            await self._kill_ladder(process)

    # ------------------------------------------------------ kill discipline

    async def _kill_ladder(self, process):
        """
        RETURN: None. killpg(SIGTERM) -> grace -> killpg(SIGKILL); applied
                to the process GROUP so children die with the test.
        """
        self._signal_group(process, signal.SIGTERM)
        with suppress(asyncio.TimeoutError):
            await asyncio.wait_for(asyncio.shield(process.wait()),
                                   timeout=_KILL_GRACE_SEC)
        if process.returncode is None or self._group_alive(process.pid):
            self._signal_group(process, getattr(signal, "SIGKILL",
                                                signal.SIGTERM))
        with suppress(Exception):
            await process.wait()

    def _hard_kill(self, process):
        """
        RETURN: None. SYNCHRONOUS, unconditional group teardown for the
                interrupted path: SIGKILL the process GROUP and the leader
                DIRECTLY. Runs even if the leader was already reaped -- its
                group id stays valid while any child lives, so the group
                kill still reaps a surviving grandchild. The direct leader
                kill covers the window before the child setsid'd (its group
                id does not exist yet, so a group kill alone would miss it).
                No await -- a cancellation cannot steal this step, so an
                interrupted run can never leak its child.
        """
        self._signal_group(process, _SIGKILL)
        if os.name == "posix":
            with suppress(ProcessLookupError, PermissionError, OSError):
                os.kill(process.pid, _SIGKILL)

    @staticmethod
    def _signal_group(process, sig):
        """
        RETURN: None. Sends 'sig' to the process group on POSIX (group id
                equals the pid: the child called setsid); falls back to
                single-process terminate/kill elsewhere.
        """
        if os.name == "posix":
            with suppress(ProcessLookupError, PermissionError, OSError):
                os.killpg(process.pid, sig)
        else:
            with suppress(Exception):
                if sig == signal.SIGTERM: process.terminate()
                else:                     process.kill()

    @staticmethod
    def _group_alive(pid):
        """
        RETURN: True,  some member of the process group still exists.
                False, else (or not determinable on this platform).
        """
        if os.name != "posix": return False
        try:
            os.killpg(pid, 0)
            return True
        except (ProcessLookupError, PermissionError, OSError):
            return False

    def _sweep(self, state):
        """
        RETURN: None. Post-mortem: kills every observed descendant that
                still exists AND matches its recorded create_time (pid
                reuse guard). Catches group escapees (double setsid).
        """
        if psutil is None: return
        for pid, created in state.descendants.items():
            with suppress(psutil.NoSuchProcess, psutil.AccessDenied,
                          Exception):
                proc = psutil.Process(pid)
                if abs(proc.create_time() - created) < 1e-4:
                    proc.kill()

    # -------------------------------------------------------- I/O machinery
    # (ported from the previous implementation; battle-tested patterns)

    async def _pump(self, stream, handler):
        """
        RETURN: None. Reads 'stream' to EOF. Chunks go to 'handler' when
                given; otherwise they are discarded -- the stream is
                ALWAYS consumed, a full OS pipe would block the child.
                A handler exception propagates (harness fault).
        """
        while not stream.at_eof():
            data = await stream.read(4096)
            if data and handler is not None:
                await handler(data)

    async def _pump_stdin(self, writer, reader):
        """
        RETURN: None. Pipes 'reader' into the child's stdin; closes on EOF.
                Completes immediately if no reader is given.
        """
        if reader is None: return
        try:
            while not reader.at_eof():
                data = await reader.read(4096)
                if not data: break
                writer.write(data)
                await writer.drain()
            if writer.can_write_eof():
                writer.write_eof()
            await writer.drain()
            writer.close()
        except (ConnectionResetError, BrokenPipeError):
            pass    # child ended before consuming stdin: normal

    async def _close_stdin_transport(self, process):
        """
        RETURN: None. Closes the writable stdin pipe and awaits the OS
                acknowledgment, preventing file-descriptor leaks.
        """
        if not process.stdin: return
        with suppress(Exception):
            process.stdin.close()
            await process.stdin.wait_closed()
