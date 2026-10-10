"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE MERGE ENGINE -- one session per key, the three writes on
         commit, and the report of what became of each.

DESCRIPTION
       ONE ENGINE, TWO DOORS. 'hwut.accept' reaches it where a nominal
       stands and the author is at a terminal (E-59); 'hwut.accept.
       interactive' reaches it by its E-51 name, which stays as an
       alias. Neither owns the loop, so a rule about promotion cannot
       hold at one door and not the other.

       THE THREE WRITES ARE E-41's, unchanged: the nominal, the
       register, the book, in that order and only on COMMIT.

       AN ASPIRANT REACHES THE SAME LOOP. A choice the book knows with
       no nominal standing (B-14) opens on the mirror 'accept_first'
       builds, and its commit is a FIRST BLESSING -- the same three
       writes, a different word in the report, and the banner says
       'aspirant' so nobody mistakes a blessing for a merge.

       THE REFUSALS ARE 'hwut.accept's OWN, asked through
       '_accept_common' -- the stain, the closing token (R-70), stderr.
       A session that ends in anything but COMMIT writes nothing at
       all: a cancelled merge leaves no half-decided nominal behind.
______________________________________________________________________________
"""
from vut.services._accept_common          import (token_terminated_f,
                                                 STDERR_IGNORED_LINE,
                                                 stderr_mention_of)
from vut.services._exit                   import E_ExitCode
from vut.services.lib.viewers             import (driver_for, E_DisplayTarget,
                                                  keyed_absent_reason,
                                                  fallback_note)
from vut.engine.operations.interaction.port import (E_Intent, merge_session,
                                                    MERGE_ROUND_MAX)

import asyncio
import io
from   vut.engine.bookkeeper.api            import carries_unaccepted_text_f
import sys


async def merge_text(subject_text, nominal_text, adapter,
                     subject_name, compare_options,
                     max_round_n=MERGE_ROUND_MAX):
    """
    RETURN: (str, E_Intent), the merged nominal stream and the intent
            that ended the session.
            (None, E_Intent.CANCEL), the session resolved nothing.

    'merge_session' with the alignment from compare's one door under
    this choice's options.
    """
    from vut.engine.compare.api import feeder_ui as compare_feeder
    from vut.engine.compare.api import Configuration
    options = compare_options if compare_options is not None \
              else Configuration()
    #  THE TOLERANCE IN MEMORY BEGINS AS THE CHOICE'S OWN (intend 21):
    #  optional on the contract, so this call is the same on every tier.
    note = getattr(adapter, "note_tolerance", None)
    if note is not None: note(options)
    def align(subject, working, tried=None):
        """RETURN: AsyncIterable[DisplayInst], the alignment of
        'subject' against 'working' -- under the tolerance the author
        TRIED where he tried one (intend 21), else under the choice's."""
        return compare_feeder.feed(tried if tried is not None else options,
                                   io.StringIO(subject), io.StringIO(working))
    return await merge_session(align, subject_text, nominal_text,
                               adapter, subject_name,
                               max_round_n=max_round_n)


def adapter_for(editor_argv=None, plain_f=False, side_by_side_f=False,
                width=None, out=None, input_f=None, console_f=False,
                err=None):
    """
    RETURN: DisplayAdapter, the session to run the merges in -- the
            KEYED screen where a person sits at a terminal; the
            line-based one under 'console_f', or where the screen cannot
            run: a scripted run, a pipe, a suite answering through
            'input', a machine without 'prompt_toolkit'.

    THE FALLBACK IS NEVER SILENT (services E-79): where the screen was
    wanted and cannot run, ONE note on 'err' says why. 'console_f' asked
    for the line-based session outright and hears nothing.
    """
    if out is None:     out = sys.stderr
    if input_f is None: input_f = input
    if err is None:     err = lambda text: sys.stderr.write(text + "\n")

    target = E_DisplayTarget.TUI
    if not console_f:
        reason = keyed_absent_reason((out,))
        if reason is None: target = E_DisplayTarget.KEYS
        else:              err(fallback_note(reason))
    return driver_for(target,
                      out            = out,
                      input_f        = input_f,
                      editor_argv    = editor_argv,
                      color_f        = False if plain_f else None,
                      merge_f        = True,
                      side_by_side_f = side_by_side_f,
                      width          = width)


