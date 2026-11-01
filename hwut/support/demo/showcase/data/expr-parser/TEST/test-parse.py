#! /usr/bin/env python3
#
# @hwut {
#     title   = "Expression parser: trees, error positions, random agreement"
#     choices {
#         trees       { features = ["precedence"] }
#         errors      { features = ["error-position"] }
#         fuzz        { features = ["agrees"]
#                       tolerance { constraints = ["mismatches == 0", "failures == 0",
#                                                  "n_plus >= 500", "n_minus >= 500", "n_times >= 500",
#                                                  "n_power >= 200", "n_neg >= 200", "depth_max >= 4"] } }
#         minus-right { features = ["violation-shown"]
#                       tolerance { constraints = ["mismatches > 0"] } }
#     }
# }
#
"""
______________________________________________________________________________
SUBJECT  the parses of ../parse.js: trees, error positions, and the values of
         random expressions against Python's
REQUIREMENT. ../parse.js (node) reads integer expressions with + - * ^ and
parentheses, operators taken from a table (../ops.json):
    R1  precedence and associativity as in mathematics: * before + -,
        ^ before *, + - * left-associative, ^ right-associative, and
        -2^2 = -(2^2);
    R2  an error names what was expected and the column where it was not
        found;
    R3  on any expression its value equals Python's value of the same text.

CHOICES
    trees        R1: a set of expressions printed as trees with their value.
    errors       R2: bad input, each with a caret under the column named.
    fuzz         R3: 3000 random expressions per run (clock seed), compared
                 with Python's eval; the operator counts show the sample is
                 broad. Laws: no mismatch, no failure, every operator drawn.
    minus-right  the table ../ops-minus-right.json declares '-' right-
                 associative (one word, copied from the '^' line): the tree
                 of 8 - 3 - 2 hangs to the right, its value is 7, and the
                 fuzz counts mismatches (law: > 0).

HWUT CONCEPTS. Trees and errors stand in '##! verbatim': by default hwut
strips a line's ends and treats a run of blanks as one blank -- a caret one
column off, or a subtree hung one level higher, would pass. Inside verbatim
every blank counts. The fuzz prints what varies as constraint bindings
('((mismatches: 0))', the operators drawn) -- the law is checked, the
recorded count is not; the number of expressions is fixed, plain text. A few mismatching expressions are shown as evidence inside
'##! ignore': the frame must be there, the random contents do not count.

READING THE GOOD. In a tree, an operator's children hang below it, left
first; a left-associative chain leans down the LEFT side; 'maths says N'
follows a value that differs from Python's. The header line shows each
operator as the table defines it, '(maths: ...)' where that is not the
mathematical convention. In the errors, the caret stands under the column
in the message; '(no column)' where the parser names none. The fuzz counts
carry their laws and verdicts.
______________________________________________________________________________
"""
import json
import os
import random
import subprocess
import sys
import time

sys.set_int_max_str_digits(0)

HERE = os.path.dirname(os.path.abspath(__file__))
TOP  = os.path.join(HERE, "..")
TREE_CASES = ["8 - 3 - 2", "2 + 3 * 4 - 5", "2 ^ 3 ^ 2", "-2 ^ 2", "(1 + 2) * -(3 - 4)"]
ERROR_CASES = ["2 * (3 + 4", "2 + * 3", "12 ) + 1", "7 % 2", "", "2 ^ -1", "((1)"]


def parse(table, lines):
    """RETURN: one result dict per input line, from parse.js."""
    p = subprocess.run(["node", os.path.join(TOP, "parse.js"), os.path.join(TOP, table)],
                       input="".join(l + "\n" for l in lines), capture_output=True, text=True, check=True)
    return [json.loads(l) for l in p.stdout.splitlines()]


def draw(tree, prefix="", last=True, top=True):
    """Prints a tree: '+--' for a child with siblings below, '`--' for the last."""
    label = tree if isinstance(tree, str) else ("neg" if tree[0] == "neg" else tree[0])
    print("    " + ("" if top else prefix + ("`-- " if last else "+-- ")) + label)
    if isinstance(tree, list):
        children = tree[1:]
        for i, child in enumerate(children):
            draw(child, "" if top else prefix + ("    " if last else "|   "), i == len(children) - 1, False)


