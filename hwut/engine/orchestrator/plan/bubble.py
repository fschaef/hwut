"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: WHICH BUBBLE RUNS WHERE (adm/WORK/spec/42-platforms.txt section 3;
         intend/26 o-50 .. o-58) -- decided before the first event, from
         the confs alone: nothing is run to learn it.

    D      the platforms DEFINED       the OUTERMOST 'hwut-root.conf''s
                                       'platform = [...]', in its order;
                                       each announces 'tools = [...]'
    R(B)   the tools bubble B requires its own 'requires = [...]' -- an
                                       inner root replaces, it inherits
                                       nothing (o-54)
    S      the platforms specified     'Wish.specified_platform_set':
                                       'local' and every '-p' (no '-p'
                                       excludes 'local', o-58)
    C(B)   the candidates              R(B) empty: {local}; else every
                                       platform of D announcing all of
                                       R(B), in D's order
    F(B)   C(B) & S, in D's order      the FIRST is taken (o-58)

    F(B) == {}                     NOT RUN, reason 'available'
    first of F(B) is local         run here, as ever
    first of F(B) not reachable    NOT RUN, reason 'reachable'
    first of F(B) reachable        HANDED -- run there by one far
                                   'hwut.run', its inner bubbles decided
                                   over there (ruling 3; the hand-over:
                                   'run/orchestrate.py')

REFUSED AT THE START (PlatformRefused): a 'platform' in an inner root
(o-53), and -- where 'hwut-tools.rst' stands beside the outermost root
(o-52) -- a tool announced or required that it does not explain.

A bubble NOT RUN hides none of its inner bubbles (ruling 19): each is
decided on its own, with the same S.

OVER THERE, 'local' IS THE PLATFORM HANDED TO (THE RULE): a far run is
told it by 'Wish.as_platform'; a bubble whose tools that platform
announces -- or that the far run cannot check, the definitions out of
its sight -- runs there as 'local'; the switch is not obeyed again.

BELOW A BUBBLE, A DIRECTORY MAY REQUIRE MORE (o-57): 'entry_gate' answers
for each directory of a bubble run here whether the platform it runs on
announces everything the directory requires; one that does not is not
entered, and said.

