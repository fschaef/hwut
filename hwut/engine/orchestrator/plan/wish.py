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
                        relative to the run's root, matched LEVEL BY
                        LEVEL: '*' inside one level, '**' any number of
                        levels (E-206) -- 'messaging/**/test-queue.py'
                        selects ACROSS THE TREE. (A path is illegal where a
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
                        so the round trip closes. A line may also be a
                        RULE (E-202): '!<target>' is '--exclude',
                        '<dir-glob>/' is '--dir', '!<dir-glob>/' is
                        '--exclude-dir', '!<hwut-root>' is
                        '--no-bubbles'. A LIST NAMES NO SET: a
                        'label:' line is refused (intend/three-worlds);
                        directory lines keep their
                        order among the command line's, the last one
                        matching deciding.
THE SHORT FORM OF HWUT 1.0 lives here too ('desugar_positional',
'with_targets'): a face may take BARE WORDS -- 'hwut.run test-app.sh
one' -- the first naming files, every further one a choice, globbing
allowed in both. It is sugar for '--glob' and nothing else, so the
short form can never mean what the long form cannot say.

    -l, --label <expr>  the runs the label expression names, out of
                        'hwut-root.labels' (disc-8): 'AND', 'OR',
                        'NOT', brackets, 'all' the universe, ',' sugar
                        for 'OR'; 'f/<id>' the runs of a feature
                        (plan/label). A UNION among the labels it names
                        -- a label names a SET, and naming two asks for
                        both. IT STANDS ALONE (intend/three-worlds,
                        ruled 2026-10-31): beside any other word of the
                        wish -- a target, a glob, a directory, a
                        wishlist, a history word, a language -- it is
                        refused by name. A face runs on a label
                        expression OR on wishlist arguments; sets are
                        combined in labels, the one domain of set
                        operations ('hwut.labels.create', '[derived]').
                        '--no-bubbles' is a word about the walk and may
                        stand beside it.
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
    '-F', '-e' AND '-k' ARE GONE from every face (spec 43, T-t): the
    runs of a feature are the label 'f/<id>'; each is refused by name.
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
                     "[--no-bubbles]")

