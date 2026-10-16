"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE 'hwut.help' COMMAND LINE -- what failed below here for a
         reason that is not a plain deviation from GOOD, and how each
         such failure is resolved (display D-34).

    hwut.help [--directory=<path>] [<wish>]

DESCRIPTION
       READS THE BOOKS, as 'hwut.report' does: the last results of every
       case the wish selects below '--directory' (the current one where
       none is given). Runs nothing.

       AN INTRODUCTION FIRST: how many cases failed for how many
       reasons, and that each has a known remedy below.

       ONCE PER FAILURE, UNDER ITS CATEGORY -- the headings the run's
       HINTS block carries (display D-35, D-36). For every failure that
       occurred: its word before '[FAIL]', its phrase and the number of
       cases; a paragraph saying what it means; a paragraph opening 'In
       order to heal, ' saying how it is resolved; a paragraph on how
       'hwut.sanitize' heals it, where a command does; and 'CONCERNED:',
       the cases as HINTS lists them -- directory, application, choice.

       A plain difference from GOOD is the ordinary business of a test
       and is not explained here; neither is a case the book never saw.

       The explanations stand in ONE table, 'engine/display/failure.py'.

       TEST RUNS WITHOUT A FEATURE, LAST: 'NONSENSE?' -- every test run
       that links to no feature while its TEST directory states
       features ('hwut-features.conf'). No failure: the run's verdict
       stands. What the word means, and how it is resolved. A tree that
       states no features says nothing here.

       FEATURES DEFINED AND NOT REGISTERED, AFTER IT (R-96): where
       'hwut-root-features.conf' stands, every feature defined in a TEST
       directory below that it has no line for -- the line 'hwut.run'
       ends with, said out. No failure. A tree without the file says
       nothing here.

       THE LAST COVERAGE RUN, AFTER THAT (coverage D-41): every selected
       case it left WITHOUT A RECORD, read from the local trace
       'TMP/hwut-traces-coverage.csv' of each directory, under the headings
       and with the words of the coverage run's HINTS. Its explanations
       stand in 'engine/display/coverage_reason.py'. A directory no
       coverage run has visited says nothing.

       WHAT THE NEXT RUN REFUSES, LAST (exploration R-80): every
       selected case under a cap the procsitter cannot enforce on this
       platform and the root conf does not acknowledge -- the caps, the
       utility that is missing where one is ('psutil'), how it is
       installed, and the 'hwut-root.conf' entry that acknowledges.
       Judged now, by the gate the run asks; no book holds a refusal.

EXIT STATUS (E-1, services/_exit.py):
    0  something was explained
    1  a Python module hwut needs is absent or too old: named, with how
       to install it, before anything else (adm/requirement-list.txt)
    3  nothing to explain: no selected case failed for a subtle reason,
       none was left without a coverage record, none is refused for
       want of an enforceable cap
    2  the command line cannot be read
