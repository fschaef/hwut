"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE COMPLETER -- what a shell's TAB is answered with (services
         E-151, adm/WORK/gathered/0s).

    hwut --command-line-complete <shell> "<the line so far>"

A COMPLETION RUNS ON EVERY TAB PRESS, so this module imports 'os' and
're' and NOTHING OF THE TREE. The option words of every face come from
'_complete_db', a module WRITTEN by 'hwut --command-line-setup'
('_complete_setup.py') and byte-compiled there: one dictionary, imported
from its '.pyc'. Where it is absent, a face completes nothing.

THREE TIERS, only the first free:

    STATIC   face names, each face's options      the generated table
    CHEAP    applications here, choices of one,   one listing, or one
             directories below                    file's head read
    DEAR     labels that stand, targets bound     one file read and
             here                                 scanned

THE LAWS: it never fails loudly -- every path that could raise ends in
NO CANDIDATES, silently (a traceback in a completion buffer corrupts the
person's line); it writes nothing, takes no lock, runs no test.

ONE COMPLETER, ONE RENDERING PER SHELL:

    bash         one candidate per line; the part of the word before
                 its last '=' or ':' is cut, since bash breaks words there
    zsh          'candidate:description' per line, ':' in the candidate
                 escaped
    powershell   'candidate<TAB>description' per line
______________________________________________________________________________
"""
import os
import re

#  WHAT FOLLOWS AN OPTION, where the table's kind ('value') says too
#  little. Read by spelling; a face that takes the option takes it in
#  this meaning (the wish's words, 'run's root).
VALUE_KIND_DB = {
    "--glob":        "app",     "--exclude":     "app",
    "--dir":         "dir",     "--exclude-dir": "dir",
    "--directory":   "dir",
    "-l":            "label",   "--label":       "label",
    "--wishlist":    "file",
}

#  WHAT A BARE WORD IS, per face. A face whose table holds the wish
#  ('--glob') takes the SHORT FORM -- the first bare word an application,
#  every further one a choice of it (gathered/0s, open b).
POSITIONAL_DB = {
    "hwut.run.play":      "app",
    "hwut.labels.add":    "label",
    "hwut.labels.remove": "label",
    "hwut.execute":       "target",
}

_WORD_RE   = re.compile(r"""("[^"]*"?|'[^']*'?|\S)+""")
_MARKER_RE = re.compile(r"@hwut\s*\{")
_NAME_RE   = re.compile(r"[A-Za-z0-9_.\-]+")
HEAD_LINE_N = 8          # 'source_file_detector.HEAD_LINE_N'
STANDARD_LABEL_TUPLE = ("all", "meta")   # 'plan/label.py': universe, standard


def main(argv, table_db=None):
    """
    RETURN: 0, always -- the candidates for the line's last word went to
            stdout, one per line in the shell's rendering; nothing where
            nothing is known or anything failed.

    'argv' is '<shell> <line>'. 'table_db' replaces the generated table
    (a page's fixture); None imports '_complete_db'.
    """
    try:
        import sys
        shell, line = argv[0], argv[1]
        if table_db is None: table_db = _table_db()
        candidate_list = complete(line, table_db)
        word = _words(line)[-1]
        out  = render(shell, word, candidate_list)
        if out: sys.stdout.write(out)
    except BaseException:  # noqa: S110 -- a TAB never fails loudly (E-151)
        pass
    return 0


def _table_db():
    """
    RETURN: dict, the generated table -- 'FACE_TUPLE' and 'TABLE' -- if
            '_complete_db' stands (or 'HWUT_COMPLETE_DB' names a file
            holding one, for a page).
            {}, else.
    """
    path = os.environ.get("HWUT_COMPLETE_DB")
    if path:
        name_db = {}
        with open(path) as fh: exec(fh.read(), name_db)
        return name_db
    try:
        from . import _complete_db
    except ImportError:
        return {}
    return vars(_complete_db)


def _words(line):
    """
    RETURN: list[str], the line's words, quotes stripped; the LAST is the
            word being completed -- "" where the line ends in a blank.
    """
    word_list = [_unquoted(m.group(0)) for m in _WORD_RE.finditer(line)]
    if not word_list or line[-1:].isspace(): word_list.append("")
    return word_list


def _unquoted(word):
    """
    RETURN: str, 'word' with its quote marks removed.
    """
    return re.sub(r"""["']""", "", word)


