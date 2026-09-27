"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: KEEPING A TRIED TOLERANCE (intend 21, 2.7) -- the question asked
         when a merge ends with the tolerance in memory changed, and the
         two ways of keeping it.

    tolerances were changed in memory for 'test.sh one':
        tolerance { numeric_ratio = 0.047 }
      (1) store them in TMP/test.sh--one.tolerance.conf
      (2) enter them into test.sh, where its other configuration stands
      (3) omit them
    keep? [1/2/3]

DESCRIPTION
       ON COMMIT all three; ON CANCEL (1) or (3) -- a cancelled session
       does not edit the page (ruled: "ask write or cancel changes upon
       cancellation").

       (1) THE TMP FILE is deletable ground and never a wallflower. It
       holds the one line a header needs and, below it, the whole scope
       as the pane showed it, so the author may paste either.

       (2) INTO THE SOURCE. The '@hwut { }' header's own 'tolerance'
       scope is replaced where one stands; else the line is added
       before the header's closing brace, in the header's comment lead.
       Only that scope is touched: every other key, every comment, the
       layout stay (E-48's rule for 'hwut.config.ignore', and its
       graveyard for the header lifted for this one scope by the ruling
       of intend 21). IT TRIES, and it refuses by name -- writing (1)
       instead, so the work is not lost -- where the file carries no
       header (the test is named under 'apps' in 'hwut.conf'), where
       the choice states its own 'tolerance' (the header's would not
       reach it), and where the file read back by the exploration's own
       reader does not say what was meant (the original stays).

       WHAT IS WRITTEN is every key whose value in memory is not
       compare's default, and every key whose value in memory differs
       from the test's own -- so a key the directory's 'hwut.conf'
       states, and the author set back, is stated back too.

       (3) with a commit: one NOTE -- the next run judges under the
       test's own tolerance, not under the one that was tried.
______________________________________________________________________________
"""
import io
import os
import re

from vut.engine.orchestrator.run.tolerance_text import (leaf_db_of, text_of,
                                                         value_text)

QUESTION_HEAD = "tolerances were changed in memory for '%s':"


def keep_question(adapter, key, directory, commit_f, err, ask):
    """
    RETURN: str, what became of the tolerance -- 'stored', 'entered',
            'omitted'.
            None, nothing to ask: the tolerance in memory is the test's
            own, or the session's tier has no tolerance pane.

    'directory' is where the test stands; 'ask' reads one answer after
    a prompt and raises EOFError where nobody can answer -- the answer
    is then (1), which touches nothing of the author's.
    """
    changed = getattr(adapter, "tolerance_changed_f", None)
    if changed is None or not changed(): return None
    options, page = adapter.tolerance_options, adapter.page_options
    line = stated_line_of(options, page)
    err(QUESTION_HEAD % key.label)
    err("    %s" % line)
    err("  (1) store them in %s" % tmp_path(key.test, key.choice))
    if commit_f:
        err("  (2) enter them into %s, where its other configuration stands"
            % key.test)
    err("  (3) omit them")
    allowed = ("1", "2", "3") if commit_f else ("1", "3")
    while True:
        try:
            answer = ask("keep? [%s] " % "/".join(allowed)).strip()
        except EOFError:
            answer = "1"
            err("NOTE: nobody to answer -- (1)")
        if answer in allowed: break

    if answer == "3":
        if commit_f:
            err("NOTE: accepted under a tried tolerance; the next run judges "
                "under the test's own")
        return "omitted"
    if answer == "2":
        reason = enter_into_source(os.path.join(directory, key.test),
                                   key.choice, options, page)
        if reason is None:
            err("entered into %s" % key.test)
            return "entered"
        err("REFUSED: not entered into %s -- %s" % (key.test, reason))
    path = store_tmp(directory, key.test, key.choice, options, page)
    err("stored in %s" % os.path.relpath(path, directory))
    return "stored"


def tmp_path(test, choice):
    """RETURN: str, the TMP file's path relative to the test's directory
               -- named as the test's nominal is, '<test>--<choice>'."""
    name = test if choice is None else "%s--%s" % (test, choice)
    return os.path.join("TMP", name + ".tolerance.conf")


def stated_line_of(options, page):
    """RETURN: str, 'tolerance { ... }' holding every key of 'options'
               that is not compare's default or not the test's own
               ('page'); 'tolerance { }' where none is."""
    from vut.engine.compare.api import Configuration
    default_db = leaf_db_of(Configuration())
    page_db    = leaf_db_of(page) if page is not None else default_db
    pair_list  = ["%s = %s" % (leaf, value_text(value))
                  for leaf, value in leaf_db_of(options).items()
                  if value != default_db[leaf] or value != page_db[leaf]]
    return "tolerance { %s }" % "  ".join(pair_list) if pair_list \
           else "tolerance { }"


def store_tmp(directory, test, choice, options, page):
    """RETURN: str, the path written: the TMP file of (1)."""
    path = os.path.join(directory, tmp_path(test, choice))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    label = test if choice is None else "%s %s" % (test, choice)
    with io.open(path, "w", encoding="utf-8") as file_handle:
        file_handle.write(
            "# THE TOLERANCE TRIED for '%s' in the merge screen.\n"
            "# In the '@hwut { }' header -- or the choice, or an 'apps'\n"
            "# entry of 'hwut.conf' -- the one line it needs:\n"
            "#\n"
            "#     %s\n"
            "#\n"
            "# Every key, as the pane showed it:\n"
            "%s" % (label, stated_line_of(options, page), text_of(options)))
    return path


def enter_into_source(path, choice, options, page):
    """
    RETURN: None, the header of 'path' now states the tolerance: its own
                  'tolerance' scope replaced, or one added.
            str, why not -- the file is left as it was.
    """
    from vut.engine.orchestrator.exploration import source_file_detector, reader
    try:
        with io.open(path, "r", encoding="utf-8") as file_handle:
            text = file_handle.read()
    except OSError as error:
        return "cannot be read: %s" % error
    region = source_file_detector.detect(text)
    if region is None:
        return "it carries no '@hwut { }' header (named under 'apps' in " \
               "'hwut.conf'?)"
    spec, fault_list = reader.read_header(text, path)
    if spec is None or fault_list:
        return "its header does not read cleanly now"
    stated = spec.choice_db.get(choice)
    if choice is not None and stated is not None and stated.tolerance is not None:
        return "choice '%s' states its own 'tolerance'; the header's would " \
               "not reach it" % choice

    block    = stated_line_of(options, page)
    new_text = _replaced(text, region, block)
    spec, fault_list = reader.read_header(new_text, path)
    if spec is None or fault_list:
        return "the header would not read (%s)" % (
                   fault_list[0].message if fault_list else "no header")
    if not _states_f(spec.root_parameters.tolerance, options, page):
        return "the header read back does not state what was meant"
    with io.open(path, "w", encoding="utf-8") as file_handle:
        file_handle.write(new_text)
    return None


_KEY_RE = re.compile(r"tolerance\s*(=\s*)?\{")


def _replaced(text, region, block):
    """RETURN: str, 'text' with the header's top-level 'tolerance' scope
               replaced by 'block' -- or, where it states none, 'block'
               added before the header's closing brace."""
    span = _tolerance_span(text, region)
    if span is not None:
        return text[:span[0]] + block + text[span[1]:]
    close_line_i = text.rfind("\n", 0, region.i_close) + 1
    before_close = text[close_line_i:region.i_close]
    if close_line_i > region.i_open and not before_close.strip(" \t#/;*-"):
        #  THE BRACE STANDS ON A LINE OF ITS OWN: a line of the header's
        #  own lead and indentation goes before it.
        return text[:close_line_i] + _lead_of(text, region) + block + "\n" \
               + text[close_line_i:]
    return text[:region.i_close].rstrip(" ") + "  " + block + " " \
           + text[region.i_close:]


def _tolerance_span(text, region):
    """RETURN: (int, int), where the header's top-level 'tolerance' scope
               begins and ends (past its closing brace).
               None, where the header states none at the top level."""
    depth, i, in_string_f = 0, region.i_open, False
    while i <= region.i_close:
        c = text[i]
        if in_string_f:
            if c == "\\": i += 2; continue
            if c == '"': in_string_f = False
        elif c == '"':
            in_string_f = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        elif depth == 1 and (i == 0 or not (text[i - 1].isalnum()
                                            or text[i - 1] == "_")):
            match = _KEY_RE.match(text, i)
            if match is not None:
                close = _matching(text, match.end() - 1)
                if close is not None: return (i, close + 1)
        i += 1
    return None


def _matching(text, i_open):
    """RETURN: int, the index of the brace closing the one at 'i_open'."""
    depth, i, in_string_f = 0, i_open, False
    while i < len(text):
        c = text[i]
        if in_string_f:
            if c == "\\": i += 2; continue
            if c == '"': in_string_f = False
        elif c == '"':
            in_string_f = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0: return i
        i += 1
    return None


def _lead_of(text, region):
    """RETURN: str, what a header line holds before its key -- the comment
               lead and the indentation -- read off the header's first
               line after the marker's."""
    body = text[region.i_open:region.i_close].split("\n")[1:]
    for line in body:
        match = re.match(r"^([^A-Za-z0-9_\"{}]*)[A-Za-z_]", line)
        if match is not None: return match.group(1)
    return "    "


def _states_f(tolerance, options, page):
    """RETURN: bool, True where the header's tolerance, as compare would
               read it, is 'options' on every key written."""
    from vut.engine.compare.api import Configuration
    from vut.engine.orchestrator.run.adapter import tolerance_applied
    read = Configuration()
    tolerance_applied(read, tolerance)
    read_db, meant_db = leaf_db_of(read), leaf_db_of(options)
    default_db = leaf_db_of(Configuration())
    page_db    = leaf_db_of(page) if page is not None else default_db
    return all(read_db[leaf] == value for leaf, value in meant_db.items()
               if value != default_db[leaf] or value != page_db[leaf])
