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
               slash_eqv      = true      -> tolerance { eq_pattern =
                                                 ["[\\\\/]+"] }
               slash_eqv      = false     -> nothing: '/' and '\\'
                                             differ unless a pattern
                                             says otherwise
                                             (the three old keys were
                                             REMOVED, not aliased)
           in any 'tolerance { }', VUT 2.0's own retired word:
               slash = true               -> eq_pattern gains "[\\\\/]+"
               slash = false              -> removed (compare C-18)

       THE AMENDING IS 'exploration/amend.py''s: every other key, comment
       and line of the file stays as it was; a scope that changes is
       rewritten on one line.

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
from   vut.engine.orchestrator.exploration               import amend
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
              "slash_eqv":      "eq_pattern"}

#  THE SLASH EQUIVALENCE AS A PATTERN (compare C-18), as a header writes
#  it: the regex [\\/]+ in a HOCON string.
SLASH_PATTERN = '"[\\\\\\\\/]+"'


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
        from vut.services._core import man_page
        body = __doc__.split("\n")
        body = [l for l in body if not l.startswith("SPDX") and not l.startswith("_")]
        write(man_page("hwut.renovate", "\n".join(body).strip("\n"),
                       usage=USAGE))
        return E_ExitCode.OK
    arguments, completion_f = parse_or_refuse(PARSER, argv, write, ARG_DB)
    if completion_f:      return E_ExitCode.OK
    if arguments is None:
        write(USAGE)
        return E_ExitCode.REFUSED
    return answered(do, Request(directory=arguments.directory or ".",
                                apply_f=arguments.apply), write, printed)


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

    #  THE OLD TOLERANCE KEYS, in the conf and in every header; and the
    #  retired 'slash' inside any 'tolerance { }'.
    for name in sorted(os.listdir(directory)):
        path = os.path.join(directory, name)
        if not os.path.isfile(path): continue
        if name != finder.CONF_NAME and name in finder.OWN_FILE_TUPLE: continue
        if name.startswith("."): continue
        text = _read(path)
        if text is None: continue
        conf_f = (name == finder.CONF_NAME)
        said = _tolerance_said(text, conf_f)
        if not said: continue
        plan.change_list.append(_Step(
            "%s: %s" % (name, said),
            lambda p=path, c=conf_f: _write(p, _renovated(_read(p), c))))
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


def _container(text, conf_f):
    """RETURN: amend.Container, the conf's 'hwut { }' or the header's
               '@hwut { }'; None where the text holds neither."""
    return amend.conf_container(text) if conf_f else amend.header_container(text)


def _old_entries(text, container):
    """RETURN: list[amend.Entry], hwut 1.0's tolerance keys standing at
               the container's top level."""
    return [entry for entry in amend.entry_list(text, container.i_open,
                                                container.i_close,
                                                container.decoration)
            if entry.key in OLD_KEY_DB]


def _slash_scopes(text, container):
    """RETURN: list[amend.Entry], every 'tolerance { }' stating 'slash'."""
    return [scope for scope in amend.scope_list(text, container, "tolerance")
            if any(key == "slash" for key, _ in
                   amend.scope_pair_list(text, container, scope))]


def _true_f(value):
    """RETURN: bool, True where a boolean's text says yes."""
    return value.strip().strip('"').lower() in ("true", "yes", "on", "1")


def _new_pair(key, value):
    """RETURN: (key, value text), hwut 1.0's key in VUT 2.0's word.
               None, where the word says nothing any more ('slash_eqv =
               false')."""
    if key == "slash_eqv":
        return ("eq_pattern", "[%s]" % SLASH_PATTERN) if _true_f(value) else None
    return (OLD_KEY_DB[key], value)


def _merged(pair_list, new_pair_list):
    """RETURN: list[(key, value text)], 'pair_list' with 'new_pair_list'
               added: a key it states already stands (the newer word),
               except 'eq_pattern', whose patterns are joined."""
    result = list(pair_list)
    for key, value in new_pair_list:
        i = next((i for i, (k, _) in enumerate(result) if k == key), None)
        if i is None:
            result.append((key, value))
        elif key == "eq_pattern":
            have = amend.string_list_of(result[i][1])
            fresh = [s for s in amend.string_list_of(value) if s not in have]
            result[i] = (key, "[%s]" % ", ".join('"%s"' % s for s in have + fresh))
    return result