______________________________________________________________________________
"""
import os
import sys
import textwrap

#  WHAT THIS MACHINE LACKS IS SAID FIRST (adm/WORK/spec/24): a census
#  module that is absent ends every import below with a traceback before
#  a word is said. The reader imports 'os' and 're' alone.
if __name__ == "__main__":
    from .lib import requirements as _requirements
    _missing_list = _requirements.missing()
    if _missing_list:
        sys.stdout.write(_requirements.missing_text(_missing_list))
        if any(row.kind == "python" for row, _ in _missing_list):
            sys.exit(1)

from ..engine.orchestrator.plan.wish import (HELP as WISH_HELP,
                                                 WishError, parse_wish,
                                                 with_targets)
from ..engine.display.failure import (failure_db, failure_of,
                                                subtle_f, category_of,
                                                E_FailureCategory,
                                                CATEGORY_HEADING_DB,
                                                HEAL_OPENER_STR)
from ..engine.display.plain import CHOICE_GAP
from ..engine.display.coverage_reason import (E_NoRecordCategory,
                                                  HEADING_DB,
                                                  no_record_db)
from ..engine.coverage.api import CoverageTraceDb, OUTCOME_OK
from .lib.cmdline import (face_parser, usage_of,
                                                parse_or_refuse)
from .lib.face import FaceError
from   ._exit                           import E_ExitCode
from   ._target                         import entered
from   .report                          import do, request_of
from ..engine.orchestrator.exploration import selection
from ..engine.orchestrator.plan.confinement import (
           acknowledgement_of, missing_utility_tuple, reason_of,
           uncapped_of, ROOT_CONF_NAME)
from ..engine.procsitter.api import INSTALL_DB, platform_name
from .lib.labels import view_at

WRAP_WIDTH = 68          # a paragraph's text, eight blanks deep: 76 in all

PARSER = face_parser("hwut.help", "Explain the subtle failures of the "
                                  "last results.",
                     word_help="a test, a test and a choice, a file glob "
                               "and a choice glob",
                     word_metavar="[<file-glob> [choice-glob]...]")
PARSER.add_argument("--directory", default=None)
ARG_DB = {"--directory": True}
USAGE  = usage_of(PARSER, ARG_DB)

HELP = __doc__.split("\n", 2)[2].rsplit("_" * 10, 1)[0].rstrip() \
       + "\n\n" + WISH_HELP + "\n" + USAGE


def token_of(row):
    """
    RETURN: str, the failure token a failing book row stands for: the
                 stain's 'unstable' first, 'unaccepted' for an aspirant,
                 the recorded report else.
            None, where the row stood, or the book never saw the case.
    """
    if row.stain_repeat_n is not None: return "unstable"
    if row.verdict_name is None or row.passed_f:  return None
    if row.verdict_name == "aspirant":            return "unaccepted"
    return row.report or None


def occurrence_db_of(block_list):
    """
    RETURN: dict, failure token -> list of (directory, file, choice),
            every subtle failure among the blocks' rows, in the order
            met; 'choice' None where the test has none.
    """
    occurrence_db = {}
    for block in block_list:
        for row in block.row_tuple:
            token = token_of(row)
            if not subtle_f(token): continue
            occurrence_db.setdefault(token, []).append(
                (block.directory or ".", row.source_file, row.choice))
    return occurrence_db


def concerned_line_list(case_list):
    """
    RETURN: list of str, the cases a failure struck, AS HINTS LISTS THEM
            (display D-35) and without the phrase: the directory once,
            each application once beneath it, ':' where its choices
            repeat it.
    """
    directory_db = {}
    for directory, file, choice in case_list:
        directory_db.setdefault(directory, []).append((file, choice))
    line_list = []
    for directory, item_list in directory_db.items():
        line_list.append(directory)
        last_file, column = None, 0
        for file, choice in item_list:
            repeat_f = (file == last_file)
            if not repeat_f: column = len(file) + CHOICE_GAP
            last_file = file
            shown     = ":" if repeat_f else file
            line_list.append("    " + ("%-*s%s" % (column, shown, choice)
                                       if choice else shown))
    return line_list


def explanation_line_list(token, case_list):
    """
    RETURN: list of str, what 'hwut.help' says of one failure: the head
            (its word, its phrase, how many cases); then, each after an
            empty line, the table's paragraphs wrapped -- what it means,
            how it is healed, how 'hwut.sanitize' heals it where it
            does; then 'CONCERNED:' and the cases.
    """
    failure = failure_of(token)
    if failure is None:
        head = "failed -- '%s'" % token
        paragraph_list = ["A reason the failure table does not know.",
                          HEAL_OPENER_STR + "read the HINTS of 'hwut.run' "
                          "for the cases below."]
    else:
        head = "%s -- %s" % (failure.comment_before_FAIL_str,
                             failure.description)
        paragraph_list = failure.paragraph_list()
    line_list = ["%s  [%i case(s)]" % (head, len(case_list))]
    for paragraph in paragraph_list:
        line_list.append("")
        line_list.extend("    " + line for line in
                         textwrap.wrap(paragraph, width=WRAP_WIDTH,
                                       break_on_hyphens=False))
    line_list.append("")
    line_list.append("    CONCERNED:")
    line_list.extend("        " + line
                     for line in concerned_line_list(case_list))
    return line_list


def coverage_occurrence_db_of(block_list, root):
    """
    RETURN: dict, coverage token -> list of (directory, file, choice):
            every case among the blocks' rows that the LAST COVERAGE
            RUN left without a record, by the local trace of its
            directory (coverage D-41); 'choice' None where the test has
            none. Empty where no trace stands.
    """
    occurrence_db = {}
    for block in block_list:
        outcome_db = CoverageTraceDb(
                         os.path.join(root, block.directory or ".")).read()
        if not outcome_db: continue
        for row in block.row_tuple:
            outcome = outcome_db.get((row.source_file, row.choice or ""))
            if outcome is None or outcome == OUTCOME_OK: continue
            occurrence_db.setdefault(outcome, []).append(
                (block.directory or ".", row.source_file, row.choice))
    return occurrence_db


def coverage_explanation_line_list(token, case_list):
    """
    RETURN: list of str, what 'hwut.help' says of one reason a coverage
            run left no record: the head (its word, its phrase, how
            many cases), the table's paragraphs wrapped, then
            'CONCERNED:' and the cases.
    """
    reason = no_record_db.get(token)
    if reason is None:
        head = "no record -- '%s'" % token
        paragraph_list = ["A reason the coverage table does not know.",
                          HEAL_OPENER_STR + "read the HINTS of "
                          "'hwut.cov.run' for the cases below."]
    else:
        head = "%s -- %s" % (reason.word, reason.phrase)
        paragraph_list = reason.paragraph_list()
    line_list = ["%s  [%i case(s)]" % (head, len(case_list))]
    for paragraph in paragraph_list:
        line_list.append("")
        line_list.extend("    " + line for line in
                         textwrap.wrap(paragraph, width=WRAP_WIDTH,
                                       break_on_hyphens=False))
    line_list.append("")
    line_list.append("    CONCERNED:")
    line_list.extend("        " + line
                     for line in concerned_line_list(case_list))
    return line_list


def uncapped_occurrence_db_of(root, wish):
    """
    RETURN: dict, tuple of cap names -> list of (directory, file,
            choice): every selected case 'hwut.run' REFUSES because a
            cap in force for it is neither enforceable on this platform
            nor acknowledged in the root conf (exploration R-80).
            Judged NOW, by the gate the run asks -- a refused case
            leaves nothing in a book to read.
    """
    occurrence_db = {}
    root = os.path.abspath(root)
    for directory, result, _, selected_list in \
            selection.of_tree_stream(root, wish, view_at(root), base_f=True):
        for case in (entry.case for entry in selected_list):
            uncapped = uncapped_of(result.app_set, case.source_file,
                                   case.choice)
            if not uncapped: continue
            occurrence_db.setdefault(uncapped, []).append(
                (directory or ".", case.source_file, case.choice))
    return occurrence_db


def uncapped_explanation_line_list(uncapped, case_list, platform):
    """
    RETURN: list of str, what 'hwut.help' says of one set of caps that
            cannot be enforced: the head (the refusal's own words, how
            many cases), what it means, the utility that is missing
            where one is, the root conf entry that acknowledges, then
            'CONCERNED:' and the cases.
    """
    #  THE PLATFORM'S WORD STANDS ON UNWRAPPED LINES ONLY -- the head
    #  and the entry: inside a paragraph its length would decide where
    #  the lines break, and the page would differ by machine.
    utility_tuple = missing_utility_tuple(uncapped, platform)
    head          = reason_of(uncapped, platform).split(" => ")[0]
    paragraph_list = [
        "Each case below is under %s, stated in its header or standing "
        "by default, and on this platform nothing enforces %s. A cap "
        "that does not cap is worse than no cap: the author believes "
        "the test confined and it is not. So the case is not run."
        % ("this cap" if len(uncapped) == 1 else "these caps",
           "it" if len(uncapped) == 1 else "them")]
    for utility in utility_tuple:
        how = INSTALL_DB.get(utility)
        paragraph_list.append(
            "MISSING: '%s' -- the procsitter watches with it, and it is "
            "not on this machine.%s"
            % (utility, " Install: '%s'." % how if how else
                        " It does not exist on this platform."))
    paragraph_list.append(
        HEAL_OPENER_STR + "%sacknowledge in '%s' that the tests run "
        "without the cap on this platform -- knowingly, for the whole "
        "tree:"
        % ("install what is missing, or " if utility_tuple else "",
           ROOT_CONF_NAME))
    line_list = ["refused -- %s  [%i case(s)]" % (head, len(case_list))]
    for paragraph in paragraph_list:
        line_list.append("")
        line_list.extend("    " + line for line in
                         textwrap.wrap(paragraph, width=WRAP_WIDTH,
                                       break_on_hyphens=False))
    line_list.append("")
    line_list.append("        " + acknowledgement_of(uncapped, platform))
    line_list.append("")
    line_list.append("    CONCERNED:")
    line_list.extend("        " + line
                     for line in concerned_line_list(case_list))
    return line_list


UNCAPPED_HEADING_STR = "CONFINEMENT -- cap not enforceable"
NONSENSE_HEADING_STR = "FEATURES -- test run without a feature"
NONSENSE_WORD_STR    = "NONSENSE?"


def nonsense_case_list_of(root):
    """
    RETURN: list of (directory, file, choice), every test run below
            'root' that links to NO feature while its TEST directory
            states features ('hwut-features.conf') -- walk order. Empty
            where no directory states features: features are not
            mandatory, and a tree without them holds no nonsense.
    """
    from hwut.engine.orchestrator.exploration.feature_relation \
                                        import relation_of_tree
    from hwut.engine.orchestrator.exploration.tree_explorer \
                                        import RootConfMissing
    try:
        relation = relation_of_tree(os.path.abspath(root))
    except RootConfMissing:
        return []
    return [(path, test, choice)
            for path in sorted(relation.test_directory_db)
            if relation.test_directory_db[path].feature_file is not None
            for test, choice
            in relation.test_directory_db[path].unlinked_tuple]


UNREGISTERED_HEADING_STR = "FEATURES -- defined, not registered"


def unregistered_of(directory):
    """
    RETURN: list of (str, str), (directory path, name) of every feature
            defined at or below 'directory' that the central file of
            features does not register; [] where no central file stands
            ('feature_detector.unregistered_list').
    """
    from hwut.engine.orchestrator.exploration.feature_detector \
                                        import unregistered_list
    from hwut.engine.orchestrator.exploration.tree_explorer \
                                        import RootConfMissing, \
                                               root_conf_directory
    try:
        root = root_conf_directory(directory)
    except RootConfMissing:
        return []
    below = os.path.relpath(os.path.abspath(directory), root)
    return unregistered_list(root, below.replace(os.sep, "/"))


def unregistered_explanation_line_list(pair_list):
    """
    RETURN: list of str, what 'hwut.help' says of features defined and not
            registered: the head, what it means, how it is resolved, then
            'CONCERNED:' and the features, '<directory>  <name>'.
    """
    paragraph_list = [
        "Each feature below is defined in its TEST directory's "
        "'hwut-features.conf', and 'hwut-root-features.conf' -- the one "
        "place where features are registered -- has no line for it: it "
        "is new, it was renamed, or its directory moved. It is NOT a "
        "failure: the test runs and is judged. But a feature that is not "
        "registered has no external id, and nothing a customer holds can "
        "name it.",
        HEAL_OPENER_STR + "run 'hwut.features.register'. It adds what is "
        "new -- an id for a directory, a line for a feature, unplaced -- "
        "and names what was renamed or moved, with the line that heals it "
        "('repoint', 'redirect'), for 'hwut.sanitize' to do. Then move the "
        "new lines into aggregates of the tree."]
    line_list = ["not registered -- defined, in no line  [%i feature(s)]"
                 % len(pair_list)]
    for paragraph in paragraph_list:
        line_list.append("")
        line_list.extend("    " + line for line in
                         textwrap.wrap(paragraph, width=WRAP_WIDTH,
                                       break_on_hyphens=False))
    line_list.append("")
    line_list.append("    CONCERNED:")
    line_list.extend("        %s  %s" % pair for pair in pair_list)
    return line_list


def nonsense_explanation_line_list(case_list):
    """
    RETURN: list of str, what 'hwut.help' says of the test runs that
            link to no feature: the head, what the word means, how it
            is resolved, then 'CONCERNED:' and the cases.
    """
    paragraph_list = [
        "Each test run below stands in a TEST directory that states its "
        "features in 'hwut-features.conf', and links to none of them. "
        "It is NOT a failure: a test run that shows acceptable behaviour "
        "is OK, and its verdict stands. The question is what it is for "
        "-- a test run that proves nothing anybody claimed is either a "
        "claim nobody wrote down, or a test nobody needs.",
        HEAL_OPENER_STR + "write the feature the test run proves into "
        "'hwut-features.conf' and name it under 'features' in the "
        "test's '@hwut { }' block; or link the test run to a feature "
        "that stands there already; or remove the test "
        "('hwut.remove')."]
    line_list = ["%s -- links to no feature  [%i case(s)]"
                 % (NONSENSE_WORD_STR, len(case_list))]
    for paragraph in paragraph_list:
        line_list.append("")
        line_list.extend("    " + line for line in
                         textwrap.wrap(paragraph, width=WRAP_WIDTH,
                                       break_on_hyphens=False))
    line_list.append("")
    line_list.append("    CONCERNED:")
    line_list.extend("        " + line
                     for line in concerned_line_list(case_list))
    return line_list


def uncapped_introduction_line_list(case_n, reason_n):
    """
    RETURN: list of str, the opening of the confinement part: how many
            cases 'hwut.run' refuses on this platform, for how many
            sets of caps.
    """
    return textwrap.wrap(
        "'hwut.run' REFUSES %i case(s) on this platform, for %i set(s) "
        "of caps the procsitter cannot enforce here. The paragraphs "
        "below explain each once, say what is missing and how to heal "
        "it, and name the cases concerned."
        % (case_n, reason_n),
        width=WRAP_WIDTH + 8, break_on_hyphens=False)


def coverage_introduction_line_list(case_n, reason_n):
    """
    RETURN: list of str, the opening of the coverage part: how many
            cases the last coverage run left without a record, for how
            many reasons.
    """
    return textwrap.wrap(
        "The last coverage run left %i case(s) without a record, for "
        "%i reason(s). The paragraphs below explain each reason once, "
        "say how to heal it, and name the cases concerned."
        % (case_n, reason_n),
        width=WRAP_WIDTH + 8, break_on_hyphens=False)


def introduction_line_list(case_n, failure_n):
    """
    RETURN: list of str, the opening of the page: how many cases failed
            for how many reasons, and that each has a known remedy
            below.
    """
    return textwrap.wrap(
        "The last results hold %i case(s) that failed for %i reason(s) "
        "other than a plain difference from GOOD. Every one of them has "
        "a known cause and a known remedy: the paragraphs below explain "
        "each reason once, say how to heal it, and name the cases "
        "concerned." % (case_n, failure_n),
        width=WRAP_WIDTH + 8, break_on_hyphens=False)


def main(argv=None, write=None):
    """
    RETURN: E_ExitCode, OK where something was explained, EMPTY where no
            selected case failed for a subtle reason, REFUSED where the
            command line cannot be read.
    """
    if write is None: write = print
    if argv is None:  argv  = sys.argv[1:]
    if "--help" in argv:
        from ._core import man_page
        write(man_page("hwut.help", HELP))
        return E_ExitCode.OK
    try:
        wish, rest_list = parse_wish(argv)
    except WishError as error:
        write("REFUSED: %s" % error)
        write(USAGE)
        return E_ExitCode.REFUSED
    arguments, completion_f = parse_or_refuse(PARSER, rest_list, write,
                                              ARG_DB)
    if completion_f:      return E_ExitCode.OK
    if arguments is None:
        write(USAGE)
        return E_ExitCode.REFUSED
    found = entered(arguments.word, arguments.directory or ".", write,
                    USAGE)
    if found is None: return E_ExitCode.REFUSED
    directory, word_list = found
    if not os.path.isdir(directory):
        write("REFUSED: the directory '%s' does not exist" % directory)
        write(USAGE)
        return E_ExitCode.REFUSED

    block_list = []
    try:
        do(request_of(with_targets(wish, word_list), directory),
           block_list.append)
    except FaceError as error:
        write(error.said)
        return error.code
    occurrence_db = occurrence_db_of(block_list)
    coverage_db   = coverage_occurrence_db_of(block_list, directory)
    uncapped_db   = uncapped_occurrence_db_of(
                        directory, with_targets(wish, word_list))
    nonsense_list = nonsense_case_list_of(directory)
    unregistered  = unregistered_of(directory)
    if not occurrence_db and not coverage_db and not uncapped_db \
       and not nonsense_list and not unregistered:
        write("nothing to explain: no case below '%s' failed for a "
              "reason other than a plain difference from GOOD" % directory)
        return E_ExitCode.EMPTY
    #  UNDER ITS CATEGORY'S HEADING (D-35), as HINTS does, and within it
    #  by the table's order, so the page is the same whatever the walk
    #  met first; a token the table does not carry comes last.
    if occurrence_db:
        rank_db = {member.value: i for i, member in enumerate(failure_db)}
        for line in introduction_line_list(
                        sum(len(v) for v in occurrence_db.values()),
                        len(occurrence_db)):
            write(line)
        for category in E_FailureCategory:
            token_list = sorted((t for t in occurrence_db
                                 if category_of(t) is category),
                                key=lambda t: (rank_db.get(t, len(rank_db)),
                                               t))
            if not token_list: continue
            write("")
            write(CATEGORY_HEADING_DB[category])
            for token in token_list:
                write("")
                for line in explanation_line_list(token,
                                                  occurrence_db[token]):
                    write("    " + line)
    #  THE COVERAGE RUN'S PART (coverage D-41), in the same shape and in
    #  its own words; an unknown token comes last, under no heading.
    if coverage_db:
        if occurrence_db: write("")
        for line in coverage_introduction_line_list(
                        sum(len(v) for v in coverage_db.values()),
                        len(coverage_db)):
            write(line)
        rank_db = {token: i for i, token in enumerate(no_record_db)}
        for category in list(E_NoRecordCategory) + [None]:
            token_list = sorted(
                (t for t in coverage_db
                 if (no_record_db[t].category if t in no_record_db
                     else None) is category),
                key=lambda t: (rank_db.get(t, len(rank_db)), t))
            if not token_list: continue
            write("")
            if category is not None: write(HEADING_DB[category])
            for token in token_list:
                write("")
                for line in coverage_explanation_line_list(
                                token, coverage_db[token]):
                    write("    " + line)
    #  THE CONFINEMENT PART (exploration R-80), last: what the NEXT run
    #  refuses, where the parts above read what the last one left.
    if uncapped_db:
        if occurrence_db or coverage_db: write("")
        platform = platform_name()
        for line in uncapped_introduction_line_list(
                        sum(len(v) for v in uncapped_db.values()),
                        len(uncapped_db)):
            write(line)
        write("")
        write(UNCAPPED_HEADING_STR)
        for uncapped in sorted(uncapped_db):
            write("")
            for line in uncapped_explanation_line_list(
                            uncapped, uncapped_db[uncapped], platform):
                write("    " + line)
    #  THE FEATURES PART, last of all: no failure, a QUESTION -- what a
    #  test run is for that proves nothing its directory claims (E-145).
    if nonsense_list:
        if occurrence_db or coverage_db or uncapped_db: write("")
        write(NONSENSE_HEADING_STR)
        write("")
        for line in nonsense_explanation_line_list(nonsense_list):
            write("    " + line)
    #  NOT REGISTERED, after it (R-96): the line 'hwut.run' ends with,
    #  said out.
    if unregistered:
        if occurrence_db or coverage_db or uncapped_db or nonsense_list:
            write("")
        write(UNREGISTERED_HEADING_STR)
        write("")
        for line in unregistered_explanation_line_list(unregistered):
            write("    " + line)
    return E_ExitCode.OK


if __name__ == "__main__":
    #  A TERMINAL SIGNAL IS AN ENDING, NOT A CRASH (E-55).
    from ._exit import guarded
    sys.exit(guarded("hwut.help", main))
