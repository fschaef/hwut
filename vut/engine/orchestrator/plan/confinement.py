"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: AN UNENFORCEABLE CAP REFUSES THE TEST (exploration R-48, R-80)
         -- judged BEFORE the run, per case, against the procsitter's
         capability board.

    procsitter's board ------.
                             +--> uncapped_tuple() --> the refusal,
    the case's caps ---------'        minus what          by cap name,
                                  'hwut-root.conf'        with the line
                                    acknowledges          that lifts it

WHAT A CASE REQUIRES. The five caps that carry a default are in force
for EVERY case, stated or not: the default is a cap. The three the
procsitter has no field for are required only where they are stated to
confine -- 'network = false', a 'file_handle_max_n', a
'write_directory_list'.

THE ACKNOWLEDGEMENT is the root conf's alone and names platform and
cap: 'procsitter { linux { network = false } }'. It says: this cap
does not cap here, and the tests run regardless -- knowingly.
______________________________________________________________________________
"""
from ...bookkeeper.api  import CAPS_FIELD_DB
from ...procsitter.api  import (INSTALL_DB, capability_db,
                                platform_name, utility_of)

ROOT_CONF_NAME = "hwut-root.conf"

#  The opening of every refusal made here: the display groups by reason,
#  and 'hwut.help' may recognise the kind by it.
REASON_OPENER  = "not enforceable on"

#  The author's word -> whether the stated value confines at all.
_UNFIELDED_DB = {
    "file_handle_max_n":    lambda value: value is not None,
    "network":              lambda value: value is False,
    "write_directory_list": lambda value: value is not None,
}


def required_tuple(*caps_tuple):
    """
    RETURN: tuple[str], the caps in force for a case, in the author's
            words, sorted: every cap carrying a default, and each
            unfielded cap the folded 'caps_tuple' states to confine.

    'caps_tuple' is the 'Caps' records from the outermost to the
    innermost word (application, then choice); None where nothing is
    stated. The innermost statement wins.
    """
    name_list = list(CAPS_FIELD_DB)
    for name, confines_f in _UNFIELDED_DB.items():
        value = None
        for caps in caps_tuple:
            if caps is None: continue
            stated = getattr(caps, name)
            if stated is not None: value = stated
        if confines_f(value): name_list.append(name)
    return tuple(sorted(name_list))


def uncapped_tuple(required, acknowledged=(), board=None):
    """
    RETURN: tuple[str], those of 'required' the procsitter cannot watch
            on this platform and 'acknowledged' does not cover; empty
            where the case may run.

    'board' is the procsitter's capability board; its own where None.
    """
    if board is None: board = capability_db()
    return tuple(name for name in required
                 if not board[CAPS_FIELD_DB.get(name, name)]
                 and name not in acknowledged)


def missing_utility_tuple(uncapped, platform):
    """
    RETURN: tuple[str], the utilities whose absence leaves caps of
            'uncapped' unwatched on 'platform', sorted -- read from the
            procsitter's 'UTILITY_DB'; empty where no utility would
            help (nothing denies the network, on any platform).
    """
    return tuple(sorted({utility for utility in
                         (utility_of(CAPS_FIELD_DB.get(name, name), platform)
                          for name in uncapped)
                         if utility is not None}))


def acknowledgement_of(uncapped, platform):
    """
    RETURN: str, the 'hwut-root.conf' entry that acknowledges the caps
            'uncapped' on 'platform', as it is written there.
    """
    return "procsitter { %s { %s } }" % (
        platform, "  ".join("%s = false" % name for name in uncapped))


def reason_of(uncapped, platform):
    """
    RETURN: str, the one-line refusal for the caps 'uncapped': what is
            not enforceable where, the utility whose absence is the
            cause where one is, and behind ' => ' what lifts it -- the
            install, the 'hwut-root.conf' entry that acknowledges.
    """
    utility_tuple = missing_utility_tuple(uncapped, platform)
    head = "%s %s %s '%s'" % (
        "cap" if len(uncapped) == 1 else "caps",
        ", ".join("'%s'" % name for name in uncapped),
        REASON_OPENER, platform)
    if utility_tuple:
        head += ": %s missing" % ", ".join("'%s'" % u for u in utility_tuple)
    remedy_list = [INSTALL_DB[u] for u in utility_tuple if u in INSTALL_DB]
    remedy_list.append("%s: %s" % (ROOT_CONF_NAME,
                                   acknowledgement_of(uncapped, platform)))
    return "%s => %s" % (head, ", or ".join(remedy_list))


def uncapped_of(app_set, test, choice, board=None, platform=None):
    """
    RETURN: tuple[str], the caps in force for the case that are neither
            watched on 'platform' nor acknowledged for it in the root
            conf, in the author's words; empty where the case may run
            -- or is no case of 'app_set'.
    """
    if platform is None: platform = platform_name()
    app = app_set.app_db.get(test)
    if app is None: return ()
    parameters   = app.choice_db.get(choice)
    acknowledged = (getattr(app_set.directory_spec, "procsitter_db", None)
                    or {}).get(platform, ())
    return uncapped_tuple(
        required_tuple(None if app.root   is None else app.root.caps,
                       None if parameters is None else parameters.caps),
        acknowledged, board)


def admit_of(app_set, board=None, platform=None):
    """
    RETURN: callable, 'admit(test, choice)': None where every cap in
            force for the case is watched or acknowledged, the refusal
            reason else.

    'board' and 'platform' stand in for the procsitter's own answers --
    for a test of this gate; None asks the procsitter.
    """
    if platform is None: platform = platform_name()

    def admit(test, choice):
        uncapped = uncapped_of(app_set, test, choice, board, platform)
        return reason_of(uncapped, platform) if uncapped else None
    return admit


def uncapped_refusal_f(reason):
    """
    RETURN: bool, whether the refusal text 'reason' is one of this
            gate's -- a case not run for want of an enforceable cap.
    """
    return (" %s " % REASON_OPENER) in (reason or "")


def refusal_of(app_set, test, choice):
    """
    RETURN: str, why the case may not be RUN on this platform -- the
                 gate's own reason, as the plan states it;
            None, where it may.

    THE DOOR FOR A FACE THAT RUNS WITHOUT A PLAN (R-80): 'hwut.accept',
    'hwut.accept.interactive', 'hwut.run.diff', 'hwut.run.play',
    'hwut.report.details' provision a candidate themselves, and ask
    here before they do.
    """
    return admit_of(app_set)(test, choice)


def refusal_line_list(name, reason):
    """
    RETURN: list[str], a face's two lines for one refused case 'name':
            'REFUSED: <name> -- <what is not enforceable>', and the
            remedy beneath it.
    """
    head, _, remedy = reason.partition(" => ")
    return ["REFUSED: %s -- %s" % (name, head), "    => %s" % remedy]
