"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE 'hwut.execute' COMMAND LINE -- run one user-defined target
         over every directory that binds targets (E-7), or shell
         commands in every test directory.

    hwut.execute <option-list> <target> <passed-through>
    hwut.execute <option-list> -c "<commands>"

OPTIONS STAND BEFORE THE TARGET NAME. Everything after the target
belongs to each directory's script, argv-style and untouched -- so
'--dir' names directories where it stands first, and is a word for
the script where it stands second.

Everything before the target name is this service's vocabulary;
everything after it goes to each directory's script, argv-style,
untouched. One target per invocation.

TWO PHASES. Phase one explores every directory below the root and
settles the plan; a refusal there costs ZERO executions. Per walked
directory, three reasons decide, in order:

    1  file present
    2  file executable
    3  shebang's interpreter executable  (where a shebang decides)

A failed reason refuses the COMPLETE target execution, except under
'-i, --ignore', which skips the failing directory. '--default='
substitutes where the target is absent. '+x' sets a+x where the
executable bit is missing; never done without it.

TARGETS ARE NOT TESTS. Exit codes are informational: reported per
directory, never deciding. The service succeeds iff phase one accepted
and every planned script was found and executed -- however it exited.

A script's cwd is its directory; the environment is inherited
unchanged. Every execution stands under the directory's lock: a target
run never collides with a test run, or another target run, on the same
directory.
______________________________________________________________________________
"""
import os
import shutil
import subprocess
import sys


from   vut.engine.bookkeeper.api   import DirectoryLock
from   vut.engine.orchestrator.exploration  import finder
from   vut.engine.orchestrator.exploration  import reader
from   vut.engine.orchestrator.exploration.task_list_query \
                                            import dir_ruled_out_f
from   vut.engine.orchestrator.exploration.tree_explorer \
                                            import explore_tree_stream
from   vut.services._exit                   import E_ExitCode


USAGE = "usage: hwut.execute [-i] [--default=<script>] [-q] [+x] " \
        "[--directory=<path>] <target> [<argument> ...]\n" \
        "       hwut.execute [-q] [--dir|--exclude-dir <glob>]... [--directory=<path>] " \
        "-c \"<commands>\""

HELP = """hwut.execute -- run one user-defined target over the tree

    hwut.execute <option-list> <target> <passed-through>
    hwut.execute <option-list> -c "<commands>"

OPTIONS STAND BEFORE THE TARGET NAME. Everything after the target
belongs to each directory's script, argv-style and untouched -- so
'--dir' names directories where it stands first, and is a word for
the script where it stands second.

Every directory below the root whose 'hwut.conf' binds targets --

    hwut {
        target {
            clean = "./clean.sh"
        }
    }

-- takes part; definition is membership. Everything after the target
name goes to each directory's script, argv-style, untouched.

'-c "<commands>"' stands where the target would: the commands run by
'sh -c' in EVERY TEST DIRECTORY -- every directory hwut finds tests in,
as 'hwut.run' walks them -- under the same lock, from the same cwd,
reported the same way. No target and no script: '--default' and '+x'
are refused beside it, and no word may follow it.

PHASE ONE settles the plan; a refusal costs zero executions. Per
directory, three reasons decide, in order:

    1  file present
    2  file executable
    3  shebang's interpreter executable  (where a shebang decides)

PHASE TWO executes, each directory under its lock, cwd the directory
itself, environment inherited unchanged. Exit codes are informational:
reported, never deciding.

OPTIONS
    -i, --ignore        skip a directory failing any of the three
                        reasons, or lacking the target
    --default=<script>  run <script> where the target is absent
    -q, --quiet         no per-directory output recording
    +x                  set a+x where the executable bit is missing;
                        never done without it
    --directory=<path>  the root to walk; the current one else
    --dir <glob>        only directories the glob names (the wish's
                        matching); may stand several times
    --exclude-dir <glob>  not the directories the glob names; with
                        '--dir', the LAST one matching decides (grep's
                        rule)
    -c "<commands>"     run <commands> by 'sh -c' in every test
                        directory, instead of a target
    --help              this text

