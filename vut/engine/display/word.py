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
PHRASE_DB = {
    "ok":                          "ok",
    "test-failed":                 "the test failed",
    "build-failed":                "the build failed",
    "launch-failed":               "the launch failed",
    "unsupported":                 "not supported here",
    "misdep":                      "missing dependency",

    "source-not-found":            "source file missing",
    "interpreter-not-found":       "interpreter missing",
    "not-equivalent-with-nominal": "differs from GOOD",
    "test-app-launch-failed":      "the application would not launch",
    "test-app-contained":          "killed by the supervisor",
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


#  One colour per directory, cycling; red and green stay reserved for
#  [FAIL] and [OK].
_NICK_CODE_TUPLE = (36, 35, 34, 33)          # cyan magenta blue yellow


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
    def fail(self, text):    return self.paint(text, 31)
    def warn(self, text):    return self.paint(text, 33)
    def start(self, text):   return self.paint(text, 34)
    def dim(self, text):     return self.paint(text, 2)
    def bold(self, text):    return self.paint(text, 1)

    def nick(self, text, index):
        """
        RETURN: str, 'text' in the cycling per-directory colour of
                'index' -- the directory's own hue, stable for the
                whole report.
        """
        return self.paint(text,
                          _NICK_CODE_TUPLE[index
                                           % len(_NICK_CODE_TUPLE)])
