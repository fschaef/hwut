"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: WHICH DIRECTORY RUNS WHERE (intend/45 R-1 .. R-7, 2026-11-15;
         intend/26 o-50 .. o-59; spec/42 section 3) -- decided before the
         first event, from the confs alone: nothing is run to learn it.

    D      the platforms DEFINED       the ROOT's 'hwut-root.conf' -- the
                                       one root of the project (R-1) --
                                       'platform = [...]', in its order;
                                       each announces 'tools = [...]'
    R(d)   the tools directory d       'requires' inherited down the
           requires                    hwut.conf files and its own, ADDED
                                       (o-57); said once for a subtree in
                                       a non-TEST hwut.conf (R-4)
    S      the platforms specified     'Wish.specified_platform_set'
    C(d)   the candidates              R(d) empty: {local}; else every
                                       platform of D announcing all of
                                       R(d), in D's order
    F(d)   C(d) & S, in D's order      the FIRST is taken (o-58)

    F(d) == {}                     NOT RUN, reason 'available'
    first of F(d) is local         run here
    first of F(d) not reachable    NOT RUN, reason 'reachable'
    first of F(d) reachable        HANDED -- every directory handed to one
                                   platform goes in ONE far 'hwut.run'
                                   ('run/orchestrate.py'): the root, the
                                   wish, '--as-platform' and the near
                                   run's platform words

OVER THERE ('Wish.as_platform'), every directory is decided alike, and runs
where it was decided for the platform handed to; the others are ELSEWHERE,
passed by in silence.

THE DECLARATION IS THE CONTRACT (R-5, R-7, amending E-226): a tool a
platform declares whose 'probe:' line in 'hwut-tools.rst' finds a program
missing -- on 'local' near, on the platform handed to over there -- stays
announced; the cases of a directory requiring it FAIL, not run,
'tool-not-provided' ('tool_absent_reason'). A tool without a 'probe:' line
is taken as declared (o-50) -- a tool is an informal name, not a program.

REFUSED AT THE START (PlatformRefused): a 'platform' in any hwut.conf
below the root (o-53), and -- where 'hwut-tools.rst' stands beside the
root (o-52) -- a tool announced or required anywhere that it does not
explain.

