"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: A LINKED NOMINAL -- 'GOOD/<key>.link' IN PLACE OF 'GOOD/<key>.txt'
         (ruled 2026-10-30, bookkeeper B-32).

A '.link' file holds ONE line: the path of another case's '.txt' nominal,
relative to the GOOD/ directory the link stands in. The case is then held
against that file, as if it stood in its own place:

    GOOD/test-b.sh--y.link        ../../world/TEST/GOOD/test-a.sh--x.txt

THE RULES, each refused by name where broken:

    a link names a '.txt'       never another '.link' -- no chains, no
                                circles, one step from a case to its text
    a link stays inside ONE ROOT
                                the 'hwut-root.conf' that bounds the link
                                bounds its target too: a bubble is closed
                                (E-200), and a link may not reach out of it
    a case has ONE nominal      a '.txt' and a '.link' of one key never
                                stand together
    only stdout links           the '.txt' subject; every other subject
                                keeps its own file

NOT A SYMLINK, on purpose: a text file reads alike on every platform and
under every checkout, and a writer that opens a symlink writes through it
without a word. Here a writer ASKS ('link_path_of') and refuses.

THE OWN NAME STAYS THE OWN NAME. 'Bookkeeper.nominal_path' keeps answering
'GOOD/<key>.txt' -- what a writer, a mover and a remover act on. Only a
READER resolves ('nominal_resolved'), so nothing that writes, moves or
removes can reach a link's target by accident.
______________________________________________________________________________
"""
import os
from   pathlib import Path

from ...auxiliary.no_entry import OUT_DIRECTORY_NAME

ROOT_CONF_NAME = "hwut-root.conf"
LINK_SUFFIX    = "link"
TEXT_SUFFIX    = "txt"

#  What the walk for links never enters: the run's products, the
#  framework's scratch, version control.
_SKIP_DIRECTORY_SET = frozenset((OUT_DIRECTORY_NAME, "TMP", ".git",
                                 "__pycache__"))


class LinkFault(Exception):
    """A '.link' that cannot be followed; the message says why, by name."""


class NominalLinked(Exception):
    """A writer met a '.link' in its key's place. 'link' is its path,
    'target_text' what it names (or why it names nothing)."""

    def __init__(self, link):
        self.link = Path(link)
        try:
            self.target_text = os.path.relpath(str(link_target(self.link)))
        except LinkFault as fault:
            self.target_text = "(%s)" % fault
        super().__init__("'%s' links '%s' -- writing would change that "
                         "GOOD" % (os.path.relpath(str(self.link)),
                                   self.target_text))


def _said(path):
    """RETURN: str, 'path' from where hwut was called -- every message
               names a file the way the caller typed toward it."""
    return os.path.relpath(os.path.abspath(str(path)))


def link_path_of(nominal_path):
    """
    RETURN: Path, the '.link' that stands IN PLACE OF the '.txt' nominal
                  'nominal_path' -- 'GOOD/x--c.txt' -> 'GOOD/x--c.link'.
            None, where no such file stands, or 'nominal_path' is no
                  '.txt' (only stdout links).
    """
    path = Path(nominal_path)
    if path.suffix != "." + TEXT_SUFFIX: return None
    link = path.with_suffix("." + LINK_SUFFIX)
    return link if link.is_file() else None


def text_path_of(link_path):
    """
    RETURN: Path, the '.txt' name the link 'link_path' stands in place of
            -- 'GOOD/x--c.link' -> 'GOOD/x--c.txt'.
    """
    return Path(link_path).with_suffix("." + TEXT_SUFFIX)


def root_of(directory):
    """
    RETURN: str, the absolute directory holding the 'hwut-root.conf' that
                 bounds 'directory' -- the innermost one at or above it.
            None, where none stands.
    """
    here = os.path.abspath(str(directory))
    while True:
        if os.path.isfile(os.path.join(here, ROOT_CONF_NAME)): return here
        parent = os.path.dirname(here)
        if parent == here: return None
        here = parent


def link_target(link_path):
    """
    RETURN: Path, the '.txt' the link 'link_path' names, normalised
            (no '..' left), where every rule holds.

    Raises LinkFault, naming the rule broken: unreadable, empty, absolute,
    not a '.txt', beyond the root, absent, or the link's own case.
    """
    link = Path(link_path)
    said = _said(link)
    try:
        line_list = [line.strip() for line in
                     link.read_text(encoding="utf-8").splitlines()]
    except (OSError, UnicodeDecodeError) as error:
        raise LinkFault("'%s' cannot be read -- %s" % (said, error)) from None
    line_list = [line for line in line_list if line]
    if len(line_list) != 1:
        raise LinkFault("'%s' holds %s -- a link holds one path"
                        % (said, "nothing" if not line_list
                                 else "%d lines" % len(line_list)))
    text = line_list[0]
    if os.path.isabs(text):
        raise LinkFault("'%s' names an absolute path '%s' -- a link is "
                        "relative to its GOOD/" % (said, text))
    if not text.endswith("." + TEXT_SUFFIX):
        raise LinkFault("'%s' names '%s' -- a link names a '.%s', never "
                        "another link" % (said, text, TEXT_SUFFIX))
    target = Path(os.path.normpath(os.path.join(
                 os.path.abspath(str(link.parent)), text)))
    fault = boundary_fault(link.parent, target.parent)
    if fault: raise LinkFault("'%s' -> '%s': %s" % (said, text, fault))
    if target == Path(os.path.abspath(str(text_path_of(link)))):
        raise LinkFault("'%s' names its own case" % said)
    if not target.is_file():
        raise LinkFault("'%s' -> '%s': no such file" % (said, text))
    return target


def boundary_fault(link_directory, target_directory):
    """
    RETURN: str, why a link in 'link_directory' may not name a file in
                 'target_directory': no root bounds one of them, or two
                 different roots do.
            None, where one root bounds both.
    """
    link_root, target_root = root_of(link_directory), root_of(target_directory)
    if link_root is None:
        return "no '%s' bounds the link" % ROOT_CONF_NAME
    if target_root != link_root:
        return "the target stands beyond the link's root '%s'" \
               % os.path.normpath(os.path.join(os.path.relpath(link_root),
                                               ROOT_CONF_NAME))
    return None


def nominal_resolved(nominal_path):
    """
    RETURN: Path, the file a READER opens for the '.txt' nominal
            'nominal_path': the file itself where it stands; the link's
            target where a '.link' stands in its place; 'nominal_path'
            unchanged where neither does (the reader then finds nothing).

    Raises LinkFault where a '.link' stands and cannot be followed.
    """
    path = Path(nominal_path)
    if path.exists(): return path
    link = link_path_of(path)
    if link is None: return path
    return link_target(link)


def link_text(link_directory, target):
    """
    RETURN: str, what a link in 'link_directory' holds to name 'target':
            the relative path, '/' between, one line.
    """
    relative = os.path.relpath(os.path.abspath(str(target)),
                               os.path.abspath(str(link_directory)))
    return relative.replace(os.sep, "/") + "\n"


def write_link(link_path, target):
    """
    RETURN: None. 'link_path' holds the path of 'target', relative to its
            GOOD/. The caller has checked the rules; the boundary is
            checked again here, since a link beyond its root must never
            be written.

    Raises LinkFault where the boundary forbids it.
    """
    link = Path(link_path)
    fault = boundary_fault(link.parent, Path(target).parent)
    if fault: raise LinkFault("'%s' -> '%s': %s"
                              % (_said(link), _said(target), fault))
    link.write_text(link_text(link.parent, target), encoding="utf-8")


def link_tuple(root):
    """
    RETURN: tuple[Path], every 'GOOD/*.link' under 'root', sorted -- the
            walk stops at an inner 'hwut-root.conf', since no link crosses
            a root, and never enters 'OUT/', 'TMP/' or '.git/'.
    """
    found_list = []
    root = os.path.abspath(str(root))
    for here, dir_list, file_list in os.walk(root):
        dir_list[:] = sorted(d for d in dir_list
                             if d not in _SKIP_DIRECTORY_SET
                             and not os.path.isfile(
                                 os.path.join(here, d, ROOT_CONF_NAME)))
        if os.path.basename(here) != "GOOD": continue
        found_list.extend(Path(here) / name for name in sorted(file_list)
                          if name.endswith("." + LINK_SUFFIX))
    return tuple(found_list)


def links_to(target, root=None):
    """
    RETURN: tuple[Path], every '.link' within the root of 'target' (or
            'root', where given) that names 'target'. A link that cannot
            be followed names nothing and is left out.
    """
    target = Path(os.path.normpath(os.path.abspath(str(target))))
    root   = root if root is not None else root_of(target.parent)
    if root is None: return ()
    hit_list = []
    for link in link_tuple(root):
        try:
            followed = link_target(link)
        except LinkFault:
            continue
        if Path(os.path.normpath(os.path.abspath(str(followed)))) == target:
            hit_list.append(link)
    return tuple(hit_list)
