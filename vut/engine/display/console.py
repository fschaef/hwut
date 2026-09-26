"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE CONSOLE'S OWN VOCABULARY (D-7) -- the tier flags, the
         colour flags, the gates and the width policy, in ONE place.
         A face states the user's words; this module decides what the
         console makes of them and hands back a view.

THREE KINDS OF WORD, THREE PARSERS, each owned by whoever understands
it:

    selection   the wish          'plan/wish.py'      parse_wish()
    execution   --jobs --no-store  the face itself
    rendering   the tier, colour   THIS module        parse_rendering()

A face never decides how something looks; this module never decides
what runs. 'parse_rendering()' mirrors 'parse_wish()' exactly: it takes
the words, yields what it understood and what it did not touch, and
raises where the words cannot want anything. The face turns the raise
into REFUSED, by name, with the usage line.

WHAT THE FACE STILL OWNS: whether its stdout is a terminal. The face
knows its own sink ('write' given, or 'print'); this module knows what
a terminal is worth.
______________________________________________________________________________
"""
import shutil
import sys

from dataclasses import dataclass

from .plain import CPlainFlow, E_Tier
from .word  import CInk, colour_decision


#  ---------------------------------------------------------------------
#  THE RENDERING WORDS -- written ONCE, spliced by every face that
#  renders (hwut.run, and whatever follows). D-8: a face never
#  describes how something looks.
#  ---------------------------------------------------------------------
USAGE_TOKEN_TUPLE = ("[-v|--verbose|--plain|--quiet|--silent]",
                     "[--colour|--no-colour]", "[--show-timing]",
                     "[--show-jobs]", "[--show-details]",
                     "[--no-failure-summary]",
                     "[--brief]",
                     "[--log <file>]")

HELP = """RENDERING -- one tier, the flags mutually exclusive
    -v, --verbose       every event as it arrives, the swallowed ones
                        included
    --plain             the default: the flow, the DIRECTORIES
                        roll-call, FAILURES last; statable redundantly
    --quiet             no flow; the closing blocks alone
    --silent            nothing on stdout; the exit status is the
                        whole report -- faults still go to stderr,
                        prefixed and nicknamed as in the flow

COLUMNS AND BLOCKS -- what the flow line carries, and what closes it
    --show-timing       a seconds column before each flow line; absent,
                        the flow carries no clock
    --show-jobs         a '|<n>|' column with the work standing at that
                        moment; absent, no such column
    --show-details      every line the run has to give: the BUILD and
                        SESSION nodes that provision a test, and what
                        else is provision rather than test. Absent,
                        only the tests and the directory's own lines
                        speak -- a FAILING provision node always does,
                        for a failed precondition is a test result
    --no-failure-summary
                        drop the closing HINTS block; absent, every
                        hint is named there

THE LOG -- the flow, in a file, where one is asked for
    --log <file>        ALSO write the flow to that file, plain, one
                        line per event, OVERWRITTEN at the run's start
                        (O-24). Without it NO FILE IS WRITTEN. The file
                        is a rendering for the eye and for a mail
                        attachment -- not a record to query: what a run
                        cost is 'TEST/hwut-traces.csv' (B-11), and what
                        it decided is the book

