#! /usr/bin/env python3
"""SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: THE 'home' FLAG OF 'support/test_writing/LANGUAGES.conf', made
         checkable (services E-216).

    adm/support_layout.py [<hwut-directory>]

prints every port with its home, then every fault, and exits 0 where there
is none, 1 else. A fault is:

    - a directory of 'support/test_writing' that LANGUAGES.conf does not
      list, or an entry with no directory;
    - a 'home' other than 'hwut' or 'support'; not exactly one
      'reference = true', or a reference whose home is not 'hwut';
    - a '.link' of a port reaching beyond the port itself and the
      reference port -- after a split nothing else stands beside it;
    - a file of hwut outside 'support/' naming a 'home = support' port by
      its path -- after a split that path is gone. ('support/demo' is the
      ports' company and goes with them.)

NOT COUNTED in the last check: the records, which keep the paths of their
day (the numbered RATIONALE of 'engine' and 'services', 'adm/WORK',
DISCUSSIONS), the feature registry 'hwut-root-features.conf', whose
entries for a departing port a split removes, and 'GOOD/' directories: a
nominal prints what its test does, and a test that reaches a port names it
in its own source, which is read.
______________________________________________________________________________
"""
import os
import re
import sys

HWUT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(
           __file__)), ".."))
sys.path.insert(0, os.path.dirname(HWUT))
from hwut.support.test_writing.python import hwut_hocon      # noqa: E402

SUPPORT       = os.path.join("support", "test_writing")
LANGUAGE_FILE = os.path.join(SUPPORT, "LANGUAGES.conf")
HOME_SET      = ("hwut", "support")
SKIP_DIR_SET  = {".git", "node_modules", "__pycache__", "OUT", "TMP",
                 ".ruff_cache"}
REGISTRY      = "hwut-root-features.conf"


def language_db(hwut_dir=HWUT):
    """
    RETURN: [0] dict, port name -> (home, reference_f), in written order,
                of every well-formed entry of LANGUAGES.conf.
            [1] list[str], one fault per entry or parse problem refused.
    """
    path = os.path.join(hwut_dir, LANGUAGE_FILE)
    if not os.path.isfile(path): return {}, ["'%s' is missing" % LANGUAGE_FILE]
    with open(path, encoding="utf-8") as fh:
        line_list = [hwut_hocon.SourceLine(text, i + 1, 0)
                     for i, text in enumerate(fh.read().split("\n"))]
    document, parse_fault_list = hwut_hocon.parse(line_list, path)
    fault_list = ["%s:%i: %s" % (LANGUAGE_FILE, f.position.line, f.message)
                  for f in parse_fault_list]
    result = {}
    for entry in document.entry_list:
        where = "%s:%i: '%s'" % (LANGUAGE_FILE, entry.key_position.line,
                                 entry.key)
        node = entry.node
        home = node.get("home") if hasattr(node, "get") else None
        if home is None or getattr(home.node, "value", None) not in HOME_SET:
            fault_list.append("%s: 'home' is one of %s"
                              % (where, ", ".join(HOME_SET)))
            continue
        reference = node.get("reference")
        reference_f = reference is not None and reference.node.value is True
        result[entry.key] = (home.node.value, reference_f)
    return result, fault_list


def shipped_tuple(hwut_dir=HWUT):
    """
    RETURN: tuple[str], the ports with 'home = hwut' -- what hwut's package
            carries of 'support/test_writing'.
    """
    db, _ = language_db(hwut_dir)
    return tuple(name for name, (home, _) in db.items() if home == "hwut")


def _is_record(relative):
    """RETURN: True, if 'relative' keeps the paths of its day; False, else."""
    if relative.startswith("adm" + os.sep + "WORK" + os.sep): return True
    if "DISCUSSIONS" in relative: return True
    return os.path.basename(relative) == "RATIONALE.txt" \
           and relative.split(os.sep)[0] in ("engine", "services")


