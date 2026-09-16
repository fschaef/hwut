"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE COMMAND LINE'S SECOND SENTENCE -- 'did you mean ...?', in
         one place, for every face.

DESCRIPTION
       A FACE THAT REFUSES A WORD KNOWS WHAT IT WOULD HAVE ACCEPTED.
       Every one of them holds that list already -- the options it
       parses, the formats it renders, the choices an application
       reports, the files a directory offers -- and every one of them
       used to throw it away and say only 'no'. Saying which word was
       probably meant costs the face one call and costs the reader
       nothing.

       THE DISTANCE IS COMPARE'S OWN. 'engine/compare/core/
       edit_operations/string.do' is the Levenshtein this project
       already measures text with; a second implementation here would
       be a second answer to one question.

       THE THRESHOLD SCALES WITH THE WORD, because a one-character slip
       in a four-letter word is a different event from one in a
       sixteen-letter word:

           up to  4 characters      distance 1
           up to  8 characters      distance 2
           longer                   distance 3

       A PREFIX IS A MATCH WHATEVER THE DISTANCE. '--dont' is five
       edits from '--dont-ask' and obviously means it; somebody who
       typed a real prefix was not guessing, he stopped early.

       LEADING DASHES AND CASE ARE IGNORED for the comparison and KEPT
       for the answer: '--Forc' should find '--force', and the reader
       must be shown the word he has to type, dashes and all.

       IT SAYS NOTHING RATHER THAN SOMETHING WRONG. Where nothing is
       close, the suffix is EMPTY and the face's refusal stands as it
       was. A wrong suggestion is worse than none: it sends a person
       to check a spelling that was never the problem.
