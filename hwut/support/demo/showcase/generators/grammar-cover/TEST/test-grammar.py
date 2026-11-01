#! /usr/bin/env python3
# @hwut {
#     title    = "Service shell: commands generated from its grammar, every alternative in every context"
#     features = ["accepts-grammar"]
#     choices {
#         covering     { features = ["accepts-grammar", "full-coverage"]
#                        tolerance { constraints = ["refused == 0", "holes == 0"] } }
#         covering-1.4 { features = ["accepts-grammar", "full-coverage", "bug-found"]
#                        tolerance { constraints = ["refused > 0", "holes == 0"] } }
#         uniform-1.4  { features = ["accepts-grammar", "hole-named"]
#                        tolerance { constraints = ["holes > 0"] } }
#     }
# }
"""
______________________________________________________________________________
SUBJECT  the commands generated from the shell's grammar, the shell's
         (../shell*.awk) answer to each, and which alternatives each context
         saw
REQUIREMENT  The service shell answers OK to every sentence of its command
             grammar ('../grammar.py'), and the generated commands of the
             nightly smoke test exercise EVERY alternative of the grammar
             in EVERY context it can appear in ('key' after 'set', after
             'get' and after 'reset' are three things to the shell).

The unit is awk: '../shell.awk', and '../shell_1_4.awk' (release 1.4, which
forgot 'parity none'). The generator walks '../grammar.py' from 'command'.

THE GENERATOR INSTRUCTION -- the grammar is the description of the tested
space; the walk says how the space is sampled:

    stream = DeterministicStream(2)
    at every SITE:  alternative = stream.select_unchosen(GRAMMAR[N], marker[site])
    site = the nonterminal N in its context: the chain of alternatives
           that led to it ('set key value -> <key>',
           'reset target -> key -> <key>')

One SelectionMarker per site: each site hands out every one of its
alternatives once before any repeats. A marker per NONTERMINAL would count
'key' as covered whatever command it came with -- and never say 'reset
baud'. The budget follows from the grammar: a site is visited exactly
once per round of the products of the alternative counts on its path, so
the budget is the largest such product -- 'reset target -> key -> <key>' needs
3 x 3 x 4 = 36 commands. The test computes and prints it: written down,
not hoped for.

covering      shell 1.5 + select_unchosen: all commands OK, every site
              exercises every alternative. Laws 'refused == 0' and
              'holes == 0'.
covering-1.4  shell 1.4 + the same walk: 'set ... none' comes up (it must)
              and is answered ERR -- the bug is found. Laws 'refused > 0',
              'holes == 0'.
uniform-1.4   shell 1.4 + stream.select (uniform, same seed, same budget):
              this walk happens to meet 'none', but two sites keep a hole
              ('get baud' and 'reset stop' never generated): what it found
              was luck, what it missed is unknown. The GOOD is the
              accepted report of the holes; law 'holes > 0'. Seed 2 is no
              trick: the sweep line shows that most seeds leave a hole
              with 'select', none with 'select_unchosen'.

HOW TO READ THE GOOD   The commands with the shell's answer, then one
table per site: count and bar per alternative; '!! never' marks a hole.
All exact: the stream is deterministic, so are the commands. The counts
of refused commands and holes are bindings, judged by the laws above.
______________________________________________________________________________
"""
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.realpath(os.path.join(
    os.path.dirname(os.path.realpath(shutil.which("hwut"))), "..", "..")))
from hwut.test_writing_support.python.deterministic_random import (DeterministicStream,
                                                                   SelectionMarker)

HERE = os.path.dirname(os.path.abspath(__file__))
UNIT = os.path.join(HERE, "..")
sys.path.insert(0, UNIT)
from grammar import GRAMMAR

SEED, SWEEP = 2, 200
CHOICE_DB = {"covering": ("shell.awk", True), "covering-1.4": ("shell_1_4.awk", True),
             "uniform-1.4": ("shell_1_4.awk", False)}


def label(alternative):
    return " ".join(s.lstrip("'") for s in alternative) or "(nothing)"


def sites(symbol="command", path=(), rounds=1):
    """Every selection site below 'symbol': (path, nonterminal, rounds), where
    'rounds' is the product of the alternative counts down to and including it."""
    alternatives = GRAMMAR[symbol]
    if len(alternatives) > 1:
        rounds *= len(alternatives)
        yield path, symbol, rounds
    for a in alternatives:
        for s in a:
            if not s.startswith("'"):
                yield from sites(s, path + (label(a),) if len(alternatives) > 1 else path, rounds)


