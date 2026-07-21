"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE
       THE SUPERVISED SYSTEM CALL -- platform-independent containment
       of unintentional misbehavior of trusted subprocesses, with
       attribution.

DESCRIPTION
       Every subprocess HWUT launches goes through the sandbox: test
       applications, build and helper tools ('make', 'scp', scripts),
       and pype filters. It replaces direct 'subprocess' usage. The
       sandbox is THE GROUND; everything else -- pipelines, the judged
       test -- is lightweight composition on top (see judged.py).

       The sandbox protects the RUN from the subprocess's BUGS: disk
       flooding, fork bombs, runaway memory growth, endless loops,
       hangs. A violation is reported as the failure of the call that
       caused it, with the exhausted resource named (SandboxResult).

       It does NOT defend against malice, does not isolate, and does
       not pin execution environments. Those concerns are resolved
       independently at the outer boundary (container, VM, dedicated
       runner) by the administrator. See SPEC-sandbox.txt.

       Dependencies: stdlib + psutil. Degradable: without psutil the
       memory and pid-count caps cannot be enforced and are REPORTED
       in SandboxResult.unenforced -- never silently ignored. On
       platforms without the 'resource' module (Windows) the CPU-time
       and file-size caps are likewise reported as unenforced; the
       wall-clock cap works everywhere.

MECHANISMS
       preexec hook     os.setsid (own process group) + rlimits for
                        CPU time, file size, process count (NPROC set
                        relative to the current per-user count).
       watchdog task    polls beside the stream readers: enforces
                        wall-clock and RSS caps over the whole process
                        group, counts group members against max_pids,
                        records peaks for attribution, and reaps
                        stragglers that outlive the test process.
       kill ladder      SIGTERM -> grace -> SIGKILL, applied to the
                        process GROUP; post-mortem sweep of any
                        observed descendant that escaped the group.

       RLIMIT_AS is deliberately NOT used: it breaks interpreters that
       reserve large virtual address spaces. Memory containment is
       watchdog-based (RSS) -- adequate against accidents; adversaries
       are out of scope.
______________________________________________________________________________
"""
import asyncio
import os
import shlex
import signal
import time
from   contextlib  import suppress
from   dataclasses import dataclass, field
from   enum        import Enum, auto
from   pathlib     import Path
from   typing      import Awaitable, Callable, Iterable, Optional

try:                import resource
except ImportError: resource = None      # e.g. Windows

try:                import psutil
except ImportError: psutil = None        # degradable, reported


_WATCHDOG_PERIOD_SEC  = 0.25   # poll period: RSS, pid count, wall clock
_KILL_GRACE_SEC       = 2.0    # SIGTERM -> SIGKILL escalation delay
_STRAGGLER_GRACE_SEC  = 1.0    # children outliving the exited test process


class SandboxPipe:
    """RETURN: --. The in-memory pipe connecting two supervised calls,
                   stdout -> stdin: the UPSTREAM call's 'stdout_handler'
                   is '.feed'; the DOWNSTREAM call's 'stdin_reader' is
                   '.reader'. '.close()' propagates end-of-stream.

    Every stage of such a chain runs in its OWN sandbox: own caps, own
    attribution -- a shell pipeline, supervised at every link.
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