#  WHAT A SAVE SHORT OF THE OUTPUT IS CALLED, at both doors (f-8).
SHORT_WORD = "saved [FAIL]"
SHORT_NOTE = "GOOD is saved; OUT still differs from it"
#  A KEY IS ANOTHER MODULE'S RECORD, frozen or slotted: what a session
#  learned of it is kept beside it, by identity, while the keys live.
_SHORT_ID_SET = set()


def short_f(key):
    """RETURN: True, a bool saying 'run_sessions' saved a GOOD for 'key'
                     that its output still differs from
               False, else
    """
    return id(key) in _SHORT_ID_SET


def run_sessions(key_list, store_of, adapter, err, setup=None,
                 max_round_n=None, ask=None):
    """
    RETURN: (accepted_list, refused_list, left_list) -- the keys that
            became nominals, the (key, reason) pairs refused after a
            commit, and the keys the author left alone.

            An ASPIRANT that commits is reported as BLESSED, not
            accepted: it had no pole to reconcile with (B-14).

            Nothing is written for a key that is refused or left: a
            merge that did not end in COMMIT leaves the pole as it
            stood.

    'setup' overrides each key's own compare configuration where the
    caller stated one on the command line; None leaves each key with
    its own.

    A TOLERANCE TRIED IN THE SESSION is asked about once the key is
    decided (intend 21, 2.7; 'keep.py'): 'ask' reads the answer, the
    terminal's by default.
    """
    accepted_list, refused_list, left_list = [], [], []
    for key in key_list:
        store   = store_of(key.where)
        options = setup if setup is not None else key.setup
        #  THE STANDING REACHES THE SCREEN (B-14). Optional on the
        #  contract, so this call is the same on every tier.
        adapter.note_standing(getattr(key, "aspirant_f", False))
        #  STDERR SPOKE (E-91): told BEFORE the session, so the screen can
        #  warn before the author merges what 's' will refuse.
        from vut.services.accept import stderr_spoke_db
        class _Case:
            source_file = key.test
            choice      = key.choice
        spoke_f   = bool(stderr_spoke_db(store, [_Case()]))
        ignored_f = getattr(key, "stderr_ignored_f", False)
        note = getattr(adapter, "note_stderr", None)
        if note is not None: note(spoke_f, ignored_f)
        #  SAID IN WORDS TOO (E-136): the stain is mentioned on every
        #  tier, not only where a screen has a foot to carry it.
        mention = stderr_mention_of(key.label, spoke_f, ignored_f)
        if mention is not None: err(mention)
        #  EVERY OTHER STAIN OF THE BOOK, in the same words as the diff
        #  says them (E-141).
        from vut.services._accept_common import stain_mention_list
        for line in stain_mention_list(key.label,
                                       getattr(key, "stain", None)):
            err(line)
        #  None MEANS THE DEFAULT, not 'no bound': 'hwut.accept' states
        #  none, and the second round -- after 'e' or 'g' -- was MEASURED
        #  to die comparing round_n against None (E-90).
        text, intent = asyncio.run(merge_text(
            key.subject_text, key.nominal_text, adapter, key.label,
            options, max_round_n=max_round_n or MERGE_ROUND_MAX))
        accepted_f = False
        if intent is not E_Intent.COMMIT or text is None:
            left_list.append(key)
        else:
            reason = refusal(store, key, text, err)
            if reason is not None:
                refused_list.append((key, reason))
            else:
                #  THE THREE WRITES OF AN ACCEPTANCE, as 'hwut.accept'
                #  makes them (E-41): the nominal, the register, the book.
                #  THE BOOK SAYS WHAT A CHECK FOUND, NOT WHAT THE KEY
                #  HOPED (r-11c): OUT is held against the nominal just
                #  written BEFORE the entry is made. A GOOD saved short of
                #  OUT stands -- and is booked as the failure a run would
                #  find, not as 'ok'.
                store.accept(key.test, key.choice, "stdout", text)
                same_f = equivalent_f(options, key.subject_text, text)
                store.bookkeeper.note_accept(
                    key.test, key.choice,
                    aspirant_f   = carries_unaccepted_text_f(text),
                    equivalent_f = same_f)
                #  A SAVE THAT LEAVES A DIFFERENCE IS SAID AS THE FAILURE
                #  IT IS (ruled 2026-10-09, f-8): the report marks it.
                if not same_f: _SHORT_ID_SET.add(id(key))
                accepted_list.append(key)
                accepted_f = True
        from .keep import keep_question
        keep_question(adapter, key, _directory_of(store, key), accepted_f,
                      err, ask or _terminal_ask)
    return (accepted_list, refused_list, left_list)


