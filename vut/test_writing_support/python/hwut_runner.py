# SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
#______________________________________________________________________________
import os
import sys
import re
import time
import threading
import tempfile
from   typing    import Callable
from   typeguard import typechecked


class HwutRunner:
    """Front end of a HWUT test application.

    A test application constructs one HwutRunner with its choice map and
    calls '.run()'. The command line selects the mode:

        app --hwut-info      print the info block; exit.
        app <choice>         normal mode: run one choice; test output on
                             the process's stdout and stderr.
        app --interactive    interactive mode: choices are started via
                             stdin; per choice, test output goes to two
                             named sink files; 'done' is reported on the
                             process's original stdout.
        app                  manual mode: list choices, read one selection
                             from stdin, run it, exit.
    """
    @typechecked
    def __init__(self,
                 argv:        list[str],
                 title:       str,
                 choice_map:  dict[str|None, Callable],
                 happy:       None | list[str] | list[re.Pattern] | str | re.Pattern = None,
                 same_f:      bool = False,
                 parallel:    str | None = None):
        """RETURN: HwutRunner, ready for '.run()'.

        'argv'        command line of the test application ('sys.argv').
        'title'       title line of the info block.
        'choice_map'  maps choice name -> test function. Key 'None' stands
                      for the single choice-less test; then it is the only
                      entry.
        'happy'       pattern(s) for the info block's 'HAPPY:' lines.
        'same_f'      True => info block carries 'SAME;'.
        'parallel'    execution scheme of interactive mode:
                          None       -- sequential, in-process
                          "process"  -- one forked child per choice;
                                        choices run concurrently.
        """
        assert choice_map
        assert parallel in (None, "process")
        # None indicates the test function for no choice. We only have apps
        # with and without choices, not both.
        if None in choice_map: assert len(choice_map) == 1

        self.title      = title
        self.argv       = argv
        self.choice     = None if len(argv) < 2 else argv[1]
        self.choice_map = choice_map
        self.parallel   = parallel
        # Provide a 'choice' by index -> also on the command line easy
        # specification.
        # NOTE: 'None' cannot be sorted against strings => safety separation
        self.sorted_choice_list = [None] if None in choice_map else sorted(choice_map)

        self.__same_result_for_all_choices = same_f

        if   type(happy) is str:        self.happy = [happy]
        elif type(happy) is list:       self.happy = [ h if type(h) is str else h.pattern for h in happy ]
        elif type(happy) is re.Pattern: self.happy = [happy.pattern]
        else:                           self.happy = []

        # Interactive mode state (armed in MODE_interactive).
        self._control       = None                # UP channel (original stdout)
        self._control_lock  = threading.Lock()
        self._stray_path    = None                # session sink for stray output
        self._pending       = {}                  # pid -> choice token
        self._pending_lock  = threading.Lock()
        self._pending_event = threading.Event()
        self._reaper_done   = threading.Event()

    def run(self):
        """RETURN: None.

        Dispatches on the first command line argument (see class docstring).
        """
        def identify_mode():
            if self.choice in ("-h", "--hi", "--hwut-info", "--sos", "--wtf"):
                return "--hwut-info"
            elif self.choice == "--interactive":
                return "--interactive"
            elif self.choice is None:
                return None
            else:
                return "--run"

        match identify_mode():
            case "--hwut-info":
                do = self.MODE_hwut_info
            case "--interactive":
                do = self.MODE_interactive
            case None:
                # If no choice is specified, but required, ask the user.
                if None not in self.choice_map:        do = self.MODE_manual_interaction_with_user
                else:                                  do = self.MODE_run_test
            case "--run":
                if self.choice not in self.choice_map: do = self.MODE_choice_does_not_exist
                else:                                  do = self.MODE_run_test
            case _:
                def do(): pass

        do()

    def MODE_choice_does_not_exist(self):
        """RETURN: never; exits with status 1.

        Reports the unavailable choice, the available ones, and the closest
        match by Levenshtein distance.
        """
        print(f"error: choice '{self.choice}' not available.")
        print(f'error: available: {", ".join(self.__printable_choice_list())}.')
        suggestion = _levenshtein_best_match(self.choice, self.sorted_choice_list)
        if suggestion is not None:
            print(f"error: did you mean '{suggestion}'?")
        sys.exit(1)

    def MODE_run_test(self):
        """RETURN: None.

        Normal mode. Runs the test of the given 'choice'; if there is no
        second command line argument the choice is 'None' and the according
        test is entered in the choice map as 'None'. Output flows on the
        process's own stdout and stderr.
        """
        self.__run_choice(self.choice)
        #  R-70: the terminal token -- the stream testifies its own
        #  completeness; always, unconditional (4a).
        print("<hwut-end>")

    def MODE_hwut_info(self):
        """RETURN: never; exits with status 0.

        Prints the info block: title, CHOICES, HAPPY patterns, SAME flag,
        INTERACTIVE capability.
        """
        for line in self.__info_block_lines(): print(line)
        sys.exit()

    def MODE_manual_interaction_with_user(self):
        """RETURN: None.

        Lists the choices with indices, reads one line from stdin, runs the
        selected choice. One shot; for another shot, call the app again.
        """
        print("Select choice:")
        for i, choice in enumerate(self.__printable_choice_list()):
            print(f"({i}) {choice}")

        cmd = self.__readline()
        if cmd is None or not cmd.isnumeric():
            print("error: bad choice or instruction")
            return
        try:
            choice = self.sorted_choice_list[int(cmd)]
        except IndexError:
            print(f"error: choice number {cmd} does not exist")
            sys.exit(-1)
        self.__run_choice(choice)

    def MODE_interactive(self):
        """RETURN: None; returns when the session ends ('quit' or EOF).

        Interactive mode. The session's channels:

            stdin                DOWN: commands from the framework.
            original stdout      UP:   protocol replies ('done', ...).
            per-choice sinks     test output: two files named in the
                                 'run' command.

        On entry, the original stdout is duplicated onto a private control
        descriptor; fd 1 and fd 2 are then pointed at a session stray sink.
        Output outside a running choice lands in the stray sink, never in
        the protocol.

        DOWN grammar (one command per line):
            run <choice> <sink-out> <sink-err>
            info
            quit | q | exit
        '<choice>' is a choice name, a decimal index into the sorted choice
        list, or '-' for the choice-less test.

        UP grammar (one message per line):
            done <choice> <status>      choice ran; sinks complete & closed
            fail <choice> <reason-...>  command not executed
            info: <line>                reply lines to 'info'
            bye                         session end; all children reaped
        """
        sys.stdout.flush(); sys.stderr.flush()
        self._control = os.fdopen(os.dup(1), "w", buffering=1)

        stray_fd, self._stray_path = tempfile.mkstemp(prefix="hwut_stray_", suffix=".txt")
        os.dup2(stray_fd, 1)
        os.dup2(stray_fd, 2)
        os.close(stray_fd)

        if self.parallel == "process":
            reaper = threading.Thread(target=self.__reap_loop,
                                      name="hwut-reaper", daemon=True)
            reaper.start()

        while (line := self.__readline()) is not None:
            if not self.__interprete(line): break

        self.__drain_children()
        self.__up("bye")

    def __interprete(self, line: str) -> bool:
        """RETURN: True,  session continues
                   False, session ends

        Interpretes one DOWN command line of interactive mode. Replies on
        the UP channel; never raises.
        """
        fields = line.split()
        match fields:
            case ["quit" | "q" | "exit"]:
                return False
            case ["info"]:
                for info_line in self.__info_block_lines():
                    self.__up(f"info: {info_line}")
                self.__up("done - 0")
            case ["run", token, sink_out, sink_err]:
                choice, found_f = self.__find_choice(token)
                if not found_f:
                    self.__up(f"fail {token} unknown-choice")
                elif self.parallel == "process":
                    self.__run_forked(token, choice, sink_out, sink_err)
                else:
                    status = self.__run_into_sinks(choice, sink_out, sink_err)
                    self.__up(f"done {token} {status}")
            case _:
                self.__up("fail - bad-command")
        return True

    def __find_choice(self, token: str) -> tuple:
        """RETURN: (choice, True),  token names an existing choice
                   (None,   False), else

        'token' is a choice name, a decimal index into the sorted choice
        list, or '-' for the 'None' choice.
        """
        if token == "-":
            return (None, None in self.choice_map)
        elif token in self.choice_map:
            return (token, True)
        elif token.isnumeric():
            try:    return (self.sorted_choice_list[int(token)], True)
            except IndexError: return (None, False)
        return (None, False)

    def __run_into_sinks(self, choice, sink_out: str, sink_err: str) -> int:
        """RETURN: 0,      test function ran and returned
                   n != 0, test function raised SystemExit(n) or an
                           exception (=> 1; traceback in the error sink)

        Runs 'choice' with fd 1 and fd 2 pointed at the two sink files.
        Before the return: Python's streams are flushed, both sinks are
        closed, fd 1 and fd 2 are restored. The return is the 'done'
        barrier for the app's own writes; writes of processes spawned by
        the choice are the choice's concern (see README, BARRIER).
        """
        out_fd = os.open(sink_out, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
        err_fd = os.open(sink_err, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)

        sys.stdout.flush(); sys.stderr.flush()
        saved_1 = os.dup(1)
        saved_2 = os.dup(2)
        os.dup2(out_fd, 1); os.close(out_fd)
        os.dup2(err_fd, 2); os.close(err_fd)

        status = 0
        try:
            self.__run_choice(choice)
            #  <hwut-end> -- stream testifies its own completeness. 
            #
            # RULES:
            #
            # -- only stdout: 
            #    stderr never carries '<hwut-end>', it reports test execution
            #    problems, not nominal behavior. output files are closed before 
            #    checked--no need to mark end.
            #
            # -- normal return only:
            #    aborted, killed, execution failures make the test output 
            #    irrelevant for comparison. no need for the marker. 
            #
            # -- not for 'pyped' output:
            #
            #    'HWUT_NO_TERMINAL' is set by the framework where a canonicaliser
            #    owns stdout; the pype then writes the token. assumption is that,
            #    tests using 'pype' are subject to racing conditions and might not
            #    be able to provide safe terminating tokens. pype-scripts can.
            #
            if not os.environ.get("HWUT_NO_TERMINAL"):
                print("<hwut-end>")
        except SystemExit as x:
            status = x.code if type(x.code) is int else (0 if x.code is None else 1)
        except BaseException:
            import traceback
            traceback.print_exc()
            status = 1
        finally:
            sys.stdout.flush(); sys.stderr.flush()
            os.dup2(saved_1, 1); os.close(saved_1)
            os.dup2(saved_2, 2); os.close(saved_2)
        return status

    def __run_forked(self, token: str, choice, sink_out: str, sink_err: str):
        """RETURN: None; registers the child, returns immediately.

        Forks one child per choice. The child runs '__run_into_sinks' and
        exits with its status; the reaper thread reports 'done' upon the
        child's end. The parent's streams are flushed before the fork.
        """
        sys.stdout.flush(); sys.stderr.flush()
        pid = os.fork()
        if pid == 0:
            try:
                status = self.__run_into_sinks(choice, sink_out, sink_err)
            except BaseException:
                status = 1
            os._exit(status & 0xFF)

        with self._pending_lock:
            self._pending[pid] = token
        self._pending_event.set()

    def __reap_loop(self):
        """RETURN: None; runs until '_reaper_done' with no pending children.

        Reaper thread of parallel interactive mode. Waits for child ends
        and reports 'done <token> <status>' on the UP channel.
        """
        while True:
            self._pending_event.wait()
            with self._pending_lock:
                if not self._pending:
                    if self._reaper_done.is_set(): return
                    self._pending_event.clear()
                    continue
            try:
                pid, wstatus = os.wait()
            except ChildProcessError:
                continue
            with self._pending_lock:
                token = self._pending.pop(pid, None)
            if token is not None:
                self.__up(f"done {token} {os.waitstatus_to_exitcode(wstatus)}")

    def __drain_children(self):
        """RETURN: None; upon return every child is reaped and reported.

        Ends the reaper thread. No-op in sequential mode.
        """
        if self.parallel != "process": return
        self._reaper_done.set()
        self._pending_event.set()
        while True:
            with self._pending_lock:
                if not self._pending: break
            time.sleep(0.02)

    def __up(self, message: str):
        """RETURN: None; 'message' is written and flushed on the UP channel.
        """
        with self._control_lock:
            self._control.write(message + "\n")

    def __info_block_lines(self) -> list[str]:
        """RETURN: list of str, the lines of the info block.
        """
        result = [ self.title if self.title.endswith(";") else self.title + ";" ]
        if None not in self.choice_map:
            result.append("CHOICES: " + ", ".join(self.sorted_choice_list) + ";")
        for happy_pattern in self.happy:
            result.append("HAPPY: " + happy_pattern + ";")
        if self.__same_result_for_all_choices:
            result.append("SAME;")
        result.append("INTERACTIVE;")
        return result

    def __printable_choice_list(self) -> list[str]:
        """RETURN: list of str, the sorted choices; the 'None' choice as '-'.
        """
        return [ "-" if c is None else c for c in self.sorted_choice_list ]

    def __run_choice(self, choice):
        """RETURN: None; upon return the test function of 'choice' has run.

        Runs the function in sync or async manner, depending on the
        function type entered in the choice map.
        """
        test_function = self.choice_map[choice]
        import asyncio
        if asyncio.iscoroutinefunction(test_function):
            asyncio.run(test_function())
        else:
            test_function()

    def __readline(self) -> str | None:
        """RETURN: str,  next non-empty stripped line from stdin
                   None, upon end of stream
        """
        try:
            while True:
                if not (line := sys.stdin.readline()): return None
                elif line := line.strip():             return line
        except EOFError:
            return None


def _levenshtein_best_match(needle: str | None, haystack: list) -> str | None:
    """RETURN: str,  element of 'haystack' with least Levenshtein distance
                     to 'needle'
               None, if 'needle' is None or 'haystack' is empty
    """
    if   needle is None:      return None
    elif not haystack:        return None
    elif needle in haystack:  return needle
    best_key  = None
    best_dist = None
    for key in haystack:
        if key is None: continue
        dist = _levenshtein_distance(needle, key)
        if best_dist is None or dist < best_dist:
            best_dist = dist
            best_key  = key
    return best_key

def _levenshtein_distance(a: str, b: str) -> int:
    """RETURN: int >= 0, the Levenshtein distance between 'a' and 'b'.
    """
    if   a == b: return 0
    elif not a:  return len(b)
    elif not b:  return len(a)
    # Ensure 'b' is the shorter one to keep memory smaller
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        cur      = [i]
        prev_j_1 = i - 1
        for j, cb in enumerate(b, start=1):
            ins  = cur[j - 1] + 1
            dele = prev[j] + 1
            sub  = prev_j_1 + (0 if ca == cb else 1)
            prev_j_1 = prev[j]
            cur.append(min(ins, dele, sub))
        prev = cur
    return prev[-1]

