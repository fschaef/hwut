#! /usr/bin/env python3
#
# @hwut {
#     title    = "Makefile: every target reachable or standalone, every non-file target .PHONY"
#     features = ["reachable", "phony"]
#     choices {
#         good   { tolerance { constraints = ["violations == 0"] } }
#         broken { tolerance { constraints = ["violations > 0"] } }
#     }
# }
#
"""
______________________________________________________________________________
SUBJECT  the target graph of one firmware Makefile (good/broken): reachability
         and .PHONY per target
REQUIREMENT (house rules of a firmware Makefile)

    R1  every target is reachable from 'all', or it is named in STANDALONE
        (clean, flash, ... -- the verbs nobody wants inside 'all');
    R2  every target whose recipe does not write '$@' -- an alias such as
        'firmware' or a verb such as 'clean' -- is listed in .PHONY.
        (A file called 'test' in the tree would otherwise silently stop
        'make test' from running anything.) 'Writes $@' is read from the
        recipe text: a recipe that names its output literally ('-o
        build/x' instead of '-o $@') counts as writing no file -- the
        house style asks for '$@' anyway.

HOW: make itself parses the Makefile: 'make -pRrq' prints its data base,
nothing is built. The test reads targets, prerequisites, recipes and
pattern rules from it and prints

    1. the TARGET GRAPH from 'all' and from each STANDALONE target, as a
       tree; a node met a second time is not unfolded again ('^ above');
    2. the INVENTORY, one row per target, sorted by name ('make -p' lists
       them in its hash table's order, which is make's business);
    3. the verdict per rule, and the count of violations.

CHOICES
    good     the Makefile keeps both rules: no violation.
    broken   three planted edits, four violations: 'test' was dropped from
             .PHONY (R2); 'distclean' fell out of STANDALONE, and with it out
             of .PHONY (R1 and R2); 'lint' was added, reached by nobody (R1).
             The GOOD file IS the accepted violation report.

HWUT CONCEPTS -- and why each one is there
    '##! verbatim'   the tree. Outside a region whitespace is tolerated and
                     lines are stripped at both ends, so a node moved one
                     level deeper would still compare equal. In a tree the
                     indentation IS the information.
    exact lines      the inventory, sorted by the test: an order that make
                     does not promise is removed at the source, so no
                     tolerance is needed for it.
    constraint       '((violations: N))' with the law in the header: the
                     good choice demands 0. A careless re-accept of a run
                     that found a violation cannot bless it -- the law
                     stands in the header, not only in the recording. The
                     broken choice states 'violations > 0': the violation
                     is reported, the VIOLATION lines say which.

READING THE GOOD: look at the tree -- does every target hang below 'all'
or a STANDALONE root? Then the 'phony' column against the 'writes' column.
______________________________________________________________________________
"""
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def database(directory):
    """RETURN: (rule_db, pattern_list, phony_set, standalone_list, order_list)
    rule_db: target -> (prerequisite_list, recipe_text) for real targets."""
    text = subprocess.run(["make", "-pRrq", "-f", "Makefile", "__probe__"],
                          cwd=directory, capture_output=True, text=True,
                          env=dict(os.environ, LC_ALL="C")).stdout
    rule_db, pattern_list, order_list = {}, [], []
    phony_set = set()
    m = re.search(r"^STANDALONE :?= (.*)$", text, re.M)
    standalone_list = m.group(1).split() if m else []
    implicit = text.split("\n# Implicit Rules\n")[1].split("\n# Files\n")[0]
    files = text.split("\n# Files\n")[1].split("\n# files hash-table stats")[0]
    for section, body in (("implicit", implicit), ("files", files)):
        for block in body.split("\n\n"):
            line_list = [l for l in block.split("\n") if l]
            if not line_list or line_list[0].startswith("# Not a target"):
                continue
            m = re.match(r"^([^#\s][^:=]*):(?!=)\s*(.*)$", line_list[0])
            if not m:
                continue
            target, prereq_list = m.group(1).strip(), m.group(2).split()
            recipe = "\n".join(l for l in line_list if l.startswith("\t"))
            if target == ".PHONY":
                phony_set.update(prereq_list)
            elif section == "implicit":
                pattern_list.append((target, prereq_list, recipe))
            elif not target.startswith("."):
                rule_db[target] = (prereq_list, recipe)
                order_list.append(target)
    return rule_db, pattern_list, phony_set, standalone_list, order_list


