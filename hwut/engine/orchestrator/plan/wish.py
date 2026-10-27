"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE WISH -- what the command line states about which tests are
         wanted. Fixed keywords, no expression grammar (P-8, P-15).

    --fail              the last recorded run's verdict was negative
    --pass              the last recorded run's verdict was positive
    --since=<point>     the last recorded run lies AT or AFTER the
                        point; a case never run is NOT wanted
    --until=<point>     the last recorded run lies BEFORE the point,
                        and a case NEVER RUN is wanted too -- the
                        stale wish
    --glob <target>     the target form (R-34) with fnmatch's '*', '?'
                        and '[ ]' in either member; may stand several
                        times. The file member MAY CARRY A PATH,
                        relative to the run's root --
                        'messaging/*/test-queue.py' -- which selects
                        ACROSS THE TREE. (A path is illegal where a
                        target names a NEIGHBOUR: 'collision' and
                        'dependency' read the bare form.)
    --exclude <target>  a target NOT wanted, whatever else selects it.
                        Same form as '--glob', path member and all;
                        may stand several times; the excludes are
                        OR'ed among themselves and AND'ed against the
                        includes -- a case is wanted where an include
                        names it AND no exclude does.
    --dir <glob>        A DIRECTORY WANTED, and every run in it. The
                        glob matches a path relative to the run's root
                        ('messaging/*') or a BARE NAME matching any
                        path COMPONENT -- the same matching
                        '--exclude-dir' uses. SEVERAL ARE A UNION
                        among themselves and NARROW against the rest
                        of the wish: '--dir a --fail' is 'the failing
                        runs under a' (disc-10). A DIRECTORY-RELATED
                        face reads the same field as its SUBJECT
                        rather than as a filter.
    --exclude-dir <glob>
                        a DIRECTORY not wanted, AND EVERY DIRECTORY
                        BELOW IT. The glob matches either a path
                        relative to the run's root ('vendor/*') or a
                        BARE NAME, in which case it matches any path
                        COMPONENT: '--exclude-dir OUT' drops
                        'a/OUT/TEST' and 'a/OUT/b/TEST' alike.
                        WHERE '--dir' AND '--exclude-dir' MEET, grep's
                        rule decides: they are read in command-line
                        order and the LAST ONE MATCHING a directory
                        decides; where none matches, the directory is
                        wanted unless the FIRST of them is a '--dir'.
                        '--exclude-dir a --dir a/keep' keeps 'a/keep'.
    --wishlist <file>   read the file's lines as targets, one per
                        line: a WISHLIST an author keeps and edits.
                        Lines starting with '#' are comments; blank
                        lines are ignored; a leading './' means the
                        WISHLIST'S OWN DIRECTORY, so a list travels
                        with the tree it describes. Globbing is
                        allowed throughout, path member included. A
                        SORTED list may ELIDE: a leading ':/' is the
                        previous line's directory, ':/:' its directory
                        and file, a choice following (disc-8). The
                        lines join the '--glob' targets and are OR'ed
                        with them. 'hwut.report.list' PRINTS this form,
                        so the round trip closes.
THE SHORT FORM OF HWUT 1.0 lives here too ('desugar_positional',
'with_targets'): a face may take BARE WORDS -- 'hwut.run test-app.sh
one' -- the first naming files, every further one a choice, globbing
allowed in both. It is sugar for '--glob' and nothing else, so the
short form can never mean what the long form cannot say.

    -l, --label <expr>  the runs the label expression names, out of
                        'hwut-root.labels' (disc-8): 'AND', 'OR',
                        'NOT', brackets, 'all' the universe, ',' sugar
                        for 'OR'. A UNION among the labels it names
                        where every other keyword narrows -- a label
                        names a SET, and naming two asks for both;
                        against the rest of the wish it still narrows.
                        ABSENT, the standard label 'meta' is SILENT:
                        a wish that asks no label does not want what
                        'meta' labels. Naming a label lifts the
                        silence.
    --faster-than=<seconds>
                        the runs THIS MACHINE last saw finish in less
                        than that: the 'Run' operation's duration, from
                        the local observation database (E-22). Seconds,
                        a decimal fraction allowed. A run this machine
                        has NOT observed is NOT selected -- silence is
                        not selected, and a fresh checkout selects
                        nothing here, which is the correct answer.
    -F, --feature <id-glob>
                        the runs linked to the FEATURES the glob names
                        (R-96): a glob over the TREE PATHS of
                        'hwut-root-features.conf', '<aggregate>/
                        <aggregate>/<external id>' -- '*' any part of one
                        level, '**' any depth (none included), '{a,b}'
                        alternatives; a bare word is '**/word'. An
                        AGGREGATE brings its whole subtree; a line of
                        'hwut.features.tree --list' fits as it stands; a
                        word with ':' is an INTERNAL id '<directory
                        id>:<name>'. A retired one is refused by name.
                        SEVERAL ARE A UNION among themselves and NARROW
                        against the rest of the wish, as '--dir'.
    -e, --feature-ext <id>
                        the runs linked to the feature whose EXTERNAL id
                        (the left side of its line in the central file) is
                        <id>; '*' matches any characters. An id that names
                        no feature, or a RETIRED one, is refused by name.
                        With '-F' a union.
    -k, --keys <expr>   the runs linked to features whose EFFECTIVE keys
                        (their own and those of every claim above them)
                        satisfy the expression -- the grammar of '-l':
                        'AND', 'OR', 'NOT', brackets, ',' for 'OR'. A
                        key no feature carries is refused by name. With
                        '-F', ONE feature must satisfy both. Labels and
                        keys are separate: '-l' names sets of RUNS, '-k'
                        categories of FEATURES.
    --language=<name>   the runs whose test application is of that
                        LANGUAGE -- the header's word, or the one its
                        extension selects in 'language-setup' (R-73).
                        May stand several times: a UNION among the
                        names, NARROWING against the rest of the wish
                        (R-75). A name no 'language-setup' entry
                        declares is refused by name. It SELECTS; it
                        states nothing about any file.

