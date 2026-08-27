"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE TREE WALK -- the stage before 'explore()'. It walks down
         from a root, finds the TEST DIRECTORIES, and folds 'hwut.conf'
         down the tree as a CONFIGURATION TREE (R-69): a parent's
         values flow down, the child's own word wins -- the R-26 law
         lifted one level.

THE CHAIN IS CLIMBED BEFORE IT IS DESCENDED. From the directory the
caller names, the walk ASCENDS through the parents, collecting every
'hwut.conf' it passes, until it reaches a 'hwut-root.conf'. The
collected confs are then applied OUTERMOST FIRST, so the innermost
word wins -- the same law as the descent, reached from the other end:

    path/hwut-root.conf                        (4)  applied first
    path/to/hwut.conf                          (3)
    path/to/my/test/hwut.conf                  (2)
    path/to/my/test/directory/TEST/hwut.conf   (1)  applied last
                                                    then the headers

THE EFFECTIVE CONFIGURATION OF A TEST DIRECTORY IS A FACT ABOUT THE
TREE, not about where the person happened to stand. Running from the
project root and running from inside a test directory must agree, and
the suite says they do.

A TREE WITH NO 'hwut-root.conf' ABOVE IT IS AN ERROR, not a default.
An author has to know that global configuration exists and that an
inheriting, shadowing chain is in force; discovering it by accident,
years later, from a value nobody can account for, is worse than being
stopped at the door.

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
from .configuration_tree import DirectorySpec


FALLBACK_TEST_DIRECTORY = "TEST"

#  The keys that flow down the tree; everything else is local.
INHERITABLE_FIELD_TUPLE = ("default_app", "language_setup", "ignore",
                           "test_directory")
LOCAL_FIELD_TUPLE       = ("on_entry", "on_exit", "collision",
                           "dependency", "target_db")

#  THE BOUNDARY OF THE ASCENT, and the most dominant configuration
#  there is. It plays BOTH ROLES: it is READ like any other conf --
#  and may be empty, which says only 'the tree ends here' -- and it
#  STOPS the climb, so nothing above a project can reach into it.
ROOT_CONF_NAME = "hwut-root.conf"


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
    inherited, ascent_fault_list = ascended_spec(root)
    fault_list.extend(ascent_fault_list)
    #  THE ROOT IS ITSELF A CANDIDATE. Standing IN a test directory and
    #  asking is the ordinary case -- it is where an author works --
    #  and a walk that only ever enters CHILDREN named 'TEST' looks
    #  everywhere except where it already stands.
    #
    #  The name it must match is the FALLBACK: 'test_directory' is
    #  stated by a PARENT's 'hwut.conf', and at the root there is no
    #  parent to state it. The root's own conf cannot be folded here
    #  either -- a test directory's conf holds LOCAL keys, and folding
    #  it as if inherited would fault on every one of them.
    if os.path.basename(os.path.normpath(root)) == FALLBACK_TEST_DIRECTORY:
        result_list.append(
            (".", explore(root, interview_runner=interview_runner,
                          inherited=inherited)))
    else:
        _walk(root, ".", inherited, interview_runner, result_list,
              fault_list)
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


class RootConfMissing(Exception):
    """No 'hwut-root.conf' stands above the named directory."""
    pass


def ascended_spec(start):
    """
    RETURN: [0] DirectorySpec, every 'hwut.conf' ABOVE 'start' folded
                in OUTERMOST FIRST, so the innermost word wins; the
                'hwut-root.conf' that ended the climb folded first of
                all.
            [1] list[Fault], what the climbed confs got wrong.

    Raises RootConfMissing where the climb reaches the file system's
    own root without meeting a 'hwut-root.conf'. A tree with no root
    conf is an ERROR, not a default (see this module's PURPOSE).

    THE CLIMB LOOKS FOR ITS BOUNDARY IN 'start' ITSELF, and for a
    plain 'hwut.conf' only ABOVE it: 'start''s own conf is read by the
    walk that follows, or by 'explore()' where 'start' is a test
    directory, and reading it twice would fold it onto itself. A
    'hwut-root.conf' is a different file and no such double arises --
    which matters, because the ordinary way to run is to stand AT the
    project root, where that file lies.

    A LOCAL KEY MET ON THE WAY UP draws a fault, exactly as one met on
    the way down: 'on_entry', 'on_exit', 'collision', 'dependency' and
    the directory's own TARGETS name local matters, and an ancestor
    has no business naming them.
    """
    here       = os.path.abspath(os.path.normpath(start))
    at_start   = True
    climbed    = []                      # innermost first
    fault_list = []
    while True:
        root_path = os.path.join(here, ROOT_CONF_NAME)
        if os.path.isfile(root_path):
            climbed.append((root_path, ROOT_CONF_NAME))
            break
        if not at_start:
            conf_path = os.path.join(here, finder.CONF_NAME)
            if os.path.isfile(conf_path):
                climbed.append((conf_path, conf_path))
        at_start = False
        parent = os.path.dirname(here)
        if parent == here:
            raise RootConfMissing(
                "no '%s' stands above '%s' -- a tree states its own "
                "boundary, and the global configuration that applies "
                "to it, in that file" % (ROOT_CONF_NAME, start))
        here = parent

    effective = DirectorySpec(language_setup={}, dependency={})
    for path, shown in reversed(climbed):        # OUTERMOST FIRST
        try:
            with open(path, "r", encoding="utf-8") as handle:
                text = handle.read()
        except OSError:
            continue
        spec, _app_db, conf_fault_list = reader.read_conf(text, shown)
        fault_list.extend(conf_fault_list)
        if spec is None: continue
        for name in LOCAL_FIELD_TUPLE:
            if getattr(spec, name):
                fault_list.append(Fault(
                    E_FaultKind.VOCABULARY, shown, spec.position,
                    "'%s' above a test directory: it names local "
                    "matters and belongs in a test directory's own "
                    "'hwut.conf'" % name))
        effective = inherited_spec(effective, spec)
    return effective, fault_list


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
