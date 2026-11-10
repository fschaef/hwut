"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE MAP TO EXTERNAL NAMES, 'hwut-feature-external-map.csv', read
         (spec 43 section 3; intend/43 T-e, T-f, T-r). Beside the forest:

    # our feature id ; the outside's name for it
    keeporder ; REQ-4711
    gateway   ; Gateway (customer spec 2.1)

    read_external(top, forest)   -> dict our id -> tuple of names | None

An EXTERNAL name is somebody else's name for one of our promises: a
customer's, a ticket's, a standard's requirement number. It is a free
string and never checked; our id is, against the forest. NO COLUMN FOR
WHOSE NAME IT IS (T-f): the audiences live in the doc file. One line per
pair; an id may carry several names. The file starts empty and may be
absent (T-r): nothing in hwut writes a line of it.
______________________________________________________________________________
"""
import os

from .suggestion import did_you_mean

from .finder import EXTERNAL_FILE_NAME


class ExternalFault(Exception):
    """The map cannot be read. 'word' and 'candidate_tuple' as in
    'feature_doc.DocFault': the text ends in their 'did you mean'."""

    def __init__(self, text, word="", candidate_tuple=()):
        super().__init__(text + (did_you_mean(word, candidate_tuple)
                                 if word else ""))
        self.word            = word
        self.candidate_tuple = tuple(candidate_tuple)


def read_external(top, forest):
    """
    RETURN: dict, our feature id -> tuple of the outside's names, in file
            order; None where no map stands
    RAISES: ExternalFault, for a line with no ';', an empty side, or an
            id 'forest' (a CForest; None: no forest) does not hold.
    """
    path = os.path.join(top, EXTERNAL_FILE_NAME)
    if not os.path.isfile(path): return None
    try:
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
    except (OSError, UnicodeDecodeError) as error:
        raise ExternalFault("%s: cannot be read (%s)"
                            % (EXTERNAL_FILE_NAME, error)) from error
    return external_of_text(text, forest)


def external_of_text(text, forest, file=EXTERNAL_FILE_NAME):
    """RETURN: dict, as 'read_external' answers it, from 'text'.
    RAISES: ExternalFault, as 'read_external' says."""
    result = {}
    id_set = forest.id_set if forest is not None else frozenset()
    for line_n, line in enumerate(text.splitlines(), start=1):
        line = line.split("#", 1)[0].strip()
        if not line: continue
        ours, mark, theirs = line.partition(";")
        ours, theirs = ours.strip(), theirs.strip()
        if not mark or not ours or not theirs:
            raise ExternalFault("FAULT: %s:%i: '%s' is no map line -- "
                                "'<our feature id> ; <their name>'"
                                % (file, line_n, line))
        if ours not in id_set:
            raise ExternalFault("FAULT: %s:%i: '%s' stands in no forest "
                                "line" % (file, line_n, ours), ours,
                                tuple(sorted(id_set)))
        result.setdefault(ours, ())
        if theirs not in result[ours]:
            result[ours] += (theirs,)
    return result
