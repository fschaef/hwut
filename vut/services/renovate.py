"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE 'hwut.renovate' COMMAND LINE -- carry what hwut 1.0 said into
         what VUT 2.0 reads (B-7, todo-1). INITIAL VERSION.

    hwut.renovate [--directory=<path>] [--apply]

DESCRIPTION
       A TREE FROM hwut 1.0 states things in places VUT no longer reads.
       This face walks every TEST directory below the root, says what it
       WOULD change, and with '--apply' changes it. Without '--apply'
       nothing is written: the report IS the product, fit to read before
       a tree is touched.

       WHAT IT TRANSLATES, today:

           hwut-info.dat, line 1          -> 'title = "..."' in hwut.conf
                                             (X-INFO-DAT)
           hwut-info.dat, '--not <glob>'  -> 'ignore = [...]' in hwut.conf
                                             (disc-6 residue, R-73)
           in a header or hwut.conf:
               numeric        = <ratio>   -> tolerance { numeric_ratio }
               whitespace_eqv = <bool>    -> tolerance { whitespace }
               slash_eqv      = <bool>    -> tolerance { slash }
                                             (the three old keys were
                                             REMOVED, not aliased)

       WHAT IT LEAVES: a key the directory already states is never
       overwritten -- the newer word stands, and the relic's is reported
       as 'kept'. The relic file itself is not deleted: the person
       deletes it once the report reads clean. Anything else the relic
       says (hwut 1.0's coverage directives) is reported as 'unknown'
       and left to the author.

       WHAT IT DOES NOT DO YET (owed, B-7): enter the books as
       'hwut.accept' does; the stderr survey (C-6); and it has not been
       developed against the real quex project, which is where the
       ruling says it must be proven.

    RETURN (exit status): OK where nothing needs renovating or
       everything asked for was applied; EMPTY where the walk found no
       TEST directory; FAULT where a write failed.
______________________________________________________________________________
"""
import os
import re
import sys

from   vut.engine.orchestrator.exploration.tree_explorer import (RootConfMissing,
                                                                 explore_tree)
from   vut.engine.orchestrator.exploration               import finder
from   ._exit                                            import E_ExitCode
from   vut.services.lib.cmdline import (face_parser, usage_of,
                                        parse_or_refuse)
from   vut.services.lib.face    import Refused, Empty, answered
from   dataclasses import dataclass

PARSER = face_parser("hwut.renovate",
                     "Carry what hwut 1.0 said into what VUT 2.0 reads.",
                     wish_f=False)
PARSER.add_argument("--directory", default=None,
                    help="the root to walk (default: the current directory)")
PARSER.add_argument("--apply", action="store_true",
                    help="write the changes; without it, report only")
ARG_DB = {"--directory": True}
USAGE  = usage_of(PARSER, ARG_DB)

RELIC_NAME = "hwut-info.dat"

#  THE OLD TOLERANCE KEYS and their new home (exploration RATIONALE, the
#  tolerance entry): one spelling for one thing.
OLD_KEY_DB = {"numeric":        "numeric_ratio",
              "whitespace_eqv": "whitespace",
              "slash_eqv":      "slash"}
#  An old key is a WORD followed by '=' and a value that runs to the
#  next blank, '}' or line end -- a 1.0 header states several on one
#  line ('numeric = 0.01  whitespace_eqv = yes').
_OLD_KEY_RE = re.compile(r"(?<![\w.])(numeric|whitespace_eqv|slash_eqv)"
                         r"(\s*=\s*)([^\s}#]+)")


@dataclass(frozen=True)
class Request:
    """WHAT WAS ASKED of 'hwut.renovate' (E-101)."""
    directory: str  = "."
    apply_f:   bool = False


@dataclass(frozen=True)
class Change:
    """One thing renovate did, or would do, to one file."""
    said:      str
    applied_f: bool = False
    fault:     str | None = None


@dataclass(frozen=True)
class Block:
    """One directory's news: its notes and its changes."""
    directory:    str
    note_tuple:   tuple = ()
    change_tuple: tuple = ()      # of Change


@dataclass(frozen=True)
class Result:
    """WHAT HAPPENED, directory by directory."""
    root:         str   = "."
    apply_f:      bool  = False
    block_tuple:  tuple = ()      # of Block
    change_n:     int   = 0
    fault_f:      bool  = False


def do(request):
    """
    RETURN: Result, what every TEST directory below the root needs --
            and, under 'apply_f', what was written.

    RAISES: Refused, where the directory does not stand or no root conf
            is above it; Empty, where no TEST directory stands below it.

    IT NEVER PRINTS (E-101). '--apply' is a FIELD OF THE REQUEST, not a
    decision of the caller's: a reader asks for the report, a writer
    asks for the writing, and both get the same record back.
    """
    root = request.directory or "."
    if not os.path.isdir(root):
        raise Refused("REFUSED: the directory '%s' does not exist" % root)
    try:
        tree = explore_tree(root)
    except RootConfMissing as error:
        raise Refused("REFUSED: %s" % error) from error
    directory_list = [directory for directory, _ in tree]
    if not directory_list:
        raise Empty("EMPTY: no TEST directory below '%s'" % root)

    block_list, change_n, fault_f = [], 0, False
    for directory in directory_list:
        plan = plan_of(os.path.join(root, directory))
        if not plan.change_list and not plan.note_list: continue
        change_list = []
        for change in plan.change_list:
            change_n += 1
            applied_f, fault = False, None
            if request.apply_f:
                try:
                    change.apply()
                    applied_f = True
                except OSError as error:
                    fault, fault_f = str(error), True
            change_list.append(Change(change.said, applied_f, fault))
        block_list.append(Block(directory, tuple(plan.note_list),
                                tuple(change_list)))
    return Result(root=root, apply_f=request.apply_f,
                  block_tuple=tuple(block_list), change_n=change_n,
                  fault_f=fault_f)


def printed(result, write):
    """RETURN: E_ExitCode. The page 'hwut.renovate' has always written."""
    for block in result.block_tuple:
        write("%s" % block.directory)
        for line in block.note_tuple: write("    %s" % line)
        for change in block.change_tuple:
            write("    %s" % change.said)
            if change.fault is not None: write("        FAULT: %s" % change.fault)
            elif change.applied_f:       write("        applied")
    if result.change_n == 0:
        write("nothing to renovate below '%s'" % result.root)
    elif not result.apply_f:
        write("")
        write("%i change(s) reported, none written: '--apply' writes them."
              % result.change_n)
    return E_ExitCode.FAULT if result.fault_f else E_ExitCode.OK


def main(argv=None, write=None):
    """
    RETURN: E_ExitCode, per the module purpose.
    """
    if write is None: write = print
    if argv is None:  argv  = sys.argv[1:]
    if "--help" in argv:
        write(USAGE)
        write("")
        body = __doc__.split("\n")
        body = [l for l in body if not l.startswith("SPDX") and not l.startswith("_")]
        write("\n".join(body).strip("\n"))
        return E_ExitCode.OK
    arguments, completion_f = parse_or_refuse(PARSER, argv, write, ARG_DB)
    if completion_f:      return E_ExitCode.OK
    if arguments is None:
        write(USAGE)
        return E_ExitCode.REFUSED
    return answered(do, Request(directory=arguments.directory or ".",
                                apply_f=arguments.apply), write, printed)


    return status


class _Step:
    """One thing renovate would do to one file: what to say, and the
    callable that does it. 'plan_of' builds these; 'do' turns each into
    the record 'Change'."""

    def __init__(self, said, apply):
        """RETURN: _Step, 'said' the line the report prints, 'apply'
                   the callable that does it."""
        self.said, self.apply = said, apply


class Plan:
    """What one directory needs."""

    def __init__(self):
        self.change_list = []
        self.note_list   = []


def plan_of(directory):
    """
    RETURN: Plan, what 'directory' needs: the relic's title and ignore
            globs carried into 'hwut.conf' where the conf does not
            already state them, the old tolerance keys rewritten in the
            conf and in every header, and notes on what is kept or
            unknown.
    """
    plan      = Plan()
    conf_path = os.path.join(directory, finder.CONF_NAME)
    conf_text = _read(conf_path)
    relic     = _relic_of(os.path.join(directory, RELIC_NAME))
    if relic is not None:
        title, ignore_list, unknown_list = relic
        if title:
            if _conf_states(conf_text, "title"):
                plan.note_list.append("kept: 'title' already stands in "
                                      "hwut.conf; the relic's is ignored")
            else:
                plan.change_list.append(_Step(
                    "hwut.conf: title = %r  (from %s)" % (title, RELIC_NAME),
                    lambda p=conf_path, t=title: _conf_add(p, "title = %s"
                                                           % _quoted(t))))
        if ignore_list:
            if _conf_states(conf_text, "ignore"):
                plan.note_list.append("kept: 'ignore' already stands in "
                                      "hwut.conf; the relic's '--not' lines "
                                      "are ignored")
            else:
                plan.change_list.append(_Step(
                    "hwut.conf: ignore = [%s]  (from %s '--not')"
                    % (", ".join(_quoted(g) for g in ignore_list), RELIC_NAME),
                    lambda p=conf_path, gs=ignore_list: _conf_add(
                        p, "ignore = [%s]" % ", ".join(_quoted(g) for g in gs))))
        for line in unknown_list:
            plan.note_list.append("unknown in %s, left to you: %r"
                                  % (RELIC_NAME, line))

    #  THE OLD TOLERANCE KEYS, in the conf and in every header.
    for name in sorted(os.listdir(directory)):
        path = os.path.join(directory, name)
        if not os.path.isfile(path): continue
        if name != finder.CONF_NAME and name in finder.OWN_FILE_TUPLE: continue
        if name.startswith("."): continue
        text = _read(path)
        if text is None: continue
        hit_list = _old_key_hits(text)
        if not hit_list: continue
        #  IN THE CONF the old keys stood at the ROOT, directory-wide;
        #  the root carries directory keys only, so the tolerance goes
        #  under 'default_app', which is what 'directory-wide' means now.
        conf_f = (name == finder.CONF_NAME)
        home   = "default_app { tolerance { %s } }" if conf_f else "tolerance { %s }"
        plan.change_list.append(_Step(
            "%s: %s -> %s" % (
                name,
                ", ".join("%s = %s" % (k, v) for k, v in hit_list),
                home % ", ".join("%s = %s" % (OLD_KEY_DB[k], v) for k, v in hit_list)),
            lambda p=path, c=conf_f: _rewrite_old_keys(p, conf_f=c)))
    return plan


def _relic_of(path):
    """RETURN: (title, ignore_list, unknown_list) read from an
               'hwut-info.dat'; None where none stands."""
    text = _read(path)
    if text is None: return None
    line_list = text.splitlines()
    title = ""
    for line in line_list:
        if line.strip():
            title = line.strip(); break
    ignore_list, unknown_list = [], []
    seen_title, seen_rule = False, False
    for line in line_list:
        stripped = line.strip()
        if not stripped: continue
        if not seen_title and stripped == title:
            seen_title = True; continue
        if seen_title and not seen_rule and re.fullmatch(r"-{3,}", stripped):
            seen_rule = True; continue
        if stripped.startswith("--not "):
            ignore_list.append(stripped[len("--not "):].strip())
        else:
            unknown_list.append(stripped)
    return title, ignore_list, unknown_list


def _old_key_hits(text):
    """RETURN: list[(old key, value)], every old tolerance key stated
               in 'text' -- inside a header comment line as well as on
               a conf line; text after a '#' that is NOT a header lead
               is a comment and not searched."""
    result = []
    for line in text.splitlines():
        result.extend((m.group(1), m.group(3))
                      for m in _OLD_KEY_RE.finditer(_code_of(line)))
    return result


def _code_of(line):
    """RETURN: str, the part of 'line' a key may stand in: the whole
               line where its first non-blank is '#' (a header line in
               a script), else the part before any '#'."""
    stripped = line.lstrip()
    if stripped.startswith("#"): return stripped[1:]
    return line.split("#", 1)[0]


def _rewrite_old_keys(path, conf_f=False):
    """RETURN: None. Every old tolerance key in the file rewritten as
               its new spelling inside 'tolerance { }', in place, on
               the line where it stood -- inside 'default_app { }' too
               where the file is the conf ('conf_f')."""
    text = _read(path)
    out  = []
    for line in text.splitlines(True):
        body = line.rstrip("\n")
        code = _code_of(body)
        if not _OLD_KEY_RE.search(code):
            out.append(line); continue
        #  ONE BLOCK PER LINE: the keys of a line gather into a single
        #  'tolerance { }' where the first stood; the others vanish.
        hit_list = list(_OLD_KEY_RE.finditer(code))
        block = "tolerance { %s }" % "  ".join(
            "%s = %s" % (OLD_KEY_DB[m.group(1)], m.group(3)) for m in hit_list)
        if conf_f: block = "default_app { %s }" % block
        lead0 = code[:len(code) - len(code.lstrip())]
        new = lead0 + code[len(lead0):hit_list[0].start()] + block
        cursor = hit_list[0].end()
        for m in hit_list[1:]:
            gap = code[cursor:m.start()]
            new += gap.rstrip() if gap.strip() else ""
            cursor = m.end()
        new += code[cursor:]
        new = lead0 + re.sub(r"[ \t]{3,}", "  ", new[len(lead0):])
        if body.lstrip().startswith("#"):
            lead = body[:len(body) - len(body.lstrip())] + "#"
            out.append(lead + new + "\n")
        else:
            tail = body[len(code):]
            out.append(new + tail + "\n")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("".join(out))


def _conf_states(conf_text, key):
    """RETURN: bool, True where 'hwut.conf' states 'key' at its root."""
    if conf_text is None: return False
    return re.search(r"^\s*%s\s*=" % re.escape(key), conf_text, re.M) is not None


def _conf_add(path, line):
    """RETURN: None. 'line' added inside the 'hwut { }' block of the
               conf at 'path' -- the file created around it where none
               stands."""
    text = _read(path)
    if text is None:
        text = "hwut {\n}\n"
    i = text.find("hwut {")
    if i < 0:
        text = "hwut {\n    %s\n}\n%s" % (line, text)
    else:
        i += len("hwut {")
        text = text[:i] + "\n    " + line + text[i:]
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def _read(path):
    """RETURN: str, the file's text; None where it cannot be read."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return None


def _quoted(text):
    """RETURN: str, 'text' as a HOCON string literal."""
    return '"%s"' % text.replace("\\", "\\\\").replace('"', '\\"')


if __name__ == "__main__":
    from ._exit import guarded
    sys.exit(guarded("hwut.renovate", main, sys.argv[1:]))