class SandboxSequence:
    """RETURN: --. A chain of supervised system calls connected
                   stdout -> stdin -- a shell pipeline, supervised at
                   every link. Construction LAUNCHES the sequence.

    'stage_list' is [(Sandbox, command_line), ...], first stage first.
    Consecutive stages are connected through SandboxPipe; the LAST
    stage's stdout feeds '.tail'. PIPE-CONSTRUCTION IS THE INTERFACE,
    in both directions: '.tail.reader' is consumed by whatever comes
    next -- another supervised call, or the comparison engine.

    Interface:
        .tail         SandboxPipe: the sequence's stdout end
        .stop_event   stops every stage of the sequence
        .running()    some stage still runs?
        .collect()    awaits everything ->
                      tuple[SandboxResult, ...], one per stage,
                      in pipeline order

    Every stage has its own sandbox: own caps, own attribution -- a
    downstream stage's work is never billed to its producer. A stage
    that ends while an UPSTREAM stage still runs stops the sequence:
    SIGPIPE semantics, supervised.
    """
    def __init__(self, stage_list, stop_event=None):
        assert stage_list
        self.stop_event   = stop_event if stop_event is not None \
                            else asyncio.Event()
        self.tail         = SandboxPipe()
        self.sandbox_list = [sandbox for sandbox, _ in stage_list]

        self._task_list = []
        pipe_list       = []
        upstream_reader = None
        last_i          = len(stage_list) - 1
        for i, (sandbox, command_line) in enumerate(stage_list):
            out_pipe = self.tail if i == last_i else SandboxPipe()
            self._task_list.append(asyncio.create_task(
                sandbox.run(command_line,
                            stdin_reader   = upstream_reader,
                            stdout_handler = out_pipe.feed,
                            stop_event     = self.stop_event)))
            pipe_list.append(out_pipe)
            upstream_reader = out_pipe.reader

        self._closer_list = [
            asyncio.create_task(self._chain(i, pipe_list[i]))
            for i in range(len(stage_list))]

    async def _chain(self, i, out_pipe):
        """
        RETURN: None. Stage i ended: EOF propagates downstream; a
                stage gone while an upstream stage still runs stops
                the whole sequence (SIGPIPE semantics, supervised).
        """
        await asyncio.shield(self._task_list[i])
        out_pipe.close()
        if any(not task.done() for task in self._task_list[:i]):
            self.stop_event.set()

    def running(self) -> bool:
        """
        RETURN: True,  some stage of the sequence still executes.
                False, else.
        """
        return any(not task.done() for task in self._task_list)

    async def collect(self):
        """
        RETURN: tuple[SandboxResult, ...], the attribution records of
                every stage, in pipeline order. Awaits every stage and
                closer.
        """
        result_list = [await task for task in self._task_list]
        for closer in self._closer_list:
            await closer
        return tuple(result_list)


class E_Network(Enum):
    """Declared network need of a test. METADATA ONLY: recorded and
    reported for the test orchestrator; not enforced by the sandbox.
    """
    NONE     = auto()    # test needs no network at all
    LOOPBACK = auto()    # local client/server only            (DEFAULT)
    HOST     = auto()    # test talks to the outside world     (opt-in)


class E_Containment(Enum):
    COMPLETED           = auto()   # process exited by itself
    WALL_CLOCK_EXCEEDED = auto()   # watchdog: max_wall_clock_sec
    CPU_TIME_EXCEEDED   = auto()   # RLIMIT_CPU (SIGXCPU)
    MEMORY_EXCEEDED     = auto()   # watchdog: group RSS over cap
    FILE_SIZE_EXCEEDED  = auto()   # RLIMIT_FSIZE (SIGXFSZ death). NOTE:
                                   # an app that ignores SIGXFSZ -- CPython
                                   # does -- gets EFBIG from write() instead
                                   # and fails by its own exception: the cap
                                   # still holds, but the run reports
                                   # COMPLETED with the app's exit code.
    PIDS_EXCEEDED       = auto()   # watchdog: group members over cap
    STOPPED             = auto()   # external stop_event
    LAUNCH_FAILED       = auto()   # command not found / not executable


@dataclass
class SandboxConfig:
    # CAPS -- enforced:
    max_wall_clock_sec: float = 60.0
    max_cpu_time_sec:   int   = 60
    max_memory_mb:      int   = 512     # watchdog RSS, whole process group
    max_pids:           int   = 32
    max_file_size_mb:   int   = 10

    # DECLARED NEEDS -- metadata: recorded, reported, reviewable;
    # acted upon by the test orchestrator, not by the sandbox:
    network:     E_Network       = E_Network.LOOPBACK
    ports:       tuple[int, ...] = ()   # ports the test binds
    extra_write: tuple[str, ...] = ()   # paths written beyond the work dir


@dataclass
class SandboxResult:
    """THE ATTRIBUTION RECORD of one sandboxed execution."""
    containment:    E_Containment
    exit_code:      Optional[int]        # None unless COMPLETED
    wall_clock_sec: float
    cpu_time_sec:   Optional[float]      # None if not measurable
    peak_memory_mb: Optional[float]      # None without psutil
    unenforced:     tuple[str, ...]      # caps the platform cannot enforce

    @property
    def ok(self) -> bool:
        """
        RETURN: True,  process completed by itself with exit code 0.
                False, else.
        """
        return self.containment is E_Containment.COMPLETED \
               and self.exit_code == 0


