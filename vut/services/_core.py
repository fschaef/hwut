"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE
       WHAT THE SERVICE FACES SHARE -- 'hwut.accept.interactive' (lib/accept/interactive.py) and
       'hwut.run.diff' (diff.py) speak one argument language.

DESCRIPTION
       The two mini-apps are HOMOGENEOUS by design: same stream
       arguments ('-' is stdin), same compare-SETUP flags, same
       renderer underneath. What they share lives here, once.

       THE SETUP FLAGS cover the setup an author reaches for at the
       command line:

           --numeric RATIO      numeric tolerance, relative [0..1]
           --pattern REGEX      an equivalence pattern (repeatable)
           --nothing PATTERN    a visible-nothing pattern (repeatable)

       Richer setups -- constraints, region parameters, marker changes
       -- belong to a test's OWN compare configuration (README 3), not
       to command-line flags; a service run inside a test run receives
       that Configuration object directly.
______________________________________________________________________________
"""
import io
import sys


USAGE_WIDTH = 78


def usage_line(prefix, token_tuple, width=USAGE_WIDTH):
    """
    RETURN: str, a wrapped usage block -- 'prefix' ('usage: hwut.run'),
            then the tokens, every continuation line aligned under the
            first token.

    A face states its arguments as a tuple and never places its own
    line breaks, so a keyword added to a shared list ('plan/wish.py':
    USAGE_TOKEN_TUPLE) cannot leave another face's usage line stale.
    """
    indent    = " " * (len(prefix) + 1)
    line_list = []
    line      = prefix
    for token in token_tuple:
        if len(line) + 1 + len(token) > width:
            line_list.append(line)
            line = indent + token
        else:
            line = "%s %s" % (line, token)
    line_list.append(line)
    return "\n".join(line_list)


def read_source(path):
    """
    RETURN: str, the stream behind 'path' -- the file's content, or
            stdin's when 'path' is '-'.
    """
    if path == "-":
        return sys.stdin.read()
    with io.open(path, "r", encoding="utf-8") as file_handle:
        return file_handle.read()


def add_setup_arguments(parser):
    """
    RETURN: None. Adds the shared compare-SETUP flags to 'parser' --
            one place, so the two faces cannot drift apart.
    """
    parser.add_argument("--numeric", type=float, default=None,
                        metavar="RATIO",
                        help="numeric tolerance, relative [0..1] "
                             "(default: the setup's own, 0 = exact)")
    parser.add_argument("--pattern", action="append", default=None,
                        metavar="REGEX",
                        help="an equivalence pattern: two elements "
                             "matching it are equivalent (repeatable)")
    parser.add_argument("--nothing", action="append", default=None,
                        metavar="PATTERN",
                        help="a visible-nothing pattern: a matching "
                             "element reads as nothing (repeatable)")


def setup_from_arguments(arguments):
    """
    RETURN: Configuration, compare's setup with the shared flags
            applied; the plain default setup when none was given.
    """
    from vut.engine.compare.api import Configuration
    configuration = Configuration()
    if arguments.numeric is not None:
        configuration.pattern_finder.numeric_tolerance_ratio = \
                                                        arguments.numeric
    if arguments.pattern is not None:
        configuration.pattern_finder.equivalent_pattern_list = \
                                                        list(arguments.pattern)
    if arguments.nothing is not None:
        configuration.pattern_finder.visible_nothing_pattern_list = \
                                                        list(arguments.nothing)
    return configuration


#  ------------------------------------------------------- the help page
#
#  EVERY FACE'S '--help' IS ONE SHAPE (services E-32, AMENDED r-11b): a
#  manual page -- NAME, then USAGE in capitals near the top, then the
#  DESCRIPTION the face wrote, then an EXAMPLE where the face states one.
#  The face keeps its own text; this function gives it the page's frame,
#  so a face cannot print its usage at the foot or leave it out.
MAN_INDENT = "    "

#  AN EXAMPLE WHERE ONE HELPS, AND NONE WHERE IT DOES NOT (ruled, r-11b):
#  the faces a newcomer types first, and the pairs whose second half is
#  not obvious from the first. A face absent here has no EXAMPLE section.
#  Every line is run by 'services/TEST/test-help-pages.sh': an example
#  the face refuses is a page that lies.
EXAMPLE_DB = {
    "hwut.run":
        "hwut.run                     everything below the root\n"
        "hwut.run --fail              what failed at the last run, again\n"
        "hwut.run 'test-parse*' --jobs=4",
    "hwut.accept":
        "hwut.accept test-parse.sh    what it printed becomes its GOOD",
    "hwut.accept.propose":
        "hwut.accept.propose -o changes.txt\n"
        "$EDITOR changes.txt          delete what you disagree with\n"
        "hwut.accept.apply changes.txt",
    "hwut.accept.apply":
        "hwut.accept.propose -o changes.txt\n"
        "hwut.accept.apply changes.txt",
    "hwut.sanitize":
        "hwut.sanitize root           asks where 'hwut-root.conf' shall stand\n"
        "hwut.sanitize remove TMP        the transient space of this directory",
    "hwut.sanitize.propose":
        "hwut.sanitize.propose -o heal.txt\n"
        "$EDITOR heal.txt             '#' before what shall not be done\n"
        "hwut.sanitize.apply heal.txt",
    "hwut.sanitize.apply":
        "hwut.sanitize.propose -o heal.txt\n"
        "hwut.sanitize.apply heal.txt",
    "hwut.remove.propose":
        "hwut.remove.propose -o gone.txt\n"
        "hwut.remove.apply gone.txt",
    "hwut.remove.apply":
        "hwut.remove.propose -o gone.txt\n"
        "hwut.remove.apply gone.txt",
    "hwut.move":
        "hwut.move test-old.sh test-new.sh",
    "hwut.rename":
        "hwut.rename test-old.sh -to test-new.sh\n"
        "hwut.rename test-io.sh small -to tiny",
    "hwut.remove":
        "hwut.remove test-gone.sh",
    "hwut.run.play":
        "hwut.run.play test-parse.sh",
    "hwut.run.stability":
        "hwut.run.stability 'test-*' --repeat=5",
    "hwut.report":
        "hwut.report --fail\n"
        "hwut.report --format=junit --out=result.xml",
    "hwut.labels.create":
        "hwut.labels.create nightly --glob 'test-net*'",
    "hwut.labels.query":
        "hwut.labels.create nightly --glob 'test-net*'\n"
        "hwut.labels.query nightly\n"
        "hwut.run --label nightly",
    "hwut.about":
        "hwut.about --version",
}


def man_page(name, text, usage=None, example=None):
    """
    RETURN: str, 'text' as a manual page for the face 'name': the
            sections NAME (the face and its first paragraph), USAGE (the
            'usage:' block found in 'text', or 'usage' where one is
            given), DESCRIPTION (everything else, as the face wrote it)
            and EXAMPLE (the lines of 'example'; the face's entry in
            EXAMPLE_DB where none is given; no section where neither
            stands). Where no
            usage is stated, the synopsis lines the face wrote below its
            first paragraph are it; where there are none, its bare name.
    """
    def usage_split(line_list):
        """RETURN: (usage lines without 'usage: ', the remaining lines)."""
        found, rest, i = [], [], 0
        while i < len(line_list):
            line = line_list[i]
            if not line.startswith("usage: "):
                rest.append(line); i += 1
                continue
            found.append(line[len("usage: "):])
            i += 1
            while i < len(line_list) and line_list[i].startswith(" ") \
                  and line_list[i].strip():
                found.append(line_list[i]); i += 1
        if len(found) > 1:
            #  THE CONTINUATION LINES keep their place under the first.
            cut = min(len(each) - len(each.lstrip()) for each in found[1:])
            cut = min(cut, len("usage: "))
            found = [found[0]] + [each[cut:] for each in found[1:]]
        return found, rest

    def ruleless(line_list):
        """RETURN: the lines without rule lines, blank ends dropped."""
        line_list = [each.rstrip() for each in line_list
                     if not (len(each.strip()) >= 10 and set(each.strip()) <= set("_"))]
        while line_list and not line_list[0]:  line_list.pop(0)
        while line_list and not line_list[-1]: line_list.pop()
        return line_list

    def broken(line):
        """RETURN: list[str], 'line' as it fits the page: whole where
                   it does, else broken before a ' [' with what follows
                   aligned under the line's second word."""
        room = USAGE_WIDTH - len(MAN_INDENT)
        if len(line) <= room: return [line]
        token_list = " ".join(line.split()).replace(" [", "\0[").split("\0")
        indent     = " " * (len(line) - len(line.lstrip())
                            + len(line.split()[0]) + 1)
        result, now = [], token_list[0]
        for token in token_list[1:]:
            if len(now) + 1 + len(token) > room:
                result.append(now); now = indent + token
            else:
                now = "%s %s" % (now, token)
        return result + [now]

    usage_list, body = usage_split(text.split("\n"))
    if usage is not None:
        usage_list, _ = usage_split(usage.split("\n"))
    stated_f = bool(usage_list)
    if not stated_f: usage_list = [name]
    body = ruleless(body)

    #  NAME: the first paragraph, said as '<face> -- <what it is>'.
    cut = body.index("") if "" in body else len(body)
    head, body = [each.strip() for each in body[:cut]], ruleless(body[cut:])
    if head:
        first = head[0]
        if first.startswith("PURPOSE:"): first = first[len("PURPOSE:"):].strip()
        for spelling in ("THE '%s' COMMAND LINE" % name, "'%s'" % name):
            if first.startswith(spelling):
                first = name + first[len(spelling):]
        if not first.startswith(name):
            first = "%s -- %s" % (name, first)
        head[0] = first
    else:
        head = [name]

    #  THE SYNOPSIS THE FACE WROTE BELOW ITS FIRST PARAGRAPH -- lines that
    #  open with the face's name and nothing else: it IS the usage where
    #  none was stated, and a repetition of it where one was.
    cut      = body.index("") if "" in body else len(body)
    synopsis = [each.strip() for each in body[:cut]]
    if synopsis and not stated_f \
       and all(each.startswith(name + " ") or each == name for each in synopsis):
        usage_list, body = synopsis, ruleless(body[cut:])
    elif synopsis and synopsis[0].startswith(name + " ") \
         and all(each.startswith(("hwut.", "[", "==")) for each in synopsis):
        body = ruleless(body[cut:])

    #  NOTHING PAST THE PAGE'S WIDTH: the first paragraph is filled anew,
    #  a usage line too long is broken before an option's bracket.
    import textwrap
    head = textwrap.wrap(" ".join(head), USAGE_WIDTH - len(MAN_INDENT),
                         break_long_words=False, break_on_hyphens=False)
    usage_list = [part for line in usage_list for part in broken(line)]

    line_list = ["NAME"] + [MAN_INDENT + each for each in head] + [""] \
              + ["USAGE"] + [MAN_INDENT + each for each in usage_list]
    if body:
        line_list.append("")
        if "DESCRIPTION" not in body: line_list.append("DESCRIPTION")
        line_list.extend(body)
    if example is None: example = EXAMPLE_DB.get(name)
    if example:
        line_list.extend(["", "EXAMPLE"])
        line_list.extend((MAN_INDENT + each) if each else ""
                         for each in example.strip("\n").split("\n"))
    return "\n".join(line_list)
