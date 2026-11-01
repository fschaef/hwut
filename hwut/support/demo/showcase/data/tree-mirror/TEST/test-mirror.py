#! /usr/bin/env python3
#
# @hwut {
#     title   = "Mirror a directory tree: before and after, as trees"
#     choices {
#         mirror { features = ["same-tree", "untouched", "only-dst"]
#                  tolerance { constraints = ["breaches == 0"] } }
#         old-cp { features = ["violation-shown"]
#                  tolerance { constraints = ["breaches > 0"] } }
#     }
# }
#
"""
______________________________________________________________________________
SUBJECT  the destination tree before and after one mirror tool (../mirror.sh
         or ../backup-old.sh) copied SRC into DST
REQUIREMENT. 'tool SRC DST' leaves DST equal to SRC:
    R1  the same paths with the same content, nothing more (dot files,
        blanks, a leading dash and non-ASCII names included);
    R2  files whose content already matched are not rewritten (their
        modification time stays), so the next incremental backup is small;
    R3  nothing outside DST changes (SRC itself, a sibling 'keep/').

CHOICES -- one fixture, two tools:
    mirror   ../mirror.sh (bash, find -print0): all three hold
             (law: breaches == 0).
    old-cp   ../backup-old.sh, 'cp -r SRC/* DST/' from the old cron job:
             the glob skips '.env', nothing stale is removed (R1), and every
             file is rewritten (R2) (law: breaches > 0).

HWUT CONCEPTS.
  * The trees stand side by side in '##! verbatim': indentation IS the
    structure, and by default hwut folds blanks.
  * The tool's own stdout log is NOT printed: it repeated the marks of the
    tree, in the order 'find' met the files. Its stderr is printed, since
    a complaint is part of the behaviour.
  * The checksum list (md5 of every file in DST after) is exact: content,
    not just names, is the requirement. The scratch directory has a new
    random path every run; where the old tool names it, the test prints
    '<tmp>' instead.
  * The number of broken rules R1..R3 is a constraint binding
    '((breaches: n))', judged by the choice's law.

READING THE GOOD. Three trees: SRC, DST before, DST after. Marks after a
name in DST after: '+' new, '~' updated, '=' left alone, '!' rewritten
though equal; in DST before: '-' gone after the run (the legend stands on
the page). Then R1..R3 as lines, and the law over them with its verdict.
______________________________________________________________________________
"""
import hashlib
import os
import subprocess
import sys
import tempfile
import atexit
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
TOP  = os.path.join(HERE, "..")
TOOL_DB = {"mirror": "mirror.sh", "old-cp": "backup-old.sh"}
SRC_DB = {".env": "TOKEN=abc\n", "README": "v2\n", "-rf": "not an option\n",
          "docs/my notes.txt": "draft 2\n", "docs/plan.txt": "same\n",
          "img/ünïcode.png": "PNG...\n", "src/main.c": "int main(void){return 0;}\n",
          "src/util/str.c": "/* str */\n"}
DST_DB = {"README": "v1\n", "docs/plan.txt": "same\n", "src/main.c": "int main(void){return 0;}\n",
          "src/old.c": "/* gone */\n", "tmp/cache/x.bin": "xx\n"}



def scratch(prefix):
    """RETURN: a fresh scratch directory, removed when the test ends."""
    path = tempfile.mkdtemp(prefix=prefix)
    atexit.register(shutil.rmtree, path, True)
    return path