SITES = list(sites())
BUDGET = max(r for _, _, r in SITES)


def site_name(path, symbol):
    return " -> ".join(path + ("<%s>" % symbol,))


def generate(prefer_unchosen, seed=None):
    stream = DeterministicStream(SEED if seed is None else seed)
    marker = dict(((p, n), SelectionMarker()) for p, n, _ in SITES)
    count = dict(((p, n), dict((id(a), 0) for a in GRAMMAR[n])) for p, n, _ in SITES)

    def expand(symbol, path):
        if symbol.startswith("'"):
            return [symbol[1:]]
        alternatives = GRAMMAR[symbol]
        if len(alternatives) == 1:
            return [w for s in alternatives[0] for w in expand(s, path)]
        site = (path, symbol)
        if prefer_unchosen: alternative = stream.select_unchosen(alternatives, marker[site])
        else:               alternative = stream.select(alternatives)
        count[site][id(alternative)] += 1
        return [w for s in alternative for w in expand(s, path + (label(alternative),))]

    return [" ".join(expand("command", ())) for _ in range(BUDGET)], count


def main(choice):
    script, prefer_unchosen = CHOICE_DB[choice]
    commands, count = generate(prefer_unchosen)
    answers = subprocess.run(["awk", "-f", os.path.join(UNIT, script)], input="\n".join(commands) + "\n",
                             capture_output=True, text=True, check=True).stdout.splitlines()
    print("unit:      ../%s" % script)
    print("generator: DeterministicStream(%d).%s per site"
          % (SEED, "select_unchosen(alternatives, marker[site])" if prefer_unchosen
             else "select(alternatives)"))
    path, symbol, rounds = max(SITES, key=lambda x: x[2])
    print("budget:    %d commands = the alternatives multiplied along the deepest site, '%s'"
          % (BUDGET, site_name(path, symbol)))
    print()
    half = (len(commands) + 1) // 2
    cells = ["%2d  %-18s -> %-9s %s" % (i + 1, c, a, "!!" if a != "OK" else "  ")
             for i, (c, a) in enumerate(zip(commands, answers))]
    for left, right in zip(cells[:half], cells[half:] + [""]):
        print(("  %s      %s" % (left, right)).rstrip())
    print()
    holes = []
    for path, n, _ in SITES:
        print("  %s:" % site_name(path, n))
        for a in GRAMMAR[n]:
            c = count[(path, n)][id(a)]
            if c == 0:
                holes.append("%s -> %s" % (site_name(path, n), label(a)))
            print("      %-14s %3d  %s" % (label(a), c, "#" * c if c else "!! never"))
    print()
    def holes_of(seed, unchosen):
        return sum(1 for site in SITES for c in generate(unchosen, seed)[1][site[:2]].values() if c == 0)
    print("seeds 1..%d, %d commands each -- walks that leave a hole: select %d of %d, select_unchosen %d of %d"
          % (SWEEP, BUDGET, sum(holes_of(k, False) > 0 for k in range(1, SWEEP + 1)), SWEEP,
             sum(holes_of(k, True) > 0 for k in range(1, SWEEP + 1)), SWEEP))
    print()
    errors = [c for c, a in zip(commands, answers) if a != "OK"]
    for c in sorted(set(errors), key=errors.index):
        n = errors.count(c)
        print("!! the shell refuses a sentence of its grammar: '%s'%s" % (c, " x%d" % n if n > 1 else ""))
    for h in holes:
        print("!! coverage hole: %s was never generated" % h)
    law = lambda n: "law == 0   %s" % ("kept" if n == 0 else "BROKEN")
    print("commands refused ((refused: %d))   %s" % (len(errors), law(len(errors))))
    print("alternatives never generated at their site ((holes: %d))   %s" % (len(holes), law(len(holes))))


if __name__ == "__main__":
    choice = sys.argv[1] if len(sys.argv) > 1 else ""
    if choice not in CHOICE_DB:
        print("choices: %s" % ", ".join(CHOICE_DB))
        sys.exit(1)
    main(choice)
    print("<hwut-end>")
