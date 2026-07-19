#! /usr/bin/env python3
"""Region handlers via the shebang framing: 'verbatim', 'ignore', the
'potpourri' parameters, and the loud framing errors.

The scenarios pin DOC/SEMANTICS.txt section 7 (region-handler contract)
and the registry's syntax rules.
"""
import sys
import os
import io
import asyncio

sys.path.insert(0, os.path.join(os.path.dirname(sys.argv[0]), "../../../../"))

from vut.engine.compare.configuration   import Configuration      # noqa: E402
import vut.engine.compare.main          as     main               # noqa: E402
from vut.engine.compare.region.registry import RegionSyntaxError  # noqa: E402

if "--hwut-info" in sys.argv:
    print("Region Handlers: shebang framing, verbatim, ignore, params, errors;")
    print("CHOICES: verbatim, ignore, params, errors;")
    sys.exit()


def make_config():
    config = Configuration()
    config.pattern_finder.numeric_tolerance_ratio      = 0.1
    config.pattern_finder.visible_nothing_pattern_list = ["nothing", "nix"]
    return config


CONFIG = make_config()


async def verdict_pair(subject_txt, nominal_txt):
    """RETURNS: (bool, bool), the Judge's and the Lawyer's verdict -- THE
                LAW requires them to agree.
    """
    judge = await main.is_equivalent(CONFIG, io.StringIO(subject_txt),
                                             io.StringIO(nominal_txt))
    lawyer = await main.is_equivalent_by_association(
                                     CONFIG, io.StringIO(subject_txt),
                                             io.StringIO(nominal_txt))
    return judge, lawyer


def show(title, subject_txt, nominal_txt):
    judge, lawyer = asyncio.run(verdict_pair(subject_txt, nominal_txt))
    agree = "ok" if judge == lawyer else "LAW-BROKEN"
    print("%-42s judge: %-5s lawyer: %-5s [%s]"
          % (title + ":", judge, lawyer, agree))


def region(handler_and_params, body):
    return "##! %s\n%s####\n" % (handler_and_params, body)


if "verbatim" in sys.argv:
    V = lambda body: region("verbatim", body)
    print("## Outer text tolerates; 'verbatim' does not.")
    show("equal",              V("a 1.0\n"),      V("a 1.0\n"))
    show("numeric jitter",     V("a 1.0\n"),      V("a 1.04\n"))
    show("whitespace width",   V("a  b\n"),       V("a b\n"))
    show("visible nothing",    V("nothing\n"),    V("nix\n"))
    show("analogy symbols",    V("((A))\n"),      V("((B))\n"))
    show("order swap",         V("a\nb\n"),       V("b\na\n"))
    show("count mismatch",     V("a\n"),          V("a\nb\n"))
    print("## Insignificant lines stay insignificant (shared substrate):")
    show("blank line extra",   V("a\n\nb\n"),     V("a\nb\n"))
    show("## comment extra",   V("a\n## c\nb\n"), V("a\nb\n"))
    print("## Reference: the same jitter in OUTER text is tolerated:")
    show("outer numeric jitter", "a 1.0\n",       "a 1.04\n")

if "ignore" in sys.argv:
    I = lambda body: region("ignore", body)
    print("## Contents are exempt; the framing is not.")
    show("different contents", I("x\ny\n"),       I("totally else\n"))
    show("empty vs full",      I(""),             I("a\nb\nc\n"))
    show("framing missing",    I("x\n"),          "x\n")
    show("empty vs missing",   I(""),             "")
    show("outer after region differs", I("x\n") + "q\n", I("y\n") + "r\n")

if "params" in sys.argv:
    P = lambda p, body: region("potpourri" + p, body)
    print("## max_comparisons: shebang > config section > default.")
    show("default",            P("", "b\na\n"),   P("", "a\nb\n"))
    show("shebang param",      P(" max_comparisons=16", "b\na\n"),
                               P("", "a\nb\n"))
    print("## config section:")
    CONFIG.region["potpourri"]["max_comparisons"] = 2
    show("tight section",      P("", "b\na\n"),   P("", "a\nb\n"))
    show("shebang overrides",  P(" max_comparisons=64", "b\na\n"),
                               P("", "a\nb\n"))
    CONFIG.region["potpourri"]["max_comparisons"] = 128

if "errors" in sys.argv:
    print("## Broken framing fails LOUDLY -- never silently reinterpreted.")
    bad = [
        ("unknown handler",   "##! quacksalber\na\n####\n"),
        ("missing name",      "##!\na\n####\n"),
        ("nesting",           "##! ignore\n##! ignore\n####\n"),
        ("stray ####",        "a\n####\n"),
        ("EOF open region",   "##! verbatim\na\n"),
        ("bad param value",   "##! potpourri max_comparisons=abc\na\n####\n"),
        ("param without =",   "##! potpourri max_comparisons\na\n####\n"),
        ("unknown param",     "##! verbatim max_comparisons=1\na\n####\n"),
    ]
    for name, subject_txt in bad:
        try:
            asyncio.run(verdict_pair(subject_txt, "a\n"))
            print("%-18s -> NO ERROR (unexpected!)" % name)
        except RegionSyntaxError as e:
            print("%-18s -> %s" % (name, e))
    print("## Longer #-runs stay commentary:")
    show("##### is ignored", "#####\na\n", "a\n")
