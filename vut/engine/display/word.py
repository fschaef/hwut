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

#  Wire token -> the phrase. Verdict words first, the operations'
#  report words after, one voice throughout.
#
#  THIS TABLE IS THE WHOLE OF THE FRAMEWORK'S ENGLISH. Every phrase a
#  rendering speaks stands here and nowhere else -- the flow line, the
#  roll-call and the HINTS block all read it -- so the vocabulary can
#  be reviewed in one screen, and translated by replacing one object.
#  A phrase written inline at a call site is a word no reviewer of
#  this table would ever see, and no translator would ever find.
PHRASE_DB = {
    "ok":                          "ok",
    "test-failed":                 "the test failed",
    "build-failed":                "the build failed",
    "launch-failed":               "the launch failed",
    "unsupported":                 "not supported here",
    "misdep":                      "missing dependency",

    #  THE APPLICATION'S OWN HEADER, not 'hwut.conf': the file the
    #  fault names carries an '@hwut { ... }' block that does not
    #  parse, so it never became a node ('orchestrate._broken_app_tuple'
    #  skips '.conf' deliberately). 'the specification' alone left the
    #  reader to guess which of the two it was.
    "spec-broken":                 "the test's own @hwut header does not parse",

    #  The frame of a directory -- its setup or its teardown.
    "frame-failed":                "the frame failed",

    #  THE BOOK DOCUMENTS WHAT TESTS EXIST. Where it records one the
    #  tree no longer declares, the two disagree and only a person can
    #  say which is wrong -- so it is a failing test, never a silence.
    #  ('hwut.remove' / 'hwut.remove-choice' heal the book where the
    #  removal was intended.)
    "test-vanished":               "recorded in the book, but no such test stands",
    "test-choice-vanished":        "recorded in the book, but the test offers no such choice",

    "unstable":                    "UNSTABLE -- not run",

    "source-not-found":            "source file missing",
    "interpreter-not-found":       "interpreter missing",
    "not-equivalent-with-nominal": "differs from GOOD",
    "not-equivalent-grew":         "extra lines; GOOD intact",
    "not-equivalent-shrank":       "lines missing; rest intact",
    "not-equivalent-diverged":     "differs from GOOD",
    "test-app-launch-failed":      "the application would not launch",
    "test-app-contained":          "killed by the supervisor",
    #  ONE PHRASE PER CAP (O-19): the HINT names what was hit; the
    #  numbers follow it in parentheses, from the event's 'detail'.
    "test-app-wall-clock-exceeded": "killed: over the wall-clock cap",
    "test-app-cpu-time-exceeded":   "killed: over the cpu-time cap",
    "test-app-memory-exceeded":     "killed: over the memory cap",
    "test-app-file-size-exceeded":  "killed: over the file-size cap",
    "test-app-pids-exceeded":       "killed: over the process cap",
    "test-app-disk-exceeded":       "killed: over the disk cap",
    "test-app-no-output":          "produced no output",
    "test-app-stalled":            "stalled, no output",
    "recording-missing":           "no recording to replay",
    "output-file-not-found":       "output file missing",
    "nominal-file-not-found":      "GOOD missing",
    "terminated-without-hwut-end": "output cut short (no <hwut-end>)",
    "unexpected-stderr":           "unexpected stderr",
    "stderr-undecided":            "stderr undecided",
    "pype-interpreter-not-found":  "pype interpreter missing",
    "pype-file-not-found":         "pype script missing",
    "pype-file-syntax-error":      "pype script has a syntax error",
    "region-syntax-error":         "region framing is broken",
    "pype-contained":              "pype killed by the supervisor",
    "pype-failed":                 "pype failed",
    "build-tool-not-found":        "build tool missing",
    "build-contained":             "build killed by the supervisor",
    "target-not-built":            "target not built",
    "acquisition-failed":          "a dependency would not be acquired",
    "display-target-unreachable":  "display target unreachable",
}


def phrase(token):
    """
    RETURN: str, the English phrase of a wire token -- the table's
            word where the table carries it; the token with its
            hyphens opened else, so a word the wire grew later is
            read, not swallowed.
    """
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


#  ORANGE IS THE DIRECTORY'S COLOUR, wherever a directory is named:
#  the DIR band's ground, and the name at the head of a HINTS block.
#  ONE NOUN, ONE COLOUR -- a reader who has learnt what orange means
#  in the band reads the same thing in the hints. 256-colour 208;
#  there is no orange in the base 16, and red and green stay reserved
#  for [FAIL] and [OK].
DIRECTORY_CODE_TUPLE = (38, 5, 208)

#  RED IS PINNED, NOT ASKED FOR BY NAME. The base-16 codes 31/41 name
#  PALETTE SLOT 1, and a theme is free to render that slot as it
#  likes -- several popular ones make it orange, which put a failure
#  in the same hue as a directory and made the two unreadable side by
#  side. 256-colour 196 is red wherever it is drawn.
FAIL_CODE      = (38, 5, 196)
FAIL_TAG_CODE  = (97, 48, 5, 196)


class CInk:
    """The ANSI pen: constructed ON or OFF, then applied per segment.
    OFF returns every text unchanged, so a captured face writes plain
    ASCII by construction."""

    def __init__(self, on_f):
        """
        RETURN: CInk, painting where 'on_f', transparent else.
        """
        self.on_f = bool(on_f)

    def paint(self, text, *code_tuple):
        """
        RETURN: str, 'text' under the given SGR codes where the ink is
                on; 'text' unchanged else.
        """
        if not self.on_f or not code_tuple: return text
        return "\x1b[%sm%s\x1b[0m" \
               % (";".join(str(code) for code in code_tuple), text)

    def ok(self, text):      return self.paint(text, 32)
    def fail(self, text):    return self.paint(text, *FAIL_CODE)

    #  THE VERDICT TAG CARRIES A GROUND, the phrase beside it does
    #  not: the tag is what an eye scans a long report for, and a
    #  block of colour is FOUND at a glance where a coloured word is
    #  read for. A phrase on a ground would be a second block
    #  competing with the first. White on green, white on red -- 97
    #  the bright foreground, 42 and 41 the grounds.
    def tag_ok(self, text):   return self.paint(text, 97, 42)
    def tag_fail(self, text): return self.paint(text, *FAIL_TAG_CODE)
    def warn(self, text):    return self.paint(text, 33)
    def start(self, text):   return self.paint(text, 34)
    def dim(self, text):     return self.paint(text, 2)
    def bold(self, text):    return self.paint(text, 1)

    def dir_band(self, text):
        """
        RETURN: str, 'text' as a FULL-WIDTH BAND: bright white on the
                directory's orange. The caller pads 'text' to the
                width it wants the ground to span; this paints, it
                does not measure.
        """
        return self.paint(text, 97, 48, 5, 208)

    def directory(self, text):
        """
        RETURN: str, a directory's name in the directory's own colour
                -- orange, the same hue the DIR band carries as its
                ground.
        """
        return self.paint(text, *DIRECTORY_CODE_TUPLE)