def plant(root, file_db):
    for rel, text in file_db.items():
        path = os.path.join(root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            fh.write(text)
        os.utime(path, ns=(1_700_000_000_000_000_000, 1_700_000_000_000_000_000))


def snapshot(root):
    """RETURN: {relative path: (md5 or 'dir', mtime_ns)}."""
    result = {}
    for here, dirs, files in os.walk(root):
        for name in dirs + files:
            path = os.path.join(here, name)
            rel = os.path.relpath(path, root) + ("/" if name in dirs else "")
            if name in dirs:
                result[rel] = ("dir", 0)
            else:
                with open(path, "rb") as fh:
                    result[rel] = (hashlib.md5(fh.read()).hexdigest(), os.stat(path).st_mtime_ns)
    return result


def tree_lines(title, snap, mark_db):
    """RETURN: the tree as text lines, '|-- ' and '`-- ' with marks."""
    lines = [title]
    def walk(prefix, parent):
        kids = sorted(p for p in snap if p != parent and p.startswith(parent)
                      and "/" not in p[len(parent):].rstrip("/"))
        for i, p in enumerate(kids):
            last = i == len(kids) - 1
            name = p[len(parent):]
            mark = mark_db.get(p, "")
            lines.append(prefix + ("`-- " if last else "|-- ") + name + ("  " + mark if mark else ""))
            if p.endswith("/"):
                walk(prefix + ("    " if last else "|   "), p)
    walk("", "")
    return lines


def main(choice):
    base = scratch("mirror-")
    src, dst, keep = (os.path.join(base, d) for d in ("src", "dst", "keep"))
    plant(src, SRC_DB); plant(dst, DST_DB); plant(keep, {"precious.txt": "do not touch\n"})
    s0, d0, k0 = snapshot(src), snapshot(dst), snapshot(keep)
    p = subprocess.run([os.path.join(TOP, TOOL_DB[choice]), src, dst], capture_output=True,
                       text=True, env=dict(os.environ, LC_ALL="C.UTF-8"))
    s1, d1, k1 = snapshot(src), snapshot(dst), snapshot(keep)

    after_mark, before_mark = {}, {}
    for rel, (md5, mtime) in d1.items():
        if rel not in d0:
            after_mark[rel] = "+"
        elif md5 == "dir":
            pass
        elif md5 != d0[rel][0]:
            after_mark[rel] = "~"
        else:
            after_mark[rel] = "=" if mtime == d0[rel][1] else "! rewritten"
    for rel in d0:
        if rel not in d1:
            before_mark[rel] = "-"
    for rel in s1:
        if rel not in d1:
            after_mark.setdefault(rel, "")

    print("tool: %s SRC DST   exit %d" % (TOOL_DB[choice], p.returncode))
    print("marks: + added  ~ changed  = untouched (same mtime)  ! rewritten though equal  - removed")
    cols = [tree_lines("SRC", s0, {}), tree_lines("DST before", d0, before_mark),
            tree_lines("DST after", d1, after_mark)]
    height = max(len(c) for c in cols)
    print("##! verbatim")
    for row in range(height):
        print("".join("%-26s" % (c[row] if row < len(c) else "") for c in cols).rstrip())
    print("####")
    print("tool stderr: %s" % ("(none)" if not p.stderr.strip() else ""))
    for line in p.stderr.splitlines():
        print("  " + line.replace(base, "<tmp>"))
    print("md5 of DST after:")
    print("##! verbatim")
    for rel, (md5, _) in sorted(d1.items()):
        if md5 != "dir":
            print("  %s  %s" % (md5, rel))
    print("####")
    want = {r: v[0] for r, v in s0.items()}
    have = {r: v[0] for r, v in d1.items()}
    missing = sorted(set(want) - set(have))
    extra   = sorted(set(have) - set(want))
    wrong   = sorted(r for r in set(want) & set(have) if want[r] != have[r])
    ok = lambda flag: "holds" if flag else "BROKEN"
    print("R1 DST == SRC        missing %d, extra %d, wrong %d   %s"
          % (len(missing), len(extra), len(wrong), ok(not (missing or extra or wrong))))
    for r in missing: print("     missing  %s" % r)
    for r in extra:   print("     extra    %s" % r)
    rewritten = sorted(r for r, m in after_mark.items() if m.startswith("!"))
    print("R2 equal files kept  rewritten %d                 %s" % (len(rewritten), ok(not rewritten)))
    print("R3 nothing outside DST changes: SRC %s, sibling keep/ %s   %s"
          % ("same" if s0 == s1 else "CHANGED", "same" if k0 == k1 else "CHANGED", ok(s0 == s1 and k0 == k1)))
    breaches = bool(missing or extra or wrong) + bool(rewritten) + (s0 != s1 or k0 != k1)
    print("rules broken ((breaches: %d))   law == 0   %s" % (breaches, ok(breaches == 0)))


if len(sys.argv) < 2 or sys.argv[1] not in TOOL_DB:
    print("choices: %s" % ", ".join(TOOL_DB))
    sys.exit(1)
main(sys.argv[1])
print("<hwut-end>")
