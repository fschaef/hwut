"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: WHAT BOTH KINDS OF ACCEPTANCE RELY ON -- classification, the
         closing-token rule, and the reading of a candidate.

DESCRIPTION
       There is ONE face, 'hwut.accept', and it switches on whether this
       is a FIRST acceptance -- no nominal stands -- or an ADAPTATION of
       a standing GOOD. The two differ in how the working nominal is
       OBTAINED and in the dynamics of the unaccepted regions that
       follow; they share everything else, and the shared part lives
       here so that a refusal rule cannot apply to one kind and not the
       other.

       THE ATOMIC REFUSAL SPANS THE SELECTION. 'token_terminated_f' is
       what 'hwut.accept' asks of every stream before anything is
       written: a candidate that never COMPLETED is not promotable, and
       one such stream refuses the whole selection (R-70). Neither
       'accept_first' nor 'accept_adapt' may own that question alone.

       THE NAME BREAKS 'services/'s single-noun convention on purpose:
       '_accept.py' beside 'accept.py' would read as a near-duplicate.
______________________________________________________________________________
"""
import io

CLOSING_TOKEN = "<hwut-end>"


def token_terminated_f(text):
    """
    RETURN: bool, True where the stream's LAST LINE is the closing
            token '<hwut-end>' (R-70) -- the stream's own testimony
            that it completed.
    """
    if text is None: return False
    line_list = text.splitlines()
    return bool(line_list) and line_list[-1] == CLOSING_TOKEN



def classify(key, force_f):
    """
    RETURN: str, which kind of acceptance the key calls for:

            'first'   no nominal stands, and the whole-take was not
                      asked ('--whole' / '--as-is' / '--force'): the
                      FIRST acceptance -- the candidate is recorded as
                      one nobody has judged yet (E-60), and the
                      session, where there is one, opens on that
            'bless'   no nominal stands and the whole-take was asked:
                      the candidate becomes the nominal WHOLE, as it
                      stands (E-109)
            'merge'   a nominal stands and '--force' was not said: this
                      is a CHANGE, and 'hwut.accept.interactive's
                      business
            'force'   a nominal stands and '--force' was said
    """
    if   not key.nominal_stands_f: return "bless" if force_f else "first"
    elif force_f:                  return "force"
    else:                          return "merge"


def read_text(path):
    """
    RETURN: str, the file's content.

            None, where it cannot be read as UTF-8 text.
    """
    try:
        with io.open(str(path), "r", encoding="utf-8") as file_handle:
            return file_handle.read()
    except (OSError, UnicodeDecodeError):
        return None


#  THE LINE A TEST STATES TO HAVE ITS STDERR DISREGARDED (E-110, E-136):
#  one spelling, quoted by every refusal and every mention.
STDERR_IGNORED_LINE = "tolerance { stderr_ignored = true }"


def stderr_ignored_f_of(configuration, choice):
    """
    RETURN: bool, True where the test's own block declares that it
            writes to stderr on purpose ('tolerance { stderr_ignored =
            true }') for 'choice'; False where it does not -- or no
            configuration stands to say so.
    """
    if configuration is None: return False
    try:
        return bool(configuration.choice_configuration(choice)
                                 .stderr_ignored_f)
    except (KeyError, AttributeError):
        return False


def stderr_mention_of(label, spoke_f, ignored_f):
    """
    RETURN: str, the one line a face shows about the case 'label'
            before it is viewed (E-136): THE STAIN -- its stderr SPOKE
            and the test's block does not tolerate it.
            None, where there is no stain to mention: stderr was
            silent, or the block tolerates it. Tolerance is no stain.
    """
    if spoke_f and not ignored_f:
        return "NOTE: %s -- STAIN: stderr SPOKE and nothing tolerates " \
               "it; an accept is refused ('%s' declares it)" \
               % (label, STDERR_IGNORED_LINE)
    return None
