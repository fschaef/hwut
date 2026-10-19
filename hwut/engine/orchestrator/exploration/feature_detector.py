"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE ONE DETECTOR (spec 23 VERSION 10 section 7, R-96). It judges
         the central file ('feature_registry.py') against how the tree
         stands, and it is the SAME detector for 'hwut.features.register'
         and for 'hwut.sanitize.propose --relations': what the one finds the
         other proposes, in one vocabulary. It detects; it never writes,
         never retires, never guesses.

    detect(root, below=None)    -> tuple of CDetection | None
    detect_of(registry, fact_db, old_tuple, below=None)  (pure)
    fact_db_of_tree(root)       -> (fact_db, old_tuple)

    fact_db   dict: path of a component (relative to the root, '/') -> the
              tuple of the feature names its TEST directory's
              'hwut-features.conf' defines; only components that OWN such a
              file stand in it.

KINDS
    old-vocabulary  a component file, or 'hwut-feature-map.conf': no longer
                    read
    dir-new         a component owns a TEST feature file and has no id
    dir-gone        an id's path stands no more
    dir-swapped     an id's path stands, but the features registered under
                    it are defined in another directory (contents exchanged)
    dir-twin        one path under two ids
    leaf-new        a name defined in a registered directory, in no line
    leaf-gone       a line names a leaf that is defined no more
    retired-use     a name defined that was retired: never bound again
    unplaced        a leaf at the top of the tree (a hint)