______________________________________________________________________________
"""
from vut.engine.compare.core.edit_operations.string import do as distance_of

import re


#  How far a word may stray, by its length. A slip in a short word is
#  a different event from a slip in a long one.
TOLERANCE_TABLE = ((4, 1), (8, 2))
TOLERANCE_MAX   = 3

#  How many guesses are worth offering. Beyond three, the list stops
#  being a suggestion and becomes a second roster.
SUGGESTION_MAX  = 3


def option_tuple(usage_text):
    """
    RETURN: tuple[str], every OPTION the usage line names, in the order
            it names them -- '--force', '--dont-ask', '-f'.

    THE FACE'S OWN USAGE IS THE LIST. Each face already spells its
    options once, in the sentence it prints when it refuses; asking
    that sentence means the suggester cannot drift from what the face
    actually takes, which a second hand-kept list would do within a
    release. A word is an option here if it begins with a dash and
    holds nothing but letters, digits and dashes after it -- and only
    where a DASH BEGINS A WORD. Without that, '<test-glob>' in a usage
    line contributes a phantom option '-glob', and a phantom is exactly
    what a suggester must not offer.
    """
    result, seen = [], set()
    for word in re.findall(r"(?:^|(?<=[\s\[(|,]))(-{1,2}[A-Za-z][A-Za-z0-9-]*)",
                           usage_text or ""):
        if word in seen: continue
        seen.add(word)
        result.append(word)
    return tuple(result)


def nearest_tuple(word, candidate_sequence, limit_n=SUGGESTION_MAX):
    """
    RETURN: tuple[str], the candidates near enough to 'word' to be
            worth naming, NEAREST FIRST, at most 'limit_n' of them --
            each spelled as the caller spelled it, so the reader is
            shown the word he has to type.

            (), where nothing is near: the caller then says only what
            it was going to say. A wrong guess is worse than no guess.

    Ties keep the candidate order the caller gave, which for a choice
    list is the order its author wrote.
    """
    plain = _plain(word)
    if not plain: return ()

    scored = []
    for candidate in candidate_sequence:
        other = _plain(candidate)
        if not other: continue
        #  COMPARED AGAINST THE RAW WORD, not the plain one: '--Force'
        #  was NOT accepted -- the parsers are case-sensitive -- and
        #  telling somebody his capital 'F' is the whole problem is
        #  exactly what this exists for.
        if candidate == word: continue
        if other.startswith(plain) or plain.startswith(other):
            scored.append((0, candidate));   continue
        gap = distance_of(plain, other)
        if gap <= _tolerance(plain): scored.append((gap, candidate))

    scored.sort(key=lambda pair: pair[0])
    return tuple(candidate for _, candidate in scored[:limit_n])


def did_you_mean(word, candidate_sequence, limit_n=SUGGESTION_MAX,
                 among_listed_f=False):
    """
    RETURN: str, a sentence to APPEND to a refusal --

                " -- did you mean '--force'?"
                " -- did you mean 'bare', 'pack' or 'raw'?"

            "", where nothing is near enough. It is written to be
            concatenated, so a face that has nothing to suggest is
            unchanged by using this.

    'among_listed_f' says the refusal ALREADY PRINTS the whole list. A
    suggestion then earns its place only by picking one out of several:
    where the list holds ONE name, the reader has just read it, and
    "offers: test-here.sh -- did you mean 'test-here.sh'?" is noise
    with a question mark on it.
    """
    candidate_sequence = list(candidate_sequence)
    if among_listed_f and len(candidate_sequence) < 2: return ""
    near_tuple = nearest_tuple(word, candidate_sequence, limit_n)
    if not near_tuple: return ""
    return " -- did you mean %s?" % _listed(near_tuple)


def _listed(name_tuple):
    """
    RETURN: str, the names quoted and joined as a person reads them:
            "'a'", "'a' or 'b'", "'a', 'b' or 'c'".
    """
    quoted = ["'%s'" % name for name in name_tuple]
    if len(quoted) == 1: return quoted[0]
    return "%s or %s" % (", ".join(quoted[:-1]), quoted[-1])


def _plain(word):
    """
    RETURN: str, the word as it is COMPARED -- leading dashes dropped,
            lowered, and anything after '=' cut off, so '--WIDTH=70'
            is measured against '--width'.
    """
    text = (word or "").split("=", 1)[0]
    return text.lstrip("-").lower()


def _tolerance(plain):
    """
    RETURN: int, how many edits away a candidate may stand and still be
            worth naming, given the length of what was typed.
    """
    for length_n, gap_n in TOLERANCE_TABLE:
        if len(plain) <= length_n: return gap_n
    return TOLERANCE_MAX


#  ---------------------------------------------------- the argparse road
#
#  A FACE THAT PARSES WITH 'argparse' HOLDS ITS VOCABULARY ALREADY: the
#  parser knows every option, its long and short spellings, whether it
#  takes a value, and any 'choices'. The face adds ONE thing the parser
#  does not know -- what a value IS, beyond a type -- as 'arg_db':
#
#      arg_db["--directory"] = True                   one or more paths
#      arg_db["--format"]    = ("traditional", "junit")  the words allowed
#
#  Both feed two readers: the refusal's 'did you mean', and the hidden
#  '--intern-cmd-get-completion-info', which prints a table a shell's
#  completion function reads (services E-81).

COMPLETION_OPTION = "--intern-cmd-get-completion-info"


def option_tuple_of_parser(parser):
    """
    RETURN: tuple[str], every option spelling the argparse 'parser'
            accepts, in the order it was added -- '-f' and '--force'
            both; positionals are not options and are not here.
    """
    import argparse
    result = []
    for action in parser._actions:
        if action.help == argparse.SUPPRESS: continue
        for spelling in action.option_strings:
            if spelling == "-h": continue      # argparse's own
            result.append(spelling)
    return tuple(result)


def did_you_mean_of_parser(word, parser, arg_db=None):
    """
    RETURN: str, 'did_you_mean' for 'word' against the parser's options
            -- and, where 'word' is '--option=value' and 'arg_db' lists
            the words that option takes, against THOSE words.
            "", where nothing is near.
    """
    arg_db = arg_db or {}
    name, _, value = word.partition("=")
    if value and name in arg_db and isinstance(arg_db[name], (tuple, list)):
        return did_you_mean(value, arg_db[name])
    candidate_list = list(option_tuple_of_parser(parser))
    candidate_list.extend(option_tuple(" ".join(parser.get_default("_shared")
                                                or ())))
    if parser.get_default("_wish_f"):
        #  A FACE THAT TAKES A WISH refuses a slip in a wish word HERE,
        #  since 'parse_wish' passed it on: the wish's options are
        #  candidates too.
        from vut.engine.orchestrator.plan.wish import USAGE_TOKEN_TUPLE
        candidate_list.extend(option_tuple(" ".join(USAGE_TOKEN_TUPLE)))
    return did_you_mean(word, candidate_list)


def completion_table(parser, arg_db=None):
    """
    RETURN: list[str], one line per option, TAB-separated, for a shell's
            completion function:

                <spelling>  <kind>  <words>

            'kind' is 'flag' (no value), 'file' (a path follows,
            'arg_db' says True), 'enum' (the allowed words follow,
            '|'-separated, from 'choices' or 'arg_db'), or 'value'
            (something else follows). A '--option=value' spelling is
            the completion function's own choice; the table does not
            spell it.
    """
    import argparse
    arg_db = arg_db or {}
    line_list = []
    #  THE SHARED LAYERS FIRST, as the line reads them: the wish, the
    #  rendering words. Their tokens say the kind -- '<file>' a path,
    #  any other '<...>' a value, none a flag.
    shared = ()
    if parser.get_default("_wish_f"):
        from vut.engine.orchestrator.plan.wish import USAGE_TOKEN_TUPLE
        shared += USAGE_TOKEN_TUPLE
    shared += tuple(parser.get_default("_shared") or ())
    for token in shared:
        kind = "flag"
        if   "<file>" in token: kind = "file"
        elif "<"      in token: kind = "value"
        for spelling in option_tuple(token):
            line_list.append("\t".join((spelling, kind, "")))
    for action in parser._actions:
        if action.help == argparse.SUPPRESS: continue
        for spelling in action.option_strings:
            if spelling == "-h": continue
            stated = arg_db.get(spelling)
            if stated is None:
                for other in action.option_strings:
                    if other in arg_db: stated = arg_db[other]; break
            if isinstance(stated, (tuple, list)):
                kind, words = "enum", "|".join(str(w) for w in stated)
            elif action.choices:
                kind, words = "enum", "|".join(str(w) for w in action.choices)
            elif stated is True:
                kind, words = "file", ""
            elif action.nargs == 0:
                kind, words = "flag", ""
            else:
                kind, words = "value", ""
            line_list.append("\t".join((spelling, kind, words)))
    return line_list


def parse_or_refuse(parser, argv, err, arg_db=None):
    """
    RETURN: [0] Namespace, the parsed arguments.
                None, where the line was refused -- the refusal, with
                'did you mean', went to 'err' -- or where the line asked
                for the completion table or for '--help', both of which
                went to stdout.
            [1] bool, True where the line asked for the completion table
                or for '--help': there is nothing to refuse, exit OK.

    THE PARSER NEVER EXITS THE PROCESS: its own error is caught and
    reworded with the suggestion, so every argparse face refuses in the
    words the hand-parsing faces refuse in.
    """
    import argparse
    import sys
    argv = list(argv)
    if COMPLETION_OPTION in argv:
        for line in completion_table(parser, arg_db): sys.stdout.write(line + "\n")
        return None, True
    parser.exit_on_error = False
    try:
        arguments, unknown = parser.parse_known_args(argv)
    except argparse.ArgumentError as error:
        err("REFUSED: %s" % error)
        return None, False
    except SystemExit as leaving:
        #  '--help' is argparse's own exit 0: printed, and nothing to do.
        return None, leaving.code in (0, None)
    if unknown:
        #  THE HOUSE WORDING, which every face refused in before it had
        #  a parser: the face's name, every word it does not take.
        err("REFUSED: '%s' does not take: %s%s"
            % (parser.prog, ", ".join(sorted(unknown)),
               did_you_mean_of_parser(unknown[0], parser, arg_db)))
        return None, False
    return arguments, False


#  ------------------------------------------------- the standard reader
#
#  EVERY FACE READS ITS LINE THE SAME WAY (services E-84): the wish words
#  first ('parse_wish' -- they are shared, and no face restates them),
#  then ONE argparse parser for what is the face's own. The usage line
#  is GENERATED from the parser, in the house style ('_core.usage_line'),
#  with the wish tokens where the face takes a wish -- so a usage line
#  can no longer under-document what its parser accepts.

def face_parser(prog, description, wish_f=True, word_help=None,
                word_metavar=None, shared_token_tuple=()):
    """
    RETURN: argparse.ArgumentParser, the standard one: no abbreviation,
            never exits on its own (parse through 'parse_or_refuse'),
            '-h/--help' left to the face's HELP text, a 'word' list
            positional where 'word_help' is given -- shown in the usage
            as 'word_metavar', which says WHAT the words are.

    'wish_f' records that this face takes the shared wish words before
    its own; 'usage_of' then prints them first. 'shared_token_tuple'
    names a SECOND shared layer read before the parser (the rendering
    words of 'hwut.run'): printed just before '--directory', and
    suggested like the parser's own. An option added with
    'help=argparse.SUPPRESS' is taken but never shown, suggested or
    completed.
    """
    import argparse
    parser = argparse.ArgumentParser(prog=prog, description=description,
                                     allow_abbrev=False, add_help=False)
    parser.set_defaults(_wish_f=wish_f, _shared=tuple(shared_token_tuple))
    if word_help is not None:
        parser.add_argument("word", nargs="*", help=word_help,
                            metavar=word_metavar)
    return parser


def long_of(action):
    """RETURN: str, an option's longest spelling."""
    return max(action.option_strings, key=len)