def complete(line, table_db):
    """
    RETURN: list[str], the candidates for the last word of 'line',
            sorted, each starting with that word.
            [], where nothing is known.
    """
    word_list = _words(line)
    word      = word_list[-1]
    face_list = list(table_db.get("FACE_TUPLE", ()))
    if len(word_list) == 1:
        return _matching(face_list, word)
    face     = os.path.basename(word_list[0])
    row_list = table_db.get("TABLE", {}).get(face, ())
    kind_db  = {row[0]: (row[1], row[2]) for row in row_list}

    #  '--option=value': the value is completed, the spelling kept.
    if word.startswith("-") and "=" in word:
        name, _, value = word.partition("=")
        return [name + "=" + c for c in _values(name, kind_db, value)]
    if word.startswith("-"):
        return _matching(sorted(kind_db), word)
    previous = word_list[-2]
    if previous in kind_db and kind_db[previous][0] != "flag":
        return _values(previous, kind_db, word)
    return _positional(face, kind_db, word_list[1:-1], word)


def _values(option, kind_db, word):
    """
    RETURN: list[str], the values 'option' takes that start with 'word'.
    """
    kind, words = kind_db.get(option, ("value", ()))
    kind = VALUE_KIND_DB.get(option, kind)
    if   kind == "enum":  return _matching(words, word)
    elif kind == "dir":   return _paths(word, app_f=False, file_f=False)
    elif kind == "file":  return _paths(word, app_f=False, file_f=True)
    elif kind == "app":   return _paths(word, app_f=True,  file_f=False)
    elif kind == "label": return _labels(word)
    return []


def _positional(face, kind_db, done_list, word):
    """
    RETURN: list[str], the candidates for a bare word of 'face', where
            'done_list' holds the words before it.
    """
    #  The bare words already given: an option's value is not one.
    bare_list, skip_f = [], False
    for w in done_list:
        if   skip_f:                                   skip_f = False
        elif w.startswith("-"):
            skip_f = "=" not in w and kind_db.get(w, ("flag",))[0] != "flag"
        else:                                          bare_list.append(w)
    kind = POSITIONAL_DB.get(face)
    if kind is None and "--glob" in kind_db: kind = "app"
    if kind == "app":
        if not bare_list: return _paths(word, app_f=True, file_f=False)
        return _matching(_choices(bare_list[0]), word)
    if kind == "label"  and not bare_list: return _labels(word)
    if kind == "target" and not bare_list: return _targets(word)
    return []


def _matching(candidate_seq, word):
    """
    RETURN: list[str], the candidates starting with 'word', sorted, once.
    """
    return sorted(set(c for c in candidate_seq if c.startswith(word)))


#  ------------------------------------------------------------- CHEAP

def _paths(word, app_f, file_f):
    """
    RETURN: list[str], the entries of the directory 'word' points into
            that start with its last part: directories (with a trailing
            '/'), and -- 'app_f' -- test applications, or -- 'file_f' --
            any file. Hidden entries only where the part starts with '.'.
    """
    head, tail = os.path.split(word)
    where      = os.path.expanduser(head) or "."
    result = []
    for name in os.listdir(where):
        if not name.startswith(tail):                     continue
        if name.startswith(".") and not tail.startswith("."): continue
        path = os.path.join(where, name)
        if os.path.isdir(path):
            if app_f and _holds_no_application_f(path): continue
            result.append(os.path.join(head, name) + "/")
        elif file_f or (app_f and _is_application(path)):
            result.append(os.path.join(head, name))
    return sorted(result)


def _holds_no_application_f(path):
    """
    RETURN: True,  the directory 'path' holds no test application to
                   step into: the 'GOOD', 'OUT' or 'TMP' of a test
                   directory (one with 'GOOD/' beside them), or one that
                   carries 'hwut.no-entry-here.marker' -- the rule of
                   'auxiliary/no_entry.py', said again here because a
                   TAB imports 'os' and 're' alone (E-151)
            False, else -- the book's D-12: 'hwut.run.play <TAB>' in a
                   test directory offered 'GOOD/ OUT/ TMP/'
    """
    if os.path.isfile(os.path.join(path, "hwut.no-entry-here.marker")):
        return True
    return os.path.basename(path) in ("GOOD", "OUT", "TMP") \
           and os.path.isdir(os.path.join(os.path.dirname(path), "GOOD"))


def _head(path):
    """
    RETURN: str, the first HEAD_LINE_N lines of the file at 'path'.
            "", where it cannot be read as text.
    """
    try:
        with open(path, errors="replace") as fh:
            return "".join(fh.readline() for _ in range(HEAD_LINE_N))
    except OSError:
        return ""


