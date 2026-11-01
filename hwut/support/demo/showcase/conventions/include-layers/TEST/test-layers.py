#! /usr/bin/env python3
#
# @hwut {
#     title    = "Include layering: no module includes a layer above its own"
#     features = ["downward-only", "every-file-layered"]
#     choices {
#         good   { tolerance { constraints = ["upward == 0", "unlayered == 0"] } }
#         broken { tolerance { constraints = ["upward > 0",  "unlayered == 0"] } }
#     }
# }
#
"""
______________________________________________________________________________
SUBJECT  the include edges between the layers of one C tree (good/broken)
REQUIREMENT: layers.ini gives every top directory a layer number (hal 0,
drivers 1, services 2, app 3).
    L1  a file may include files of its own layer and of layers
        below it -- never of a layer above. A UART driver that logs through
        the logger service makes the HAL depend on everything the logger
        depends on; the compiler does not mind, the next port to a new
        board does.
    L2  every file lies in a directory that layers.ini names.

HOW: the test resolves every '#include' as the compiler does: each
directive, spelled as written ("x.h", <dir/x.h>, "../dir/x.h"), is handed
to 'gcc -E -H' from the including file's directory with the include path
of layers.ini [build] cflags. The file gcc opens decides the layer -- not
the spelling. Files outside the tree (<stdio.h>) are outside the layering;
an include gcc cannot find stops the test. It prints
    1. the LAYERS as bands, top layer first, with their files;
    2. the INCLUDE MATRIX: how many includes go from the layer of the row to
       the layer of the column. Below the diagonal is downward (allowed), the
       diagonal is within a layer (allowed), above it is upward: such a cell
       is written '[n]'. L1 holds when the upper right triangle is empty;
    3. every upward edge, with file and line.

CHOICES
    good     four layers, all includes downward or level.
    good     spells its includes three ways ("gpio.h" via -Ihal, <hal/uart.h>,
             "../drivers/modem.h") -- the matrix counts them all.
    broken   three upward includes, one per spelling: hal/uart.c "logger.h",
             hal/gpio.c "../services/telemetry.h", drivers/modem.c
             <app/app_config.h> -- and all still compile.

HWUT CONCEPTS
    constraints  good: 'upward == 0' -- the requirement; broken: 'upward > 0'
                 -- the violation is reported, its exact count is the
                 picture's business. 'unlayered == 0' is L2 on both.
    exact lines  bands, matrix and the edge count; a cell is a count, so one
                 new upward include turns '.' into '[1]' AND fails the law,
                 and an include the resolver missed changes 'edges: n'.

READING THE GOOD: the upper right triangle of the matrix -- every cell '.'.
______________________________________________________________________________
"""
import configparser
import os
import re
import shlex
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def resolve(root, cflags, path, directive):
    """RETURN: the file (relative to root) gcc opens for 'directive' written
               in 'path'; None if it lies outside the tree (system header)."""
    here = os.path.dirname(os.path.join(root, path))
    flags = [f[:2] + os.path.join(root, f[2:]) if f.startswith("-I") else f for f in cflags]
    r = subprocess.run(["gcc", "-E", "-H", "-x", "c", "-", "-o", os.devnull] + flags,
                       input=directive + "\n", cwd=here, capture_output=True, text=True)
    hit = [l[2:] for l in r.stderr.splitlines() if l.startswith(". ")]
    if r.returncode != 0 or not hit:
        sys.exit("%s: %s -- gcc cannot resolve it:\n%s" % (path, directive, r.stderr))
    rel = os.path.relpath(os.path.normpath(os.path.join(here, hit[0])), root)
    return None if rel.startswith("..") else rel


def main(choice):
    root = os.path.realpath(os.path.join(HERE, "..", choice))
    ini = configparser.ConfigParser()
    ini.read(os.path.join(root, "layers.ini"))
    layer_db = {name: int(n) for name, n in ini["layers"].items()}
    cflags = shlex.split(ini["build"]["cflags"])
    layer_list = sorted(layer_db, key=layer_db.get)
    file_list = sorted(os.path.join(d, f) for d in os.listdir(root)
                       if os.path.isdir(os.path.join(root, d)) for f in os.listdir(os.path.join(root, d))
                       if f.endswith((".c", ".h")))
    edge_list = []   # (file, line, spelling, resolved file)
    for path in file_list:
        for i, line in enumerate(open(os.path.join(root, path)), 1):
            m = re.match(r'\s*#\s*include\s*([<"][^>"]+[>"])', line)
            if m:
                target = resolve(root, cflags, path, "#include " + m.group(1))
                if target:
                    edge_list.append((path, i, m.group(1), target))
    unlayered = sorted({p.split("/")[0] for p in file_list} - set(layer_db))

    print("layering of '%s' (layers.ini, gcc %s)" % (choice, " ".join(cflags)))
    print()
    print("LAYERS  (a layer may include itself and what stands below it)")
    for name in reversed(layer_list):
        files = " ".join(p.split("/", 1)[1] for p in file_list if p.startswith(name + "/"))
        print("  L%d %-9s | %s" % (layer_db[name], name, files))
    for name in unlayered:
        print("  ?? %-9s | not in layers.ini" % name)
    print()
    print("INCLUDE MATRIX  includes from the row's layer into the column's (as gcc resolves them)")
    print("                " + "".join("%-10s" % n for n in layer_list).rstrip())
    upward_list = []
    for src in layer_list:
        cell_list = []
        for dst in layer_list:
            n = sum(1 for p, _, _, t in edge_list
                    if p.split("/")[0] == src and t.split("/")[0] == dst)
            up = layer_db[dst] > layer_db[src]
            cell_list.append("." if n == 0 else "[%d]" % n if up else str(n))
        print("  %-13s " % ("%s (L%d)" % (src, layer_db[src])) + "".join("%-10s" % c for c in cell_list).rstrip())
    print("  ^ rows include columns; '[n]' = upward, forbidden; upper right must be '.'")
    print()
    for path, line, spelling, target in edge_list:
        a, b = path.split("/")[0], target.split("/")[0]
        if a in layer_db and b in layer_db and layer_db[b] > layer_db[a]:
            upward_list.append(path)
            print("UPWARD  %-19s includes %-26s = %-21s L%d %s -> L%d %s"
                  % ("%s:%d" % (path, line), spelling, target, layer_db[a], a, layer_db[b], b))
    law = lambda n: "law == 0   %s" % ("kept" if n == 0 else "BROKEN")
    print("edges: %d   L1 upper right empty: upward ((upward: %d))   %s"
          % (len(edge_list), len(upward_list), law(len(upward_list))))
    print("files outside every layer ((unlayered: %d))   %s" % (len(unlayered), law(len(unlayered))))


if __name__ == "__main__":
    choice = sys.argv[1] if len(sys.argv) > 1 else ""
    if choice not in ("good", "broken"):
        print("choices: good, broken")
        sys.exit(1)
    main(choice)
    print("<hwut-end>")