A 'hwut-root.conf' BELOW THE ROOT is another project, never walked from
above (R-3). A directory is named by its path from the top, '.' for the
top itself.
______________________________________________________________________________
"""
import os
import re
import shutil
from dataclasses import dataclass

from ..exploration.task_list     import SelectionError
from ..exploration.tree_explorer import (ROOT_CONF_NAME, ascended_spec,
                                         root_conf_directory)
from ...                         import platforms
from .wish                       import LOCAL_PLATFORM

RUN       = "run"
NOT_RUN   = "not-run"
HANDED    = "handed"
#  OVER THERE, A DIRECTORY DECIDED FOR ANOTHER PLATFORM (intend/45 R-4): the
#  far run passes it by in silence -- the platform it was decided for runs it.
ELSEWHERE = "elsewhere"

@dataclass(frozen=True, slots=True)
class CBubbleDecision:
    """What one bubble comes to under one command (spec/42 section 3)."""
    path:           str          # absolute: the directory of its root conf
    name:           str          # from the top, '/'-separated
    platform_tuple: tuple        # its 'requires' as read; None: none
    required_tuple: tuple        # C(B), the candidates, D's order
    feasible_tuple: tuple        # F(B), D's order
    state:          str          # RUN, NOT_RUN, HANDED
    platform:       str = ""     # the platform taken; '' where none
    spec:           dict = None  # that platform's entry, 'recipe' absolute
    reason:         str = ""     # 'available', 'reachable' (NOT_RUN)
    text:           str = ""     # the NOTE's text (NOT_RUN)
    tool_tuple:     tuple = ()   # what the platform taken announces
    absent_tuple:   tuple = ()   # of (tool, programs): 'local' declares
                                 # it, its probe finds not (E-226)
    directory_tuple: tuple = ()  # HANDED, grouped: the test directories
                                 # the far run takes, from the root


class PlatformRefused(SelectionError):
    """The confs refused at the start (intend/26 o-52, o-53): a 'platform'
    in an inner root, or a tool 'hwut-tools.rst' does not explain."""


TOOLS_FILE_NAME = "hwut-tools.rst"


def decision_tuple(top, wish):
    """
    RETURN: tuple of CBubbleDecision, one: the ROOT's own -- the nearest
            'hwut-root.conf' at or above 'top', the project (intend/45
            R-1, R-2). Every directory below it is decided by the walk
            ('decider', R-4).

    Raises PlatformRefused where a hwut.conf below the root says
    'platform' (o-53) or a tool announced or required anywhere in the
    project is not explained by 'hwut-tools.rst' (o-52), each named;
    RootConfMissing where no root bounds 'top'.
    """
    top       = os.path.abspath(top)
    shown     = _specified_shown(wish)
    specified = wish.specified_platform_set()
    #  THE NEAREST ROOT IS THE PROJECT (intend/45 R-1, R-2): the climb
    #  stops at it; a root above it is beyond the radar, one below it a
    #  project of its own, never walked from here (R-3).
    outermost = root_conf_directory(top)
    declared  = ascended_spec(outermost)[0].platform_tuple or ()
    defined, absent = probed(declared, outermost,
                             wish.as_platform or LOCAL_PLATFORM)

    refusal_list = []
    read_list    = [(outermost, _name_of(outermost, top),
                     ascended_spec(outermost)[0].requires_tuple or ())]
    #  EVERY hwut.conf OF THE PROJECT IS ASKED (intend/45 R-1): 'platform'
    #  stands in the root alone (o-53); every tool required is explained
    #  (o-52) -- below the root, wherever it is said.
    for path, conf_spec in _conf_spec_tuple(outermost):
        name = _name_of(path, top)
        if conf_spec.platform_tuple:
            refusal_list.append(
                "%s/hwut.conf: 'platform' stands in the root alone (%s); "
                "here say 'requires = [ <tool> ... ]' (intend/26 o-53)"
                % (name, os.path.join(outermost, ROOT_CONF_NAME)))
        if conf_spec.requires_tuple:
            read_list.append((path, name, conf_spec.requires_tuple))
    refusal_list.extend(_unexplained_tuple(outermost, declared, read_list))
    if refusal_list:
        raise PlatformRefused(("\n" + " " * 9).join(refusal_list))

    #  THE ROOT'S OWN DECISION; every directory below is decided by the
    #  walk ('decider', intend/45 R-4).
    path, name, required = read_list[0]
    return (_decided(path, name, required, defined, specified, shown,
                     wish.as_platform, outermost, absent),)


def _conf_spec_tuple(outermost):
    """
    RETURN: tuple of (str, DirectorySpec): every directory below the root
            'outermost' -- a project of its own (a 'hwut-root.conf')
            excluded, and what no walk enters -- whose 'hwut.conf' reads,
            with what it says; walk order.
    """
    from ..exploration import finder, reader
    from ....auxiliary.no_entry import entered
    found = []
    for here, name_list, _ in os.walk(outermost):
        name_list[:] = entered(here, name_list, boundary_f=True)
        if here == outermost: continue
        text = finder.conf_text(here)
        if text is None: continue
        spec, _app_db, _fault_list = reader.read_conf(text, finder.CONF_NAME)
        if spec is not None: found.append((here, spec))
    return tuple(found)


def decider(top, wish):
    """
    RETURN: function 'decide(directory, required)', the CBubbleDecision of
            the ABSOLUTE 'directory' requiring the tools 'required' (what
            it inherits and states, o-57) under 'wish' (intend/45 R-4):
            RUN where the first defined platform announcing all of it,
            among those specified, is 'local' -- over there: is the
            platform handed to; HANDED or NOT_RUN 'reachable' where it is
            another; NOT_RUN 'available' where none is; over there
            ELSEWHERE where it is another than the one handed to.

    Raises RootConfMissing where no root bounds 'top'.
    """
    top       = os.path.abspath(top)
    outermost = root_conf_directory(top)
    defined, absent = probed(ascended_spec(outermost)[0].platform_tuple
                             or (), outermost,
                             wish.as_platform or LOCAL_PLATFORM)
    specified = wish.specified_platform_set()
    shown     = _specified_shown(wish)

    def decide(directory, required):
        """RETURN: CBubbleDecision of 'directory' requiring 'required'."""
        return _decided(directory, _name_of(directory, top),
                        tuple(dict.fromkeys(required or ())), defined,
                        specified, shown, wish.as_platform, outermost,
                        absent)
    return decide


def governing_decision(directory, wish):
    """
    RETURN: CBubbleDecision of 'directory' for 'wish' (intend/45 R-4): what
            it requires -- inherited down the hwut.conf files and its own
            -- decided as 'hwut.run' decides it: a face that runs one
            directory ('hwut.play') runs it where the run would.

    Raises PlatformRefused as 'decision_tuple'; RootConfMissing where no
    root bounds it.
    """
    from ..exploration.tree_explorer import own_requires
    decision_tuple(directory, wish)          # the refusals, said first
    required = tuple(ascended_spec(directory)[0].requires_tuple or ()) \
               + own_requires(directory)
    return decider(root_conf_directory(directory), wish)(
               os.path.abspath(directory), required)


def case_required_tuple(app_set, test, choice):
    """
    RETURN: tuple of str, the tools the case 'test' 'choice' of 'app_set'
            requires in its own header -- the application's 'requires',
            then its choice's (intend/26 o-59); empty where it says none,
            or is no case of 'app_set'.
    """
    app = app_set.app_db.get(test)
    if app is None: return ()
    parameters = app.choice_db.get(choice)
    return tuple(dict.fromkeys(
               tuple(getattr(app.root, "requires", None) or ())
               + tuple(getattr(parameters, "requires", None) or ())))


#  THE OPENER OF A REFUSAL THAT FAILS (intend/45 R-5): 'orchestrate' counts
#  such a case as a FAIL, 'tool-not-provided', not as a refusal.
TOOL_ABSENT_OPENER = "does not provide tool"


def tool_absent_refusal_f(reason):
    """RETURN: bool, the refusal 'reason' is a platform's breach of what it
    declares (R-5) -- the case fails, not run."""
    return (" %s " % TOOL_ABSENT_OPENER) in (reason or "")


def tool_absent_reason(decision, required):
    """
    RETURN: str, 'platform local does not provide tool iverilog (not on
            PATH: iverilog, vvp; hwut-tools.rst probe)' where the platform
            of 'decision' declares a tool of 'required' its probe finds
            missing (intend/45 R-5, R-7); None, else.
    """
    pair_list = [(tool, lacking) for tool, lacking in decision.absent_tuple
                 if tool in required]
    if not pair_list: return None
    program_list = list(dict.fromkeys(p for _, lacking in pair_list
                                      for p in lacking))
    return "platform %s does not provide tool %s (not on PATH: %s; %s probe)" \
           % (decision.platform or LOCAL_PLATFORM,
              ", ".join(t for t, _ in pair_list), ", ".join(program_list),
              TOOLS_FILE_NAME)


def case_refusal(decision, app_set, test, choice):
    """
    RETURN: str, why the case may not run where its bubble runs -- 'requires
            ghdl; local does not hold it' -- its header requiring a tool the
            platform of 'decision' does not announce (intend/26 o-59);
            None, where it may, or where 'decision' is None.
    """
    if decision is None: return None
    required = tuple(decision.platform_tuple or ()) \
               + case_required_tuple(app_set, test, choice)
    absent = tool_absent_reason(decision, required)
    if absent is not None: return absent
    missing = tuple(t for t in case_required_tuple(app_set, test, choice)
                    if t not in decision.tool_tuple)
    if not missing: return None
    return "requires %s; %s does not hold it => a platform " \
           "announcing it, '-p <platform>' (intend/26 o-59)" \
           % (", ".join(missing), decision.platform or LOCAL_PLATFORM)


def owner_of(decision_db, directory):
    """
    RETURN: CBubbleDecision of the deepest bubble of 'decision_db' at or
            above the absolute 'directory'; None where none is.
    """
    owner = None
    for path, decision in decision_db.items():
        if directory == path or directory.startswith(path + os.sep):
            if owner is None or len(path) > len(owner.path):
                owner = decision
    return owner


def candidates_of(directory):
    """
    RETURN: tuple of str, C of 'directory' (intend/45 R-4) -- the
            platforms announcing all it requires, inherited down the
            hwut.conf files and its own, definitions' order; ('local',)
            where it requires nothing.
    """
    from ..exploration.tree_explorer import own_requires
    outermost = root_conf_directory(directory)
    defined   = ascended_spec(outermost)[0].platform_tuple or ()
    required  = tuple(dict.fromkeys(
                    tuple(ascended_spec(directory)[0].requires_tuple or ())
                    + own_requires(directory)))
    return candidate_tuple(required, defined)


def tools_of(defined, platform):
    """
    RETURN: tuple of str, the tools platform 'platform' announces among
            the definitions 'defined' -- empty where it is not defined.
    """
    for name, spec in defined:
        if name == platform: return tuple(spec.get("tools", ()))
    return ()


def candidate_tuple(required, defined):
    """
    RETURN: tuple of str, C(B): ('local',) where 'required' is empty --
            a subtree requiring nothing runs here; else every platform of
            'defined' announcing every tool of 'required', in the
            definitions' order (intend/26 o-51, o-58).
    """
    if not required: return (LOCAL_PLATFORM,)
    return tuple(name for name, spec in defined
                 if set(required) <= set(spec.get("tools", ())))


def _decided(path, name, required, defined, specified, shown, as_platform,
             outermost, absent=()):
    """
    RETURN: CBubbleDecision of one bubble: RUN where the platform taken
            is 'local' (or, over there, the platform handed to); NOT_RUN
            'available' where no candidate is specified; else NOT_RUN
            'reachable' or HANDED, as 'platforms.is_available' answers.
    """
    candidates = candidate_tuple(required, defined)
    feasible   = tuple(c for c in candidates if c in specified)
    if as_platform is not None:
        #  OVER THERE (intend/45 R-4): every directory is decided as the
        #  near run decided it -- the same definitions, the same words --
        #  and runs here where it was decided FOR THIS PLATFORM; the far
        #  run passes the others by. Definitions out of sight: what was
        #  handed runs.
        if (feasible and feasible[0] == as_platform) \
           or (not defined and required):
            tool_tuple = tools_of(defined, as_platform) or tuple(required)
            return CBubbleDecision(path=path, name=name,
                                   platform_tuple=required or None,
                                   required_tuple=(LOCAL_PLATFORM,),
                                   feasible_tuple=(LOCAL_PLATFORM,),
                                   state=RUN, platform=as_platform,
                                   tool_tuple=tool_tuple,
                                   absent_tuple=absent)
        return CBubbleDecision(path=path, name=name,
                               platform_tuple=required or None,
                               required_tuple=candidates,
                               feasible_tuple=feasible, state=ELSEWHERE)
    here = LOCAL_PLATFORM
    common = dict(path=path, name=name, platform_tuple=required or None,
                  required_tuple=candidates, feasible_tuple=feasible,
                  absent_tuple=absent)
    if not feasible:
        if not required:
            text = "%s/: requires no tool -- runs on local; specified %s" \
                   % (name, shown)
        elif not candidates:
            text = "%s/: requires %s; no platform holds it" \
                   % (name, ", ".join(required))
        else:
            text = "%s/: requires %s, held by %s; specified %s" \
                   % (name, ", ".join(required), ", ".join(candidates),
                      shown)
        return CBubbleDecision(state=NOT_RUN, reason="available",
                               text=text, **common)
    platform   = feasible[0]
    tool_tuple = tools_of(defined, here if platform == LOCAL_PLATFORM
                                   else platform)
    if platform == LOCAL_PLATFORM:
        return CBubbleDecision(state=RUN, platform=platform,
                               tool_tuple=tool_tuple, **common)
    spec = _resolved(dict(defined)[platform], outermost)
    available_f, why = platforms.is_available(platform, spec)
    if not available_f:
        return CBubbleDecision(state=NOT_RUN, platform=platform, spec=spec,
                               reason="reachable",
                               text="%s/: platform '%s' not reachable: %s"
                                    % (name, platform, why),
                               tool_tuple=tool_tuple, **common)
    return CBubbleDecision(state=HANDED, platform=platform, spec=spec,
                           tool_tuple=tool_tuple, **common)


def _resolved(spec, path):
    """
    RETURN: dict, 'spec' without hwut's own 'tools' and with a relative
            'recipe' made absolute against the directory 'path' of the
            outermost root, where it is defined -- a path the platform
            opens from anywhere (engine/platforms RATIONALE PL-1).
    """
    spec   = {k: v for k, v in spec.items() if k != "tools"}
    recipe = spec.get("recipe")
    if not recipe or os.path.isabs(recipe): return spec
    return dict(spec, recipe=os.path.normpath(os.path.join(path, recipe)))


def explained_tool_set(outermost):
    """
    RETURN: frozenset of str, the tools 'hwut-tools.rst' beside the
            outermost root explains -- one '[[tool]]' each (intend/26
            o-52). None where the file does not stand: nothing is bound.
    """
    path = os.path.join(outermost, TOOLS_FILE_NAME)
    if not os.path.isfile(path): return None
    with open(path, encoding="utf-8") as fh:
        return frozenset(_TOOL_MARK_RE.findall(fh.read()))


_TOOL_MARK_RE = re.compile(r"\[\[([^\[\]\s]+)\]\]")
_PROBE_RE     = re.compile(r"^\s+probe:[ \t]*(.*?)\s*$")


def probe_db(outermost):
    """
    RETURN: dict, tool -> tuple of str: the programs a 'probe:' line under
            its '[[tool]]' in 'hwut-tools.rst' beside the outermost root
            names ('probe: iverilog vvp'); empty where the file does not
            stand or names none (E-226).
    """
    path = os.path.join(outermost, TOOLS_FILE_NAME)
    if not os.path.isfile(path): return {}
    db, tool = {}, None
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            mark = _TOOL_MARK_RE.match(line)
            if mark is not None:
                tool = mark.group(1); continue
            probe = _PROBE_RE.match(line)
            if probe is not None and tool is not None:
                db[tool] = tuple(probe.group(1).split())
    return db


def probed(defined, outermost, here=LOCAL_PLATFORM):
    """
    RETURN: (defined, absent): 'defined' AS DECLARED -- the declaration is
            the contract (intend/45 R-5): the same on both sides of a
            hand-over, so both decide alike -- and 'absent', a tuple of
            (tool, programs not on PATH), one pair per tool platform
            'here' declares whose 'probe:' line in 'hwut-tools.rst' finds
            a program missing ON THIS MACHINE. 'here' is 'local' near,
            the platform handed to over there (R-7). A tool without a
            'probe:' line is taken as declared (o-50).
    """
    db = probe_db(outermost) if defined else {}
    if not db: return defined, ()
    absent = []
    for tool in tools_of(defined, here):
        lacking = tuple(p for p in db.get(tool, ())
                        if shutil.which(p) is None)
        if lacking: absent.append((tool, lacking))
    return defined, tuple(absent)


def _unexplained_tuple(outermost, defined, read_list):
    """
    RETURN: tuple of str, one refusal line per tool announced in 'defined'
            or required by a bubble of 'read_list' that 'hwut-tools.rst'
            does not explain; empty where the file does not stand or
            explains them all (o-52: optional, but binding).
    """
    explained = explained_tool_set(outermost)
    if explained is None: return ()
    line_list = []
    for name, spec in defined:
        for tool in spec.get("tools", ()):
            if tool not in explained:
                line_list.append("platform '%s' announces '%s'; %s does "
                                 "not explain it -- add '[[%s]]'"
                                 % (name, tool, TOOLS_FILE_NAME, tool))
    for _path, name, required in read_list:
        for tool in required:
            if tool not in explained:
                line_list.append("%s/ requires '%s'; %s does not explain "
                                 "it -- add '[[%s]]'"
                                 % (name, tool, TOOLS_FILE_NAME, tool))
    return tuple(line_list)


def _specified_shown(wish):
    """
    RETURN: str, S as the NOTE says it: 'local' first where it is
            specified, then the '-p' names in their order.
    """
    name_list = [] if wish.exclude_local_f else [LOCAL_PLATFORM]
    name_list += [n for n in wish.platform_tuple if n not in name_list]
    return ", ".join(name_list)


def _name_of(path, top):
    """
    RETURN: str, the bubble at 'path' named from 'top', '/'-separated:
            '.' for 'top' itself, '..' and up for a bubble above it.
    """
    return os.path.relpath(path, top).replace(os.sep, "/")
