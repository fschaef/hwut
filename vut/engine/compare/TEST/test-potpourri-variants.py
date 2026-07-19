#! /usr/bin/env python3
"""Potpourri variants: the 'subset' and 'duplicates' flags.

Pins DOC/SEMANTICS.txt section 7.5 (POTPOURRI variants): subset (subject
may be a subset of the nominal; surplus nominal lines are legal and shown
neutrally) and duplicates (LITERAL collapse before matching; collapsed
repetitions are shown neutrally). Both flags are nominal-authoritative
and combine.
"""
import sys
import os
import io
import asyncio

sys.path.insert(0, os.path.join(os.path.dirname(sys.argv[0]), "../../../../"))

from vut.engine.compare.configuration import Configuration      # noqa: E402
import vut.engine.compare.main        as     main               # noqa: E402

if "--hwut-info" in sys.argv:
    print("Potpourri Variants: subset, duplicates;")
    print("CHOICES: subset, duplicates, combined;")
    sys.exit()


def make_config():
    config = Configuration()
    config.pattern_finder.numeric_tolerance_ratio = 0.1
    return config


CONFIG = make_config()


async def verdict_pair(subject_txt, nominal_txt):
    """RETURNS: (bool, bool), Judge and Lawyer verdict -- THE LAW requires
                agreement.
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
    print("%-44s judge: %-5s lawyer: %-5s [%s]"
          % (title + ":", judge, lawyer, agree))


def region(flags, body):
    return "##! potpourri%s\n%s####\n" % (flags, body)


if "subset" in sys.argv:
    print("## subset: every SUBJECT line needs a distinct partner; surplus")
    print("## nominal lines are legal.")
    show("proper subset",       region(" subset", "b\n"),
                                region(" subset", "a\nb\nc\n"))
    show("equal sets",          region(" subset", "b\na\n"),
                                region(" subset", "a\nb\n"))
    show("subject line unmatched", region(" subset", "x\n"),
                                region(" subset", "a\nb\n"))
    show("superset is NOT subset", region(" subset", "a\nb\nc\n"),
                                region(" subset", "a\nb\n"))
    show("duplicate needs two partners", region(" subset", "a\na\n"),
                                region(" subset", "a\nb\n"))
    show("with analogies",      region(" subset", "x ((B))\n"),
                                region(" subset", "x ((A))\ny ((C))\n"))
    show("with numeric tolerance", region(" subset", "v 1.05\n"),
                                region(" subset", "v 1.0\nw 2.0\n"))
    print("## Nominal is authoritative -- subject need not repeat the flag:")
    show("flag on nominal only", region("", "b\n"),
                                region(" subset", "a\nb\nc\n"))
    print("## Without the flag, counts must agree (unchanged):")
    show("plain potpourri",     region("", "b\n"),
                                region("", "a\nb\n"))

if "duplicates" in sys.argv:
    print("## duplicates: repetitions collapse LITERALLY before matching")
    print("## (set semantics); the collapsed lines are display-neutral.")
    show("subject repetitions collapse", region(" duplicates", "a\na\nb\n"),
                                region(" duplicates", "a\nb\n"))
    show("nominal repetitions collapse", region(" duplicates", "a\nb\n"),
                                region(" duplicates", "a\na\nb\nb\n"))
    show("sets must still agree", region(" duplicates", "a\na\n"),
                                region(" duplicates", "a\nb\n"))
    show("whitespace-normalized collapse", region(" duplicates", "a  1\na 1\n"),
                                region(" duplicates", "a 1\n"))
    print("## Without the flag, duplicates count (unchanged):")
    show("plain potpourri",     region("", "a\na\nb\n"),
                                region("", "a\nb\n"))

if "combined" in sys.argv:
    print("## subset + duplicates combine.")
    show("collapsed subject subset", region(" subset duplicates", "a\na\n"),
                                region(" subset duplicates", "a\nb\n"))
    show("violation still detected", region(" subset duplicates", "x\nx\n"),
                                region(" subset duplicates", "a\nb\n"))