EXIT STATUS
    0    phase one accepted; every planned script executed
    1    a refusal, a fault, or a script not executed
    2    the command line cannot be read
    3    no directory below the root binds any target -- or, under
         '-c', holds any test"""


def main(argv=None, write=None):
    """
    RETURN: E_ExitCode, the exit status (E-1): OK where phase one
            accepted and every planned script was found and executed,
            FAULT where a refusal, a fault or a non-execution stands,
            REFUSED where the command line cannot be read, EMPTY where
            no directory below the root binds any target.

    'write' takes one line at a time; 'print' where none is given, so
    a test may capture the face without a process.
    """
    if write is None: write = print
    if argv  is None: argv  = sys.argv[1:]

    arguments = _read_command_line(argv, write)
    if arguments is None:          return E_ExitCode.REFUSED
    if arguments == "help":        return E_ExitCode.OK

    if arguments["command"] is not None:
        plan = _test_directory_plan(arguments)
        if not plan:
            write("no directory below '%s' holds any test."
                  % arguments["directory"])
            return E_ExitCode.EMPTY
        return _phase_two(arguments, plan, 0, write)

    plan, refusal_list, skipped_n, empty_f = _phase_one(arguments)
    for line in refusal_list:
        write(line)
    if refusal_list:
        write("REFUSED: nothing has run.")
        return E_ExitCode.FAULT
    if empty_f:
        write("no directory below '%s' binds any target."
              % arguments["directory"])
        return E_ExitCode.EMPTY

    return _phase_two(arguments, plan, skipped_n, write)


def _read_command_line(argv, write):
    """
    RETURN: dict,   the read command line -- target, passed-through
                    arguments, options, root directory.
            "help", '--help' stood before the target name.
            None,   the command line cannot be read (refusal written).

    Everything before the first bare token is this service's
    vocabulary; the bare token is the target; everything after it is
    passed through untouched.
    """
    result = {"target": None, "pass_through": [], "ignore_f": False,
              "default": None, "quiet_f": False, "plus_x_f": False,
              "directory": ".", "dir_tuple": (), "dir_rule_tuple": (),
              "command": None}
    i = 0
    while i < len(argv):
        argument = argv[i]
        if   argument == "--help":
            write(HELP)
            return "help"
        elif argument in ("-i", "--ignore"):  result["ignore_f"] = True
        elif argument in ("-q", "--quiet"):   result["quiet_f"]  = True
        elif argument == "+x":                result["plus_x_f"] = True
        elif argument.startswith("--default="):
            result["default"] = argument[len("--default="):]
        elif argument.startswith("--directory="):
            result["directory"] = argument[len("--directory="):]
        elif argument in ("--dir", "--exclude-dir") \
             or argument.startswith(("--dir=", "--exclude-dir=")):
            #  THE WISH'S OWN WORD (disc-10). A face whose SUBJECT is
            #  directories reads the same option every other face
            #  reads as a filter -- one selection language, and a
            #  person who learnt '--dir' on 'hwut.run' has learnt it
            #  here.
            #
            #  IT MUST STAND BEFORE THE TARGET NAME. Everything after
            #  the target belongs to the SCRIPT, argv-style and
            #  untouched -- that is this face's oldest law, and
            #  '--dir' does not get to break it.
            #  '--exclude-dir' is its opposite, and the two are decided
            #  in command-line order by grep's rule (services E-15).
            word, _eq, text = argument.partition("=")
            if not _eq:
                i += 1
                if i >= len(argv):
                    write("REFUSED: '%s' stands without a glob" % word)
                    write(USAGE)
                    return None
                text = argv[i]
            kind = "+" if word == "--dir" else "-"
            if kind == "+": result["dir_tuple"] = result["dir_tuple"] + (text,)
            result["dir_rule_tuple"] = result["dir_rule_tuple"] \
                                       + ((kind, text),)
        elif argument == "-c":
            i += 1
            if i >= len(argv):
                write("REFUSED: '-c' stands without commands")
                write(USAGE)
                return None
            result["command"] = argv[i]
            if i + 1 < len(argv):
                write("REFUSED: '-c' runs its commands and nothing "
                      "follows it: '%s'" % argv[i + 1])
                write(USAGE)
                return None
            return _command_checked(result, write)
        elif argument.startswith("-") or argument.startswith("+"):
            write("REFUSED: unknown option '%s'" % argument)
            write(USAGE)
            return None
        else:
            result["target"]       = argument
            result["pass_through"] = list(argv[i+1:])
            return result
        i += 1
    write("REFUSED: no target named, and no '-c'")
    write(USAGE)
    return None


def _command_checked(result, write):
    """
    RETURN: dict, 'result' where the options beside '-c' belong to it.
            None, where one belongs to a TARGET's script -- '--default',
                  '+x' -- (refusal written).
    """
    for flag, key in (("--default", "default"), ("+x", "plus_x_f")):
        if result[key]:
            write("REFUSED: '%s' belongs to a target's script, not to "
                  "'-c'" % flag)
            write(USAGE)
            return None
    return result


def _test_directory_plan(arguments):
    """
    RETURN: list, (directory, None, False) per TEST DIRECTORY below the
            root -- every directory hwut finds tests in, walked as
            'hwut.run' walks them -- that '--dir' leaves standing, walk
            order.
    """
    wanted_f = _wanted_f_of(arguments["dir_rule_tuple"])
    return [(relative, None, False)
            for relative, _result in explore_tree_stream(
                                         arguments["directory"])
            if wanted_f(relative.replace(os.sep, "/"))]


def _phase_one(arguments):
    """
    RETURN: [0] list, the plan: (directory, script, chmod_f) per
                participating directory, walk order -- the directories
                skipped under '-i' are not in it.
            [1] list[str], the refusal lines; non-empty refuses the
                COMPLETE execution.
            [2] int, the directories skipped under '-i'.
            [3] bool, True where no directory binds any target.

    A directory PARTICIPATES where its 'hwut.conf' binds any target;
    definition is membership. Three reasons decide per directory, in
    order: file present, file executable, shebang's interpreter
    executable. '-i' turns any refusal of a directory, absence
    included, into a skip.
    """
    root         = arguments["directory"]
    name         = arguments["target"]
    plan         = []
    refusal_list = []
    skipped_n    = 0
    found_any_f  = False

    wanted_f = _wanted_f_of(arguments["dir_rule_tuple"])
    for relative in _walk(root):
        if not wanted_f(relative): continue
        directory = os.path.normpath(os.path.join(root, relative))
        text      = finder.conf_text(directory)
        if text is None: continue
        conf_name = "%s/%s" % (relative, finder.CONF_NAME)
        spec, _app_db, fault_list = reader.read_conf(text, conf_name)
        if fault_list:
            refusal_list.extend(str(fault) for fault in fault_list)
            continue
        if not spec.target_db: continue
        found_any_f = True

        script = spec.target_db.get(name)
        if script is None and arguments["default"] is not None:
            script = arguments["default"]
        if script is None:
            if arguments["ignore_f"]:
                skipped_n += 1
                continue
            refusal_list.append(
                "REFUSED: %s: target '%s' is not bound"
                % (relative, name))
            continue

        reason, chmod_f = _runnability(directory, script,
                                       arguments["plus_x_f"])
        if reason is not None:
            if arguments["ignore_f"]:
                skipped_n += 1
                continue
            refusal_list.append("REFUSED: %s: %s" % (relative, reason))
            continue
        plan.append((relative, script, chmod_f))

    return plan, refusal_list, skipped_n, not found_any_f


def _phase_two(arguments, plan, skipped_n, write):
    """
    RETURN: E_ExitCode -- OK where every planned script executed,
            FAULT where one did not: its lock was held, or its
            execution failed. However a script EXITED never decides.

    Each directory runs under its DirectoryLock; cwd is the directory;
    the environment is inherited unchanged; the passed-through
    arguments are the one channel this service adds.
    """
    root        = arguments["directory"]
    executed_n  = 0
    failed_list = []
    for relative, script, chmod_f in plan:
        directory = os.path.normpath(os.path.join(root, relative))
        lock      = DirectoryLock(directory)
        if lock.acquire() is False:
            failed_list.append(
                "%s: another live run holds the directory" % relative)
            continue
        try:
            if chmod_f:
                path = os.path.join(directory, script)
                os.chmod(path, os.stat(path).st_mode | 0o111)
            if arguments["command"] is not None:
                argv, shown = ["sh", "-c", arguments["command"]], \
                              arguments["command"]
            else:
                argv, shown = [script] + arguments["pass_through"], script
            try:
                process = subprocess.run(argv, cwd=directory,
                                         capture_output=True, text=True)
            except OSError as error:
                failed_list.append("%s: cannot execute '%s': %s"
                                   % (relative, shown, error))
                continue
        finally:
            if lock.taken: lock.release()

        executed_n += 1
        if not arguments["quiet_f"]:
            write(":: %s: %s [exit %d]"
                  % (relative, shown, process.returncode))
            if process.stdout:
                write(process.stdout.rstrip("\n"))
            if process.stderr:
                write("-- stderr --")
                write(process.stderr.rstrip("\n"))

    for line in failed_list:
        write("FAILED: %s" % line)
    write("directories: %d  executed: %d  skipped: %d"
          % (len(plan) + skipped_n, executed_n, skipped_n))
    return E_ExitCode.FAULT if failed_list else E_ExitCode.OK


def _wanted_f_of(rule_tuple):
    """
    RETURN: callable, taking a root-relative directory and answering
            whether the directory rules want it -- the wish's own
            matching and grep's order rule ('task_list_query'), so a
            person who learnt them on 'hwut.run' has learnt them here.
    """
    return lambda relative: not dir_ruled_out_f(relative, rule_tuple)


def _walk(root):
    """
    YIELD: [0] str  one directory below 'root', root-relative,
                    '/'-separated, '.' for the root itself -- sorted
                    order, names beginning '.' passed over.
    """
    yield "."
    for here, directory_list, _file_list in os.walk(root):
        directory_list[:] = sorted(name for name in directory_list
                                   if not name.startswith("."))
        for name in directory_list:
            relative = os.path.relpath(os.path.join(here, name), root)
            yield relative.replace(os.sep, "/")


def _runnability(directory, script, plus_x_f):
    """
    RETURN: [0] str | None -- the refusing reason sentence; None where
                the script may run. The three reasons, in order: file
                present, file executable, shebang's interpreter
                executable.
            [1] bool, True where '+x' turns the missing executable bit
                into a planned chmod.
    """
    path = os.path.join(directory, script)
    if not os.path.isfile(path):
        return "file '%s' is not present" % script, False

    chmod_f = False
    if not os.access(path, os.X_OK):
        if not plus_x_f:
            return ("file '%s' is not executable ('+x' sets it)"
                    % script), False
        chmod_f = True

    interpreter = _shebang_interpreter(path)
    if interpreter is not None:
        if os.path.isabs(interpreter):
            good_f = os.path.isfile(interpreter) \
                     and os.access(interpreter, os.X_OK)
        else:
            good_f = shutil.which(interpreter) is not None
        if not good_f:
            return ("shebang interpreter '%s' is not executable"
                    % interpreter), False
    return None, chmod_f


def _shebang_interpreter(path):
    """
    RETURN: str,  the interpreter the script's shebang names -- the
                  argument of '/usr/bin/env' where the shebang speaks
                  through it.
            None, the file carries no shebang -- the reason does not
                  apply.
    """
    try:
        with open(path, "rb") as file_handle:
            first = file_handle.readline(256)
    except OSError:
        return None
    if not first.startswith(b"#!"): return None
    try:
        token_list = first[2:].decode("utf-8", "replace").split()
    except Exception:
        return None
    if not token_list: return None
    interpreter = token_list[0]
    if os.path.basename(interpreter) == "env" and len(token_list) > 1:
        return token_list[1]
    return interpreter


if __name__ == "__main__":
    #  A TERMINAL SIGNAL IS AN ENDING, NOT A CRASH (E-55).
    from   vut.services._exit import guarded
    sys.exit(guarded("hwut.execute", main, sys.argv[1:]))