def _is_application(path):
    """
    RETURN: True,  if the file's head carries the marker '@hwut {'.
            False, else.
    The detector's decoration rules are not repeated: a file quoting a
    header in its head is offered, and refused when it is run.
    """
    return _MARKER_RE.search(_head(path)) is not None


def _choices(path):
    """
    RETURN: list[str], the choices the '@hwut { }' header of the file at
            'path' declares -- 'choices = [...]' or the names of a
            'choices { name { } ... }' block.
            [], else.
    """
    with open(os.path.expanduser(path), errors="replace") as fh:
        text = fh.read(1 << 16)
    m = _MARKER_RE.search(text)
    if m is None: return []
    #  The decoration is whatever stands before the marker on its line;
    #  it is cut from the head of every header line.
    line_start = text.rfind("\n", 0, m.start()) + 1
    decoration = text[line_start:m.start()].strip()
    line_list  = []
    for line in text[line_start:].splitlines():
        line = line.strip()
        if decoration and line.startswith(decoration):
            line = line[len(decoration):]
        line_list.append(line)
    body = "\n".join(line_list)
    m = re.search(r"(?m)^\s*choices\s*(=|:)?\s*([\[{])", body)
    if m is None: return []
    if m.group(2) == "[":
        inner = body[m.end():body.find("]", m.end())]
        return [_unquoted(w) for w in re.findall(r"""("[^"]*"|'[^']*'|[^\s,"']+)""", inner)]
    result, depth, i = [], 1, m.end()
    while i < len(body) and depth:
        c = body[i]
        if   c == "{": depth += 1
        elif c == "}": depth -= 1
        elif depth == 1:
            n = _NAME_RE.match(body, i)
            if n is not None:
                rest = body[n.end():].lstrip(" \t")
                if rest[:1] in ("{", "=", ":"): result.append(n.group(0))
                i = n.end()
                continue
        i += 1
    return result


#  -------------------------------------------------------------- DEAR

def _root_directory():
    """
    RETURN: str, the nearest directory at or above the current one that
            holds 'hwut-root.conf'.
            None, where none does.
    """
    here = os.getcwd()
    while True:
        if os.path.isfile(os.path.join(here, "hwut-root.conf")): return here
        parent = os.path.dirname(here)
        if parent == here: return None
        here = parent


def _labels(word):
    """
    RETURN: list[str], the labels that stand in the tree's
            'hwut-root.labels' -- and 'all', 'meta' -- that start with
            'word'.
    """
    name_set = set(STANDARD_LABEL_TUPLE)
    root = _root_directory()
    if root is not None:
        path = os.path.join(root, "hwut-root.labels")
        if os.path.isfile(path):
            with open(path, errors="replace") as fh:
                for line in fh:
                    if line.lstrip().startswith("#"): continue
                    _, sep, labels = line.rpartition(" : ")
                    if sep: name_set.update(labels.split())
    return _matching(name_set, word)


def _targets(word):
    """
    RETURN: list[str], the target names bound in the current
            directory's 'hwut.conf' ('target { <name> = ... }') that
            start with 'word'. The tree below is not walked: a walk is
            not a TAB's to pay.
    """
    if not os.path.isfile("hwut.conf"): return []
    with open("hwut.conf", errors="replace") as fh: text = fh.read()
    m = re.search(r"\btarget\s*\{", text)
    if m is None: return []
    result, depth, i = [], 1, m.end()
    while i < len(text) and depth:
        c = text[i]
        if   c == "{": depth += 1
        elif c == "}": depth -= 1
        elif c == "#":
            i = text.find("\n", i)
            if i < 0: break
            continue
        elif depth == 1:
            n = _NAME_RE.match(text, i)
            if n is not None:
                if text[n.end():].lstrip(" \t")[:1] in ("=", ":", "{"):
                    result.append(n.group(0))
                i = n.end()
                continue
        i += 1
    return _matching(result, word)


#  --------------------------------------------------------- rendering

def render(shell, word, candidate_list):
    """
    RETURN: str, the candidates in the rendering 'shell' reads, one per
            line, a newline after each.
            "", for no candidate or a shell not known.
    """
    if not candidate_list: return ""
    if shell == "bash":
        #  bash replaces only the part after its last word break.
        cut = max(word.rfind("="), word.rfind(":")) + 1
        line_list = [c[cut:] for c in candidate_list]
    elif shell == "zsh":
        line_list = [c.replace(":", "\\:") for c in candidate_list]
    elif shell == "powershell":
        line_list = ["%s\t%s" % (c, c) for c in candidate_list]
    else:
        return ""
    return "".join(x + "\n" for x in line_list)
