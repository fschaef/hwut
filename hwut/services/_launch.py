"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: EVERY FACE STARTS HERE (adm/WORK/spec/24). In a clone every face
         is a shim in 'bin/' running 'python3 -m hwut.services._launch
         <module>'; in an installation it is an entry point landing in
         'main()'. Either way the face's module runs as '__main__' --
         exactly what '-m' does -- under THE URGENCY REACTION (E-224):

    the interpreter older than hwut allows   the report, status 1
    a census module absent                   the report, status 1
    the face killed by a crash signal        the report, then the same
    (SEGV, ABRT, BUS, ILL, FPE)              signal: the caller sees the
                                             death it would have seen

    The report is 'lib/system_report.py''s: what this machine is, what
    went wrong, and the line saying to pass it to an AI assistant. A
    machine without 'python3' is said by 'services/_no_python.sh'.

    face_module_db()   face name -> module, read off the shims in a clone,
                       or off '_launch_db' (written by the package build)
                       where no shim stands
    launch(module, face)   the face's module run under the reaction
    main()             the entry point of every installed face

THE WATCHER. Only a parent sees how a process died, so the face runs in a
forked child and this process waits. The child stays in the parent's
process group: Ctrl-C, a 'killpg' of the procsitter, 'pkill -f' reach it
directly, once. The parent therefore delivers NOTHING on such a signal --
a second SIGTERM in the guard's cleanup (E-55) would print a traceback.
A signal that reached the parent ALONE ('kill <pid>') is passed on once,
when the child still runs FORWARD_DELAY seconds later. Endings are not
crashes: 130, 141, 143 are exit statuses (E-1), passed through as given;
every other death by signal is passed on as that signal, unreported.

