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