def equivalent_f(options, subject_text, nominal_text):
    """RETURN: True, a bool saying compare finds 'subject_text' equivalent
                     to 'nominal_text' under 'options' -- the verdict a
                     run of this OUT against this GOOD would book.
               False, where it does not, or where the nominal's regions
                      cannot be read.
    """
    from vut.engine.compare.api import (Configuration, ConstraintSpecError,
                                        RegionSyntaxError, is_equivalent)
    setup = options if options is not None else Configuration()
    try:
        return bool(asyncio.run(is_equivalent(setup,
                                              io.StringIO(subject_text),
                                              io.StringIO(nominal_text))))
    except (ConstraintSpecError, RegionSyntaxError):
        return False


def _directory_of(store, key):
    """RETURN: str, the directory the test stands in -- where its GOOD
               directory stands."""
    return str(store.bookkeeper.nominal_path(key.test, key.choice,
                                             "stdout").parent.parent)


def _terminal_ask(prompt):
    """RETURN: str, one line the person typed after 'prompt' -- asked on
               stderr like every session face's UI.

               Raises EOFError where stdin is closed."""
    sys.stderr.write(prompt)
    sys.stderr.flush()
    line = sys.stdin.readline()
    if not line: raise EOFError
    return line


def refusal(store, key, text, err):
    """
    RETURN: str, why this text may NOT become the nominal -- in
            'hwut.accept's words.

            None, where it may.
    """
    from vut.services.accept import stderr_spoke_db, stderr_decision

    from vut.engine.bookkeeper.api import unstable_f
    if unstable_f(store.bookkeeper.stain(key.test, key.choice)):
        return "a stained choice has no pole to declare"
    if not token_terminated_f(text):
        return "the closing token '<hwut-end>' is not the last line " \
               "-- a stream that never COMPLETED is not promotable"
    #  A TEXT THAT BREAKS ITS CONSTRAINTS IS NEVER ACCEPTED (E-124): held
    #  against itself, as it would stand as the GOOD.
    from .constraint import own_finding_text_list
    own_list = own_finding_text_list(getattr(key, "setup", None), text)
    if own_list:
        return "the text breaks its constraints -- %s" % "; ".join(own_list)

    class _Case:
        source_file = key.test
        choice      = key.choice

    spoke_db = stderr_spoke_db(store, [_Case()])
    if stderr_decision(spoke_db,
                       lambda test, choice:
                           getattr(key, "stderr_ignored_f", False)):
        return "stderr spoke and nothing tolerates it ('%s' in the " \
               "test's block declares it)" % STDERR_IGNORED_LINE
    return None


def report(accepted_list, refused_list, left_list, key_n, err):
    """
    RETURN: E_ExitCode, FAULT where anything was refused or saved short
            of its output, OK otherwise.

    The same block both doors print, so a script reading it need not
    know which face ran.
    """
    err("")
    err("=" * 78)
    err("ACCEPTED  %d of %d" % (len(accepted_list), key_n))
    err("-" * 78)
    for key in accepted_list:
        #  A FIRST BLESSING IS NOT A MERGE (B-14, E-51/E-59): an
        #  aspirant had no pole to reconcile with, so the word for what
        #  happened to it is 'hwut.accept's own.
        if short_f(key):
            err("    %-14s %s -- %s" % (SHORT_WORD, key.label, SHORT_NOTE))
            continue
        err("    %-14s %s" % ("blessed" if getattr(key, "aspirant_f", False)
                              else "accepted", key.label))
    for key, reason in refused_list: err("    refused        %s -- %s"
                                         % (key.label, reason))
    for key in left_list:            err("    left alone     %s" % key.label)
    err("=" * 78)
    any_short_f = any(short_f(key) for key in accepted_list)
    return E_ExitCode.FAULT if refused_list or any_short_f else E_ExitCode.OK