THE ROOT IS A DIRECTORY LIKE ANY OTHER (the book's D-3): its own TEST
directory defining features gets an id standing for '.'. That id is
never gone and never redirected -- the root does not move.

PAIRING (a gone with a new), NAMED on the proposal line, never guessed:

    directories   the FINGERPRINT: the names registered under a gone id
                  against the names defined in an unregistered directory.
                  Paired only where the pair is mutually best, unique and
                  the overlap is at least HALF of the gone id's names.
    leaves        an equal NAME is the same leaf and is not gone. A leaf
                  renamed leaves no old title behind (a live leaf is a line
                  of ids, its title stands in the TEST file only), so: in a
                  directory with exactly ONE gone and exactly ONE new leaf
                  they are paired; with more, 'unpaired' lists the
                  candidates. Across directories (a block moved by hand) the
                  one gone name and the one new name that are EQUAL are
                  paired. A new name of a directory whose gone leaf is not
                  paired is HELD: no 'register' is proposed for it, and
                  'hwut.features.register' writes no line for it, until the
                  gone one is repointed or retired -- a minted id would take
                  the place of the external id the world knows (the book's
                  D-7). A rename is 'hwut.features.rename'.

PROPOSALS -- the lines of 'hwut.sanitize', one vocabulary for the detector,
'hwut.features.register' and 'hwut.sanitize.propose'; the old value stands
in the note behind '#', which no reader of commands reads (E-130):

    register <path>
    redirect <id> <new path>                  # from <old path>
    repoint <external id> <new internal id>   # from <old internal id>
    fold <id> <first id>                      # one path, two ids
    # unpaired <id | external> <what> (candidates: ...)

A finding carries them as data too ('command_tuple': (verb, words, note));
an 'unpaired' line is no command, only said.
______________________________________________________________________________
"""
import os
from   dataclasses import dataclass

from .finder           import FEATURE_FILE_NAME, MAP_FILE_NAME
from .feature_relation import read_feature_file, TEST_NAME
from .feature_registry import (read_registry, leaf_list,
                               retired_internal_set)

OLD_VOCABULARY = "old-vocabulary"
DIR_NEW        = "dir-new"
DIR_GONE       = "dir-gone"
DIR_SWAPPED    = "dir-swapped"
DIR_TWIN       = "dir-twin"
LEAF_NEW       = "leaf-new"
LEAF_GONE      = "leaf-gone"
RETIRED_USE    = "retired-use"
UNPLACED       = "unplaced"
KIND_TUPLE     = (OLD_VOCABULARY, DIR_NEW, DIR_GONE, DIR_SWAPPED, DIR_TWIN,
                  LEAF_NEW, LEAF_GONE, RETIRED_USE, UNPLACED)
HINT_TUPLE     = (UNPLACED,)

#  What a walk does not enter: the volatile directories of a run and of a
#  checkout (the same the census strips), and every hidden one.
PRUNE_NAME_TUPLE = ("TMP", "OUT", "__pycache__", "htmlcov", "node_modules")


@dataclass(frozen=True)
class CDetection:
    """One disagreement. 'subject' is what it is about (an id, a path, an
    external id), 'text' the line the report prints after it, 'proposal'
    the lines proposed, 'path_tuple' the directories concerned (for 'below')."""
    kind:          str
    subject:       str
    text:          str
    command_tuple: tuple = ()        # of (verb, word tuple, note | None)
    unpaired:      str | None = None # what could not be paired, said
    path_tuple:    tuple = ()

    @property
    def proposal(self):
        """RETURN: tuple of str, the proposal lines as 'hwut.sanitize'
        spells them: one per command, its note behind '  # '; an
        'unpaired' finding as a comment line."""
        result = tuple(command_line(*each) for each in self.command_tuple)
        if self.unpaired is not None:
            result += ("# unpaired %s" % self.unpaired,)
        return result

    @property
    def hint_f(self):
        """RETURN: True, the detection is a hint, no disagreement."""
        return self.kind in HINT_TUPLE


def command_line(verb, word_tuple, note=None):
    """RETURN: str, a command as a line of 'hwut.sanitize' spells it."""
    line = " ".join((verb,) + tuple(word_tuple))
    return line + "  # " + note if note else line


# -- the facts of the tree ----------------------------------------------

def fact_db_of_tree(root, below="."):
    """RETURN: tuple (dict, tuple): [0] fact_db: path -> tuple of the names
    the TEST directory below that path defines, for every component whose
    TEST directory holds a 'hwut-features.conf'; [1] the paths (relative,
    '/') of what is a vocabulary of the past: a 'hwut-features.conf' outside
    a TEST directory, a 'hwut-feature-map.conf'. Sorted, deterministic.
    Only what stands at or below 'below' (a path relative to 'root') is
    walked; the paths stay relative to 'root'."""
    fact_db, old_list = {}, []
    for directory, name_list, file_list in os.walk(os.path.join(root,
                                                                below)):
        name_list[:] = sorted(each for each in name_list
                              if not each.startswith(".")
                              and each not in PRUNE_NAME_TUPLE)
        relative = os.path.relpath(directory, root).replace(os.sep, "/")
        test_f   = os.path.basename(directory) == TEST_NAME
        if FEATURE_FILE_NAME in file_list:
            if test_f:
                file = read_feature_file(directory)
                component = posix_parent(relative)
                if file is not None:
                    fact_db[component] = file.name_tuple()
            else:
                old_list.append(join(relative, FEATURE_FILE_NAME))
        if MAP_FILE_NAME in file_list:
            old_list.append(join(relative, MAP_FILE_NAME))
    return fact_db, tuple(sorted(old_list))


def posix_parent(path):
    """RETURN: str, the parent of the relative 'path' ('.' at the top)."""
    return path.rpartition("/")[0] or "."


def join(relative, name):
    """RETURN: str, 'name' below the relative directory 'relative'."""
    return name if relative == "." else relative + "/" + name


def unregistered_list(root, below="."):
    """RETURN: list of (str, str), (directory path, name) of every feature
    defined in a TEST directory at or below 'below' whose internal id has
    no line in the central file -- its directory has no id there, or the
    name stands in no leaf; a retired name is not counted (it is the
    detector's 'retired-use'). [] where no central file stands, or it states
    a fault. Walks only below 'below': cheap enough for the end of a run."""
    registry = read_registry(root)
    if registry is None or registry.fault_tuple: return []
    fact_db, _ = fact_db_of_tree(root, below)
    id_of   = {each.path: each.id for each in registry.directory_tuple}
    live    = {leaf.internal for _, leaf in leaf_list(registry)}
    retired = retired_internal_set(registry)
    result  = []
    for path in sorted(fact_db):
        for name in fact_db[path]:
            internal = "%s:%s" % (id_of.get(path), name)
            if internal not in live and internal not in retired:
                result.append((path, name))
    return result


# -- the detector -------------------------------------------------------

def detect(root, below=None):
    """
    RETURN: tuple of CDetection, every disagreement of the central file
            with the tree below 'root' (and, in 'below', only those whose
            directory lies at or below the path 'below'), sorted
            None, no central file stands (the caller says 'init')
    """
    registry = read_registry(root)
    if registry is None: return None
    fact_db, old_tuple = fact_db_of_tree(root)
    return detect_of(registry, fact_db, old_tuple, below)


def detect_of(registry, fact_db, old_tuple=(), below=None):
    """RETURN: tuple of CDetection, as 'detect', from a registry and the
    facts of the tree (pure)."""
    found = list(_old_list(old_tuple))
    path_of = {each.id: each.path for each in registry.directory_tuple}
    id_of   = {}
    for each in registry.directory_tuple:
        id_of.setdefault(each.path, []).append(each.id)
    found += _twin_list(id_of)
    name_db = _registered_name_db(registry)           # id -> set of names
    #  THE ROOT'S ID IS NEVER GONE: the root does not move, and its id is
    #  never sent elsewhere (the book's D-3, R-5). Where its TEST directory
    #  defines nothing any more, its leaves are gone one by one.
    gone_set = {i for i, p in path_of.items()
                if p not in fact_db and p != "."}
    new_set  = {p for p in fact_db if p not in id_of}
    pair_db, dir_list = _directory_pair_list(
        path_of, name_db, fact_db, gone_set, new_set)
    found += dir_list
    swap_list, mutual_db = _swap_list(path_of, id_of, name_db, fact_db,
                                      gone_set)
    found += swap_list
    #  Where the directory is, as it will stand once the proposals are
    #  applied: a paired gone id at its new path, a mutual swap exchanged;
    #  a gone id without a partner nowhere; the second id of a twin none
    #  (it folds into the first and defines nothing of its own).
    effective = {i: (p if i not in gone_set else pair_db.get(i))
                 for i, p in path_of.items()}
    effective.update(mutual_db)
    for id_list in id_of.values():
        for later in id_list[1:]: effective[later] = None
    found += _leaf_list(registry, effective, fact_db, path_of)
    found += [CDetection(UNPLACED, leaf.external,
                         "'%s' is in no aggregate" % leaf.external)
              for path, leaf in leaf_list(registry) if not path]
    found = _below(found, below)
    return tuple(sorted(found, key=lambda each: (
        KIND_TUPLE.index(each.kind), each.subject, each.text)))


def _below(found, below):
    """RETURN: list of CDetection, those whose directories lie at or below
    the path 'below' (all, where 'below' is None or '.'); one that names no
    directory stays."""
    if below in (None, "", "."): return found
    prefix = below.rstrip("/") + "/"
    return [each for each in found
            if not each.path_tuple
            or any(p == below.rstrip("/") or p.startswith(prefix)
                   for p in each.path_tuple)]


def _old_list(old_tuple):
    """RETURN: list of CDetection, the vocabulary of the past that stands."""
    return [CDetection(OLD_VOCABULARY, path,
                       "%s   no longer read; migrate" % path,
                       (), None, (posix_parent(path),))
            for path in old_tuple]


def _twin_list(id_of):
    """RETURN: list of CDetection, a path under two ids or more: the later
    ones fold into the first."""
    result = []
    for path, id_list in sorted(id_of.items()):
        if len(id_list) > 1:
            result.append(CDetection(
                DIR_TWIN, path,
                "%s   under two ids: %s" % (path, ", ".join(id_list)),
                tuple(("fold", (other, id_list[0]), "one path, two ids")
                      for other in id_list[1:]), None, (path,)))
    return result


def _registered_name_db(registry):
    """RETURN: dict, directory id -> set of the names of the live leaves
    registered under it."""
    result = {}
    for _, leaf in leaf_list(registry):
        result.setdefault(leaf.directory_id, set()).add(leaf.name)
    return result


def _top(score_list):
    """RETURN: tuple (int, list): the best score of the (score, key) pairs
    and the sorted keys that reach it; (0, []) where none scores."""
    best = max((score for score, _ in score_list), default=0)
    if best == 0: return 0, []
    return best, sorted(key for score, key in score_list if score == best)


def _half_f(overlap, total):
    """RETURN: True, 'overlap' is at least half of 'total' (and not 0)."""
    return overlap >= 1 and overlap * 2 >= total


def _directory_pair_list(path_of, name_db, fact_db, gone_set, new_set):
    """RETURN: tuple (dict, list): [0] gone id -> the new path it is paired
    with; [1] list of CDetection (dir-gone for every gone id, with the
    redirect or the 'unpaired' line; dir-new for every new path not paired)."""
    def overlap(i, p): return len(name_db.get(i, set()) & set(fact_db[p]))

    best_u = {i: _top([(overlap(i, p), p) for p in new_set])
              for i in gone_set}
    best_g = {p: _top([(overlap(i, p), i) for i in gone_set])
              for p in new_set}
    pair_db, result = {}, []
    for i in sorted(gone_set):
        s, top = best_u[i]
        total = len(name_db.get(i, ()))
        paired = None
        if len(top) == 1 and _half_f(s, total):
            u = top[0]
            if best_g[u][1] == [i]: paired = u
        old = path_of[i]
        if paired is not None:
            pair_db[i] = paired
            result.append(CDetection(
                DIR_GONE, i, "%s   '%s' stands no more" % (i, old),
                (("redirect", (i, paired), "from %s" % old),), None,
                (old, paired)))
        else:
            candidate = sorted(p for p in new_set if overlap(i, p) >= 1)
            result.append(CDetection(
                DIR_GONE, i, "%s   '%s' stands no more" % (i, old),
                (), "%s %s (candidates: %s)" % (
                    i, old, ", ".join(candidate) or "none"), (old,)))
    paired_path = set(pair_db.values())
    for p in sorted(new_set - paired_path):
        result.append(CDetection(DIR_NEW, p, "%s   no directory id" % p,
                                 (("register", (p,), None),), None, (p,)))
    return pair_db, result


def _swap_list(path_of, id_of, name_db, fact_db, gone_set):
    """RETURN: tuple (list, dict): [0] list of CDetection, ids whose path
    stands but whose registered features are defined in another directory:
    a mutual pair gets two redirects, else 'unpaired'; [1] id -> the path
    the redirect would send it to, for the mutual pairs only."""
    def overlap(i, p): return len(name_db.get(i, set()) & set(fact_db[p]))

    away = {}
    for i, path in path_of.items():
        if i in gone_set or not name_db.get(i) or path == ".": continue
        total = len(name_db[i])
        if overlap(i, path) * 2 >= total: continue
        score = sorted(((overlap(i, p), p) for p in fact_db if p != path),
                       reverse=True)
        if score and _half_f(score[0][0], total) \
           and (len(score) == 1 or score[1][0] < score[0][0]):
            away[i] = score[0][1]
    result, mutual_db = [], {}
    for i in sorted(away):
        there = away[i]
        mate  = [j for j in id_of.get(there, []) if away.get(j) == path_of[i]]
        if len(mate) == 1:
            command, unpaired = (("redirect", (i, there),
                                  "from %s" % path_of[i]),), None
            mutual_db[i] = there
        else:
            command, unpaired = (), "%s %s (candidates: %s)" % (
                i, path_of[i], there)
        result.append(CDetection(
            DIR_SWAPPED, i,
            "%s   '%s' stands; its features are defined in '%s'"
            % (i, path_of[i], there),
            command, unpaired, (path_of[i], there)))
    return result, mutual_db


def _leaf_list(registry, effective, fact_db, path_of):
    """RETURN: list of CDetection, the leaves gone and new, with the
    pairings named, and the names defined that were retired."""
    live      = {leaf.internal: leaf for _, leaf in leaf_list(registry)}
    retired   = retired_internal_set(registry)
    defined   = {}                              # internal id -> path
    for i, path in effective.items():
        for name in fact_db.get(path, ()) if path is not None else ():
            defined["%s:%s" % (i, name)] = path
    #  The leaves of a gone directory that is not paired are said by the
    #  directory ('dir-gone'), not once more by each of them.
    gone_list = sorted(each for each in live if each not in defined
                       and effective.get(live[each].directory_id) is not None)
    new_list  = sorted(each for each in defined if each not in live
                       and each not in retired)
    result = []
    for internal in sorted(each for each in defined if each in retired):
        result.append(CDetection(
            RETIRED_USE, internal,
            "%s   retired; a TEST directory defines it again" % internal,
            (), None, (defined[internal],)))
    pair_db = _leaf_pair_db(gone_list, new_list, live, effective)
    paired_new = {new for new, _ in pair_db.values()}
    held_db    = {}            # new internal id -> the gone it may be
    for old in gone_list:
        if old in pair_db: continue
        for each in _candidate_list(old, new_list):
            if each.partition(":")[0] == old.partition(":")[0]:
                held_db.setdefault(each, []).append(live[old].external)
    for old in gone_list:
        leaf = live[old]
        path = path_of.get(leaf.directory_id)
        if old in pair_db:
            new, _ = pair_db[old]
            command = (("repoint", (leaf.external, new), "from %s" % old),)
            unpaired = None
        else:
            candidate = _candidate_list(old, new_list)
            command = ()
            unpaired = "%s %s (candidates: %s)" % (
                leaf.external, old, ", ".join(candidate) or "none")
        result.append(CDetection(
            LEAF_GONE, leaf.external,
            "%s   %s is defined no more" % (leaf.external, old),
            command, unpaired, (path,) if path else ()))
    for new in new_list:
        if new in paired_new: continue
        path = defined[new]
        if new in held_db:
            #  A CANDIDATE OF A GONE LEAF is not proposed for registering:
            #  'hwut.features.register' holds it back (the book's D-7).
            #  'repoint' makes it the gone one; retiring the gone one makes
            #  it new.
            command  = ()
            unpaired = ("%s (candidate of: %s; held until repointed, "
                        "or the gone retired)"
                        % (new, ", ".join(held_db[new])))
        else:
            command, unpaired = (("register", (path,), None),), None
        result.append(CDetection(
            LEAF_NEW, new, "%s   '%s' is in no line" % (path, new.partition(":")[2]),
            command, unpaired, (path,)))
    return result


def _candidate_list(old, new_list):
    """RETURN: list of str, the new internal ids that could be the pair of
    the gone 'old': those of its own directory, then those of the same name
    elsewhere."""
    directory, _, name = old.partition(":")
    return [each for each in new_list
            if each.partition(":")[0] == directory
            or each.partition(":")[2] == name]


def _leaf_pair_db(gone_list, new_list, live, effective):
    """RETURN: dict, gone internal id -> (new internal id, why), the pairs
    that are certain enough to be proposed: in one directory exactly one
    gone and exactly one new; across directories the one gone and the one
    new of an EQUAL name."""
    pair_db, taken = {}, set()
    for directory in sorted({each.partition(":")[0] for each in gone_list}):
        gone = [each for each in gone_list if each.partition(":")[0] == directory]
        new  = [each for each in new_list if each.partition(":")[0] == directory]
        if len(gone) == 1 and len(new) == 1:
            pair_db[gone[0]] = (new[0], "the only one in its directory")
            taken.add(new[0])
    for old in gone_list:
        if old in pair_db: continue
        name  = old.partition(":")[2]
        same  = [each for each in new_list
                 if each.partition(":")[2] == name and each not in taken]
        gone_same = [each for each in gone_list
                     if each.partition(":")[2] == name and each not in pair_db]
        if len(same) == 1 and len(gone_same) == 1:
            pair_db[old] = (same[0], "the same name")
            taken.add(same[0])
    return pair_db


__all__ = ("detect", "detect_of", "fact_db_of_tree", "CDetection",
           "KIND_TUPLE")