def _link_fault_list(hwut_dir, db, reference_list):
    """
    RETURN: list[str], one fault per '.link' of a port that reaches beyond
            the port and the reference ports ('reference_list').
    """
    fault_list = []
    for name in db:
        port = os.path.join(hwut_dir, SUPPORT, name)
        allowed = [os.path.realpath(port)] \
                  + [os.path.realpath(os.path.join(hwut_dir, SUPPORT, r))
                     for r in reference_list]
        for dirpath, dirnames, filenames in os.walk(port):
            dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIR_SET)
            for f in sorted(filenames):
                if not f.endswith(".link"): continue
                link = os.path.join(dirpath, f)
                with open(link, encoding="utf-8") as fh:
                    target = fh.read().strip()
                aim = os.path.realpath(os.path.join(dirpath, target))
                if not any(aim == a or aim.startswith(a + os.sep)
                           for a in allowed):
                    fault_list.append("'%s' links beyond its port and the "
                                      "reference: '%s'"
                                      % (os.path.relpath(link, hwut_dir),
                                         target))
    return fault_list


def _naming_fault_list(hwut_dir, departing_list):
    """
    RETURN: list[str], one fault per file of hwut outside the support tree
            that names a departing port by its path.
    """
    if not departing_list: return []
    regex = re.compile(r"support/test_writing/(%s)\b"
                       % "|".join(map(re.escape, departing_list)))
    fault_list = []
    support_dir = os.path.join(hwut_dir, "support")   # the ports and demos
    for dirpath, dirnames, filenames in os.walk(hwut_dir):
        if dirpath == support_dir or dirpath.startswith(support_dir + os.sep):
            dirnames[:] = []
            continue
        dirnames[:] = sorted(d for d in dirnames
                             if d not in SKIP_DIR_SET and d != "GOOD")
        for f in sorted(filenames):
            path     = os.path.join(dirpath, f)
            relative = os.path.relpath(path, hwut_dir)
            if relative == REGISTRY or _is_record(relative): continue
            try:
                with open(path, encoding="utf-8") as fh: text = fh.read()
            except (UnicodeDecodeError, OSError):
                continue
            hit = regex.search(text)
            if hit:
                line = text.count("\n", 0, hit.start()) + 1
                fault_list.append("'%s':%i names the 'home = support' port "
                                  "'%s'" % (relative, line, hit.group(1)))
    return fault_list


def check(hwut_dir=HWUT):
    """
    RETURN: [0] dict, port name -> (home, reference_f), as language_db.
            [1] list[str], every fault of the layout; empty where it holds.
    """
    db, fault_list = language_db(hwut_dir)
    support_dir = os.path.join(hwut_dir, SUPPORT)
    present = sorted(d for d in os.listdir(support_dir)
                     if os.path.isdir(os.path.join(support_dir, d))
                     and d not in SKIP_DIR_SET) \
              if os.path.isdir(support_dir) else []
    for name in present:
        if name not in db and not any("'%s'" % name in f for f in fault_list):
            fault_list.append("'%s/%s' is not listed in LANGUAGES.conf"
                              % (SUPPORT, name))
    for name in db:
        if name not in present:
            fault_list.append("'%s' is listed, but '%s/%s' does not stand"
                              % (name, SUPPORT, name))
    reference_list = [name for name, (_, ref_f) in db.items() if ref_f]
    if len(reference_list) != 1:
        fault_list.append("%i ports say 'reference = true' -- exactly one "
                          "does" % len(reference_list))
    for name in reference_list:
        if db[name][0] != "hwut":
            fault_list.append("the reference '%s' has 'home = %s' -- a "
                              "reference stays with hwut" % (name, db[name][0]))
    fault_list += _link_fault_list(hwut_dir, {n: v for n, v in db.items()
                                              if n in present}, reference_list)
    fault_list += _naming_fault_list(hwut_dir, [n for n, (home, _)
                                                in db.items()
                                                if home == "support"])
    return db, fault_list


def main(argv):
    """RETURN: int, 0 where the layout holds, 1 where a fault stands."""
    hwut_dir = os.path.abspath(argv[0]) if argv else HWUT
    db, fault_list = check(hwut_dir)
    for name, (home, reference_f) in db.items():
        print("%-12s home = %s%s" % (name, home,
                                       "  (reference)" if reference_f else ""))
    for fault in fault_list:
        print("FAULT: %s" % fault)
    print("support layout: %s" % ("holds" if not fault_list
                                  else "%i fault(s)" % len(fault_list)))
    return 1 if fault_list else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
