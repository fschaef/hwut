import os
import sys
import asyncio
import re
import threading
from   typing    import Callable, Optional, ContextManager
from   typeguard import typechecked
import stat
from   pathlib import Path
import tempfile

class HwutRunner:
    @staticmethod
    @typechecked
    def insert_project_path(directory_n:    int | None = None,
                            root_dir_name:  str | None = None):
        """Inserts a project root into sys.path.

        Modes:
          1) directory_n: go N directories up from the importing module file
          2) root_dir_name: walk upwards from importing module file until a directory
                            with that name is found; insert its PARENT into sys.path
                            so that imports like '<root_dir_name>.some.module' work.

        test_file_path:
            The content of variable '__file__' in the test script (optional).
        """
        test_file_path = _get_importing_module_file()
        if test_file_path is None:
            raise Exception("Cannot determine '__file__' of importing module.")

        if (directory_n is None) == (root_dir_name is None):
            raise ValueError("Provide exactly one of: directory_n or root_dir_name.")

        base_dir = os.path.abspath(os.path.dirname(test_file_path))

        if root_dir_name is not None:
            # Walk upwards until we find a directory named root_dir_name.
            cur = base_dir
            while True:
                if os.path.basename(cur) == root_dir_name:
                    parent = os.path.dirname(cur)
                    sys.path.insert(0, parent)
                    return
                nxt = os.path.dirname(cur)
                if nxt == cur:
                    break
                cur = nxt
            raise Exception(
                f"Cannot find directory named '{root_dir_name}' while walking up from '{base_dir}'."
            )

        # directory_n mode
        project_root_dir_raw = os.path.join(base_dir, *(['..'] * int(directory_n)))
        project_root_dir = os.path.abspath(project_root_dir_raw)
        sys.path.insert(0, project_root_dir)

    @typechecked
    def __init__(self, 
                 argv:        list[str],
                 title:       str,
                 choice_map:  dict[str, Callable],
                 happy:       None | list[str] | list[re.Pattern] | str | re.Pattern = None,
                 same_f:      bool = False):
        assert choice_map
        # None indicates the test function for no choice. We only have apps with
        # and without choices, not both.
        if None in choice_map: assert len(choice_map) == 1

        self.title       = title
        self.argv        = argv
        self.choice      = None if len(argv) < 2 else argv[1]
        self.choice_map  = choice_map 
        # Provide a 'choice' by index -> also on the command line easy specification
        # NOTE: 'None' cannot be sorted against strings => safety separation
        self.sorted_choice_list = [None] if None in choice_map else sorted(choice_map)

        self.__same_result_for_all_choices = same_f

        if   type(happy) is str:        self.happy = [happy]
        elif type(happy) is list:       self.happy = [ h if type(h) is str else h.pattern for h in happy ]
        elif type(happy) is re.Pattern: self.happy = [happy.pattern]
        else:                           self.happy = []

        self._stop_event               = threading.Event()

        self._stdout_stream = None
        self._stderr_stream = None

    def run(self):
        def identify_mode():
            if self.choice in ("-h", "--hi", "--hwut-info", "--sos", "--wtf"):
                return "--hwut-info"
            elif self.choice == "--controlled-by-hwut":
                return "--controlled-by-hwut"
            elif self.choice is None:
                return None
            else:
                return "--run"

        match identify_mode():
            case "--hwut-info": 
                do = self.MODE_hwut_info
            case "--controlled-by-hwut":
                do = self.MODE_controlled_by_hwut
            case None:
                # If no choice is specified, but required, we ask the user to provide it
                if None not in self.choice_map:        do = self.MODE_manual_interaction_with_user
                else:                                  do = self.MODE_run_test
            case "--run":
                if self.choice not in self.choice_map: do = self.MODE_choice_does_not_exist
                else:                                  do = self.MODE_run_test
            case _:
                def do(): pass

        do()

    def MODE_choice_does_not_exist(self):
        print(f"error: choice '{self.choice}' not available.")
        print(f'error: available: {", ".join(self.sorted_choice_list)}.')
        suggestion = _levenshtein_best_match(self.choice, self.sorted_choice_list)
        if suggestion is not None:
            print(f"error: did you mean '{suggestion}'?")
        sys.exit(1)

    def MODE_run_test(self):
        """Runs the test with the given 'choice'. If there is no choice, i.e.
        second command line argument, then it is 'None'. The according test is
        entered in the choice map as 'None'.

        Runs the test in sync or async mode, depending on the function type
        that is entered in the choice map.
        """
        self.__run_choice(self.choice)

    def MODE_controlled_by_hwut(self):
        def _hwut_controlled_agent():
            while not self._stop_event.is_set():
                self.__interprete(self.__readline())

        thread = threading.Thread(
            target = _hwut_controlled_agent,
            name   = "hwut-interactive",
            daemon = True
        )

        thread.start()

        try:
            while not self._stop_event.is_set():
                self._stop_event.wait(0.2)
        except KeyboardInterrupt:
            self._stop_event.set()

    def MODE_hwut_info(self):
        print(self.title + ";" if self.title[-1] != ";" else "")
        print("CHOICES: " + ", ".join(self.sorted_choice_list) + ";")

        for happy_pattern in self.happy:       print("HAPPY: " + happy_pattern + ";")
        if self.__same_result_for_all_choices: print("SAME;")
        sys.exit()

    def MODE_manual_interaction_with_user(self):
        print("Select choice:")
        for i, choice in enumerate(self.sorted_choice_list):
            print(f"({i}) {choice}")

        # One shot, then leave. If user wants another shot => call app again.
        self.__interprete(self.__readline())

    def __run_choice(self, choice):
        test_function = self.choice_map[choice]
        if asyncio.iscoroutinefunction(test_function):
            asyncio.run(test_function())
        else:
            test_function()

    def __interprete(self, cmd):
        """Interpretes 'cmd'. That is it executes the related 'choice' or
        the related command. 

        Upon termination request the '_stop_event' is set. It is assumed, that
        other callers exit immediately (one shot call to '__interprete()').
        """
        if cmd is None:
            print("error: bad choice or instruction") 
            self._stop_event.set()
        elif cmd.isnumeric():
            try:
                choice = self.sorted_choice_list[int(cmd)]
            except Exception:
                print(f"error: choice number {cmd} does not exist")
                sys.exit(-1)
            self.__run_choice(choice)
        elif cmd in ("quit", "q", "exit"):
            self._stop_event.set()

    def __readline(self) -> str | None:
        try:
            while True:
                if not (line := sys.stdin.readline()): return None
                elif line := line.strip():             return line
        except EOFError:
            return None

