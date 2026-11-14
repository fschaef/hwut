"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE URGENCY REPORT -- what this machine is and what went wrong on
         it, said so that a person can pass it to an AI assistant as it
         stands (adm/WORK/spec/24, the urgency reaction, services E-224).

    report_text(face, problem, failed)   the whole report: the headline,
                                         the '<hwut-system>' block, the
                                         line that says what to do with it
    block_line_list(face, problem, failed)   the block alone; 'hwut.help'
                                         prints it under its notice

ONE BLOCK FOR EVERY CALLER: '_launch' (Python too old, a census module
absent, a face ended by a crash signal) and 'hwut.help' print the same
lines, built here. Only 'services/_no_python.sh' writes its own, where no
Python stands to build one.

OLD SYNTAX ON PURPOSE: this module is read where the interpreter may be
older than hwut allows -- that is one of the things it reports. No
f-strings, no assignment expressions, no 'match'. It imports nothing of
hwut but 'requirements', which imports 'os' and 're' alone.

A MACHINE FACT NEVER ENTERS A GOOD: every value here is one. A page that
shows the block prints its KEYS and masks the values.
______________________________________________________________________________
"""
import os
import platform
import sys

BEGIN = "<hwut-system>"
END   = "</hwut-system>"
ADVICE = ("Pass the lines from %s to %s to your AI assistant: they say "
          "what this machine is and what went wrong on it." % (BEGIN, END))

_PACKAGE = os.path.normpath(os.path.join(os.path.dirname(
               os.path.abspath(__file__)), "..", ".."))


def report_text(face, problem, failed=None, sentence=None):
    """
    RETURN: str, the whole urgency report, ending in a newline -- the
            sentence ('<face> cannot run: <problem>.' where None); a
            blank line; the block; a blank line; the advice.
    """
    if sentence is None: sentence = headline(face, problem)
    line_list = [sentence, ""]
    line_list.extend(block_line_list(face, problem, failed))
    line_list.extend(["", ADVICE])
    return "\n".join(line_list) + "\n"


def headline(face, problem):
    """
    RETURN: str, '<face> cannot run: <problem>.' -- the one sentence a
            person reads before the block.
    """
    return "%s cannot run: %s." % (face, problem.rstrip("."))


def block_line_list(face, problem, failed=None):
    """
    RETURN: list[str], the block from '<hwut-system>' to '</hwut-system>':
            one 'key: value' line per fact, in a fixed order, the values
            aligned; 'missing' with one indented line per requirement
            ('none' where every one stands); 'failed' only where given.
            A path below the home directory is written with '~'.
    """
    pair_list = [("face",    face),
                 ("problem", problem.rstrip(".")),
                 ("os",      os_text()),
                 ("python",  python_text()),
                 ("pip",     pip_text()),
                 ("hwut",    hwut_text()),
                 ("on PATH", path_text()),
                 ("cores",   str(os.cpu_count()))]
    if failed is not None:
        pair_list.append(("failed", failed))
    width = max(len(key) for key, _ in pair_list + [("missing", "")]) + 2
    result = [BEGIN]
    for key, value in pair_list:
        result.append(("%s:" % key).ljust(width) + value)
    result.extend(missing_line_list(width))
    result.append(END)
    return result


def os_text():
    """
    RETURN: str, '<distribution> (<system> <release>, <machine>)' -- the
            distribution's PRETTY_NAME from '/etc/os-release' where it
            stands, the system's name else.
    """
    name = None
    try:
        with open("/etc/os-release") as fh:
            for line in fh:
                if line.startswith("PRETTY_NAME="):
                    name = line.split("=", 1)[1].strip().strip('"')
    except OSError:
        pass
    if name is None: name = platform.system() or "unknown system"
    return "%s (%s %s, %s)" % (name, platform.system(), platform.release(),
                               platform.machine())


def python_text():
    """
    RETURN: str, '<version> <interpreter> (<kind>)' -- the kind 'venv
            <prefix>' where the interpreter runs in a virtual
            environment, 'system' else.
    """
    if getattr(sys, "base_prefix", sys.prefix) != sys.prefix:
        kind = "venv %s" % home_short(sys.prefix)
    else:
        kind = "system"
    return "%s %s (%s)" % (platform.python_version(),
                           home_short(sys.executable or "unknown"), kind)


def pip_text():
    """
    RETURN: str, pip's version where this interpreter has pip, 'present'
            where its version cannot be read, 'absent' where it has none.
    """
    import importlib.util
    if importlib.util.find_spec("pip") is None:
        return "absent"
    try:
        from importlib.metadata import version
        return version("pip")
    except Exception:   # noqa: S110 -- no metadata: present, version unknown
        return "present"


def hwut_text():
    """
    RETURN: str, '<package directory> (clone, commit <hash>)' where the
            package stands in a git clone, '(clone)' where its commit
            cannot be read, '(installed <version>)' where no 'bin/' shim
            stands beside it.
    """
    where = home_short(_PACKAGE)
    if not os.path.isfile(os.path.join(_PACKAGE, "bin", "hwut")):
        return "%s (installed %s)" % (where, version_text())
    commit = commit_text(os.path.dirname(_PACKAGE))
    if commit is None:
        return "%s (clone)" % where
    return "%s (clone, commit %s)" % (where, commit)


def version_text():
    """
    RETURN: str, hwut's version from 'adm/version.py'; 'unknown' where it
            cannot be read.
    """
    try:
        with open(os.path.join(_PACKAGE, "adm", "version.py")) as fh:
            for line in fh:
                if line.startswith("String"):
                    return line.split("=", 1)[1].strip().strip('"')
    except OSError:
        pass
    return "unknown"


def commit_text(repository):
    """
    RETURN: str, the first seven digits of the commit HEAD names in
            'repository', read off '.git' without running git (a
            worktree's '.git' file is followed, a ref looked up loose
            and in 'packed-refs').
            None, where none of that can be read.
    """
    git = os.path.join(repository, ".git")
    try:
        if os.path.isfile(git):
            with open(git) as fh: line = fh.read().strip()
            if not line.startswith("gitdir:"): return None
            git = os.path.join(repository, line.split(":", 1)[1].strip())
        with open(os.path.join(git, "HEAD")) as fh: head = fh.read().strip()
        if not head.startswith("ref:"):
            return head[:7] or None
        ref = head.split(":", 1)[1].strip()
        for base in (git, common_directory(git)):
            path = os.path.join(base, ref)
            if os.path.isfile(path):
                with open(path) as fh: return fh.read().strip()[:7] or None
            packed = os.path.join(base, "packed-refs")
            if os.path.isfile(packed):
                with open(packed) as fh:
                    for line in fh:
                        if line.rstrip().endswith(" " + ref):
                            return line[:7]
    except OSError:
        return None
    return None


def common_directory(git):
    """
    RETURN: str, the directory a worktree's 'commondir' names -- where its
            branches stand; 'git' itself where it names none.
    """
    try:
        with open(os.path.join(git, "commondir")) as fh:
            return os.path.normpath(os.path.join(git, fh.read().strip()))
    except OSError:
        return git


def path_text():
    """
    RETURN: str, where 'hwut' stands on PATH; 'absent' where it does not
            -- a demonstration page calls the faces by PATH.
    """
    import shutil
    found = shutil.which("hwut")
    return "absent" if found is None else home_short(found)


def missing_line_list(width):
    """
    RETURN: list[str], 'missing:' followed by one line per requirement
            'hwut.help' checks that this machine lacks -- kind, name,
            what is wrong, and how Debian/Ubuntu and pip bring it -- each
            indented to 'width'; 'missing: none' where every one stands.
    """
    from .requirements import missing
    head = "missing:".ljust(width)
    row_list = missing()
    if not row_list:
        return [head + "none"]
    result = []
    for row, what in row_list:
        how = ("pip: %s" % row.debian[4:]) if row.debian.startswith("pip:") \
              else ("apt: %s" % row.debian)
        if row.kind == "python" and not row.debian.startswith("pip:"):
            how += " | pip: %s" % (("%s>=%s" % (row.name, row.least))
                                   if row.least else row.name)
        text = "%s %s (%s) %s" % (row.kind, row.name, what, how)
        result.append((head if not result else " " * width) + text)
    return result


def home_short(path):
    """
    RETURN: str, 'path' with the home directory written '~' where it
            stands below it -- no user's name travels in a report;
            'path' unchanged else.
    """
    home = os.path.expanduser("~")
    if home and home != "/" and (path == home
                                 or path.startswith(home + os.sep)):
        return "~" + path[len(home):]
    return path