def shown_of(action):
    """RETURN: str, the spelling a usage line shows -- the longest; and
               where a shorter '--' spelling is a PREFIX of it, both at
               once: '--stderr-tol[erated]'."""
    long_name = long_of(action)
    for other in action.option_strings:
        if other != long_name and other.startswith("--") \
           and long_name.startswith(other):
            return "%s[%s]" % (other, long_name[len(other):])
    return long_name


def usage_of(parser, arg_db=None, width=None):
    """
    RETURN: str, the usage block for the parser's face, in the house
            style: 'usage: <prog>', the wish tokens where the face takes
            a wish, the positional's own token, then one token per
            option -- '[--force]' for a flag, '[--width=<width>]' for a
            value, '[--format=a|b]' for an enumeration,
            '[--directory=<path>]' where 'arg_db' says a path follows.
    """
    from vut.services._core import usage_line, USAGE_WIDTH
    from vut.engine.orchestrator.plan.wish import USAGE_TOKEN_TUPLE
    arg_db = arg_db or {}
    token_list = []
    if parser.get_default("_wish_f"): token_list.extend(USAGE_TOKEN_TUPLE)
    import argparse
    positional = None
    for action in parser._actions:
        if not action.option_strings:
            if action.dest == "word": positional = action
            continue
        if action.help == argparse.SUPPRESS: continue
        if long_of(action) == "--directory":
            token_list.extend(parser.get_default("_shared") or ())
        long_name = shown_of(action)
        stated = next((arg_db[s] for s in action.option_strings if s in arg_db),
                      None)
        if isinstance(stated, (tuple, list)):
            value = "=%s" % "|".join(str(w) for w in stated)
        elif action.choices:
            value = "=%s" % "|".join(str(w) for w in action.choices)
        elif stated is True:
            value = "=<path>"
        elif action.nargs == 0:
            value = ""
        else:
            value = "=<%s>" % (action.metavar or action.dest).lower()
        import argparse as _argparse
        if isinstance(action, _argparse._AppendAction):
            #  REPEATABLE: the wish's own form, '[--glob <target>]...'.
            token_list.append("[%s %s]..." % (long_name, value[1:]))
            continue
        token_list.append("[%s%s]" % (long_name, value))
    if positional is not None:
        #  THE HOUSE ORDER: the wish, then what the words are, then the
        #  face's own options.
        wish_n = len(USAGE_TOKEN_TUPLE) if parser.get_default("_wish_f") else 0
        token_list.insert(wish_n,
                          positional.metavar or "[<%s>...]" % positional.dest)
    return usage_line("usage: %s" % parser.prog, tuple(token_list),
                      width or USAGE_WIDTH)
