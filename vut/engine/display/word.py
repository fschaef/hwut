"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE WORDS AND THE INK (D-2, D-6) -- the ONE place a machine
         token becomes English, and the ONE decision whether a line
         carries colour.

'phrase()' maps the wire's tokens -- verdict words and the operations'
report words alike -- onto the phrases every rendering speaks: the
flow line, the roll-call and the failure block draw from this table
and from nowhere else. A token the table does not carry prints with
its hyphens opened, never swallowed (the stability promise: the wire
grows, the display keeps reading).

'colour_decision()' is taken ONCE, at a face's 'main', and handed down
as a flag; no line re-sniffs. '--colour' is enforcement and beats
every gate, 'NO_COLOR' included; '--no-colour' is refusal; where
neither is spoken, the gates decide and ALL must pass.
______________________________________________________________________________
"""
from .failure import failure_db, failure_of

#  Wire token -> the phrase, for every token that is NOT a failure. A
#  failure's phrase is its 'description' in 'failure.failure_db' (D-34).
#
#  THESE TWO TABLES ARE THE WHOLE OF THE FRAMEWORK'S ENGLISH. Every
#  phrase a rendering speaks stands in one of them and nowhere else --
#  the flow line, the roll-call and the HINTS block all read them
#  through 'phrase()'. A phrase written inline at a call site is a word
#  no reviewer would ever see, and no translator would ever find.
PHRASE_DB = {
    "ok":                          "ok",
}


#  THE REASON WORD BEFORE '[FAIL]' (display D-31) and every failure's
#  phrase stand in ONE table, 'failure.failure_db' (D-34): a failure's
#  category, word, phrase and help, each once. A plain difference from
#  GOOD carries no word (ruled 2026-09-29), and neither does success.
REASON_WORD_DB = {f.failure_id.value: f.comment_before_FAIL_str
                  for f in failure_db.values() if not f.is_deviation()}
QUIET_REASON_SET = frozenset(["ok"] + [f.failure_id.value
                                       for f in failure_db.values()
                                       if f.is_deviation()])


def reason_word(token):
    """
    RETURN: str,  the short word that stands before '[FAIL]' for the
                  reason 'token' -- its failure's word from
                  'failure.failure_db', 'failed' for a token the table
                  does not carry.
            None, where no word stands: no token, success, or a failure
                  about equivalence ('QUIET_REASON_SET').
    """
    if not token or token in QUIET_REASON_SET: return None
    return REASON_WORD_DB.get(token, "failed")


def phrase(token):
    """
    RETURN: str, the English phrase of a wire token -- the table's
            word where the table carries it; the token with its
            hyphens opened else, so a word the wire grew later is
            read, not swallowed.
    """
    failure = failure_of(token)
    if failure is not None: return failure.description
    known = PHRASE_DB.get(token)
    if known is not None: return known
    return str(token).replace("-", " ")


def colour_decision(environ, tty_f, force_f=False, veto_f=False):
    """
    RETURN: bool, True where the rendering is to carry ANSI colour.

    Taken once, at 'main'; never re-sniffed per line. 'force_f'
    ('--colour') wins over everything, 'NO_COLOR' included; 'veto_f'
    ('--no-colour') wins over the gates; where neither is spoken, ALL
    gates must pass -- refuse rather than guess, at the door:

        tty_f               stdout is a terminal, not a pipe, not a
                            capture
        NO_COLOR unset      https://no-color.org -- ANY value silences
        CI unset            a CI log is a file, not a screen
        TERM set, not dumb  the terminal claims a capability
        not Windows-blind   on 'nt' only where ANSI is known enabled
                            (ANSICON, WT_SESSION or ConEmuANSI)
    """
    import os
    if force_f: return True
    if veto_f:  return False
    if not tty_f:                          return False
    if environ.get("NO_COLOR") is not None: return False
    if environ.get("CI")       is not None: return False
    term = environ.get("TERM")
    if not term or term == "dumb":         return False
    if os.name == "nt" \
       and environ.get("ANSICON")   is None \
       and environ.get("WT_SESSION") is None \
       and environ.get("ConEmuANSI") != "ON":
        return False
    return True


#  THE ENGINE'S OWN DEFAULTS, role by role, in the preferences'
#  vocabulary: what is painted where no face hands in a preference
#  file. 'bin/.hwut.conf' states the same words. Two rulings live here:
#
#  ORANGE IS THE DIRECTORY'S COLOUR, wherever a directory is named:
#  the DIR band's ground, and the name at the head of a HINTS block.
#  ONE NOUN, ONE COLOUR. 256-colour 208; there is no orange in the base
#  16, and red and green stay reserved for [FAIL] and [OK].
#
#  RED IS PINNED, NOT ASKED FOR BY NAME. The base-16 codes 31/41 name
#  PALETTE SLOT 1, and a theme is free to render that slot as it
#  likes -- several popular ones make it orange, which put a failure
#  in the same hue as a directory. 256-colour 196 is red wherever it
#  is drawn -- which is why 'run.fail' is 'c256:196', not 'red'.
ROLE_DEFAULT_DB = {
    "run.ok":            "green",
    "run.fail":          "c256:196",
    "run.tag-ok":        "bright-white bg-green",
    "run.tag-fail":      "bright-white bg256:196",
    "run.warn":          "yellow",
    "run.start":         "blue",
    "run.dim":           "dim",
    "run.bold":          "bold",
    "run.directory":     "c256:208",
    "run.dir-band":      "bright-white bg256:208",
    "run.block-error":   "bold bright-white bg256:196",
    "run.ground-ok":     "bright-white bg-green",
    "run.ground-skip":   "black bg-yellow",
    "run.ground-fail":   "bright-white bg256:196",
    "run.ground-open":   "bright-white bg-blue",
    "run.build":         "green",
    "run.built":         "bright-white",
    "run.progress":      "bright-white bg-blue",
}


from vut.engine.display.colour import paint


class CInk:
    """The ANSI pen: constructed ON or OFF, then applied per segment.
    OFF returns every text unchanged, so a captured face writes plain
    ASCII by construction."""

    def __init__(self, on_f, color_of=None):
        """
        RETURN: CInk, painting where 'on_f', transparent else.

        'color_of' answers a ROLE ('run.fail') with a colour, in the
        preferences' vocabulary. A face hands in the person's
        preferences ('services/lib/preferences.py'); the engine, which
        never reads a preference file, paints 'ROLE_DEFAULT_DB' -- the
        codes it always painted (services E-82).
        """
        self.on_f     = bool(on_f)
        self.color_of = color_of or ROLE_DEFAULT_DB.get

    def paint(self, text, *code_tuple):
        """
        RETURN: str, 'text' under the given SGR codes where the ink is
                on; 'text' unchanged else.
        """
        if not self.on_f or not code_tuple: return text
        return "\x1b[%sm%s\x1b[0m" \
               % (";".join(str(code) for code in code_tuple), text)

    def role(self, text, role):
        """
        RETURN: str, 'text' in the colour the person's preferences give
                'role' (services E-78) where the ink is on; 'text'
                unchanged else. The preferences are read only when the
                ink is on -- a captured face never reads them.
        """
        if not self.on_f: return text
        return paint(text, self.color_of(role) or "")

    def ok(self, text):      return self.role(text, "run.ok")
    def fail(self, text):    return self.role(text, "run.fail")

    #  THE VERDICT TAG CARRIES A GROUND, the phrase beside it does
    #  not: the tag is what an eye scans a long report for, and a
    #  block of colour is FOUND at a glance where a coloured word is
    #  read for. A phrase on a ground would be a second block
    #  competing with the first. White on green, white on red -- 97
    #  the bright foreground, 42 and 41 the grounds.
    def tag_ok(self, text):   return self.role(text, "run.tag-ok")
    def tag_fail(self, text): return self.role(text, "run.tag-fail")
    def warn(self, text):    return self.role(text, "run.warn")
    def start(self, text):   return self.role(text, "run.start")
    def dim(self, text):     return self.role(text, "run.dim")
    def bold(self, text):    return self.role(text, "run.bold")

    def dir_band(self, text):
        """
        RETURN: str, 'text' as a FULL-WIDTH BAND: bright white on the
                directory's orange. The caller pads 'text' to the
                width it wants the ground to span; this paints, it
                does not measure.
        """
        return self.role(text, "run.dir-band")

    #  THE FINAL BAR'S THREE GROUNDS: ok on green, skipped on yellow,
    #  failed on red -- a block of colour whose WIDTH is the count, so
    #  the shape of a run is read before its numbers are. Each carries
    #  its word: bright white (97) on green and red, black (30) on
    #  yellow, where white would not read. THE FAIL GROUND IS THE ONE
    #  THE '[FAIL]' TAG WEARS -- 'run.tag-fail', 256-colour 196 --
    #  never the base-16 '41', which is palette slot 1 and orange in
    #  several themes.
    #  'ERROR' IS A BLOCK, NOT A WORD (O-24): the same red ground the
    #  '[FAIL]' tag and the closing bar wear, bright white and bold on
    #  it -- a fault stands in the flow where START and DONE stand, and
    #  must be seen at a glance among them.
    def block_error(self, text):  return self.role(text, "run.block-error")

    def ground_ok(self, text):    return self.role(text, "run.ground-ok")
    def ground_skip(self, text):  return self.role(text, "run.ground-skip")
    def ground_fail(self, text):  return self.role(text, "run.ground-fail")
    def ground_open(self, text):  return self.role(text, "run.ground-open")
    def build(self, text):        return self.role(text, "run.build")
    def built(self, text):        return self.role(text, "run.built")
    def progress(self, text):     return self.role(text, "run.progress")

    def directory(self, text):
        """
        RETURN: str, a directory's name in the directory's own colour
                -- orange, the same hue the DIR band carries as its
                ground.
        """
        return self.role(text, "run.directory")
