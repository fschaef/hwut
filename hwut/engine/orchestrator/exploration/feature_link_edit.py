"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE LINKS OF THE TEST HEADERS, rewritten -- 'features = [...]'
         in a test's '@hwut { }' block (spec 43 section 5, T-d): what
         'hwut.features.rename' changes besides the three feature files.

    links_mapped(text, map_f)          -> str   one source, every link
    links_planned(root, map_f)         -> dict  source path -> new text
    links_written(root, plan_db)       -> list  one line per file written
    write_atomic(path, text)

Only the quoted words inside a 'features = [...]' of the header are
touched, every other byte stays.
______________________________________________________________________________
"""
import os
import re

from . import amend

_LINK_LIST_RE = re.compile(r"\bfeatures\s*=\s*\[[^\]]*\]", re.DOTALL)
_QUOTED_RE    = re.compile(r'"([^"]*)"')


def write_atomic(path, text):
    """RETURN: None. 'text' written to 'path' through a temporary file
    beside it, renamed over it; the mode of a file that stood is kept."""
    mode      = os.stat(path).st_mode if os.path.exists(path) else None
    temporary = path + ".tmp-%d" % os.getpid()
    with open(temporary, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.replace(temporary, path)
    if mode is not None: os.chmod(path, mode)


def links_mapped(text, map_f):
    """
    RETURN: str, the source 'text' with every quoted link inside a
            'features = [...]' of its '@hwut { }' header replaced by
            'map_f(link)' where that is not None -- the rest byte for
            byte; 'text' itself where it has no header.
    """
    container = amend.header_container(text)
    if container is None: return text

    def quoted(match):
        found = map_f(match.group(1))
        return match.group(0) if found is None else '"%s"' % found

    head = text[container.i_open:container.i_close]
    head = _LINK_LIST_RE.sub(lambda m: _QUOTED_RE.sub(quoted, m.group(0)),
                             head)
    return text[:container.i_open] + head + text[container.i_close:]


def links_planned(root, map_f, bubble_gate=None):
    """
    RETURN: dict, source path -> its new text: every test application of
            the tree below 'root' whose header 'links_mapped' changes --
            the bubbles below walked as 'bubble_gate' says
            ('tree_explorer.explore_tree_stream'). Nothing is written.
    """
    from .tree_explorer import explore_tree_stream
    plan_db = {}
    for relative, result in explore_tree_stream(root, boundary_f=False,
                                                bubble_gate=bubble_gate):
        directory = os.path.normpath(os.path.join(root, relative))
        for app in sorted(result.app_set, key=lambda a: a.source_file):
            source = os.path.join(directory, app.source_file)
            try:
                with open(source, encoding="utf-8") as fh: before = fh.read()
            except (OSError, UnicodeDecodeError):
                continue
            after = links_mapped(before, map_f)
            if after != before: plan_db[source] = after
    return plan_db


def links_written(root, plan_db):
    """RETURN: list of str, one '    link renamed in <file>' line per file
    of 'plan_db' (path -> text), each written, its mode kept; the paths
    relative to 'root'."""
    line_list = []
    for source in sorted(plan_db):
        write_atomic(source, plan_db[source])
        line_list.append("    link renamed in %s"
                         % os.path.relpath(source, root).replace(os.sep, "/"))
    return line_list