A <point> is a SPAN back from now, or an ANCHOR:

    span      a number and a unit 's', 'm', 'h', 'd': '90s', '2h', '7d'
    anchor    'today', 'yesterday'          that day, 00:00
              'last-week'                   Monday of the week before,
                                            00:00
              'last-month'                  the 1st of the month
                                            before, 00:00
              a weekday, 'monday'           the most recent such day,
                                            today counted, 00:00
              a month, 'january'            the 1st of the most recent
                                            such month, this one
                                            counted, 00:00

All reckoning is in UTC, where the Bookkeeper's instants live.

HOW THE KEYWORDS COMBINE: several '--glob' occurrences hold ONE
question and are OR'ed among themselves -- a case matching any of them
matches. The keywords of DIFFERENT kinds are AND'ed: '--fail
--since=2h' wants a case that failed AND ran within two hours. An
absent keyword asks nothing. '--fail --pass' can want nothing and is
refused at the door; so is '--since=X --until=Y' whose window is
empty.

A wish stating nothing at all wants everything. An empty match is
legal and reported; it is not a refusal (P-9).
______________________________________________________________________________
"""
import calendar
import os
import re
from dataclasses import dataclass, replace
from datetime    import datetime, timedelta, timezone

from .label      import LabelExprError, parse_expression


UNIT_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86400}

WEEKDAY_INDEX = {name.lower(): index for index, name
                 in enumerate(calendar.day_name)}      # monday -> 0
MONTH_INDEX   = {name.lower(): index for index, name
                 in enumerate(calendar.month_name) if index}


#  ---------------------------------------------------------------------
#  THE WISH'S OWN WORDS -- DATA, written ONCE: the argument list a face
#  adds to its own, and the block that describes them. A face that
#  re-describes these keywords in its own prose puts a second
#  description beside this one with nothing keeping the two aligned.
#
#  HOW a usage line is laid out is NOT this module's business (D-8):
#  the wrapping lives with the faces, in 'services/_core.py'.
#  ---------------------------------------------------------------------
USAGE_TOKEN_TUPLE = ("[--fail]", "[--pass]", "[--since=<point>]",
                     "[--until=<point>]", "[--glob <target>]...",
                     "[--exclude <target>]...",
                     "[--dir <glob>]...",
                     "[--exclude-dir <glob>]...",
                     "[--wishlist <file>]...", "[-l|--label <expr>]",
                     "[--language=<name>]...", "[--faster-than=<sec>]",
                     "[-F|--feature <id-glob>]...",
                     "[-e|--feature-ext <id>]...", "[-k|--keys <expr>]",
                     "[--no-boundary]")

HELP = """SELECTION -- the wish; an absent keyword asks nothing
    --fail              the last recorded run's verdict was negative
    --pass              the last recorded run's verdict was positive
    --since=<point>     the last recorded run lies AT or AFTER the
                        point; a case never run is not wanted
    --until=<point>     the last recorded run lies BEFORE the point,
                        and a case NEVER RUN is wanted too -- the
                        stale wish
    --exclude <target>  a target NOT wanted, whatever else selects it
    --dir <glob>        A DIRECTORY WANTED, and every run in it. The
                        glob matches a path relative to the run's root
                        ('messaging/*') or a BARE NAME matching any
                        path COMPONENT -- the same matching
                        '--exclude-dir' uses. SEVERAL ARE A UNION
                        among themselves and NARROW against the rest
                        of the wish: '--dir a --fail' is 'the failing
                        runs under a' (disc-10). A DIRECTORY-RELATED
                        face reads the same field as its SUBJECT
                        rather than as a filter.
    --exclude-dir <glob>
                        a directory not wanted, and every directory
                        below it; a bare name matches any component
                        WHERE '--dir' AND '--exclude-dir' MEET, grep's
                        rule decides: they are read in command-line
                        order and the LAST ONE MATCHING a directory
                        decides; where none matches, the directory is
                        wanted unless the FIRST of them is a '--dir'.
                        '--exclude-dir a --dir a/keep' keeps 'a/keep'.
    --wishlist <file>   the file's lines as targets, '#' comments and
                        blanks dropped, './' meaning the file's own
                        directory
    --glob <target>     a target: a file name, or a file name and a
                        choice name with one blank between, either
                        carrying fnmatch's '*', '?' and '[ ]':
                            --glob "test-*.py quick-[0-2]"
                        may stand several times; the globs are OR'ed
                        among themselves
    -l, --label <expr>  the runs the label expression names ('AND',
                        'OR', 'NOT', brackets; ',' is 'OR'; 'all' the
                        universe); a union among its labels, narrowing
                        against the rest; absent, 'meta' is silent --
                        which a LITERAL target overrides, and a glob
                        does not (it warns instead)
    --language=<name>   the runs of test applications of that language;
                        several are a union, narrowing against the rest
    -F, --feature <id-glob>
                        the runs linked to the features the glob names:
                        tree paths of the central file 'a/b/<external
                        id>' ('*' one level, '**' any depth, '{a,b}'), a
                        bare word anywhere, an aggregate its subtree; or
                        an internal id 'X:name'. Several are a union,
                        narrowing against the rest
    -e, --feature-ext <id>
                        the runs linked to the feature of that external
                        id ('*' any characters); with '-F' a union
    --no-boundary       walk INTO an inner 'hwut-root.conf' (RQ-1) --
                        what every run does since RQ-9: a bubble of its
                        own is entered, its configuration reset from
                        that file alone, nothing above reaching below.
                        Accepted for the scripts that say it. Selects
                        nothing by itself
    -k, --keys <expr>   the runs linked to features whose effective keys
                        satisfy the expression ('AND', 'OR', 'NOT',
                        brackets; ',' is 'OR'); a key flows down from the
                        aggregates above a leaf, never up
    --faster-than=<seconds>
                        the runs this machine last saw finish faster
                        than that; one this machine never saw is not
                        wanted
    <app> [<choice>...] the short form: bare words are targets, the
                        first naming files, each further one a
                        choice; globbing allowed in both"""


class WishError(Exception):
    """A wish the command line cannot mean: an unreadable point, a
    keyword without its value, a combination that can want nothing."""


@dataclass(frozen=True, slots=True)
class Wish:
    """What the command line states. 'None' is 'asks nothing'; the
    empty glob tuple asks nothing too -- UNLESS a wishlist was read
    ('wishlist_f'), which states its emptiness. 'since_spec' and
    'until_spec'
    hold the author's own words ('2h', 'monday'); the instant they
    mean is a function of now and is answered by 'cutoff_instant'."""
    fail_f:     bool  = False
    pass_f:     bool  = False
    since_spec: str | None = None
    until_spec: str | None = None
    glob_tuple:        tuple = ()
    wishlist_f:        bool  = False
    exclude_tuple:     tuple = ()
    exclude_dir_tuple: tuple = ()
    dir_tuple:         tuple = ()
    label_spec: str | None = None
    language_tuple:    tuple = ()
    #  Integer MILLISECONDS, and the unit is in the name: the command
    #  line takes human seconds and converts at the boundary (E-23).
    faster_than_ms:    int | None = None
    #  NO NOMINAL STANDS (E-58): what was never accepted -- the whole
    #  case, as '##! unaccepted' marks a stretch of one.
    unaccepted_f:      bool  = False
    #  '--dir' and '--exclude-dir' IN COMMAND-LINE ORDER, as ('+', glob)
    #  and ('-', glob): the order decides (grep's rule, see HELP).
    dir_rule_tuple:    tuple = ()
    #  THE FEATURES WANTED (R-95): id globs, a union, and an expression
    #  over the keys of the features. Both narrow against the rest.
    feature_tuple:     tuple = ()
    keys_spec:         str | None = None
    #  FEATURES BY THEIR EXTERNAL ID (R-96): what a customer holds.
    feature_ext_tuple: tuple = ()
    #  THE WALK ENTERS INNER ROOTS (RQ-1, '--no-boundary') -- the default
    #  since RQ-9 (E-200); the word stays readable. It states nothing of
    #  what is wanted.
    no_boundary_f:     bool  = False
    #  THE RECORDINGS A WISHLIST NAMES BY DIGEST (E-168): pairs
    #  '(<literal target>, <tag>)', the target as the list's line
    #  expanded. Read by 'hwut.accept' alone; every other face refuses.
    digest_tuple:      tuple = ()

    def states_nothing_f(self):
        """
        RETURN: bool, True where the wish states no keyword at all --
                everything is wanted.

        A WISHLIST THAT WAS READ STATES SOMETHING, even where it named
        nothing. An enumeration's EMPTINESS IS A STATEMENT -- the
        author commented the last line out and means it -- while the
        absence of any wish is not a statement at all. Without this
        distinction, narrowing a list by commenting lines out reaches
        a point where the list explodes into the whole tree, which is
        the opposite of what the file says.
        """
        return not (self.fail_f or self.pass_f or self.unaccepted_f
                    or self.glob_tuple
                    or self.wishlist_f or self.exclude_tuple
                    or self.exclude_dir_tuple or self.dir_tuple) \
               and self.since_spec is None and self.until_spec is None \
               and self.label_spec is None and not self.language_tuple \
               and self.faster_than_ms is None \
               and not self.feature_tuple and self.keys_spec is None \
               and not self.feature_ext_tuple

    def asks_feature_f(self):
        """
        RETURN: bool, True where the wish names features or keys -- a
                question only the feature relation of the tree can
                answer.
        """
        return bool(self.feature_tuple) or self.keys_spec is not None \
               or bool(self.feature_ext_tuple)

    def asks_glob_f(self):
        """
        RETURN: bool, True where the TARGETS are a question -- globs
                stated, or a wishlist read whatever it held.
        """
        return bool(self.glob_tuple) or self.wishlist_f

    def asks_label_f(self):
        """
        RETURN: bool, True where the wish names labels -- a question
                only 'hwut-root.labels' can answer, so a CLabelView
                must be handed down wherever it is asked.
        """
        return self.label_spec is not None

    def asks_base_f(self):
        """
        RETURN: bool, True where a question can only be answered out
                of the Bookkeeper's base or this machine's local
                observations: --fail, --pass, --since, --until,
                --faster-than.
        """
        return self.fail_f or self.pass_f or self.unaccepted_f \
               or self.since_spec is not None \
               or self.until_spec is not None \
               or self.faster_than_ms is not None

    def __str__(self):
        """
        RETURN: str, the wish as the command line states it; '(all)'
                where it states nothing.
        """
        if self.states_nothing_f(): return "(all)"
        part_list = []
        if self.fail_f:                 part_list.append("--fail")
        if self.unaccepted_f:           part_list.append("--unaccepted")
        if self.no_boundary_f:          part_list.append("--no-boundary")
        if self.pass_f:                 part_list.append("--pass")
        if self.since_spec is not None:
            part_list.append("--since=%s" % self.since_spec)
        if self.until_spec is not None:
            part_list.append("--until=%s" % self.until_spec)
        part_list.extend('--glob "%s"' % text
                         for text in self.glob_tuple)
        part_list.extend('--exclude "%s"' % text
                         for text in self.exclude_tuple)
        part_list.extend('--dir "%s"' % text
                         for text in self.dir_tuple)
        part_list.extend('--exclude-dir "%s"' % text
                         for text in self.exclude_dir_tuple)
        if self.label_spec is not None:
            part_list.append('--label "%s"' % self.label_spec)
        part_list.extend("--language=%s" % name
                         for name in self.language_tuple)
        if self.faster_than_ms is not None:
            part_list.append("--faster-than=%g"
                             % (self.faster_than_ms / 1000.0))
        part_list.extend('--feature "%s"' % text
                         for text in self.feature_tuple)
        part_list.extend('--feature-ext "%s"' % text
                         for text in self.feature_ext_tuple)
        if self.keys_spec is not None:
            part_list.append('--keys "%s"' % self.keys_spec)
        return " ".join(part_list)


def parse_wish(argv, digest_f=False):
    """
    RETURN: [0] Wish, what the selection keywords of 'argv' state.
            [1] list[str], the arguments that are none of them, in
                order -- the caller's own.

    Raises WishError, naming the argument, for: a point that cannot be
    read; '--glob', '--wishlist', '--since' or '--until' standing
    without a value; a wishlist file that cannot be read; '--fail'
    beside '--pass'; a '--since'/'--until' pair whose window is empty
    for every now.

    A WISHLIST'S LINES BECOME GLOB TARGETS, in file order, after any
    '--glob' already read: they hold ONE question with them and are
    OR'ed, which is what a list of wanted tests means.
    """
    fail_f     = False
    unaccepted_f = False
    no_boundary_f = False
    pass_f     = False
    since_spec = None
    until_spec = None
    glob_list        = []
    exclude_list     = []
    exclude_dir_list = []
    dir_list         = []
    dir_rule_list    = []
    wishlist_f       = False
    digest_list      = []
    label_spec       = None
    language_list    = []
    faster_than_ms   = None
    feature_list     = []
    feature_ext_list = []
    keys_spec        = None
    rest_list        = []

    index = 0
    while index < len(argv):
        argument = argv[index]
        index   += 1
        if   argument == "--fail":  fail_f = True
        elif argument == "--unaccepted": unaccepted_f = True
        elif argument == "--no-boundary": no_boundary_f = True
        elif argument == "--pass":  pass_f = True
        elif argument.startswith("--since="):
            since_spec = _validated(argument[len("--since="):], argument)
        elif argument.startswith("--until="):
            until_spec = _validated(argument[len("--until="):], argument)
        elif argument in ("--since", "--until"):
            raise WishError("'%s' stands without a point; write "
                            "'%s=2h' or '%s=yesterday'"
                            % (argument, argument, argument))
        elif argument == "--glob":
            if index >= len(argv):
                raise WishError("'--glob' stands without a target")
            glob_list.append(argv[index])
            index += 1
        elif argument.startswith("--glob="):
            glob_list.append(argument[len("--glob="):])
        elif argument in ("--exclude", "--exclude-dir"):
            if index >= len(argv):
                raise WishError("'%s' stands without a target" % argument)
            if argument == "--exclude": exclude_list.append(argv[index])
            else:
                exclude_dir_list.append(argv[index])
                dir_rule_list.append(("-", argv[index]))
            index += 1
        elif argument.startswith("--exclude="):
            exclude_list.append(argument[len("--exclude="):])
        elif argument.startswith("--exclude-dir="):
            exclude_dir_list.append(argument[len("--exclude-dir="):])
            dir_rule_list.append(("-", argument[len("--exclude-dir="):]))
        elif argument == "--dir":
            if index >= len(argv):
                raise WishError("'--dir' stands without a glob")
            dir_list.append(argv[index])
            dir_rule_list.append(("+", argv[index])); index += 1
        elif argument.startswith("--dir="):
            dir_list.append(argument[len("--dir="):])
            dir_rule_list.append(("+", argument[len("--dir="):]))
        elif argument == "--wishlist":
            if index >= len(argv):
                raise WishError("'--wishlist' stands without a file")
            target_tuple, found = _wishlist_read(argv[index], digest_f)
            glob_list.extend(target_tuple)
            digest_list.extend(found)
            wishlist_f = True
            index += 1
        elif argument.startswith("--wishlist="):
            target_tuple, found = _wishlist_read(
                argument[len("--wishlist="):], digest_f)
            glob_list.extend(target_tuple)
            digest_list.extend(found)
            wishlist_f = True
        elif argument in ("--label", "-l") \
                or argument.startswith("--label=") \
                or argument.startswith("-l="):
            #  '-l' IS '--label' AND NOTHING ELSE (E-112): a label is
            #  asked for by name, never resolved out of a bare word --
            #  a wish says what it means, whatever the tree holds.
            if argument in ("--label", "-l"):
                if index >= len(argv):
                    raise WishError("'%s' stands without an "
                                    "expression" % argument)
                text   = argv[index]
                index += 1
            elif argument.startswith("-l="):
                text = argument[len("-l="):]
            else:
                text = argument[len("--label="):]
            if label_spec is not None:
                raise WishError(
                    "'--label' stands twice; one expression holds "
                    "the whole question -- write "
                    "'--label \"%s OR %s\"'" % (label_spec, text))
            try:
                parse_expression(text)
            except LabelExprError as error:
                raise WishError("'--label %s' cannot be read -- %s"
                                % (text, error)) from None
            label_spec = text
        elif argument in ("--feature", "-F") \
                or argument.startswith("--feature="):
            if argument in ("--feature", "-F"):
                if index >= len(argv):
                    raise WishError("'%s' stands without an id glob"
                                    % argument)
                text   = argv[index]
                index += 1
            else:
                text = argument[len("--feature="):]
            if not text.strip():
                raise WishError("'--feature' names no id")
            if text.strip() not in feature_list:
                feature_list.append(text.strip())
        elif argument in ("--feature-ext", "-e") \
                or argument.startswith("--feature-ext="):
            if argument in ("--feature-ext", "-e"):
                if index >= len(argv):
                    raise WishError("'%s' stands without an external id"
                                    % argument)
                text   = argv[index]
                index += 1
            else:
                text = argument[len("--feature-ext="):]
            if not text.strip():
                raise WishError("'--feature-ext' names no id")
            if text.strip() not in feature_ext_list:
                feature_ext_list.append(text.strip())
        elif argument in ("--keys", "-k") or argument.startswith("--keys="):
            if argument in ("--keys", "-k"):
                if index >= len(argv):
                    raise WishError("'%s' stands without an expression"
                                    % argument)
                text   = argv[index]
                index += 1
            else:
                text = argument[len("--keys="):]
            if keys_spec is not None:
                raise WishError(
                    "'--keys' stands twice; one expression holds the "
                    "whole question -- write '--keys \"%s OR %s\"'"
                    % (keys_spec, text))
            try:
                parse_expression(text)
            except LabelExprError as error:
                raise WishError("'--keys %s' cannot be read -- %s"
                                % (text, error)) from None
            keys_spec = text
        elif argument == "--faster-than" \
             or argument.startswith("--faster-than="):
            text = argument[len("--faster-than="):] \
                   if "=" in argument else ""
            if not text:
                raise WishError("'--faster-than' stands without a span; "
                                "write '--faster-than=2.5' -- seconds")
            try:
                seconds = float(text)
            except ValueError:
                raise WishError("'--faster-than=%s' is not a number of "
                                "seconds" % text) from None
            if seconds <= 0.0:
                raise WishError("'--faster-than=%s': a span must be "
                                "positive" % text)
            faster_than_ms = int(seconds * 1000)
        elif argument == "--language":
            raise WishError("'--language' stands without a name; write "
                            "'--language=python'")
        elif argument.startswith("--language="):
            name = argument[len("--language="):].strip()
            if not name:
                raise WishError("'--language=' names nothing")
            if name not in language_list: language_list.append(name)
        else:
            rest_list.append(argument)

    if fail_f and pass_f:
        raise WishError("'--fail' beside '--pass' can want nothing")
    if since_spec is not None and until_spec is not None \
       and _span_or_none(since_spec) is not None \
       and _span_or_none(until_spec) is not None \
       and _span_or_none(since_spec) <= _span_or_none(until_spec):
        raise WishError(
            "'--since=%s --until=%s': the window is empty -- 'until' "
            "must lie further back than 'since'"
            % (since_spec, until_spec))

    return (Wish(fail_f, pass_f, since_spec, until_spec,
                 tuple(glob_list), wishlist_f,
                 tuple(exclude_list), tuple(exclude_dir_list),
                 tuple(dir_list), label_spec, tuple(language_list),
                 faster_than_ms, unaccepted_f, tuple(dir_rule_list),
                 tuple(feature_list), keys_spec, tuple(feature_ext_list),
                 digest_tuple=tuple(digest_list),
                 no_boundary_f=no_boundary_f),
            rest_list)


#  A WISHLIST LINE MAY END IN ONE '--digest=<tag>' (E-168).
_DIGEST_SUFFIX_RE = re.compile(r"\s+--digest=(\S+)\s*$")
_GLOB_MARK_TUPLE  = ("*", "?", "[")


def wishlist_target_tuple(file_name):
    """
    RETURN: tuple[str], the targets a wishlist file states, as
            '_wishlist_read' reads them, if success.
            raises WishError, else -- also where a line carries a
            '--digest', which only 'hwut.accept' reads.
    """
    return _wishlist_read(file_name, False)[0]


def _wishlist_read(file_name, digest_f):
    """
    RETURN: [0] tuple[str], the targets the wishlist file states, in
                file order, if success;
            [1] tuple[(str, str)], '(<target>, <tag>)' for every line
                ending in '--digest=<tag>', the target as in [0];
            raises WishError naming file and line, else.

    A '--digest' stands only after a LITERAL target -- a glob names a
    set nobody has looked at yet (E-168) -- and only where the caller
    reads it ('digest_f', 'hwut.accept'); every other face refuses it
    by name, so a check written in the list is never silently dropped.

    One target per line, '#' comments and blank lines dropped, a
    leading './' replaced by the file's OWN directory.

    Raises WishError naming the file where it cannot be read: a
    wishlist that is not there is a command line that cannot be read,
    not an empty selection.

    THE './' IS THE LIST'S OWN GROUND. A list describes a tree and
    should travel with it, so 'messaging.txt' beside 'messaging/' may
    say './queue/TEST/test-a.py' and mean it wherever the checkout
    sits. A line already naming a path relative to the run's root is
    left as it stands.
    """
    try:
        with open(file_name, "r", encoding="utf-8") as file_handle:
            line_list = file_handle.read().splitlines()
    except OSError as error:
        raise WishError("the wishlist '%s' cannot be read -- %s"
                        % (file_name, error)) from None

    #  ABSOLUTE, always: the list's ground must be a place, not a
    #  path relative to wherever the reader happens to stand. That is
    #  what lets a list travel with the tree it describes.
    here = os.path.abspath(os.path.dirname(file_name) or ".")
    target_list = []
    digest_list = []
    for number, line in enumerate(line_list, start=1):
        text = line.strip()
        if not text or text.startswith("#"): continue
        tag   = None
        match = _DIGEST_SUFFIX_RE.search(text)
        if match is not None:
            if not digest_f:
                raise WishError("'%s', line %d: '--digest' is read by "
                                "'hwut.accept' alone" % (file_name, number))
            tag  = match.group(1)
            text = text[:match.start()].rstrip()
            if any(mark in text for mark in _GLOB_MARK_TUPLE):
                raise WishError("'%s', line %d: '--digest' follows a glob "
                                "-- a digest names ONE recording; name the "
                                "test run literally" % (file_name, number))
        if text.startswith(":"):
            previous = target_list[-1] if target_list else None
            try:
                text = expanded_target(text, previous)
            except ElisionError as error:
                raise WishError("'%s', line %d: %s"
                                % (file_name, number, error)) from None
        elif text.startswith("./"):
            text = "%s/%s" % (here.replace(os.sep, "/").rstrip("/"),
                              text[2:])
        target_list.append(text)
        if tag is not None: digest_list.append((text, tag))
    return tuple(target_list), tuple(digest_list)


def desugar_positional(word_list):
    """
    RETURN: tuple[str], the wish globs a SHORT FORM asks for -- empty
            where no word stands.

    THE SHORT FORM OF HWUT 1.0, revived: the first word names files,
    every further word a choice; each choice becomes its own target,
    and the wish OR's them. Globbing is allowed in BOTH members, as
    it is in '--glob'.

        ("test-*.py", "one", "two")
            -> ("test-*.py one", "test-*.py two")
        ("test-*.py",)
            -> ("test-*.py",)          every choice of the file

    IT IS SUGAR AND NOTHING MORE: it becomes wish globs, and the
    wish's own engine does the selecting. One selection language, so
    the short form can never mean what the long form cannot say.

    A face whose bare words already mean something else --
    'hwut.rename <app> -to <app>', 'hwut.labels.create <label>' -- does
    not call this: the sugar is a thing a face asks for, never a
    thing 'parse_wish' does behind its back.
    """
    if not word_list: return ()
    file_glob    = word_list[0]
    choice_tuple = tuple(word_list[1:])
    if not choice_tuple: return (file_glob,)
    return tuple("%s %s" % (file_glob, choice)
                 for choice in choice_tuple)


def with_targets(wish, word_list):
    """
    RETURN: Wish, 'wish' with the short form's targets added to its
            globs -- 'wish' itself where no word stands.
    """
    glob_tuple = desugar_positional(word_list)
    if not glob_tuple: return wish
    return replace(wish, glob_tuple=wish.glob_tuple + glob_tuple)


class ElisionError(Exception):
    """An elided target that cannot be expanded: a ditto with no
    predecessor, a ':/:' without a choice, a lone ':'."""


def expanded_target(text, previous):
    """
    RETURN: str, the target 'text' with its elision expanded against
            'previous' -- the LAST EXPANDED TARGET before it (disc-8):

                :/<file> [<choice>]   previous target's DIRECTORY
                :/: <choice>          its directory AND its file

    Raises ElisionError where no expansion can be meant: 'previous' is
    None -- A DITTO WITH NO PREDECESSOR is the one way the notation
    can be silently wrong, expanded against the wrong entry it names a
    real run nobody meant -- or ':/:' stands without a choice, which
    would only name the previous run again, or the mark is malformed.
    """
    if previous is None:
        raise ElisionError("a ditto ('%s') stands with no target "
                           "before it to elide from" % text)
    previous_file = previous.split(" ", 1)[0]
    if text.startswith(":/:"):
        choice = text[len(":/:"):].strip()
        if not choice:
            raise ElisionError("':/:' stands without a choice -- it "
                               "would only name the previous run "
                               "again")
        return "%s %s" % (previous_file, choice)
    if text.startswith(":/"):
        rest = text[len(":/"):].strip()
        if not rest:
            raise ElisionError("':/' stands without a file")
        directory = previous_file.rsplit("/", 1)[0] \
                    if "/" in previous_file else ""
        return "%s/%s" % (directory, rest) if directory else rest
    raise ElisionError("a leading ':' is an elision mark and reads "
                       "':/' or ':/:' -- '%s' is neither" % text)


def cutoff_instant(spec, now):
    """
    RETURN: datetime, the instant the point names, reckoned in UTC
            from 'now': 'now - span' for a span, the anchor's 00:00
            for an anchor.

    'spec' has passed 'parse_wish'; an unknown word here is a defect
    and asserts.
    """
    if now.tzinfo is None: now = now.replace(tzinfo=timezone.utc)
    span = _span_or_none(spec)
    if span is not None:
        return now - timedelta(seconds=span)

    day  = now.date()
    word = spec.lower()
    if word == "today":
        anchor_day = day
    elif word == "yesterday":
        anchor_day = day - timedelta(days=1)
    elif word == "last-week":
        anchor_day = day - timedelta(days=day.weekday() + 7)
    elif word == "last-month":
        first      = day.replace(day=1)
        anchor_day = (first - timedelta(days=1)).replace(day=1)
    elif word in WEEKDAY_INDEX:
        back       = (day.weekday() - WEEKDAY_INDEX[word]) % 7
        anchor_day = day - timedelta(days=back)
    elif word in MONTH_INDEX:
        month = MONTH_INDEX[word]
        year  = now.year if month <= now.month else now.year - 1
        anchor_day = day.replace(year=year, month=month, day=1)
    else:
        raise AssertionError("'%s' passed parsing yet names no point" % spec)
    return datetime(anchor_day.year, anchor_day.month, anchor_day.day,
                    tzinfo=timezone.utc)


def _validated(text, argument):
    """
    RETURN: str, the point as written, once it is known to be readable:
            a span, or a word of the anchor vocabulary.

    Raises WishError, naming the argument, else.
    """
    if _span_or_none(text) is not None: return text
    word = text.lower()
    if word in ("today", "yesterday", "last-week", "last-month") \
       or word in WEEKDAY_INDEX or word in MONTH_INDEX:
        return word
    raise WishError(
        "'%s': a point is a span -- a number and one of 's', 'm', "
        "'h', 'd', as in '2h' -- or one of: today, yesterday, "
        "last-week, last-month, a weekday, a month" % argument)


def _span_or_none(text):
    """
    RETURN: float, the span in seconds where 'text' is a number and a
            unit / None, else -- including where the number is
            negative, which no span is.
    """
    if not text or text[-1] not in UNIT_SECONDS: return None
    try:
        number = float(text[:-1])
    except ValueError:
        return None
    if number < 0: return None
    return number * UNIT_SECONDS[text[-1]]
