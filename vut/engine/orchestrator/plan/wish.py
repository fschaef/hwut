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
                        times

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
from dataclasses import dataclass
from datetime    import datetime, timedelta, timezone


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
                     "[--until=<point>]", "[--glob <target>]...")

HELP = """SELECTION -- the wish; an absent keyword asks nothing
    --fail              the last recorded run's verdict was negative
    --pass              the last recorded run's verdict was positive
    --since=<point>     the last recorded run lies AT or AFTER the
                        point; a case never run is not wanted
    --until=<point>     the last recorded run lies BEFORE the point,
                        and a case NEVER RUN is wanted too -- the
                        stale wish
    --glob <target>     a target: a file name, or a file name and a
                        choice name with one blank between, either
                        carrying fnmatch's '*', '?' and '[ ]':
                            --glob "test-*.py quick-[0-2]"
                        may stand several times; the globs are OR'ed
                        among themselves"""


class WishError(Exception):
    """A wish the command line cannot mean: an unreadable point, a
    keyword without its value, a combination that can want nothing."""


@dataclass(frozen=True, slots=True)
class Wish:
    """What the command line states. 'None' is 'asks nothing'; the
    empty glob tuple asks nothing too. 'since_spec' and 'until_spec'
    hold the author's own words ('2h', 'monday'); the instant they
    mean is a function of now and is answered by 'cutoff_instant'."""
    fail_f:     bool  = False
    pass_f:     bool  = False
    since_spec: str | None = None
    until_spec: str | None = None
    glob_tuple: tuple = ()

    def states_nothing_f(self):
        """
        RETURN: bool, True where the wish states no keyword at all --
                everything is wanted.
        """
        return not (self.fail_f or self.pass_f or self.glob_tuple) \
               and self.since_spec is None and self.until_spec is None

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
        return " ".join(part_list)


def parse_wish(argv):
    """
    RETURN: [0] Wish, what the selection keywords of 'argv' state.
            [1] list[str], the arguments that are none of them, in
                order -- the caller's own.

    Raises WishError, naming the argument, for: a point that cannot be
    read; '--glob', '--since' or '--until' standing without a value;
    '--fail' beside '--pass'; a '--since'/'--until' pair whose window
    is empty for every now.
    """
    fail_f     = False
    pass_f     = False
    since_spec = None
    until_spec = None
    glob_list  = []
    rest_list  = []

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
                 tuple(glob_list)),
            rest_list)


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
        assert False, "'%s' passed parsing yet names no point" % spec
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
