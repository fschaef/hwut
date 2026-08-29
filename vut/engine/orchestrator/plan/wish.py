"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
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
                        with them. 'hwut.wishlist' PRINTS this form,
                        so the round trip closes.
THE SHORT FORM OF HWUT 1.0 lives here too ('desugar_positional',
'with_targets'): a face may take BARE WORDS -- 'hwut.run test-app.sh
one' -- the first naming files, every further one a choice, globbing
allowed in both. It is sugar for '--glob' and nothing else, so the
short form can never mean what the long form cannot say.

    --label <expr>      the runs the label expression names, out of
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
                     "[--wishlist <file>]...", "[--label <expr>]")

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
    --wishlist <file>   the file's lines as targets, '#' comments and
                        blanks dropped, './' meaning the file's own
                        directory
    --glob <target>     a target: a file name, or a file name and a
                        choice name with one blank between, either
                        carrying fnmatch's '*', '?' and '[ ]':
                            --glob "test-*.py quick-[0-2]"
                        may stand several times; the globs are OR'ed
                        among themselves
    --label <expr>      the runs the label expression names ('AND',
                        'OR', 'NOT', brackets; ',' is 'OR'; 'all' the
                        universe); a union among its labels, narrowing
                        against the rest; absent, 'meta' is silent --
                        which a LITERAL target overrides, and a glob
                        does not (it warns instead)
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
        return not (self.fail_f or self.pass_f or self.glob_tuple
                    or self.wishlist_f or self.exclude_tuple
                    or self.exclude_dir_tuple or self.dir_tuple) \
               and self.since_spec is None and self.until_spec is None \
               and self.label_spec is None

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
                of the Bookkeeper's base: --fail, --pass, --since,
                --until.
        """
        return self.fail_f or self.pass_f \
               or self.since_spec is not None \
               or self.until_spec is not None

    def __str__(self):
        """
        RETURN: str, the wish as the command line states it; '(all)'
                where it states nothing.
        """
        if self.states_nothing_f(): return "(all)"
        part_list = []
        if self.fail_f:                 part_list.append("--fail")
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
        return " ".join(part_list)


def parse_wish(argv):
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
    pass_f     = False
    since_spec = None
    until_spec = None
    glob_list        = []
    exclude_list     = []
    exclude_dir_list = []
    dir_list         = []
    wishlist_f       = False
    label_spec       = None
    rest_list        = []

    index = 0
    while index < len(argv):
        argument = argv[index]
        index   += 1
        if   argument == "--fail":  fail_f = True
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
            else:                       exclude_dir_list.append(argv[index])
            index += 1
        elif argument.startswith("--exclude="):
            exclude_list.append(argument[len("--exclude="):])
        elif argument.startswith("--exclude-dir="):
            exclude_dir_list.append(argument[len("--exclude-dir="):])
        elif argument == "--dir":
            if index >= len(argv):
                raise WishError("'--dir' stands without a glob")
            dir_list.append(argv[index]); index += 1
        elif argument.startswith("--dir="):
            dir_list.append(argument[len("--dir="):])
        elif argument == "--wishlist":
            if index >= len(argv):
                raise WishError("'--wishlist' stands without a file")
            glob_list.extend(wishlist_target_tuple(argv[index]))
            wishlist_f = True
            index += 1
        elif argument.startswith("--wishlist="):
            glob_list.extend(
                wishlist_target_tuple(argument[len("--wishlist="):]))
            wishlist_f = True
        elif argument == "--label" or argument.startswith("--label="):
            if argument == "--label":
                if index >= len(argv):
                    raise WishError("'--label' stands without an "
                                    "expression")
                text   = argv[index]
                index += 1
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
                 tuple(dir_list), label_spec),
            rest_list)


def wishlist_target_tuple(file_name):
    """
    RETURN: tuple[str], the targets a wishlist file states, in file
            order -- one per line, '#' comments and blank lines
            dropped, and a leading './' replaced by the file's OWN
            directory.

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
    for number, line in enumerate(line_list, start=1):
        text = line.strip()
        if not text or text.startswith("#"): continue
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
    return tuple(target_list)


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
    'hwut.rename <old> <new>', 'hwut.labels.create <label>' -- does
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
