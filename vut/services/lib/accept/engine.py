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
from vut.services._accept_common          import token_terminated_f
from vut.services._exit                   import E_ExitCode
from vut.services.lib.viewers             import (driver_for, E_DisplayTarget,
                                                  keyed_absent_reason,
                                                  fallback_note)
from vut.engine.operations.interaction.port import (E_Intent, merge_session,
                                                    MERGE_ROUND_MAX)

import asyncio
import io
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
    def align(subject, working):
        """RETURN: AsyncIterable[DisplayInst], the alignment of
        'subject' against 'working'."""
        return compare_feeder.feed(options, io.StringIO(subject),
                                   io.StringIO(working))
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


def run_sessions(key_list, store_of, adapter, err, setup=None,
                 max_round_n=None, stderr_tol_f=False):
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
    """
    accepted_list, refused_list, left_list = [], [], []
    for key in key_list:
        store   = store_of(key.where)
        options = setup if setup is not None else key.setup
        #  THE STANDING REACHES THE SCREEN (B-14). Optional on the
        #  contract, so this call is the same on every tier.
        adapter.note_standing(getattr(key, "aspirant_f", False))
        #  STDERR SPOKE (E-91): told BEFORE the session, so the screen can
        #  warn before the author merges what 'q' will refuse.
        from vut.services.accept import stderr_spoke_db
        class _Case:
            source_file = key.test
            choice      = key.choice
        note = getattr(adapter, "note_stderr", None)
        if note is not None: note(bool(stderr_spoke_db(store, [_Case()])))
        #  None MEANS THE DEFAULT, not 'no bound': 'hwut.accept' states
        #  none, and the second round -- after 'e' or 'g' -- was MEASURED
        #  to die comparing round_n against None (E-90).
        text, intent = asyncio.run(merge_text(
            key.subject_text, key.nominal_text, adapter, key.label,
            options, max_round_n=max_round_n or MERGE_ROUND_MAX))
        if intent is not E_Intent.COMMIT or text is None:
            left_list.append(key)
            continue
        reason = refusal(store, key, text, stderr_tol_f, err)
        if reason is not None:
            refused_list.append((key, reason))
            continue
        #  THE THREE WRITES OF AN ACCEPTANCE, as 'hwut.accept' makes
        #  them (E-41): the nominal, the register, the book.
        store.accept(key.test, key.choice, "stdout", text)
        store.bookkeeper.note_accept(key.test, key.choice)
        accepted_list.append(key)
    return (accepted_list, refused_list, left_list)


def refusal(store, key, text, stderr_tol_f, err):
    """
    RETURN: str, why this text may NOT become the nominal -- in
            'hwut.accept's words.

            None, where it may.
    """
    from vut.services.accept import stderr_spoke_db, stderr_decision

    if store.bookkeeper.stain(key.test, key.choice) is not None:
        return "a stained choice has no pole to declare"
    if not token_terminated_f(text):
        return "the closing token '<hwut-end>' is not the last line " \
               "-- a stream that never COMPLETED is not promotable"

    class _Case:
        source_file = key.test
        choice      = key.choice

    spoke_db = stderr_spoke_db(store, [_Case()])
    if spoke_db:
        refused = stderr_decision(store, spoke_db, stderr_tol_f, err)
        if refused:
            return "stderr spoke and nothing tolerates it ('--stderr-tol')"
    return None


def report(accepted_list, refused_list, left_list, key_n, err):
    """
    RETURN: E_ExitCode, FAULT where anything was refused, OK otherwise.

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
        err("    %-14s %s" % ("blessed" if getattr(key, "aspirant_f", False)
                              else "accepted", key.label))
    for key, reason in refused_list: err("    refused        %s -- %s"
                                         % (key.label, reason))
    for key in left_list:            err("    left alone     %s" % key.label)
    err("=" * 78)
    return E_ExitCode.FAULT if refused_list else E_ExitCode.OK
