#! /usr/bin/env python3
#
# @hwut {
#     title      = "Stateful Constraints: bindings, space, dependencies, errors"
#     choices    = ["basic", "deps", "errors", "lawyer", "strings"]
# }
#
"""STATEFUL CONSTRAINTS: '((name: value))' bindings + Configuration.constraint_db.

Pins DOC/SEMANTICS.txt section 10: check-on-entry into the constraint
space; subject-side violation = red cell (verdict False, never loud);
nominal-side violation = loud ConstraintSpecError (asymmetry); missing
dependency / division by zero / any evaluation failure = red; static
circularity pre-check = loud; order-free scopes (potpourri, unordered/key
tables) reject nominal bindings loudly; Judge/Lawyer reachability of loud
errors is mirrored (THE LAW).
"""
import sys
import os
import io
import asyncio

sys.path.insert(0, os.path.join(os.path.dirname(sys.argv[0]), "../../../../"))

from vut.engine.compare.configuration      import Configuration      # noqa: E402
import vut.engine.compare.main             as     main               # noqa: E402
from vut.engine.compare.engine.constraints import ConstraintSpecError, \
                                                  ConstraintDb        # noqa: E402
from vut.engine.compare.region.registry    import RegionSyntaxError  # noqa: E402

if "--hwut-info" in sys.argv:
    print("Stateful Constraints: bindings, space, dependencies, errors;")
    print("CHOICES: basic, deps, strings, lawyer, errors;")
    sys.exit()


def make_config(constraint_db):
    config = Configuration()
    config.constraint_db = constraint_db
    return config


async def verdict_pair(config, subject_txt, nominal_txt):
    """RETURNS: (judge, lawyer) -- each True/False, or 'type-name!' if the
                face raised. THE LAW requires identical entries.
    """
    async def run(f):
        try:
            return await f(config, io.StringIO(subject_txt),
                                   io.StringIO(nominal_txt))
        except (ConstraintSpecError, RegionSyntaxError) as e:
            return "%s!" % e.__class__.__name__
    return (await run(main.is_equivalent),
            await run(main.is_equivalent_by_association))


def show(title, constraint_db, subject_txt, nominal_txt):
    config = make_config(constraint_db)
    judge, lawyer = asyncio.run(verdict_pair(config, subject_txt,
                                                     nominal_txt))
    agree = "ok" if judge == lawyer else "LAW-BROKEN"
    print("%-46s judge: %-25s lawyer: %-25s [%s]"
          % (title + ":", judge, lawyer, agree))


if "basic" in sys.argv:
    print("## Check-on-entry: the moment a variable enters, its constraints run.")
    DB = {"t": "t > 0 and t < 100"}
    show("no bindings at all",  DB, "hello\n",           "hello\n")
    show("binding holds",       DB, "start ((t: 12))\n", "start ((t: 7))\n")
    show("subject violates",    DB, "start ((t: 812))\n","start ((t: 7))\n")
    show("value free if legal", DB, "start ((t: 99))\n", "start ((t: 1))\n")
    show("name mismatch",       DB, "start ((u: 12))\n", "start ((t: 7))\n")
    show("binding vs plain",    DB, "start 12\n",        "start ((t: 7))\n")
    print("## An unconstrained variable enters freely (it may serve as input).")
    show("unconstrained var",   DB, "level ((x: 3))\n",  "level ((x: 9))\n")
    print("## Empty constraint_db: bindings still compare by name, no checks.")
    show("no db, names equal",  {}, "a ((t: 812))\n",    "a ((t: 7))\n")
    show("no db, names differ", {}, "a ((u: 812))\n",    "a ((t: 7))\n")
    print("## Sequentiality: entries after the abort point are not processed.")
    show("mismatch shields late binding",
         {"t": "t > 0"},
         "AAA\nz ((t: -5))\n",
         "BBB\nz ((t: 1))\n")


if "deps" in sys.argv:
    print("## Constraints in terms of each other; values develop in line order.")
    DB = {"y": "y >= x"}
    show("dep satisfied",  DB, "a ((x: 3))\nb ((y: 7))\n",
                               "a ((x: 1))\nb ((y: 2))\n")
    show("dep violated",   DB, "a ((x: 9))\nb ((y: 7))\n",
                               "a ((x: 1))\nb ((y: 2))\n")
    print("## Missing dependency on the NOMINAL side: broken spec (loud).")
    show("dep missing in nominal too", DB,
         "b ((y: 7))\na ((x: 3))\n",
         "b ((y: 2))\na ((x: 1))\n")
    print("## Missing dependency hit by the SUBJECT alone (short-circuit): red.")
    DBS = {"y": "y == 2 or y >= x"}
    show("dep missing, subject only", DBS,
         "b ((y: 7))\n",
         "b ((y: 2))\n")
    print("## Later entries see updated values (monotonic steps).")
    DB2 = {"s": "s > p", "p": "p >= 0"}
    show("monotone ok",    DB2, "((p: 0)) then ((s: 1)) then\n",
                                "((p: 0)) then ((s: 5)) then\n")
    show("monotone broken",DB2, "((p: 4)) then ((s: 1)) then\n",
                                "((p: 0)) then ((s: 5)) then\n")
    print("## ANY evaluation failure is red, never loud (subject side):")
    DBZ = {"q": "1 / q > 0.1"}
    show("division by zero", DBZ, "v ((q: 0))\n", "v ((q: 2))\n")
    show("type clash",       DBZ, "v ((q: \"txt\"))\n", "v ((q: 2))\n")


