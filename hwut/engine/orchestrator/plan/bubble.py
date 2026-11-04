"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: WHICH BUBBLE RUNS WHERE (adm/WORK/spec/42-platforms.txt section 3;
         intend/42 rulings 10, 12, 19, 21) -- decided before the first
         event, from the confs alone: nothing is run to learn it.

    S      the platforms the command specifies   'Wish.specified_platform_set'
    Q(B)   the platforms bubble B requires       its 'platform = [...]';
                                                 {local} where it says none
    F(B)   S & Q(B)

    |F(B)| > 1 for any bubble      REFUSED, every such bubble named
    F(B) == {}                     NOT RUN, reason 'available'
    F(B) == {local}                run here, as ever
    F(B) == {f}, f not reachable   NOT RUN, reason 'reachable'
    F(B) == {f}, reachable         HANDED to f -- run there by one far
                                   'hwut.run', its inner bubbles decided
                                   over there (ruling 3; the hand-over:
                                   'run/orchestrate.py')

A bubble NOT RUN hides none of its inner bubbles (ruling 19): each is
decided on its own, with the same S.

OVER THERE, 'local' IS THE PLATFORM HANDED TO (THE RULE): a far run is
told it by 'Wish.as_platform', and a bubble requiring that platform
requires 'local' -- the switch is not obeyed again (ruling 3).

THE BUBBLES ARE THE WALK'S: the one that governs the top -- the nearest
'hwut-root.conf' at or above it -- and every inner one below, unless the
wish says '--no-bubbles' (E-202). A bubble is named by its path from the
top, '.' for the top's own, '..' and up for one above it.
______________________________________________________________________________
"""
import os
from dataclasses import dataclass

from ..exploration.task_list     import SelectionError
from ..exploration.tree_explorer import (ascended_spec, inner_root_tuple,
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
    platform_tuple: tuple        # its 'platform' list as read; None: none
    required_tuple: tuple        # Q(B), the list's order
    feasible_tuple: tuple        # F(B), the list's order
    state:          str          # RUN, NOT_RUN, HANDED
    platform:       str = ""     # the one platform of F(B); '' where none
    spec:           dict = None  # that platform's entry, 'recipe' absolute
    reason:         str = ""     # 'available', 'reachable' (NOT_RUN)
    text:           str = ""     # the NOTE's text (NOT_RUN)


class PlatformRefused(SelectionError):
    """A command that specifies more than one platform a bubble requires
    (spec/42 section 3): refused at the start, every such bubble named."""


def decision_tuple(top, wish):
    """
    RETURN: tuple of CBubbleDecision, every bubble the walk from 'top'
            meets that is decided HERE -- outermost first, the one
            governing 'top' first -- if no bubble meets more than one
            specified platform. A bubble inside one HANDED to a platform
            is not among them: it is decided over there (ruling 3).

    Raises PlatformRefused, naming every bubble where |F(B)| > 1 with its
    remedy; RootConfMissing where no root bounds 'top'.
    """
    top   = os.path.abspath(top)
    shown = _specified_shown(wish)
    specified_set = wish.specified_platform_set()
    path_list = [root_conf_directory(top)]
    #  WALK ORDER: sorted component by component, as the walk descends --
    #  an outer bubble before its inner ones, a sibling's after them.
    if not wish.no_bubbles_f:
        path_list.extend(sorted(inner_root_tuple(top),
                                key=lambda path: path.split(os.sep)))

    read_list, refusal_list = [], []
    for path in path_list:
        platform_tuple = ascended_spec(path)[0].platform_tuple
        required = tuple(name for name, _ in platform_tuple) \
                   if platform_tuple else (LOCAL_PLATFORM,)
        if wish.as_platform is not None:
            required = tuple(dict.fromkeys(
                           LOCAL_PLATFORM if name == wish.as_platform
                           else name for name in required))
        feasible = tuple(name for name in required if name in specified_set)
        name     = _name_of(path, top)
        if len(feasible) > 1:
            refusal_list.append(_refusal_text(name, required, shown, feasible))
        read_list.append((path, name, platform_tuple, required, feasible))
    if refusal_list:
        raise PlatformRefused(("\n" + " " * 9).join(refusal_list))

    decision_list, handed_list = [], []
    for path, name, platform_tuple, required, feasible in read_list:
        if any(path.startswith(outer + os.sep) for outer in handed_list):
            continue
        decision = _decided(path, name, platform_tuple, required, feasible,
                            shown)
        if decision.state == HANDED: handed_list.append(path)
        decision_list.append(decision)
    return tuple(decision_list)


def governing_decision(directory, wish):
    """
    RETURN: CBubbleDecision of the ONE bubble that governs 'directory' --
            the nearest 'hwut-root.conf' at or above it -- for 'wish': a
            face that runs one directory ('hwut.play') decides as
            'hwut.run' does, inner bubbles aside.

    Raises PlatformRefused where that bubble meets more than one
    specified platform; RootConfMissing where no root bounds it.
    """
    from dataclasses import replace
    return decision_tuple(directory, replace(wish, no_bubbles_f=True))[0]


def _decided(path, name, platform_tuple, required, feasible, shown):
    """
    RETURN: CBubbleDecision of one bubble, F(B) having at most one
            member: NOT_RUN 'available' where F(B) is empty; RUN where it
            is {local}; else NOT_RUN 'reachable' or HANDED, as
            'platforms.is_available' answers for its one platform.
    """
    common = dict(path=path, name=name, platform_tuple=platform_tuple,
                  required_tuple=required, feasible_tuple=feasible)
    if not feasible:
        return CBubbleDecision(state=NOT_RUN, reason="available",
                               text="%s/: requires %s; specified %s"
                                    % (name, ", ".join(required), shown),
                               **common)
    platform = feasible[0]
    if platform == LOCAL_PLATFORM:
        return CBubbleDecision(state=RUN, platform=platform, **common)
    spec = _resolved(dict(platform_tuple)[platform], path)
    available_f, why = platforms.is_available(platform, spec)
    if not available_f:
        return CBubbleDecision(state=NOT_RUN, platform=platform, spec=spec,
                               reason="reachable",
                               text="%s/: platform '%s' not reachable: %s"
                                    % (name, platform, why),
                               **common)
    return CBubbleDecision(state=HANDED, platform=platform, spec=spec,
                           **common)


def _resolved(spec, path):
    """
    RETURN: dict, 'spec' with a relative 'recipe' made absolute against
            the bubble's directory 'path' -- a path the platform opens
            from anywhere (engine/platforms RATIONALE PL-1).
    """
    recipe = spec.get("recipe")
    if not recipe or os.path.isabs(recipe): return dict(spec)
    return dict(spec, recipe=os.path.normpath(os.path.join(path, recipe)))


def _refusal_text(name, required, shown, feasible):
    """
    RETURN: str, two lines naming bubble 'name', what it requires, what
            is specified -- and the remedy: one platform of F(B).
    """
    other_tuple = tuple(f for f in feasible if f != LOCAL_PLATFORM)
    if LOCAL_PLATFORM in feasible:
        remedy = "narrow with '--exclude-local -p %s', or run without '-p'" \
                 % other_tuple[0]
    else:
        remedy = "narrow to one: %s" % " or ".join("'-p %s'" % f
                                                    for f in feasible)
    return "%s/: requires %s; specified %s\n         => %s" \
           % (name, ", ".join(required), shown, remedy)


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
