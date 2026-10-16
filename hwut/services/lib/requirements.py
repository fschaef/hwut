"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE ONE READER of 'adm/requirement-list.txt' for what a USER'S
         installation needs (adm/WORK/spec/24-installation-packages.txt).

The list is the one place; the wheel's dependencies, the Debian package's
'Depends' and what 'hwut.help' names as missing are read off it here and
nowhere restated. The list stands at the same place below the package
root in a clone and in every installed form.

IMPORTS 'os' AND 're' ALONE: 'hwut.help' asks before anything of the tree
is imported, since a missing module would end the import with a traceback
before a word could be said.
______________________________________________________________________________
"""
import os
import re

LIST_PATH = os.path.normpath(os.path.join(os.path.dirname(
                os.path.abspath(__file__)), "..", "..", "adm",
                "requirement-list.txt"))

_ROW_RE = re.compile(r"^(program|python|library)\s+(\S+)\s+(census|road)"
                     r"\s+(\S+)\s*(.*)$")
_LEAST_RE = re.compile(r"^([^><=\s]+)(?:>=(\S+))?$")


class Row:
    """One entry of the list: 'kind', 'name' (the module, program or
    library), 'least' (pip's oldest version measured to work, or None),
    'need', 'debian' (the package), 'debian_least' (Debian's numbering,
    or None), 'note'."""
    def __init__(self, kind, name_word, need, debian_word, note):
        self.kind, self.need, self.note = kind, need, note
        self.name,   self.least        = _LEAST_RE.match(name_word).groups()
        self.debian, self.debian_least = _LEAST_RE.match(debian_word).groups()


def rows(path=LIST_PATH):
    """
    RETURN: list[Row], every entry of the list in the order it stands.
            [], where the list cannot be read.
    """
    try:
        with open(path) as fh: text = fh.read()
    except OSError:
        return []
    result = []
    for line in text.splitlines():
        m = _ROW_RE.match(line)
        if m is not None: result.append(Row(*m.groups()))
    return result


def user_rows(path=LIST_PATH):
    """
    RETURN: list[Row], what an installation of hwut needs to run: the
            'python' modules of need 'census', the program 'python3' and
            the library 'vterm'. The rest serves developing hwut, or a road.
    """
    return [r for r in rows(path)
            if r.need == "census"
            and (r.kind == "python"
                 or (r.kind, r.name) in (("program", "python3"),
                                         ("library", "vterm")))]


def wheel_dependencies(path=LIST_PATH):
    """
    RETURN: list[str], the wheel's 'dependencies' -- '<module>>=<least>'
            per census module.
    """
    return ["%s>=%s" % (r.name, r.least) if r.least else r.name
            for r in user_rows(path) if r.kind == "python"]


def python_least(path=LIST_PATH):
    """
    RETURN: str, the oldest Python stated ('3.10'), the wheel's
            'requires-python'; None, where the list states none.
    """
    for r in user_rows(path):
        if r.kind == "program" and r.name == "python3": return r.debian_least
    return None


def debian_depends(path=LIST_PATH):
    """
    RETURN: str, the Debian package's 'Depends' line, its versions in
            Debian's numbering: 'python3 (>= 3.10), python3-bidict (>=
            0.22.1), ..., libvterm0'.
    """
    return ", ".join("%s (>= %s)" % (r.debian, r.debian_least)
                     if r.debian_least else r.debian
                     for r in user_rows(path))


def _version_tuple(text):
    """
    RETURN: tuple[int], the leading numbers of a version ('3.0.43' ->
            (3, 0, 43)); () where it holds none.
    """
    return tuple(int(n) for n in re.findall(r"\d+", text.split("+")[0])[:4])


def missing(path=LIST_PATH):
    """
    RETURN: list[(Row, str)], each user requirement this machine lacks,
            with what is wrong: 'absent', or 'too old: <version>'. A module
            is looked for without importing it.
            [], where every one stands.
    """
    import importlib.util
    result = []
    for r in user_rows(path):
        if r.kind == "python":
            if importlib.util.find_spec(r.name) is None:
                result.append((r, "absent"))
                continue
            if r.least:
                try:
                    from importlib.metadata import version
                    found = version(r.name)
                except Exception:   # noqa: S110 -- a module without metadata is not judged
                    continue
                if _version_tuple(found) < _version_tuple(r.least):
                    result.append((r, "too old: %s" % found))
        elif r.kind == "library":
            import ctypes.util
            if ctypes.util.find_library(r.name) is None:
                result.append((r, "absent"))
    return result


def missing_text(missing_list):
    """
    RETURN: str, one paragraph per missing requirement -- what it is,
            what is wrong, how Debian/Ubuntu and pip install it.
            "", for an empty list.
    """
    out = []
    for row, what in missing_list:
        noun = {"python":  "the Python module",
                "library": "the shared library"}.get(row.kind, row.kind)
        out.append("MISSING: %s '%s' (%s) -- %s." % (noun, row.name, what,
                                                     row.note))
        out.append("    Debian/Ubuntu:  sudo apt install %s" % row.debian)
        if row.kind == "python":
            out.append("    pip:            pip install '%s>=%s'"
                       % (row.name, row.least) if row.least
                       else "    pip:            pip install %s" % row.name)
    return "\n".join(out) + ("\n" if out else "")