def _without_slash(pair_list):
    """RETURN: list[(key, value text)], a scope's pairs with 'slash'
               retired: gone, and where it said yes, the pattern added."""
    slash = [value for key, value in pair_list if key == "slash"]
    rest  = [(key, value) for key, value in pair_list if key != "slash"]
    if slash and _true_f(slash[-1]):
        return _merged(rest, [("eq_pattern", "[%s]" % SLASH_PATTERN)])
    return rest


def _tolerance_said(text, conf_f):
    """RETURN: str, what renovating the text's tolerance words does, as
               the report says it; '' where nothing needs it."""
    container = _container(text, conf_f)
    if container is None: return ""
    part_list = []
    old_list = _old_entries(text, container)
    if old_list:
        old_pair_list = [(e.key, amend.value_text(text, e, container.decoration))
                         for e in old_list]
        new_list = [pair for pair in (_new_pair(k, v) for k, v in old_pair_list)
                    if pair is not None]
        home = "app_defaults { tolerance { %s } }" if conf_f else "tolerance { %s }"
        part_list.append("%s -> %s" % (
            ", ".join("%s = %s" % pair for pair in old_pair_list),
            home % ", ".join("%s = %s" % pair for pair in new_list)
            if new_list else "nothing: '/' and '\\' differ unless a pattern "
                             "says otherwise"))
    for scope in _slash_scopes(text, container):
        pair_list = amend.scope_pair_list(text, container, scope)
        value = [v for k, v in pair_list if k == "slash"][-1]
        part_list.append("tolerance { slash = %s } -> %s" % (
            value, "eq_pattern gains %s" % SLASH_PATTERN if _true_f(value)
                   else "removed"))
    return "; ".join(part_list)


def _renovated(text, conf_f):
    """RETURN: str, 'text' with its tolerance words renovated: every
               'slash' retired, hwut 1.0's keys taken out of the top
               level and stated in the tolerance scope -- the header's,
               or under the conf's 'app_defaults'."""
    container = _container(text, conf_f)
    for scope in reversed(_slash_scopes(text, container)):
        text = amend.scope_rewrite(
                   text, container, scope,
                   _without_slash(amend.scope_pair_list(text, container, scope)))
        container = _container(text, conf_f)

    old_list = _old_entries(text, container)
    if not old_list: return text
    new_list = [pair for pair in
                (_new_pair(e.key, amend.value_text(text, e, container.decoration))
                 for e in old_list) if pair is not None]
    for entry in reversed(old_list):
        text = amend.entry_remove(text, container, entry)
        container = _container(text, conf_f)
    if not new_list: return text
    if not conf_f:
        scope = _top_scope(text, container, "tolerance")
        present = amend.scope_pair_list(text, container, scope) if scope else []
        return amend.scope_set(text, container, "tolerance",
                               _merged(present, new_list))
    home = _top_scope(text, container, "app_defaults")
    if home is None:
        return amend.entry_add(text, container, "app_defaults { %s }"
                               % amend.scope_text("tolerance", new_list))
    inner = amend.Container(home.i_value, home.i_end - 1, "",
                            container.lead + "    ")
    scope = _top_scope(text, inner, "tolerance")
    present = amend.scope_pair_list(text, inner, scope) if scope else []
    return amend.scope_set(text, inner, "tolerance", _merged(present, new_list))


def _top_scope(text, container, name):
    """RETURN: amend.Entry, the container's top-level scope 'name'; None
               where it states none."""
    return next((entry for entry in amend.entry_list(text, container.i_open,
                                                     container.i_close,
                                                     container.decoration)
                 if entry.key == name and entry.object_f), None)


def _write(path, text):
    """RETURN: None. 'text' is the file at 'path' now."""
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def _conf_states(conf_text, key):
    """RETURN: bool, True where 'hwut.conf' states 'key' at its root."""
    if conf_text is None: return False
    return re.search(r"^\s*%s\s*=" % re.escape(key), conf_text, re.M) is not None


def _conf_add(path, line):
    """RETURN: None. 'line' added as the first entry inside the 'hwut { }'
               block of the conf at 'path' -- the file created around it
               where none stands."""
    text = _read(path)
    if text is None:
        text = "hwut {\n}\n"
    container = amend.conf_container(text)
    if container is None:
        text = "hwut {\n    %s\n}\n%s" % (line, text)
    else:
        text = amend.entry_add(text, container, line, first_f=True)
    _write(path, text)


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