OLD SYNTAX ON PURPOSE, as in 'lib/system_report.py': the age check runs
before anything newer is compiled.
______________________________________________________________________________
"""
import os
import re
import sys

BIN = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(
          __file__)), "..", "bin"))
_MODULE_RE = re.compile(r"python3\s+(?:-I\s+)?-m\s+(?:hwut\.services\._launch"
                        r"\s+)?([A-Za-z0-9_.]+)")

#  THE SIGNALS OF A CRASH: the process did something the machine refused.
#  The names, not the numbers: the numbers differ between platforms.
CRASH_NAME_TUPLE = ("SIGSEGV", "SIGABRT", "SIGBUS", "SIGILL", "SIGFPE")
FORWARD_DELAY    = 2.0      # seconds a lone signal waits before it is passed on


def shim_module_db(bin_directory=BIN):
    """
    RETURN: dict, face name -> module, for every 'hwut' and 'hwut.*' shim
            in 'bin_directory' that runs 'python3 -m <module>' (directly
            or through 'hwut.services._launch').
            {}, where the directory holds none.
    """
    result = {}
    try:
        name_list = os.listdir(bin_directory)
    except OSError:
        return result
    for name in name_list:
        if not (name == "hwut" or name.startswith("hwut.")): continue
        try:
            with open(os.path.join(bin_directory, name)) as fh:
                m = _MODULE_RE.search(fh.read())
        except (OSError, UnicodeDecodeError):
            continue
        if m is not None: result[name] = m.group(1)
    return result


def face_module_db():
    """
    RETURN: dict, face name -> module, of this installation: the shims
            where they stand (a clone), the build's '_launch_db' else.
    """
    result = shim_module_db()
    if result: return result
    try:
        from ._launch_db import FACE_MODULE_DB
    except ImportError:
        return {}
    return dict(FACE_MODULE_DB)


def face_of(module):
    """
    RETURN: str, the face that runs 'module' -- 'hwut.run' for
            'hwut.services.run'; the module's own name where no face
            runs it. 'hwut' (the default face) is named only where no
            other face runs the module.
    """
    name_list = sorted(name for name, m in face_module_db().items()
                       if m == module)
    named = [name for name in name_list if name != "hwut"]
    if named: return named[0]
    return name_list[0] if name_list else module


def too_old_problem(version_tuple, least_text):
    """
    RETURN: str, the problem an interpreter of 'version_tuple' has when
            hwut needs 'least_text' ('3.10') -- 'Python 3.8.10 is older
            than 3.10, the least hwut runs on'.
            None, where 'version_tuple' is not older.
    """
    least = tuple(int(part) for part in least_text.split("."))
    if tuple(version_tuple[:len(least)]) >= least:
        return None
    return ("Python %s is older than %s, the least hwut runs on"
            % (".".join(str(n) for n in version_tuple[:3]), least_text))


def least_python():
    """
    RETURN: str, the least Python version the requirement list names for
            'python3' ('3.10'); None, where the list names none.
    """
    from .lib.requirements import rows
    for row in rows():
        if row.kind == "program" and row.name == "python3":
            return row.debian_least
    return None


def census_module_set():
    """
    RETURN: set, the names of the Python modules of need 'census' -- those
            whose absence is an urgency, not a defect of hwut.
    """
    from .lib.requirements import rows
    return set(row.name for row in rows()
               if row.kind == "python" and row.need == "census")


def failed_text(error):
    """
    RETURN: str, '<type>: <message> (<file>:<line>)' -- the place being
            the innermost frame of the hwut tree that met 'error', its
            path below the package's parent; without the place where no
            frame of the tree stands.
    """
    package = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    place = None
    tb = error.__traceback__
    while tb is not None:
        file_name = os.path.abspath(tb.tb_frame.f_code.co_filename)
        if file_name.startswith(package + os.sep):
            place = "%s:%i" % (os.path.relpath(file_name, package),
                               tb.tb_lineno)
        tb = tb.tb_next
    text = "%s: %s" % (type(error).__name__, error)
    return text if place is None else "%s (%s)" % (text, place)


def urgent(face, problem, failed=None, sentence=None):
    """
    RETURN: None. The urgency report written to stderr, flushed.
    """
    from .lib.system_report import report_text
    sys.stdout.flush()
    sys.stderr.write(report_text(face, problem, failed, sentence))
    sys.stderr.flush()


def run_face(module, face):
    """
    RETURN: None, where the module ends without 'sys.exit' -- it runs as
            '__main__' and its exit is the process's. A census module absent ends with the report and
            status 1; any other exception goes through untouched.
    """
    import runpy
    try:
        runpy.run_module(module, run_name="__main__", alter_sys=True)
    except ModuleNotFoundError as error:
        top = (error.name or "").split(".")[0]
        if top not in census_module_set():
            raise
        urgent(face or face_of(module),
               "the Python module '%s' is absent" % top, failed_text(error))
        sys.exit(1)


def launch(module, face=None):
    """
    RETURN: never. 'module' run as the face 'face' (looked up where None,
            for the report only) under the urgency reaction. Where the
            platform cannot fork, the module runs without the watcher.
    """
    least = least_python()
    problem = None if least is None \
              else too_old_problem(sys.version_info, least)
    if problem is not None:
        urgent(face or face_of(module), problem)
        sys.exit(1)
    if not hasattr(os, "fork"):
        run_face(module, face)
        sys.exit(0)
    #  THE COPY-ON-WRITE OF THE CHILD is the watcher's cost: the face
    #  touches the heap it inherits. Frozen, the collector leaves it alone
    #  (measured: +4.7 ms per call -> +2.5 ms).
    import gc
    gc.freeze()
    child = os.fork()
    if child == 0:
        import faulthandler
        faulthandler.enable()       # the crash names its Python stack
        run_face(module, face)
        sys.exit(0)                 # the module ended without 'sys.exit'
    watch(child, module, face)


def watch(child, module, face):
    """
    RETURN: never. Waits for 'child' and ends as it ended: its exit
            status passed through; a crash signal reported and then
            raised here; any other signal raised here unreported.
    """
    import signal
    pending = []

    def lone(signal_n, frame):
        """RETURN: None. A signal the group delivers reached the child as
        well; one that came to this process alone is passed on later."""
        pending.append(signal_n)
        signal.setitimer(signal.ITIMER_REAL, FORWARD_DELAY)

    def forward(signal_n, frame):
        """RETURN: None. The child still runs: the lone signal is passed
        on, once."""
        while pending:
            try:                    os.kill(child, pending.pop(0))
            except OSError:         pass

    for name in ("SIGINT", "SIGTERM", "SIGHUP", "SIGQUIT"):
        if hasattr(signal, name):
            signal.signal(getattr(signal, name), lone)
    signal.signal(signal.SIGALRM, forward)
    _, status = os.waitpid(child, 0)    # retried after a handler (PEP 475)
    signal.setitimer(signal.ITIMER_REAL, 0)
    if os.WIFEXITED(status):
        os._exit(os.WEXITSTATUS(status))
    signal_n = os.WTERMSIG(status)
    crash_set = set(getattr(signal, name) for name in CRASH_NAME_TUPLE
                    if hasattr(signal, name))
    if signal_n in crash_set:
        face = face or face_of(module)
        name = signal.Signals(signal_n).name
        urgent(face, "killed by %s, a crash" % name,
               "the Python stack, printed above this report",
               "%s was killed by %s, a crash." % (face, name))
    signal.signal(signal_n, signal.SIG_DFL)
    os.kill(os.getpid(), signal_n)
    os._exit(128 + signal_n)        # a signal this process may not die by


def main():
    """
    RETURN: never -- the entry point of every installed face: the face
            its name names, launched. A name no face carries ends with
            status 2, said on stderr.
    """
    name = os.path.basename(sys.argv[0])
    module = face_module_db().get(name)
    if module is None:
        sys.stderr.write("REFUSED: '%s' is no face of hwut\n" % name)
        sys.exit(2)
    sys.argv[0] = name
    launch(module, name)


if __name__ == "__main__":
    #  THE SHIM'S WAY IN: 'python3 -m hwut.services._launch <module> ...'.
    #  The module's word leaves the command line; what follows is the
    #  face's own.
    if len(sys.argv) < 2:
        sys.stderr.write("REFUSED: '_launch' needs the module to run\n")
        sys.exit(2)
    _module = sys.argv.pop(1)
    launch(_module)