class _RunState:
    """Shared mutable state between run(), watchdog, and stop watcher."""
    __slots__ = ("cause", "peak_memory_mb", "peak_pids", "cpu_time_sec",
                 "descendants")

    def __init__(self):
        self.cause          = None    # first containment cause wins
        self.peak_memory_mb = None
        self.peak_pids      = None
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


class Sandbox:
    def __init__(self, config: SandboxConfig, work_dir: str):
        self.config   = config
        self.work_dir = Path(work_dir).resolve()

    # ------------------------------------------------------------------ API

    async def run(self,
                  command_line:    str,
                  stdout_handler:  None | Callable[[bytes], Awaitable[None]] = None,
                  stderr_handler:  None | Callable[[bytes], Awaitable[None]] = None,
                  stdin_reader:    None | asyncio.StreamReader = None,
                  stop_event:      None | asyncio.Event = None,
                  backup_file_set: None | Iterable[str] = None) -> SandboxResult:
        """
        RETURN: SandboxResult, the attribution record of the completed (or
                contained) run: what ended it, exit code, wall clock, cpu
                time, peak memory, and any caps the platform could not
                enforce.

        Basic sandboxed system call. Handlers, if given, receive output
        chunks as they arrive; otherwise the channels are drained. Never
        raises on TEST misbehavior -- misbehavior is a RESULT, not an
        exception. Raises only on harness-level faults (a handler raising,
        bad configuration).
        """
        if backup_file_set:
            self._backup_files(backup_file_set)

        state              = _RunState()
        preexec, unenforced = self._make_preexec()
        rusage_before      = self._rusage_children()
        t0                 = time.monotonic()

        try:
            process = await asyncio.create_subprocess_exec(
                *shlex.split(command_line),
                stdin  = asyncio.subprocess.PIPE,
                stdout = asyncio.subprocess.PIPE,
                stderr = asyncio.subprocess.PIPE,
                cwd    = self.work_dir,
                **self._spawn_kwargs(preexec))
        except (FileNotFoundError, PermissionError, NotADirectoryError):
            return SandboxResult(E_Containment.LAUNCH_FAILED, None,
                                 time.monotonic() - t0, None, None,
                                 unenforced)

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
        try:
            # Completes when (a) process exited AND both output pipes hit
            # EOF, or (b) a pump raised (harness fault in a handler).
            await asyncio.wait({exit_task, out_task, err_task},
                               return_when=asyncio.FIRST_EXCEPTION)
        finally:
            if process.returncode is None:
                await self._kill_ladder(process)
            all_tasks = (out_task, err_task, in_task, dog_task,
                         stop_task, exit_task)
            for task in all_tasks:
                if not task.done(): task.cancel()
            results = await asyncio.gather(*all_tasks,
                                           return_exceptions=True)
            harness_error = next(
                (r for r in results[:2]
                 if isinstance(r, Exception)
                 and not isinstance(r, asyncio.CancelledError)),
                None)
            await self._close_stdin_transport(process)
            self._sweep(state)

        if harness_error is not None:
            raise harness_error

        wall = time.monotonic() - t0
        cpu  = self._cpu_time(rusage_before, state)
        return self._make_result(process.returncode, state, wall, cpu,
                                 unenforced)

    # ------------------------------------------------------- result shaping

    def _make_result(self, returncode, state, wall, cpu, unenforced):
        """
        RETURN: SandboxResult, containment cause derived from the recorded
                watchdog/stop cause first, else from the death signal
                (SIGXCPU/SIGXFSZ -> rlimit containment), else COMPLETED.
        """
        if state.cause is not None:
            containment, exit_code = state.cause, None
        elif resource is not None and returncode == -signal.SIGXCPU:
            containment, exit_code = E_Containment.CPU_TIME_EXCEEDED, None
        elif resource is not None and returncode == -signal.SIGXFSZ:
            containment, exit_code = E_Containment.FILE_SIZE_EXCEEDED, None
        else:
            containment, exit_code = E_Containment.COMPLETED, returncode

        return SandboxResult(containment    = containment,
                             exit_code      = exit_code,
                             wall_clock_sec = wall,
                             cpu_time_sec   = cpu,
                             peak_memory_mb = state.peak_memory_mb,
                             unenforced     = unenforced)

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
                    enforce (honest-reporting; surfaces in SandboxResult).
        """
        unenforced = []
        if psutil is None:
            # No RSS watchdog; and NPROC needs the current per-user count.
            unenforced += ["max_memory_mb", "max_pids"]
        if resource is None:
            unenforced += ["max_cpu_time_sec", "max_file_size_mb"]
            return None, tuple(unenforced)

        cpu_sec    = self.config.max_cpu_time_sec
        fsize_byte = self.config.max_file_size_mb * 1024 * 1024
        nproc      = self._nproc_limit()

        def preexec():
            # Child context, post-fork pre-exec: keep it minimal; a cap
            # the kernel refuses is skipped (kernel ceilings vary).
            with suppress(ValueError, OSError):
                resource.setrlimit(resource.RLIMIT_CPU,
                                   (cpu_sec, cpu_sec + 1))
            with suppress(ValueError, OSError):
                resource.setrlimit(resource.RLIMIT_FSIZE,
                                   (fsize_byte, fsize_byte))
            if nproc is not None:
                with suppress(ValueError, OSError):
                    resource.setrlimit(resource.RLIMIT_NPROC,
                                       (nproc, nproc))

        return preexec, tuple(unenforced)

    def _nproc_limit(self):
        """
        RETURN: int,  RLIMIT_NPROC value: current per-user process count
                      plus max_pids. NPROC counts the USER's processes, so
                      the limit must ride on top of what already runs.
                None, if the current count cannot be determined (no
                      psutil) -- NPROC is then left alone; the watchdog's
                      group count still enforces max_pids.
        """
        if psutil is None or not hasattr(os, "getuid"):
            return None
        uid = os.getuid()
        n   = 0
        for proc in psutil.process_iter(attrs=("uids",)):
            with suppress(Exception):
                uids = proc.info["uids"]
                if uids is not None and uids.real == uid:
                    n += 1
        if n == 0: return None
        return n + self.config.max_pids

    # ------------------------------------------------------------- watchdog

    async def _watchdog(self, process, state, t0):
        """
        RETURN: None.

        Enforces, at _WATCHDOG_PERIOD_SEC resolution:
          -- max_wall_clock_sec over the whole run,
          -- max_memory_mb as summed RSS over the process group,
          -- max_pids as the group member count,
        records peaks and observed descendants for attribution and the
        post-mortem sweep, and reaps stragglers: descendants that outlive
        the exited test process beyond _STRAGGLER_GRACE_SEC.
        """
        main = None
        if psutil is not None:
            with suppress(Exception):
                main = psutil.Process(process.pid)
        exited_at = None

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
                    state.set_cause(E_Containment.WALL_CLOCK_EXCEEDED)
                    await self._kill_ladder(process)
                    return
                if main is not None:
                    self._sample(main, state)
                    if state.peak_memory_mb is not None \
                       and state.peak_memory_mb > self.config.max_memory_mb \
                       and self._current_memory_mb(main) \
                           > self.config.max_memory_mb:
                        state.set_cause(E_Containment.MEMORY_EXCEEDED)
                        await self._kill_ladder(process)
                        return
                    if state.peak_pids is not None \
                       and state.peak_pids > self.config.max_pids:
                        state.set_cause(E_Containment.PIDS_EXCEEDED)
                        await self._kill_ladder(process)
                        return

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

    async def _watch_stop(self, process, state, stop_event):
        """
        RETURN: None. Waits on 'stop_event'; on set, records STOPPED and
                runs the kill ladder. Completes immediately if no event.
        """
        if stop_event is None: return
        await stop_event.wait()
        if process.returncode is None:
            state.set_cause(E_Containment.STOPPED)
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

    # ---------------------------------------------------------- file backup

    def _backup_files(self, filenames: Iterable[str]):
        """
        RETURN: None. Renames each existing watched file to
                '<name>-<n>.BACKUP' where n is the smallest unused
                counter -- deterministic names, no timestamps.
        """
        for name in filenames:
            path = self.work_dir / name
            if not path.exists(): continue
            n = 1
            while (backup := path.with_name(f"{path.name}-{n}.BACKUP")) \
                  .exists():
                n += 1
            path.rename(backup)