def _get_importing_module_file():
    """RETURNS: file name of the module that imported the module of the caller of this function.
                None if that failed.
    """
    import inspect

    for frame_info in inspect.stack()[1:]:
        module = inspect.getmodule(frame_info.frame)
        if module and hasattr(module, "__file__"):
            return module.__file__
    return None

def _levenshtein_best_match(needle: str | None, haystack: list[str]) -> str | None:
    if   needle is None:      return None
    elif not haystack:        return None
    elif needle in haystack:  return needle
    best_key  = None
    best_dist = None
    for key in haystack:
        dist = _levenshtein_distance(needle, key)
        if best_dist is None or dist < best_dist:
            best_dist = dist
            best_key  = key
    return best_key

def _levenshtein_distance(a: str, b: str) -> int:
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
            ins = cur[j - 1] + 1
            dele = prev[j] + 1
            sub = prev_j_1 + (0 if ca == cb else 1)
            prev_j_1 = prev[j]
            cur.append(min(ins, dele, sub))
        prev = cur
    return prev[-1]

def make_script_application(file_name:       Optional[str], 
                            shebang:         str, 
                            script_txt_list: list[str],
                            display_f:       bool = True) -> Optional[str]:
    """RETURNS: filename (str) != "", if script is generated and executable
                None,                 if not

    'shebang'         tells what interpreter to use
    'script_txt_list' defines the text of the script

    This function generates a (temporary) test script that may be used for 
    interaction with unit tests.
    """ 
    script_path = None

    content = shebang if shebang.startswith("#!") else f"#!{shebang}"
    content += "\n" + "\n".join(script_txt_list) + "\n"

    try:
        if file_name is None:
            # delete=False is necessary so the file remains after the handle is closed
            # allowing a sandbox process to find and execute it.
            with tempfile.NamedTemporaryFile(prefix="test_app_", delete=False) as tmp:
                script_path = Path(tmp.name)
        else:
            script_path = Path(file_name)

        script_path.write_text(content)
        script_path.chmod(script_path.stat().st_mode | stat.S_IEXEC) # make 'executable'
        
    except Exception:
        if script_path and script_path.exists():
            try:
                script_path.unlink()
            except Exception:
                pass
        return None

    if display_f:
        if not file_name: file_name = "<temporary file>"
        print(f"SCRIPT: '{file_name}' " + "{")
        for line in content.splitlines():
            print(f"    {line}")
        print("}")
      
    return str(script_path)

class ScriptApplication(ContextManager[str]):
    """A context manager wrapper for make_script_application.
    Ensures the generated script is deleted upon exiting the 'with' block.
    """
    def __init__(self, file_name, shebang, script_txt_list, display_f=True):
        self.params = {
            'file_name': file_name,
            'shebang': shebang,
            'script_txt_list': script_txt_list,
            'display_f': display_f
        }
        self.path = None

    def __enter__(self) -> str:
        result = make_script_application(**self.params)
        if result is None:
            raise RuntimeError("make_script_application failed to generate a script.")
        
        self.path = result
        return self.path

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.path and os.path.exists(self.path):
            try:
                os.unlink(self.path)
            except Exception:
                pass
