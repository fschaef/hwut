"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: 'did you mean ...?' -- the suggestion every refusal appends,
         for the faces ('services/lib/cmdline' re-exports it, and says
         why it is built as it is) and for the engine's own refusals of
         a name: an unknown feature id ('f/<id>', the forest, the doc
         file, the map; spec 43 section 6). It stands here, below the
         faces, because the engine imports no face (adm/LAYERING.txt);
         it is the one implementation, moved, not a second one.

    nearest_tuple(word, candidate_sequence)  -> tuple of str
    did_you_mean(word, candidate_sequence)   -> str, '' or ' -- did ...?'
______________________________________________________________________________
"""
from ...compare.core.edit_operations.string import do as distance_of


#  How far a word may stray, by its length. A slip in a short word is
#  a different event from a slip in a long one.
TOLERANCE_TABLE = ((4, 1), (8, 2))
TOLERANCE_MAX   = 3

#  How many guesses are worth offering. Beyond three, the list stops
#  being a suggestion and becomes a second roster.
SUGGESTION_MAX  = 3


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