#  THE PLATFORM WORDS (spec/42 section 2): WHERE the selected runs run.
#  Read by the faces that run a test -- 'hwut.run', 'hwut.play' -- and by
#  'hwut.sanitize.propose', which names every platform and runs nothing
#  (intend/42 ruling 12); every other face that reads the wish refuses
#  them by name ('PLATFORM_FACE_TEXT'). Shown only by the faces that take
#  them: their usage carries 'PLATFORM_USAGE_TOKEN_TUPLE', their help
#  'PLATFORM_HELP'.
LOCAL_PLATFORM            = "local"
PLATFORM_FACE_TEXT        = "hwut.run, hwut.play"
PLATFORM_WORD_TUPLE       = ("-p", "--exclude-local")
PLATFORM_USAGE_TOKEN_TUPLE = ("[-p <platform>]...", "[--exclude-local]")
PLATFORM_HELP = """PLATFORM -- where the selected runs run
    -p <platform>       ADDS the platform to those specified; 'local',
                        this machine, is specified without it. A bubble
                        whose 'hwut-root.conf' says 'platform = [...]'
                        requires those platforms; one with none requires
                        'local'. A bubble runs where the two meet; where
                        they do not, it is not run. May stand several
                        times; a platform no bubble requires is a NOTE
    --exclude-local     takes 'local' out of those specified: only the
                        bubbles requiring a '-p' platform run"""

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
                        directory; a line may be a rule instead:
                            !<target>       not wanted ('--exclude')
                            <dir-glob>/     wanted ('--dir')
                            !<dir-glob>/    not entered ('--exclude-dir')
                            !<hwut-root>    '--no-bubbles'
                        the last directory line matching decides; a
                        list names no set -- no 'label:' line
    --glob <target>     a target: a file name, or a file name and a
                        choice name with one blank between, either
                        carrying fnmatch's '*', '?' and '[ ]':
                            --glob "test-*.py quick-[0-2]"
                        in a path, '*' stays inside one level and '**'
                        spans any number: "net/**/test-*.py"
                        may stand several times; the globs are OR'ed
                        among themselves
    -l, --label <expr>  the runs the label expression names ('AND',
                        'OR', 'NOT', brackets; ',' is 'OR'; 'all' the
                        universe; 'f/<id>' the runs of a feature by its
                        id, an aggregate its subtree). It STANDS ALONE: beside
                        a target, a glob, a directory, a wishlist or a
                        history word it is refused -- combine sets in
                        labels. Absent, 'meta' is silent -- which a
                        LITERAL target overrides, and a glob does not
                        (it warns instead)
    --language=<name>   the runs of test applications of that language;
                        several are a union, narrowing against the rest
    --no-bubbles        do not enter an inner 'hwut-root.conf' (RQ-9):
                        by default the walk enters every bubble below,
                        each under its own configuration. Selects
                        nothing by itself
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
    #  THE WALK STAYS OUT OF INNER BUBBLES (RQ-9, E-202): '--no-bubbles',
    #  or '!<hwut-root>' in a wishlist. By default a walk that selects
    #  enters every inner 'hwut-root.conf'. A word about the WALK: it
    #  states nothing of what is wanted.
    no_bubbles_f:      bool  = False
    #  THE RECORDINGS A WISHLIST NAMES BY DIGEST (E-168): pairs
    #  '(<literal target>, <tag>)', the target as the list's line
    #  expanded. Read by 'hwut.accept' alone; every other face refuses.
    digest_tuple:      tuple = ()
    #  WHERE THE RUNS RUN (spec/42 section 2): the '-p' names in order,
    #  each once, and '--exclude-local'. Words about WHERE: they state
    #  nothing of what is wanted, as '--no-bubbles' states nothing.
    platform_tuple:    tuple = ()
    exclude_local_f:   bool  = False
    #  THE PLATFORM THIS RUN IS (spec/42, THE RULE: "over there, a far
    #  run's own 'local' IS the platform it was handed to"): written by the
    #  near hand-over alone ('far_argv'), never by a person.
    as_platform:       str | None = None

    def far_argv(self, bubble, platform):
        """
        RETURN: list of str, the words a far 'hwut.run' takes to run what
                this wish wants of the bubble at 'bubble' (relative to
                the near root, '.' the root itself) -- spec/42 section 4:
                its targets and directory rules RE-ROOTED at the bubble,
                one outside it dropped, every other word as given, no
                '-p' (over there, S = {local}), and '--as-platform=' naming
                'platform': its 'local' IS that platform -- if the wish
                wants anything there.
                None, else: targets or '--dir' rules stood and none of
                them reaches into the bubble.
        """
        target_list = [t for t in (_rerooted(g, bubble)
                                   for g in self.glob_tuple) if t is not None]
        if self.glob_tuple and not target_list: return None
        rule_list, wanted_f = [], not any(sign == "+" for sign, _
                                          in self.dir_rule_tuple)
        for sign, glob_text in self.dir_rule_tuple:
            if glob_text.rstrip("/") in _ancestor_tuple(bubble):
                wanted_f = wanted_f or sign == "+"
                continue
            rerooted = _rerooted(glob_text, bubble)
            if rerooted is None: continue
            rule_list.append((sign, rerooted))
            wanted_f = wanted_f or sign == "+"
        if not wanted_f: return None
        argv = ["--as-platform=%s" % platform]
        if self.fail_f:       argv.append("--fail")
        if self.pass_f:       argv.append("--pass")
        if self.unaccepted_f: argv.append("--unaccepted")
        if self.no_bubbles_f: argv.append("--no-bubbles")
        if self.since_spec is not None: argv.append("--since=" + self.since_spec)
        if self.until_spec is not None: argv.append("--until=" + self.until_spec)
        for target in target_list:  argv += ["--glob", target]
        for target in (_rerooted(e, bubble) for e in self.exclude_tuple):
            if target is not None: argv += ["--exclude", target]
        for sign, glob_text in rule_list:
            argv += ["--dir" if sign == "+" else "--exclude-dir", glob_text]
        if self.label_spec is not None: argv += ["--label", self.label_spec]
        argv += ["--language=" + name for name in self.language_tuple]
        if self.faster_than_ms is not None:
            argv.append("--faster-than=%g" % (self.faster_than_ms / 1000.0))
        return argv

    def specified_platform_set(self):
        """
        RETURN: frozenset of str, S of spec/42 section 2 -- 'local',
                unless '--exclude-local' took it out, and every '-p'
                name.
        """
        local = frozenset() if self.exclude_local_f \
                else frozenset((LOCAL_PLATFORM,))
        return local | frozenset(self.platform_tuple)

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
               and self.faster_than_ms is None

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
        if self.states_nothing_f() and not self.platform_tuple \
           and not self.exclude_local_f and self.as_platform is None:
            return "(all)"
        part_list = []
        if self.fail_f:                 part_list.append("--fail")
        if self.unaccepted_f:           part_list.append("--unaccepted")
        if self.no_bubbles_f:           part_list.append("--no-bubbles")
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
        if self.as_platform is not None:
            part_list.append("--as-platform=%s" % self.as_platform)
        if self.exclude_local_f:        part_list.append("--exclude-local")
        part_list.extend("-p %s" % name for name in self.platform_tuple)
        return " ".join(part_list)


