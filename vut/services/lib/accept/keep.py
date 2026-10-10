"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: KEEPING A TRIED TOLERANCE (intend 21, 2.7) -- what is shown and
         asked when a merge ends with the tolerance in memory changed,
         and the two ways of keeping it.

    tolerances were changed in memory for 'test.sh one' -- to copy:

        tolerance {
            numeric_ratio = 0.047
            eq_pattern    = ["id=[0-9abz]{3,4};"]
        }

      [1]      store them in TMP/test.sh--one.tolerance.conf
      [2]      enter them into test.sh, where its other configuration stands
      <enter>  omit them -- copy them from above
    >

DESCRIPTION
       THE MENU SPEAKS THE CHECKLIST'S IDIOM ('lib/checklist.py'): a
       number in brackets picks, '<enter>' takes what stands beside it,
       the prompt is '> ', and an answer that picks nothing is said and
       asked again.

       ON COMMIT all three; ON CANCEL [1] or <enter> -- a cancelled
       session does not edit the page (ruled: "ask write or cancel
       changes upon cancellation").

       [1] THE TMP FILE is deletable ground and never a wallflower. It
       holds the one line a header needs and, below it, the whole scope
       as the pane showed it, so the author may paste either.

       [2] INTO THE SOURCE, by 'exploration/amend.py' -- the one
       implementation every face that writes into an author's file uses.
       The header's own top-level 'tolerance' scope is replaced where
       one stands; else a line is added before the header's closing
       brace, in the header's own decoration and indentation, whatever
       the language (X-DECORATION). Every other byte stays. IT TRIES,
       and refuses by name -- writing [1] instead, so the work is not
       lost -- where the file carries no header (the test is named
       under 'apps' in 'hwut.conf'), where the choice states its own
       'tolerance' (the header's would not reach it), and where the
       file read back by the exploration's own reader does not say
       what was meant (the original stays).

       WHAT IS WRITTEN is every key whose value in memory is not
       compare's default, and every key whose value in memory differs
       from the test's own -- so a key the directory's 'hwut.conf'
       states, and the author set back, is stated back too.

       <enter> after a commit: one NOTE -- the next run judges under the
       test's own tolerance, not under the one that was tried.

       NOBODY TO ANSWER (stdin closed): [1], which touches nothing of the
       author's.
______________________________________________________________________________
"""
import io
import os

from vut.engine.orchestrator.run.tolerance_text import (leaf_db_of, text_of,
                                                         value_text)
from vut.engine.orchestrator.exploration        import amend
from vut.auxiliary.no_entry import TRANSIENT_DIRECTORY_NAME

QUESTION_HEAD = "tolerances were changed in memory for '%s' -- to copy:"


def keep_question(adapter, key, directory, commit_f, err, ask):
    """
    RETURN: str, what became of the tolerance -- 'stored', 'entered',
            'omitted'.
            None, nothing to ask: the tolerance in memory is the test's
            own, or the session's tier has no tolerance pane.

    'directory' is where the test stands; 'ask' reads one answer after
    a prompt and raises EOFError where nobody can answer.
    """
    changed = getattr(adapter, "tolerance_changed_f", None)
    if changed is None or not changed(): return None
    options, page = adapter.tolerance_options, adapter.page_options
    pair_list = stated_pair_list(options, page)
    err(QUESTION_HEAD % key.label)
    err("")
    for line in pretty_line_list(pair_list): err("    " + line)
    err("")
    err("  [1]      store them in %s" % tmp_path(key.test, key.choice))
    if commit_f:
        err("  [2]      enter them into %s, where its other configuration "
            "stands" % key.test)
    err("  <enter>  omit them -- copy them from above")
    allowed = ("1", "2", "") if commit_f else ("1", "")
    while True:
        try:
            answer = ask("> ").strip()
        except EOFError:
            answer = "1"
            err("NOTE: nobody to answer -- [1]")
        if answer in allowed: break
        err("  (not one of %s: '%s')"
            % (", ".join("[%s]" % a if a else "<enter>" for a in allowed),
               answer))

    if answer == "":
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
    return os.path.join(TRANSIENT_DIRECTORY_NAME, name + ".tolerance.conf")


def stated_pair_list(options, page):
    """RETURN: list[(key, value text)], every key of 'options' that is not
               compare's default or not the test's own ('page'), in the
               header's spelling."""
    from vut.engine.compare.api import Configuration
    default_db = leaf_db_of(Configuration())
    page_db    = leaf_db_of(page) if page is not None else default_db
    return [(leaf, value_text(value))
            for leaf, value in leaf_db_of(options).items()
            if value != default_db[leaf] or value != page_db[leaf]]


def stated_line_of(options, page):
    """RETURN: str, 'tolerance { ... }' holding 'stated_pair_list'."""
    return amend.scope_text("tolerance", stated_pair_list(options, page)) \
           .replace("{  }", "{ }")


def pretty_line_list(pair_list):
    """RETURN: list[str], the scope as a person copies it: one key a line,
               the '=' aligned."""
    width = max((len(key) for key, _ in pair_list), default=0)
    return ["tolerance {"] \
           + ["    %-*s = %s" % (width, key, value) for key, value in pair_list] \
           + ["}"]


def store_tmp(directory, test, choice, options, page):
    """RETURN: str, the path written: the TMP file of [1]."""
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
    from vut.engine.orchestrator.exploration import reader
    try:
        with io.open(path, "r", encoding="utf-8") as file_handle:
            text = file_handle.read()
    except OSError as error:
        return "cannot be read: %s" % error
    container = amend.header_container(text)
    if container is None:
        return "it carries no '@hwut { }' header (named under 'apps' in " \
               "'hwut.conf'?)"
    spec, fault_list = reader.read_header(text, path)
    if spec is None or fault_list:
        return "its header does not read cleanly now"
    stated = spec.choice_db.get(choice)
    if choice is not None and stated is not None and stated.tolerance is not None:
        return "choice '%s' states its own 'tolerance'; the header's would " \
               "not reach it" % choice

    new_text = amend.scope_set(text, container, "tolerance",
                               stated_pair_list(options, page))
    spec, fault_list = reader.read_header(new_text, path)
    if spec is None or fault_list:
        return "the header would not read (%s)" % (
                   fault_list[0].message if fault_list else "no header")
    if not _states_f(spec.root_parameters.tolerance, options, page):
        return "the header read back does not state what was meant"
    with io.open(path, "w", encoding="utf-8") as file_handle:
        file_handle.write(new_text)
    return None


def _states_f(tolerance, options, page):
    """RETURN: bool, True where the header's tolerance, as compare would
               read it, is 'options' on every key written."""
    from vut.engine.compare.api import Configuration
    from vut.engine.orchestrator.run.adapter import tolerance_applied
    read = Configuration()
    tolerance_applied(read, tolerance)
    read_db, meant_db = leaf_db_of(read), leaf_db_of(options)
    stated = dict(stated_pair_list(options, page))
    return all(read_db[leaf] == meant_db[leaf] for leaf in stated)
