"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: AMENDING WHAT AN AUTHOR WROTE -- a header's '@hwut { }' or a
         'hwut.conf' -- by TEXT SURGERY, one entry or one scope at a time.
         The one implementation behind every face that writes into the
         author's files: 'hwut.config.ignore' (the 'ignore' list),
         'hwut.renovate' (hwut 1.0's words, the retired 'slash'), and the
         merge's keeping of a tried tolerance ('lib/accept/keep.py').

DESCRIPTION
       THE AUTHOR'S FILE STAYS THE AUTHOR'S (services E-48). What is not
       amended is left byte for byte: every other key, every comment, the
       layout. A file is never re-rendered from a parse tree -- a parser
       that round-trips comments and layout does not exist here, and a
       half-faithful one would be worse than none.

       A CONTAINER is the braces one amends inside: the header's region
       (the detector's, decoration and all -- X-DECORATION) or the conf's
       'hwut { }'. Entries are read at the container's top level; a
       SCOPE ('tolerance { ... }') is an entry whose value is an object,
       and scopes are found at any depth.

       WHAT A REWRITTEN SCOPE LOOKS LIKE: one line, 'key { a = 1  b = 2 }',
       in place of the old one. Comments INSIDE that scope are lost; the
       rest of the file is not touched. A scope left empty is removed,
       its line with it where nothing else stood there.

       A NEW LINE is written in the container's own lead: the decoration
       and indentation its first entry line shows ('#     ', 'REM   ',
       '-- |    '), so a header in any language stays that language. A
       container on one line takes the new entry on that line.

       THE VALUES ARE TEXT. An entry's value is carried as it was written
       -- a quoted string with its escapes, a list, an object -- and a
       value spanning lines is joined, its decorations dropped.
______________________________________________________________________________
"""
import re

from dataclasses import dataclass

from . import source_file_detector


@dataclass(frozen=True)
class Container:
    """The braces to amend inside."""
    i_open:     int     # index of '{'
    i_close:    int     # index of the matching '}'
    decoration: str     # what heads each line inside (a header's), or ''
    lead:       str     # what a NEW line inside is headed with


@dataclass(frozen=True)
class Entry:
    """One 'key = value' at one level of a container or scope."""
    key:     str
    i_key:   int        # where the key begins
    i_value: int        # where the value begins
    i_end:   int        # one past where the value ends
    object_f: bool      # the value is '{ ... }'


# ----------------------------------------------------------------- containers

def header_container(text):
    """
    RETURN: Container, the '@hwut { }' header of a source file's text.
            None, the text carries no header.
    """
    region = source_file_detector.detect(text)
    if region is None: return None
    decoration = getattr(region, "decoration", "")
    return Container(region.i_open, region.i_close, decoration,
                     _lead_of(text, region.i_open, region.i_close, decoration))


_CONF_RE = re.compile(r"^[ \t]*hwut\s*\{", re.M)


def conf_container(text):
    """
    RETURN: Container, the 'hwut { }' block of a 'hwut.conf' text.
            None, the text holds none.
    """
    match = _CONF_RE.search(text)
    if match is None: return None
    i_open  = match.end() - 1
    i_close = _matching(text, i_open, "")
    if i_close is None: return None
    return Container(i_open, i_close, "", "    ")


def _lead_of(text, i_open, i_close, decoration):
    """RETURN: str, what heads the container's first line with an entry
               -- its decoration and indentation, read the way the
               unwrapper reads them -- so a new line looks like its
               neighbours. The decoration and five blanks where no entry
               line stands; four blanks where there is no decoration."""
    from .unwrapper import _common_prefix
    line_list = text[i_open + 1:i_close].split("\n")[1:]
    content_list = [line for line in line_list if line.strip()]
    if decoration and content_list \
       and all(line.lstrip().startswith(decoration) for line in content_list):
        for line in content_list:
            stripped = line.lstrip()
            rest = stripped[len(decoration):]
            if rest.strip() and rest.strip()[0] not in "{}":
                return line[:len(line) - len(stripped)] + decoration \
                       + rest[:len(rest) - len(rest.lstrip())]
    elif content_list:
        prefix = _common_prefix(line_list)
        for line in content_list:
            rest = line[len(prefix):]
            if rest.strip() and rest.strip()[0] not in "{}":
                return prefix + rest[:len(rest) - len(rest.lstrip())]
    return (decoration + "     ") if decoration else "    "


# -------------------------------------------------------------------- reading

_KEY_RE = re.compile(r"[A-Za-z_][\w.+\-]*")


def entry_list(text, i_open, i_close, decoration=""):
    """
    RETURN: list[Entry], the entries directly inside the braces at
            'i_open'..'i_close', in order. A comment ('#' or '//' to the
            end of the line) and the DECORATION at a line's head are
            skipped; what cannot be read as an entry ends the reading.
    """
    result = []
    i = i_open + 1
    while True:
        i = _skip(text, i, i_close, decoration)
        if i >= i_close: break
        if text[i] == ",": i += 1; continue
        if text[i] == '"':
            end = _string_end(text, i)
            key, i_key, i = text[i + 1:end], i, end + 1
        else:
            match = _KEY_RE.match(text, i)
            if match is None: break
            key, i_key, i = match.group(0), i, match.end()
        while i < i_close and text[i] in " \t": i += 1
        if i < i_close and text[i] in "=:": i += 1
        while i < i_close and text[i] in " \t": i += 1
        if i >= i_close: break
        i_value = i
        if text[i] == "{":
            end = _matching(text, i, decoration)
            if end is None: break
            result.append(Entry(key, i_key, i_value, end + 1, True))
            i = end + 1
        elif text[i] == "[":
            end = _matching(text, i, decoration, "[", "]")
            if end is None: break
            result.append(Entry(key, i_key, i_value, end + 1, False))
            i = end + 1
        elif text[i] == '"':
            end = _string_end(text, i)
            result.append(Entry(key, i_key, i_value, end + 1, False))
            i = end + 1
        else:
            match = re.compile(r"[^\s,}#]+").match(text, i)
            if match is None: break
            result.append(Entry(key, i_key, i_value, match.end(), False))
            i = match.end()
    return result


def scope_list(text, container, name):
    """
    RETURN: list[Entry], every scope called 'name' inside the container,
            at any depth, in order.
    """
    result = []
    def walk(i_open, i_close):
        for entry in entry_list(text, i_open, i_close, container.decoration):
            if not entry.object_f: continue
            if entry.key == name: result.append(entry)
            else:                 walk(entry.i_value, entry.i_end - 1)
    walk(container.i_open, container.i_close)
    return result


def value_text(text, entry, decoration=""):
    """RETURN: str, the entry's value as written, on one line: a value
               spanning lines is joined, the decoration at each line's
               head dropped."""
    raw = text[entry.i_value:entry.i_end]
    if "\n" not in raw: return raw
    part_list = []
    for i, line in enumerate(raw.split("\n")):
        if i:
            line = line.lstrip()
            if decoration and line.startswith(decoration):
                line = line[len(decoration):].lstrip()
        part_list.append(line.strip() if i else line.rstrip())
    return " ".join(part for part in part_list if part)


def string_list_of(value):
    """RETURN: list[str], the quoted strings of a list value, AS WRITTEN
               (escapes kept); [] where it holds none."""
    return re.findall(r'"((?:[^"\\]|\\.)*)"', value)


# ------------------------------------------------------------------- amending

def scope_set(text, container, name, pair_list):
    """
    RETURN: str, 'text' with the container's top-level scope 'name'
            holding exactly 'pair_list' -- [(key, value text)] -- written
            on one line where the old scope stood, or added as a new line
            (a new entry, on a one-line container) where none stood. An
            empty 'pair_list' removes the scope.
    """
    for entry in entry_list(text, container.i_open, container.i_close,
                            container.decoration):
        if entry.key == name and entry.object_f:
            return scope_rewrite(text, container, entry, pair_list)
    if not pair_list: return text
    return entry_add(text, container, scope_text(name, pair_list))


def scope_rewrite(text, container, scope, pair_list):
    """RETURN: str, 'text' with 'scope' (an Entry) rewritten to hold
               'pair_list' on one line; removed where it is empty."""
    if not pair_list:
        return _cut(text, scope.i_key, scope.i_end, container.decoration)
    return text[:scope.i_key] + scope_text(scope.key, pair_list) \
           + text[scope.i_end:]


def scope_pair_list(text, container, scope):
    """RETURN: list[(key, value text)], what 'scope' holds, one line
               each value."""
    return [(entry.key, value_text(text, entry, container.decoration))
            for entry in entry_list(text, scope.i_value, scope.i_end - 1,
                                    container.decoration)]


def scope_text(name, pair_list):
    """RETURN: str, 'name { a = 1  b = 2 }'."""
    return "%s { %s }" % (name, "  ".join("%s = %s" % pair
                                           for pair in pair_list))


def entry_add(text, container, entry_line, first_f=False):
    """
    RETURN: str, 'text' with 'entry_line' ('key = value') added at the
            container's top level: on a line of its own, in the
            container's lead, before the closing brace -- or, under
            'first_f', right after the opening one; on a one-line
            container, before its closing brace on that line.
    """
    i_open, i_close = container.i_open, container.i_close
    if "\n" not in text[i_open:i_close]:
        return text[:i_close].rstrip(" ") + "  " + entry_line + " " \
               + text[i_close:]
    if first_f:
        return text[:i_open + 1] + "\n" + container.lead + entry_line \
               + text[i_open + 1:]
    line_i = text.rfind("\n", 0, i_close) + 1
    before = text[line_i:i_close]
    if before.strip(" \t" + container.decoration):
        #  THE BRACE CLOSES A LINE WITH CONTENT: the entry goes on a line
        #  of its own after it, before the brace.
        return text[:i_close].rstrip(" ") + "\n" + container.lead \
               + entry_line + "\n" + before[:len(before) - len(before.lstrip())] \
               + text[i_close:]
    return text[:line_i] + container.lead + entry_line + "\n" + text[line_i:]


def entry_remove(text, container, entry):
    """RETURN: str, 'text' without 'entry' -- its line with it where
               nothing else stood there."""
    return _cut(text, entry.i_key, entry.i_end, container.decoration)


def list_extend(text, container, key, item_list):
    """
    RETURN: str, 'text' with the quoted strings 'item_list' added to the
            top-level list 'key' where it stands, before its ']'; a new
            'key = [...]' as the container's FIRST entry where it does
            not. Items it holds already are not added twice.
    """
    for entry in entry_list(text, container.i_open, container.i_close,
                            container.decoration):
        if entry.key != key: continue
        have = set(string_list_of(text[entry.i_value:entry.i_end]))
        fresh = [item for item in item_list if item not in have]
        if not fresh: return text
        close_i = entry.i_end - 1
        return text[:close_i] + "".join(', "%s"' % item for item in fresh) \
               + text[close_i:]
    return entry_add(text, container, "%s = [%s]"
                     % (key, ", ".join('"%s"' % item for item in item_list)),
                     first_f=True)


# ----------------------------------------------------------------- the texture

def _skip(text, i, i_close, decoration):
    """RETURN: int, the first index at or after 'i' holding content:
               blanks, line breaks, the decoration at a line's head and
               comments passed over."""
    line_head_f = False
    while i < i_close:
        c = text[i]
        if c == "\n":
            i += 1; line_head_f = True
            continue
        if c in " \t":
            i += 1
            continue
        if line_head_f and decoration and text.startswith(decoration, i):
            i += len(decoration); line_head_f = False
            continue
        line_head_f = False
        if c == "#" or text.startswith("//", i):
            end = text.find("\n", i)
            i = i_close if end < 0 or end > i_close else end
            continue
        return i
    return i_close


def _string_end(text, i):
    """RETURN: int, the index of the quote closing the string at 'i'."""
    i += 1
    while i < len(text) and text[i] not in '"\n':
        if text[i] == "\\": i += 1
        i += 1
    return i


def _matching(text, i_open, decoration, open_c="{", close_c="}"):
    """RETURN: int, the index of the bracket closing the one at 'i_open';
               strings skipped, the decoration at a line's head skipped.
               None, no match."""
    depth, i, n = 0, i_open, len(text)
    while i < n:
        c = text[i]
        if c == "\n" and decoration:
            j = i + 1
            while j < n and text[j] in " \t": j += 1
            if text.startswith(decoration, j):
                i = j + len(decoration)
                continue
        if c == '"':
            i = _string_end(text, i)
        elif c == open_c:
            depth += 1
        elif c == close_c:
            depth -= 1
            if depth == 0: return i
        i += 1
    return None


def _cut(text, i_begin, i_end, decoration):
    """RETURN: str, 'text' without [i_begin, i_end) -- and without its
               line where nothing but blanks and the decoration remain
               there; else without the blanks before it."""
    line_begin = text.rfind("\n", 0, i_begin) + 1
    line_end   = text.find("\n", i_end)
    if line_end < 0: line_end = len(text)
    rest = text[line_begin:i_begin] + text[i_end:line_end]
    if not rest.strip(" \t" + decoration) and line_end < len(text):
        return text[:line_begin] + text[line_end + 1:]
    j = i_begin
    while j > line_begin and text[j - 1] in " \t": j -= 1
    if text[i_end:line_end].strip() == "" or text[i_end:i_end + 1] in " \t":
        return text[:j] + text[i_end:]
    return text[:j] + " " + text[i_end:]