if "strings" in sys.argv:
    print("## Quoted-string values; Python string functions in constraints.")
    DB = {"mode": "mode.startswith(\"run-\") and len(mode) < 12",
          "tag":  "tag.lower() == mode.replace(\"run-\", \"\")"}
    show("strings hold", DB,
         "m ((mode: \"run-fast\"))\nt ((tag: \"FAST\"))\n",
         "m ((mode: \"run-slow\"))\nt ((tag: \"slow\"))\n")
    show("prefix violated", DB,
         "m ((mode: \"walk-fast\"))\n",
         "m ((mode: \"run-slow\"))\n")
    show("cross-var string dep violated", DB,
         "m ((mode: \"run-fast\"))\nt ((tag: \"slow\"))\n",
         "m ((mode: \"run-slow\"))\nt ((tag: \"slow\"))\n")
    print("## Number vs string in the same variable: evaluation failure = red.")
    show("kind drift", {"v": "v > 0"},
         "a ((v: \"high\"))\n", "a ((v: 3))\n")


if "lawyer" in sys.argv:
    print("## The Lawyer's cells: a violating binding is a red MISMATCH row.")
    config = make_config({"t": "t > 0 and t < 100"})

    async def cells(subject_txt, nominal_txt):
        async for chunk_pair in main.associate(config,
                                               io.StringIO(subject_txt),
                                               io.StringIO(nominal_txt)):
            for line_pair in chunk_pair:
                print("   equivalent=%-5s  subject_line_n=%2s nominal_line_n=%2s"
                      % (line_pair.is_equivalent(),
                         line_pair.subject_line_n, line_pair.nominal_line_n))

    print("-- subject violation on line 2 (red), line 3 shielded (space dead):")
    asyncio.run(cells("ok\nx ((t: 666))\ny ((t: 777))\n",
                      "ok\nx ((t: 5))\ny ((t: 6))\n"))
    print("-- all constraints hold (all rows green):")
    asyncio.run(cells("ok\nx ((t: 66))\n",
                      "ok\nx ((t: 5))\n"))


if "errors" in sys.argv:
    print("## Static checks are LOUD at build time (broken specification).")

    def loud(title, constraint_db):
        try:
            ConstraintDb(constraint_db)
            print("%-46s -no error-" % (title + ":"))
        except ConstraintSpecError as e:
            print("%-46s ConstraintSpecError: %s" % (title + ":", e))

    loud("unparseable",    {"a": "a >== 1"})
    loud("free input name is NOT static",  {"a": "a > free_input"})
    loud("forbidden call", {"a": "__import__(\"os\")"})
    loud("forbidden node", {"a": "[a for a in (1,)]"})
    loud("bad attribute",  {"a": "a.__class__"})
    loud("cycle a->b->a",  {"a": "a > b", "b": "b > a"})
    loud("cycle 3-long",   {"a": "a > b", "b": "b > c", "c": "c > a"})
    loud("self-ref is ok", {"a": "a > 0 and a < a + 1"})
    loud("list of constraints", {"a": ["a > 0", "a < 10"]})

    print("## Nominal violating its OWN constraint: loud (asymmetry rule).")
    show("nominal violates", {"t": "t > 0"},
         "v ((t: 5))\n", "v ((t: -1))\n")
    print("## ... but not if it sits BEHIND the abort point (reachability):")
    show("nominal violation shielded", {"t": "t > 0"},
         "AAA\nv ((t: 5))\n", "BBB\nv ((t: -1))\n")

    print("## Order-free scopes reject NOMINAL bindings loudly.")
    show("potpourri nominal binding", {"t": "t > 0"},
         "##! potpourri\na\n####\n",
         "##! potpourri\na ((t: 1))\n####\n")
    show("potpourri subject binding = red", {"t": "t > 0"},
         "##! potpourri\na ((t: 1))\n####\n",
         "##! potpourri\na\n####\n")
    show("unordered table nominal binding", {"t": "t > 0"},
         "##! table unordered\na 1\n####\n",
         "##! table unordered\na ((t: 1))\n####\n")
    show("key table nominal binding", {"t": "t > 0"},
         "##! table key=0\na 1\n####\n",
         "##! table key=0\na ((t: 1))\n####\n")
    print("## Ordered tables never tolerance-lex: a binding is inert text.")
    show("ordered table binding inert", {"t": "t > 0"},
         "##! table\na ((t: -5))\n####\n",
         "##! table\na ((t: -5))\n####\n")