def trees(table):
    for text, result in zip(TREE_CASES, parse(table, TREE_CASES)):
        maths = eval(text.replace("^", "**"))
        print("%-22s = %s%s" % (text, result["value"],
                                "" if int(result["value"]) == maths else "   maths says %d" % maths))
        draw(result["ast"])


def errors(table):
    for text, result in zip(ERROR_CASES, parse(table, ERROR_CASES)):
        print("input  |%s" % text)
        col = result.get("column", 0)
        print("       |%s%s" % (" " * (col - 1) + "^" if col else "(no column)",
                                "  " + result["error"]))


def random_expr(rng, depth, count):
    """RETURN: a random expression text; 'count' tallies what was drawn."""
    count["depth"] = max(count["depth"], 4 - depth)
    k = rng.random()
    if depth == 0 or k < 0.2:
        return str(rng.randint(0, 20))
    if k < 0.3:
        return "(" + random_expr(rng, depth - 1, count) + ")"
    if k < 0.4:
        count["neg"] += 1
        return "-" + random_expr(rng, depth - 1, count)
    op = rng.choice("+-*^")
    count[op] += 1
    if op == "^":                  # small powers: a shallow base, a literal exponent chain
        right = str(rng.randint(0, 3)) if rng.random() < 0.6 else "%d ^ %d" % (rng.randint(0, 2), rng.randint(0, 2))
        left  = random_expr(rng, min(depth - 1, 1), count)
    else:
        right = random_expr(rng, depth - 1, count)
        left  = random_expr(rng, depth - 1, count)
    return left + rng.choice(("", " ")) + op + " " + right


def fuzz(table, n=3000):
    seed = time.time_ns()
    rng = random.Random(seed)
    count = {"+": 0, "-": 0, "*": 0, "^": 0, "neg": 0, "depth": 0}
    texts = [random_expr(rng, 4, count) for _ in range(n)]
    mismatch, failure = [], 0
    for text, result in zip(texts, parse(table, texts)):
        if "error" in result:
            failure += 1
        elif int(result["value"]) != eval(text.replace("^", "**")):
            mismatch.append((text, result["value"], eval(text.replace("^", "**"))))
    print("## seed %d" % seed)
    print("random expressions: %d, depth up to ((depth_max: %d))" % (n, count["depth"]))
    print("operators drawn:  + ((n_plus: %d))  - ((n_minus: %d))  * ((n_times: %d))   law >= 500 each"
          % (count["+"], count["-"], count["*"]))
    print("                  ^ ((n_power: %d))  unary - ((n_neg: %d))   law >= 200 each" % (count["^"], count["neg"]))
    law = lambda n: "law == 0   %s" % ("kept" if n == 0 else "BROKEN")
    print("parse failures:     ((failures: %d))   %s" % (failure, law(failure)))
    print("value != Python's:  ((mismatches: %d))   %s" % (len(mismatch), law(len(mismatch))))
    print("##! ignore")
    for text, got, want in sorted(mismatch, key=lambda m: len(m[0]))[:3]:
        print("    %s  ->  %s, Python says %s" % (text, got, want))
    print("####")


def main(choice):
    table = "ops-minus-right.json" if choice == "minus-right" else "ops.json"
    with open(os.path.join(TOP, table)) as fh:
        op_db = json.load(fh)
    print("operator table: %s   %s" % (table, "  ".join(
        "%s prec %d %s%s" % (op, v["prec"], v["assoc"], "" if v["assoc"] == want else " (maths: %s)" % want)
        for (op, v), want in zip(op_db.items(), ("left", "left", "left", "right")))))
    if choice in ("trees", "minus-right"):
        print("##! verbatim")
        trees(table)
        print("####")
    if choice == "errors":
        print("##! verbatim")
        errors(table)
        print("####")
    if choice in ("fuzz", "minus-right"):
        fuzz(table)


if len(sys.argv) < 2 or sys.argv[1] not in ("trees", "errors", "fuzz", "minus-right"):
    print("choices: trees, errors, fuzz, minus-right")
    sys.exit(1)
main(sys.argv[1])
print("<hwut-end>")