def parse_wish(argv, digest_f=False, take_tuple=None,
               operand_ends_f=False, platform_f=False):
    """
    RETURN: [0] Wish, what the selection keywords of 'argv' state.
            [1] list[str], the arguments that are none of them, in
                order -- the caller's own.

    'platform_f' is a face that RUNS (spec/42 section 2): it alone reads
    '-p <platform>' and '--exclude-local'; any other face that reads the
    whole wish is refused them by name. '--exclude-local' with no '-p'
    is refused: it leaves no platform.

    THE ONE READER OF EVERY FACE THAT SELECTS. 'take_tuple' names the
    wish words the face takes, by their long spelling ('--dir',
    '--no-bubbles'); None takes every one. A wish word the face does
    not take is NOT READ: it lands in [1] as typed, and the face's own
    reader refuses it by name, as it refuses any word it does not know.
    'operand_ends_f': the first bare word ends the reading -- it and
    every word after it land in [1] untouched (a face whose words after
    its operand belong to someone else: 'hwut.execute's script).

    '-l' STANDS ALONE: beside any other word of the wish it is refused
    by name ('label_mix_text'); bare targets join later, and
    'with_targets' refuses them the same way.

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
    no_bubbles_f = False
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
    platform_list    = []
    exclude_local_f  = False
    as_platform      = None
    rest_list        = []
    #  THE FIRST WORD OF THE WISHLIST FAMILY, as typed: '-l' beside it
    #  is refused, naming it (R-b).
    family_word      = None

    index = 0
    while index < len(argv):
        argument = argv[index]
        index   += 1
        if operand_ends_f and not argument.startswith(("-", "+")):
            rest_list.extend(argv[index - 1:])
            break
        if take_tuple is not None and _long_word_of(argument) not in take_tuple:
            rest_list.append(argument)
            continue
        if family_word is None and _family_word_f(argument):
            family_word = argument
        if   argument == "--fail":  fail_f = True
        elif argument == "--unaccepted": unaccepted_f = True
        elif argument == "--no-bubbles": no_bubbles_f = True
        elif argument == "--no-boundary":
            #  RETIRED (RQ-9, E-202): it asked what every walk now does.
            raise WishError(NO_BOUNDARY_RETIRED_TEXT)
        elif argument == "--pass":  pass_f = True
        elif argument.startswith("--as-platform="):
            #  THE HAND-OVER'S OWN WORD (spec/42, THE RULE): not shown in
            #  any usage; a face that does not run is refused it.
            if not platform_f:
                raise WishError("'--as-platform' is for the faces that run: "
                                "%s" % PLATFORM_FACE_TEXT)
            as_platform = argument[len("--as-platform="):].strip() or None
        elif argument in PLATFORM_WORD_TUPLE or argument.startswith("-p="):
            word = argument.split("=", 1)[0]
            if not platform_f:
                raise WishError("'%s' is for the faces that run: %s"
                                % (word, PLATFORM_FACE_TEXT))
            if argument == "--exclude-local":
                exclude_local_f = True
                continue
            if argument == "-p":
                if index >= len(argv):
                    raise WishError("'-p' stands without a platform")
                name   = argv[index]
                index += 1
            else:
                name = argument[len("-p="):]
            if not name.strip():
                raise WishError("'-p' names no platform")
            if name.strip() not in platform_list:
                platform_list.append(name.strip())
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
                raise WishError("'%s' stands without a %s"
                                % (argument, "target" if argument == "--exclude"
                                             else "glob"))
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
            listed = _wishlist_read(argv[index], digest_f)
            glob_list.extend(listed.target_tuple)
            digest_list.extend(listed.digest_tuple)
            exclude_list.extend(listed.exclude_tuple)
            for sign, glob_text in listed.dir_rule_tuple:
                (dir_list if sign == "+" else exclude_dir_list).append(glob_text)
            dir_rule_list.extend(listed.dir_rule_tuple)
            no_bubbles_f = no_bubbles_f or listed.no_bubbles_f
            #  A LIST OF RULES ALONE wants what its rules leave, as the
            #  same words on the command line would; an EMPTY list wants
            #  nothing (E-202).
            wishlist_f = wishlist_f or _states_targets_f(listed)
            index += 1
        elif argument.startswith("--wishlist="):
            listed = _wishlist_read(argument[len("--wishlist="):], digest_f)
            glob_list.extend(listed.target_tuple)
            digest_list.extend(listed.digest_tuple)
            exclude_list.extend(listed.exclude_tuple)
            for sign, glob_text in listed.dir_rule_tuple:
                (dir_list if sign == "+" else exclude_dir_list).append(glob_text)
            dir_rule_list.extend(listed.dir_rule_tuple)
            no_bubbles_f = no_bubbles_f or listed.no_bubbles_f
            #  A LIST OF RULES ALONE wants what its rules leave, as the
            #  same words on the command line would; an EMPTY list wants
            #  nothing (E-202).
            wishlist_f = wishlist_f or _states_targets_f(listed)
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
                    "the whole question -- %s"
                    % _label_remedy(label_spec, text,
                                    "write '--label \"%s OR %s\"'"))
            try:
                parse_expression(text)
            except LabelExprError as error:
                raise WishError("'--label %s' cannot be read -- %s"
                                % (text, error)) from None
            label_spec = text
        elif argument in FEATURE_WORD_TUPLE \
                or argument.startswith(("--feature=", "--feature-ext=",
                                        "--keys=")):
            raise WishError(_feature_retired_text(argument))
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

    if exclude_local_f and not platform_list:
        raise WishError("'--exclude-local' leaves no platform -- add "
                        "'-p <name>'")
    if label_spec is not None and family_word is not None:
        raise WishError(label_mix_text(label_spec, family_word))
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
                 digest_tuple=tuple(digest_list),
                 no_bubbles_f=no_bubbles_f,
                 platform_tuple=tuple(platform_list),
                 exclude_local_f=exclude_local_f,
                 as_platform=as_platform),
            rest_list)


def _rerooted(text, bubble):
    """
    RETURN: str, a target or directory glob of the near root as the far
            run under 'bubble' reads it: a bare name (no '/' in its file
            part) unchanged; a path below 'bubble' with that prefix
            taken off; a path whose first component is a glob unchanged
            -- it may reach in anywhere -- if it applies there.
            None, else: a path that lies outside the bubble.
    """
    file_part, blank, rest = text.partition(" ")
    if "/" not in file_part or bubble in (".", ""): return text
    prefix = bubble.rstrip("/") + "/"
    if file_part.startswith(prefix):
        return file_part[len(prefix):] + blank + rest
    if any(mark in file_part.split("/")[0] for mark in _GLOB_MARK_TUPLE):
        return text
    return None


def _ancestor_tuple(bubble):
    """
    RETURN: tuple of str, 'bubble' and every directory above it, as the
            near root names them: 'a/b' -> ('a/b', 'a').
    """
    part_list = [p for p in bubble.split("/") if p not in ("", ".")]
    return tuple("/".join(part_list[:n])
                 for n in range(len(part_list), 0, -1))


def unrequired_platform_note_tuple(wish, required_iterable):
    """
    RETURN: tuple of str, one NOTE per '-p' name that no bubble can use
            -- 'NOTE  -p lab-3: no bubble below requires it' (spec/42
            section 2) -- in the order the names were typed; empty where
            every one is a candidate of some bubble, or no '-p' stands.

    'required_iterable' yields, per bubble, its candidates -- the names
    of the platforms announcing what it requires ('plan/bubble.py'
    'candidate_tuple'; ('local',) where it requires nothing).
    """
    if not wish.platform_tuple: return ()
    required_set = set()
    for name_tuple in required_iterable:
        required_set.update(name_tuple or (LOCAL_PLATFORM,))
    return tuple("NOTE  -p %s: no bubble below requires it" % name
                 for name in wish.platform_tuple
                 if name not in required_set)


#  A WISHLIST LINE MAY END IN ONE '--digest=<tag>' (E-168).
_DIGEST_SUFFIX_RE = re.compile(r"\s+--digest=(\S+)\s*$")
_GLOB_MARK_TUPLE  = ("*", "?", "[")

#  THE ONE RESERVED WORD OF A WISHLIST (RQ-9, E-202): '!<hwut-root>'
#  keeps the walk out of every inner 'hwut-root.conf'.
BUBBLE_WORD = "<hwut-root>"


#  THE WISHLIST FAMILY (intend/three-worlds): every word of the wish that
#  states WHICH runs by an attribute -- place, history, language. '-l'
#  is refused beside each. '--no-bubbles' speaks of the walk alone.
_FAMILY_WORD_TUPLE  = ("--fail", "--pass", "--unaccepted", "--glob",
                       "--exclude", "--exclude-dir", "--dir", "--wishlist",
                       "--since", "--until", "--language", "--faster-than")
FEATURE_WORD_TUPLE  = ("--feature", "-F", "--feature-ext", "-e",
                       "--keys", "-k")


#  THE SHORT SPELLINGS OF THE WISH, each to its long one: a face's
#  'take_tuple' names the long one, and takes both.
_LONG_OF_SHORT_DB = {"-l": "--label"}


def _long_word_of(argument):
    """
    RETURN: str, the option word of 'argument' by its long spelling --
            '--glob' for '--glob=x', '--label' for '-l' and '-l=x' -- if
            it is an option.
            None, else: a bare word, which no 'take_tuple' names.
    """
    if not argument.startswith("-"): return None
    word = argument.split("=", 1)[0]
    return _LONG_OF_SHORT_DB.get(word, word)


def _family_word_f(argument):
    """
    RETURN: bool, True where 'argument' is a word of the wishlist family
            ('--fail', '--dir x', '--since=2h', ...) -- one '-l' may not
            stand beside.
    """
    return argument in _FAMILY_WORD_TUPLE \
           or argument.split("=", 1)[0] in _FAMILY_WORD_TUPLE


def label_mix_text(label_spec, word):
    """
    RETURN: str, the refusal of '-l <label_spec>' beside the wishlist
            argument 'word' (R-b): what was asked, why not, and the way
            -- the set named by 'hwut.labels.create', then combined.
    """
    return ("'--label %s' beside '%s': a label expression or wishlist "
            "arguments, never both -- sets are combined in labels => "
            "'hwut.labels.create <name> %s ...', then '--label \"%s AND "
            "<name>\"'" % (label_spec, word, word, label_spec))


def _feature_retired_text(argument):
    """
    RETURN: str, the refusal of '-F', '-e' or '-k' on any face: they are
            gone (spec 43, T-t); the runs of a feature are the label
            'f/<id>'.
    """
    return ("'%s' is gone: the runs of a feature are the label "
            "'f/<id>' => '--label f/<id>'; the ids stand in "
            "'hwut.features.tree --list'" % argument.split("=", 1)[0])


def _label_remedy(first, second, either_form):
    """
    RETURN: str, the remedy for two label expressions where one may
            stand: 'drop one' where both read alike (book D-79, measured:
            '--label "components OR components"'); else 'either_form'
            filled with both, the one expression asking for either.
    """
    if " ".join(first.split()) == " ".join(second.split()):
        return "both say '%s' => drop one" % " ".join(first.split())
    return either_form % (first, second)


#  A LABEL LINE OF A WISHLIST (E-206): 'label: <expression>'.
_LABEL_LINE_RE = re.compile(r"^label\s*:(.*)$")

#  '--no-boundary' asked, before RQ-9, what every walk now does.
NO_BOUNDARY_RETIRED_TEXT = (
    "'--no-boundary' is retired: a walk enters every inner "
    "'hwut-root.conf' (RQ-9) => drop it; '--no-bubbles' stays out")


@dataclass(frozen=True)
class CWishlist:
    """What one wishlist file states, its lines sorted into the wish's
    own fields, each in file order."""
    target_tuple:   tuple = ()     # wanted targets ('--glob')
    digest_tuple:   tuple = ()     # (<literal target>, <tag>)
    exclude_tuple:  tuple = ()     # '!<target>'       ('--exclude')
    dir_rule_tuple: tuple = ()     # ('+'|'-', <glob>) ('--dir', '--exclude-dir')
    no_bubbles_f:   bool  = False  # '!<hwut-root>'    ('--no-bubbles')


def _states_targets_f(listed):
    """
    RETURN: True,  the list 'listed' speaks of WANTED targets: it holds
                   one, or it holds no line at all -- an empty list
                   wants nothing;
            False, it holds rules alone ('!...', '<dir>/', '!<hwut-root>'),
                   which narrow like their command-line words.
    """
    return bool(listed.target_tuple) \
           or not (listed.exclude_tuple or listed.dir_rule_tuple
                   or listed.no_bubbles_f)


def wishlist_target_tuple(file_name):
    """
    RETURN: tuple[str], the targets a wishlist file states, as
            '_wishlist_read' reads them, if success;
            raises WishError, else -- also where a line carries a
            '--digest', which only 'hwut.accept' reads, or a rule of
            another kind ('!...', '.../'): a face that reads targets
            alone must not drop a line silently.
    """
    listed = _wishlist_read(file_name, False)
    if listed.exclude_tuple or listed.dir_rule_tuple or listed.no_bubbles_f:
        raise WishError("'%s': this face reads targets alone -- no '!' "
                        "line, no directory line ('<dir>/'), no '%s'"
                        % (file_name, BUBBLE_WORD))
    return listed.target_tuple


def _wishlist_read(file_name, digest_f):
    """
    RETURN: CWishlist, what the file states, line kind by line kind,
            each in file order, if success;
            raises WishError naming file and line, else.

    ONE LINE, ONE RULE (E-202):
        <target>              wanted                   '--glob'
        !<target>             not wanted               '--exclude'
        <dir-glob>/           a directory wanted       '--dir'
        !<dir-glob>/          a directory not entered  '--exclude-dir'
        !<hwut-root>          no inner bubble entered  '--no-bubbles'
    A LIST NAMES NO SET (intend/three-worlds, ruled 2026-10-31): a
    'label:' line -- E-206's, retired -- is refused by name; a set by
    name is a label, combined in labels.
    A trailing '/' makes a DIRECTORY line: a target names a file and
    never ends in one. Directory lines keep their order among the
    command line's own '--dir'/'--exclude-dir', and the LAST ONE
    MATCHING decides -- grep's rule, and '.gitignore''s.

    A '--digest' stands only after a LITERAL wanted target -- a glob
    names a set nobody has looked at yet (E-168) -- and only where the
    caller reads it ('digest_f', 'hwut.accept'); every other face
    refuses it by name, so a check written in the list is never
    silently dropped.

    '#' comments and blank lines dropped; a leading './' replaced by
    the file's OWN directory.

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
    def grounded(text):
        """RETURN: str, 'text' with a leading './' made the list's own
                   directory; 'text' as it stands, else."""
        if not text.startswith("./"): return text
        return "%s/%s" % (here.replace(os.sep, "/").rstrip("/"), text[2:])

    target_list  = []
    digest_list  = []
    exclude_list = []
    rule_list    = []
    no_bubbles_f = False
    previous     = None            # the last target line, '!' or not
    for number, line in enumerate(line_list, start=1):
        text = line.strip()
        if not text or text.startswith("#"): continue
        def refused(why):
            """RETURN: WishError naming file, line and 'why'."""
            return WishError("'%s', line %d: %s" % (file_name, number, why))
        #  A LABEL LINE (E-206, retired by intend/three-worlds): a list
        #  names no set. Refused BY NAME, never read as a target.
        if _LABEL_LINE_RE.match(text.lstrip("!").strip()):
            raise refused("'label:' is no wishlist line -- a list names no "
                          "set => '--label <expr>' alone, or name the "
                          "list's runs: 'hwut.labels.create <name> "
                          "--wishlist %s'" % file_name)
        negated_f = text.startswith("!")
        if negated_f:
            text = text[1:].strip()
            if not text: raise refused("'!' negates nothing")
        if text.startswith("<") and text.endswith(">"):
            if text != BUBBLE_WORD:
                raise refused("'%s' is no word of a wishlist; the one "
                              "reserved word is '!%s'" % (text, BUBBLE_WORD))
            if not negated_f:
                raise refused("'%s' alone asks the default -- every walk "
                              "enters inner bubbles; '!%s' stays out"
                              % (BUBBLE_WORD, BUBBLE_WORD))
            no_bubbles_f = True
            continue
        tag   = None
        match = _DIGEST_SUFFIX_RE.search(text)
        if match is not None:
            if not digest_f:
                raise refused("'--digest' is read by 'hwut.accept' alone")
            if negated_f:
                raise refused("'--digest' after '!' -- a digest blesses a "
                              "recording; an excluded run has none to bless")
            tag  = match.group(1)
            text = text[:match.start()].rstrip()
            if any(mark in text for mark in _GLOB_MARK_TUPLE):
                raise refused("'--digest' follows a glob -- a digest names "
                              "ONE recording; name the test run literally")
        if text.endswith("/") and not text.startswith(":"):
            glob_text = grounded(text).rstrip("/")
            if not glob_text: raise refused("'/' names no directory")
            rule_list.append(("-" if negated_f else "+", glob_text))
            continue
        if text.startswith(":"):
            try:
                text = expanded_target(text, previous)
            except ElisionError as error:
                raise refused(str(error)) from None
        else:
            text = grounded(text)
        previous = text
        if negated_f:
            exclude_list.append(text)
            continue
        target_list.append(text)
        if tag is not None: digest_list.append((text, tag))
    return CWishlist(tuple(target_list), tuple(digest_list),
                     tuple(exclude_list), tuple(rule_list), no_bubbles_f)


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
            globs -- 'wish' itself where no word stands -- if success;
            raises WishError, else: a target beside '-l' (R-b).
    """
    glob_tuple = desugar_positional(word_list)
    if not glob_tuple: return wish
    if wish.label_spec is not None:
        raise WishError(label_mix_text(wish.label_spec, word_list[0]))
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