THE BUBBLES ARE THE WALK'S: the one that governs the top -- the nearest
'hwut-root.conf' at or above it -- and every inner one below, unless the
wish says '--no-bubbles' (E-202). A bubble is named by its path from the
top, '.' for the top's own, '..' and up for one above it.
______________________________________________________________________________
"""
import os
import re
from dataclasses import dataclass

from ..exploration.task_list     import SelectionError
from ..exploration.tree_explorer import (ROOT_CONF_NAME, ascended_spec,
                                         inner_root_tuple,
                                         outermost_root_directory,
                                         root_conf_directory)
from ...                         import platforms
from .wish                       import LOCAL_PLATFORM

RUN     = "run"
NOT_RUN = "not-run"
HANDED  = "handed"

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


class PlatformRefused(SelectionError):
    """The confs refused at the start (intend/26 o-52, o-53): a 'platform'
    in an inner root, or a tool 'hwut-tools.rst' does not explain."""


TOOLS_FILE_NAME = "hwut-tools.rst"


def decision_tuple(top, wish):
    """
    RETURN: tuple of CBubbleDecision, every bubble the walk from 'top'
            meets that is decided HERE -- outermost first, the one
            governing 'top' first. A bubble inside one HANDED to a
            platform is not among them: it is decided over there.

    Raises PlatformRefused where an inner root defines platforms or a
    tool is not explained by 'hwut-tools.rst' (each named);
    RootConfMissing where no root bounds 'top'.
    """
    top       = os.path.abspath(top)
    shown     = _specified_shown(wish)
    specified = wish.specified_platform_set()
    outermost = outermost_root_directory(top)
    defined   = ascended_spec(outermost)[0].platform_tuple or ()
    path_list = [root_conf_directory(top)]
    #  WALK ORDER: sorted component by component, as the walk descends --
    #  an outer bubble before its inner ones, a sibling's after them.
    if not wish.no_bubbles_f:
        path_list.extend(sorted(inner_root_tuple(top),
                                key=lambda path: path.split(os.sep)))

    refusal_list = []
    read_list    = []
    for path in path_list:
        spec = ascended_spec(path)[0]
        name = _name_of(path, top)
        if path != outermost and spec.platform_tuple:
            refusal_list.append(
                "%s/hwut-root.conf: 'platform' stands in the outermost "
                "root alone (%s); here say 'requires = [ <tool> ... ]' "
                "(intend/26 o-53)"
                % (name, os.path.join(outermost, ROOT_CONF_NAME)))
        read_list.append((path, name, spec.requires_tuple or ()))
    refusal_list.extend(_unexplained_tuple(outermost, defined, read_list))
    if refusal_list:
        raise PlatformRefused(("\n" + " " * 9).join(refusal_list))

    decision_list, handed_list = [], []
    for path, name, required in read_list:
        if any(path.startswith(outer + os.sep) for outer in handed_list):
            continue
        decision = _decided(path, name, required, defined, specified,
                            shown, wish.as_platform, outermost)
        if decision.state == HANDED: handed_list.append(path)
        decision_list.append(decision)
    return tuple(decision_list)


def governing_decision(directory, wish):
    """
    RETURN: CBubbleDecision of the ONE bubble that governs 'directory' --
            the nearest 'hwut-root.conf' at or above it -- for 'wish': a
            face that runs one directory ('hwut.play') decides as
            'hwut.run' does, inner bubbles aside.

    Raises PlatformRefused as 'decision_tuple'; RootConfMissing where no
    root bounds it.
    """
    from dataclasses import replace
    return decision_tuple(directory, replace(wish, no_bubbles_f=True))[0]


def entry_refusal(decision_db, top, directory, required):
    """
    RETURN: str, the NOTE that 'directory' is not entered -- 'NOTE
            sub/: requires ghdl; linux does not hold it' -- where the
            platform its bubble runs on does not announce every tool of
            'required' (intend/26 o-57); None, else, and None where no
            bubble decided here governs it.

    'decision_db' maps a bubble's path to its CBubbleDecision; the
    bubble governing 'directory' is the deepest at or above it.
    """
    owner = owner_of(decision_db, directory)
    if owner is None or owner.state != RUN: return None
    missing = tuple(t for t in required if t not in owner.tool_tuple)
    if not missing: return None
    held_by = owner.platform if owner.platform != LOCAL_PLATFORM \
              else LOCAL_PLATFORM
    return "NOTE  %s/: requires %s; %s does not hold it" \
           % (_name_of(directory, top), ", ".join(missing), held_by)


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


def case_refusal(decision, app_set, test, choice):
    """
    RETURN: str, why the case may not run where its bubble runs -- 'requires
            ghdl; local does not hold it' -- its header requiring a tool the
            platform of 'decision' does not announce (intend/26 o-59);
            None, where it may, or where 'decision' is None.
    """
    if decision is None: return None
    missing = tuple(t for t in case_required_tuple(app_set, test, choice)
                    if t not in decision.tool_tuple)
    if not missing: return None
    return "requires %s; %s does not hold it => a platform announcing " \
           "it, '-p <platform>' (intend/26 o-59)" \
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
    RETURN: tuple of str, C(B) of the bubble governing 'directory' --
            the platforms announcing what it requires, definitions'
            order; ('local',) where it requires nothing.
    """
    outermost = outermost_root_directory(directory)
    defined   = ascended_spec(outermost)[0].platform_tuple or ()
    required  = ascended_spec(root_conf_directory(directory))[0] \
                .requires_tuple or ()
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
             outermost):
    """
    RETURN: CBubbleDecision of one bubble: RUN where the platform taken
            is 'local' (or, over there, the platform handed to); NOT_RUN
            'available' where no candidate is specified; else NOT_RUN
            'reachable' or HANDED, as 'platforms.is_available' answers.
    """
    candidates = candidate_tuple(required, defined)
    if as_platform is not None and required \
       and (not defined or as_platform in candidates):
        #  OVER THERE (ruling 3): handed here, it runs here.
        tool_tuple = tools_of(defined, as_platform) or tuple(required)
        return CBubbleDecision(path=path, name=name,
                               platform_tuple=required or None,
                               required_tuple=(LOCAL_PLATFORM,),
                               feasible_tuple=(LOCAL_PLATFORM,),
                               state=RUN, platform=LOCAL_PLATFORM,
                               tool_tuple=tool_tuple)
    here = as_platform or LOCAL_PLATFORM          # what 'local' is
    feasible = tuple(c for c in candidates if c in specified)
    common = dict(path=path, name=name, platform_tuple=required or None,
                  required_tuple=candidates, feasible_tuple=feasible)
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
