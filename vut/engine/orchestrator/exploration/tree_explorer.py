"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE TREE WALK -- the stage before 'explore()'. It walks down
         from a root, finds the TEST DIRECTORIES, and folds 'hwut.conf'
         down the tree as a CONFIGURATION TREE (R-69): a parent's
         values flow down, the child's own word wins -- the R-26 law
         lifted one level.

A TEST DIRECTORY is one whose NAME equals the effective
'test_directory' key -- 'TEST' where nobody states it. The name that
applies to a directory is decided by its parent chain: a directory
cannot rename itself.

WHAT FLOWS DOWN -- the keys that configure tests in general:

    default_app       merged parameter by parameter, child's word wins
    language_setup    per language, the child's word wins whole
    ignore            the child's word wins whole
    test_directory    the child's word wins

WHAT DOES NOT: 'on_entry', 'on_exit', 'collision', 'dependency' name
LOCAL files and actions; stated at a tree level -- a directory that is
not a test directory -- they draw a fault and flow nowhere.

The walk descends in sorted order, skips names beginning '.', and does
not descend INTO a test directory: what stands below one is that
directory's own.
______________________________________________________________________________
"""
import os
from dataclasses import dataclass, replace

from .          import finder
from .          import reader
from .explorer  import explore
from .fault     import Fault, E_FaultKind
from .specification import DirectorySpec


FALLBACK_TEST_DIRECTORY = "TEST"

#  The keys that flow down the tree; everything else is local.
INHERITABLE_FIELD_TUPLE = ("default_app", "language_setup", "ignore",
                           "test_directory")
LOCAL_FIELD_TUPLE       = ("on_entry", "on_exit", "collision",
                           "dependency")


@dataclass(frozen=True, slots=True)
class CTreeExploration:
    """What one TREE yields: the test directories in walk order, each
    with its ExplorationResult, and the faults of the walk itself.
    A directory is named RELATIVE to the root, '/'-separated."""
    root:         str
    result_tuple: tuple      # of (directory, ExplorationResult)
    fault_tuple:  tuple

    def __iter__(self):
        """YIELD: [0] str                one directory, walk order.
                  [1] ExplorationResult  what it offers."""
        yield from self.result_tuple


def explore_tree(root, interview_runner=None):
    """
    RETURN: CTreeExploration -- every test directory below 'root',
            explored under the configuration tree, in walk order.

    A tree-level 'hwut.conf' that cannot be read, or that states a
    LOCAL key, contributes a fault; its inheritable keys still flow
    where they were read.
    """
    fault_list  = []
    result_list = []
    _walk(root, ".", DirectorySpec(language_setup={}, dependency={}),
          interview_runner, result_list, fault_list)
    return CTreeExploration(root         = root,
                            result_tuple = tuple(result_list),
                            fault_tuple  = tuple(fault_list))


def inherited_spec(parent, child):
    """
    RETURN: DirectorySpec, the spec that GOVERNS where 'child' stands:
            the inheritable fields of 'parent', each overwritten where
            'child' states its own word; 'default_app' merged parameter
            by parameter (R-26); the local fields are the child's
            alone.
    """
    field_db = {}
    for name in INHERITABLE_FIELD_TUPLE:
        mine, theirs = getattr(parent, name), getattr(child, name)
        if name == "default_app" and mine is not None \
           and theirs is not None:
            field_db[name] = mine.merged_with(theirs)
        else:
            field_db[name] = theirs if theirs else mine
    return replace(child, **field_db)


def _walk(root, relative, effective, interview_runner,
          result_list, fault_list):
    """
    RETURN: None. One directory of the walk: fold its 'hwut.conf' onto
            'effective', recurse into its sub-directories in sorted
            order, and explore those whose name is the effective test
            directory name.
    """
    directory = os.path.normpath(os.path.join(root, relative))
    effective = _folded(directory, relative, effective, fault_list)
    marker    = effective.test_directory or FALLBACK_TEST_DIRECTORY

    for name in sorted(os.listdir(directory)):
        if name.startswith("."):                          continue
        path = os.path.join(directory, name)
        if not os.path.isdir(path):                       continue
        child_relative = _joined(relative, name)
        if name == marker:
            result = explore(path, interview_runner=interview_runner,
                             inherited=effective)
            result_list.append((child_relative, result))
        else:
            _walk(root, child_relative, effective, interview_runner,
                  result_list, fault_list)


def _folded(directory, relative, effective, fault_list):
    """
    RETURN: DirectorySpec, 'effective' with this tree level's own
            'hwut.conf' folded in -- 'effective' untouched where the
            level carries none.

    A LOCAL key stated here draws a fault: this directory is not a
    test directory, and 'on_entry', 'on_exit', 'collision' and
    'dependency' name local matters.
    """
    text = finder.conf_text(directory)
    if text is None: return effective

    conf_name = _joined(relative, finder.CONF_NAME)
    spec, _app_db, conf_fault_list = reader.read_conf(text, conf_name)
    fault_list.extend(conf_fault_list)
    if spec is None: return effective

    for name in LOCAL_FIELD_TUPLE:
        if getattr(spec, name):
            fault_list.append(Fault(
                E_FaultKind.VOCABULARY, conf_name, spec.position,
                "'%s' at a tree level: it names local matters and "
                "belongs in a test directory's own 'hwut.conf'"
                % name))
    return inherited_spec(effective, spec)


def _joined(relative, name):
    """
    RETURN: str, the '/'-joined relative path; 'name' alone where
            'relative' is '.'.
    """
    if relative == ".": return name
    return "%s/%s" % (relative, name)