COLOUR -- decided once, at the door
    --colour            enforcement: on, over every gate, NO_COLOR
                        included
    --no-colour         off, always
    (neither)           on only where stdout is a terminal, NO_COLOR
                        and CI are unset, and TERM claims a capability"""


class RenderingError(Exception):
    """The rendering words cannot want anything."""


#  The flag as the user spells it -> the tier it names.
TIER_FLAG_DB = {"-v":        E_Tier.VERBOSE,
                "--verbose": E_Tier.VERBOSE,
                "--quiet":   E_Tier.QUIET,
                "--silent":  E_Tier.SILENT}

#  '--plain' names the default; it is statable, so a script can pin
#  the rendering even where the default moves later (D-4).
PLAIN_FLAG = "--plain"

COLOUR_FLAG    = "--colour"
NO_COLOUR_FLAG = "--no-colour"

#  WHERE THE MARGINALIA GO by default. A name, not a path: the log is
#  written where the face was called, which is where its reader is.
#  NO DEFAULT LOG (O-24): a file exists because it was asked for.
DEFAULT_LOG_NAME = None

DEFAULT_WIDTH = 78
MINIMUM_WIDTH = 40
MAXIMUM_WIDTH = 120


@dataclass(slots=True)
class CRenderingWish:
    """What the words said about rendering: which tier, whether
    colour was enforced or refused, which columns the flow line
    carries, and whether the closing FAILURES block stands."""
    tier:      E_Tier = E_Tier.PLAIN
    log_path:  str    = None
    force_f:   bool   = False
    veto_f:    bool   = False
    timing_f:  bool   = False
    jobs_f:    bool   = False
    detail_f:  bool   = False
    failure_summary_f: bool = True
    brief_f: bool = False


def parse_rendering(argument_list):
    """
    RETURN: [0] CRenderingWish, the tier and the colour enforcement
                the words asked for; the defaults where they said
                nothing.
            [1] list, the words this module did not touch, in order.

    Raises 'RenderingError' where the words cannot want anything: two
    tiers at once, '--plain' beside another tier, '--colour' beside
    '--no-colour', or a '--log' naming no
    file.
    """
    tier_flag_list = []
    plain_f        = False
    force_f        = False
    veto_f         = False
    timing_f       = False
    jobs_f         = False
    detail_f       = False
    summary_f      = True
    brief_f        = False
    log_path       = None
    rest_list      = []
    argument_i     = -1
    while argument_i + 1 < len(argument_list):
        argument_i += 1
        argument    = argument_list[argument_i]
        #  '--log <file>' TAKES THE WORD AFTER IT, and '--log=<file>'
        #  says the same thing in one word; both are spelt in the
        #  wild and neither is worth refusing.
        if argument == "--log":
            if argument_i + 1 >= len(argument_list):
                raise RenderingError("'--log' wants a file name after it")
            argument_i += 1
            log_path    = argument_list[argument_i]
            continue
        if argument.startswith("--log="):
            log_path    = argument[len("--log="):]
            if not log_path:
                raise RenderingError("'--log=' wants a file name after it")
            continue
        if   argument in TIER_FLAG_DB:      tier_flag_list.append(argument)
        elif argument == PLAIN_FLAG:        plain_f = True
        elif argument == COLOUR_FLAG:       force_f = True
        elif argument == NO_COLOUR_FLAG:    veto_f  = True
        elif argument == "--show-timing":   timing_f  = True
        elif argument == "--show-jobs":     jobs_f    = True
        elif argument == "--show-details":  detail_f  = True
        elif argument == "--brief":         brief_f   = True
        elif argument == "--no-failure-summary":
                                            summary_f = False
        else:                               rest_list.append(argument)

    if len(set(TIER_FLAG_DB[flag] for flag in tier_flag_list)) > 1:
        raise RenderingError("choose one of -v/--verbose, --quiet, "
                             "--silent")
    if plain_f and tier_flag_list:
        raise RenderingError("'--plain' beside '%s' can want nothing"
                             % tier_flag_list[0])
    if force_f and veto_f:
        raise RenderingError("'--colour' beside '--no-colour' can want "
                             "nothing")

    tier = TIER_FLAG_DB[tier_flag_list[0]] if tier_flag_list \
           else E_Tier.PLAIN
    return CRenderingWish(tier=tier, force_f=force_f, veto_f=veto_f,
                          timing_f=timing_f, jobs_f=jobs_f,
                          detail_f=detail_f,
                          failure_summary_f=summary_f,
                          brief_f=brief_f,
                          log_path=log_path), \
           rest_list


def console_width(environ, tty_f, size_of=None):
    """
    RETURN: int, the width the dotted fill aims at: THE TERMINAL'S OWN
            WIDTH where one listens, held between MINIMUM_WIDTH and
            MAXIMUM_WIDTH; DEFAULT_WIDTH otherwise -- a piped or
            captured report is 78 wide, deterministically (O-30).

    THE TERMINAL IS ASKED, NOT ONLY THE ENVIRONMENT (ruled, D-19).
    'COLUMNS' is a shell variable and most shells do not export it, so
    a report that trusted it alone drew 78 columns on a 200-column
    screen. 'COLUMNS' still wins where it stands and reads as a
    number: the user who states a width means it. Otherwise the
    terminal answers through 'size_of' -- 'shutil.get_terminal_size'
    by default, which asks the device.

    THE CAP IS NOT COSMETIC: a line drawn to the full width of a very
    wide terminal is a line the eye must travel, and the dots between
    the name and the verdict stop joining the two.
    """
    if not tty_f: return DEFAULT_WIDTH
    if environ.get("COLUMNS", "").isdigit():
        return _held(int(environ["COLUMNS"]))
    try:
        column_n = (size_of or shutil.get_terminal_size)().columns
    except (OSError, ValueError):
        return DEFAULT_WIDTH
    #  A DEVICE THAT ANSWERS NOTHING answers zero; the fallback is the
    #  deterministic width, not a line of 40 dots.
    if column_n < 1: return DEFAULT_WIDTH
    return _held(column_n)


def _held(column_n):
    """RETURN: int, 'column_n' held between MINIMUM_WIDTH and
    MAXIMUM_WIDTH."""
    return min(max(column_n, MINIMUM_WIDTH), MAXIMUM_WIDTH)


def _terminal_write(text):
    """RETURN: None. 'text' written to the terminal as it stands -- no
    newline -- and flushed, so a line redrawn in place shows at once."""
    sys.stdout.write(text)
    sys.stdout.flush()


def console_view(rendering_wish, write, write_error, environ, tty_f,
                 write_log=None, color_of=None, write_wallflowers=None,
                 root=None, started_at=None):
    """
    RETURN: CPlainFlow, the console view the words asked for -- tier,
            ink and width already decided.

    The colour decision is taken HERE, once, and handed to the view as
    a constructed pen; no line re-sniffs (D-2).

    'write_log' is the face's, exactly as 'write' and 'write_error'
    are: THE FACE OWNS ITS SINKS. This module says a log stands and
    what goes in it; opening a file, and closing it, is the caller's
    -- a renderer that opened files would own a resource it cannot
    promise to release. 'write_wallflowers' is the face's on the same
    terms.
    """
    ink = CInk(colour_decision(environ, tty_f,
                               force_f=rendering_wish.force_f,
                               veto_f=rendering_wish.veto_f),
               color_of=color_of)
    return CPlainFlow(write, write_error,
                      width=console_width(environ, tty_f),
                      ink=ink, tier=rendering_wish.tier,
                      timing_f=rendering_wish.timing_f,
                      jobs_f=rendering_wish.jobs_f,
                      detail_f=rendering_wish.detail_f,
                      failure_summary_f
                          =rendering_wish.failure_summary_f,
                      brief_f=rendering_wish.brief_f,
                      write_log=write_log,
                      write_wallflowers=write_wallflowers,
                      #  THE PROGRESS LINE is a COLOURED TERMINAL's: it
                      #  stands exactly where the colours stand -- never
                      #  in a pipe, a log or a test page, never where the
                      #  colours are turned off, and not under SILENT.
                      started_at=started_at,
                      progress_write=_terminal_write
                          if tty_f and ink.on_f
                             and rendering_wish.tier is not E_Tier.SILENT
                          else None,
                      root=root)