def children(node, rule_db, pattern_list):
    """RETURN: (prerequisite_list, via) -- explicit, or from a pattern rule."""
    if node in rule_db:
        return rule_db[node][0], None
    for target, prereq_list, recipe in pattern_list:
        rx = "^" + re.escape(target).replace("%", "(.+)") + "$"
        m = re.match(rx, node)
        if m:
            return [p.replace("%", m.group(1)) for p in prereq_list], target
    return [], None


def writes_file(node, rule_db, pattern_list):
    if node in rule_db:
        return "$@" in rule_db[node][1]
    return children(node, rule_db, pattern_list)[1] is not None


def draw(node, rule_db, pattern_list, phony_set, seen, prefix, last, out, top):
    prereq_list, via = children(node, rule_db, pattern_list)
    if node in phony_set:
        tag = " (phony)"
    elif writes_file(node, rule_db, pattern_list):
        tag = " [file%s]" % (", rule " + via if via else "")
    elif node in rule_db:
        tag = " (NOT phony)"
    else:
        tag = ""                                     # a source file
    branch = "" if top else ("`-- " if last else "+-- ")
    again = node in seen and prereq_list
    out.append(prefix + branch + node + tag + ("  ^ above" if again else ""))
    if again:
        return
    seen.add(node)
    prefix += "" if top else ("    " if last else "|   ")
    for i, child in enumerate(prereq_list):
        draw(child, rule_db, pattern_list, phony_set, seen, prefix,
             i == len(prereq_list) - 1, out, False)


def main(choice):
    directory = os.path.join(HERE, "..", choice)
    rule_db, pattern_list, phony_set, standalone_list, order_list = database(directory)

    seen, tree = set(), ["== from 'all' =="]
    for root in ["all"] + standalone_list:
        if root == standalone_list[0]:
            tree.append("== from STANDALONE ==")
        draw(root, rule_db, pattern_list, phony_set, seen, "", True, tree, True)

    reached_db = {}
    for root in ["all"] + standalone_list:
        stack = [root]
        while stack:
            node = stack.pop()
            if node in reached_db:
                continue
            reached_db[node] = "all" if root == "all" else "STANDALONE"
            stack.extend(children(node, rule_db, pattern_list)[0])
    for node in sorted(set(order_list) - set(reached_db)):
        if "== reached from nowhere ==" not in tree:
            tree.append("== reached from nowhere ==")
        draw(node, rule_db, pattern_list, phony_set, seen, "", True, tree, True)

    print("Makefile of '%s' -- data base of 'make -pRrq'; nothing is built" % choice)
    print("STANDALONE = %s" % " ".join(standalone_list))
    print()
    print("TARGET GRAPH  roots: all, STANDALONE, then any target nobody reaches")
    print("              (phony) in .PHONY   [file] recipe writes $@")
    print("##! verbatim")
    for line in tree:
        print(line)
    print("####")
    print()
    print("INVENTORY  (sorted by target)")
    print("target             writes-$@  phony  reached-from")
    violation_list = []
    for target in sorted(order_list):
        prereq_list, recipe = rule_db[target]
        writes = "$@" in recipe
        phony = target in phony_set
        reached = reached_db.get(target, "NOWHERE")
        print("%-18s %-10s %-6s %s" % (target,
              "yes" if writes else "no", "yes" if phony else "NO" if not writes else "no",
              reached))
        if reached == "NOWHERE":
            violation_list.append("R1  '%s' is reached from neither 'all' nor STANDALONE" % target)
        if not writes and not phony:
            violation_list.append("R2  '%s' writes no file, but is not .PHONY" % target)
    print()
    print("R1  every target is reachable from 'all' or named in STANDALONE")
    print("R2  every target whose recipe does not write $@ is .PHONY")
    for violation in sorted(violation_list):
        print("VIOLATION " + violation)
    print("((violations: %d))   law == 0   %s" % (len(violation_list), "kept" if not violation_list else "BROKEN"))


if __name__ == "__main__":
    choice = sys.argv[1] if len(sys.argv) > 1 else ""
    if choice not in ("good", "broken"):
        print("choices: good, broken")
        sys.exit(1)
    main(choice)
    print("<hwut-end>")
