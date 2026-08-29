"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE TREE PLAN -- one CTestPlan per test directory, in walk
         order (P-17). Directories run SERIALLY, each under its own
         frame ('on_entry'/'on_exit', P-10) and its own Bookkeeper;
         the tree level adds ORDER over directories and nothing else.

An entry names its directory RELATIVE to the root; the root itself
stands on the CTreePlan, so no entry carries a machine-chosen path.
______________________________________________________________________________
"""

from dataclasses import dataclass

from ..exploration.task_list_query import CTestTaskListQuery
from .determine import determine
from .label     import swallowed_warning_tuple
from .printer   import print_plan


@dataclass(frozen=True, slots=True)
class CTreePlanEntry:
    """One test directory's share of the tree plan: the plan itself,
    the frame the scheduler puts around it, the reports determination
    made, and the faults exploration met there."""
    directory:    str            # relative to the tree plan's root
    plan:         object         # CTestPlan
    app_set:      object         # the CTestAppSet it was determined from
    on_entry:     str | None
    on_exit:      str | None
    report_tuple: tuple
    fault_tuple:  tuple


@dataclass(frozen=True, slots=True)
class CTreePlan:
    """The plans of a tree, in walk order."""
    root:          str
    entry_tuple:   tuple
    fault_tuple:   tuple         # the WALK's own faults
    warning_tuple: tuple = ()    # findings that decide nothing

    def __iter__(self):
        """YIELD: [0] CTreePlanEntry  one directory's entry, walk
                                      order."""
        yield from self.entry_tuple


def determine_tree(tree_exploration, wish, bookkeeper_factory=None,
                   label_view=None,
                   build_interview=None):
    """
    RETURN: CTreePlan, one plan per test directory of
            'tree_exploration', each determined for 'wish'.

    'bookkeeper_factory' takes a directory path and answers ITS
    Bookkeeper -- made above, handed down. Required where the wish
    asks the base ('--fail', '--pass', '--since=', '--until=').

    Raises AssertionError where the wish asks the base and no factory
    was handed down -- refused at the door, not answered by guessing.
    """
    assert bookkeeper_factory is not None or not wish.asks_base_f(), \
           "the wish asks the base (%s) and no Bookkeeper factory " \
           "was handed down" % wish

    entry_list  = []
    met_set     = set()
    visible_set = set()
    for directory, result in tree_exploration:
        bookkeeper = None
        if wish.asks_base_f():
            bookkeeper = bookkeeper_factory(directory)
        #  THE WALK'S 'directory' IS ALREADY RELATIVE to the root,
        #  which is exactly what a path-bearing glob is matched
        #  against ('messaging/*/test-queue.py').
        task_list          = CTestTaskListQuery(
                                 wish, bookkeeper,
                                 directory=directory,
                                 root=tree_exploration.root,
                                 label_view=label_view)
        plan, report_list  = determine(result.app_set, task_list)
        if label_view is not None and wish.glob_tuple:
            met, visible = task_list.glob_reach(result.app_set)
            met_set.update(met)
            visible_set.update(visible)
        spec               = result.app_set.directory_spec
        entry_list.append(CTreePlanEntry(
            directory    = directory,
            plan         = plan,
            app_set      = result.app_set,
            on_entry     = spec.on_entry,
            on_exit      = spec.on_exit,
            report_tuple = tuple(report_list),
            fault_tuple  = tuple(result.fault_list)))
    return CTreePlan(
        root          = tree_exploration.root,
        entry_tuple   = tuple(entry_list),
        fault_tuple   = tuple(tree_exploration.fault_tuple),
        warning_tuple = swallowed_warning_tuple(met_set, visible_set))


def print_tree_plan(tree_plan, write=None):
    """
    RETURN: None. Writes the canonical text of every entry: the
            directory's name as a heading, its faults and reports,
            then its plan -- one blank line between entries.
    """
    if write is None: write = print
    for fault in tree_plan.fault_tuple:
        write(str(fault))
    first_f = True
    for entry in tree_plan:
        if not first_f: write("")
        first_f = False
        write("[ %s ]" % entry.directory)
        for fault in entry.fault_tuple:
            write(str(fault))
        for report in entry.report_tuple:
            write("REPORT: %s" % report)
        print_plan(entry.plan, write)
