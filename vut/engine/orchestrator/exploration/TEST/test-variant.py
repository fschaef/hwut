#! /usr/bin/env python3
#
# @hwut {
#     title      = "Variant groups: dimensions of configuration"
#     choices    = ["declared", "refused", "selected", "vocabulary"]
#     eq-pattern = ["SUCCESS.*"]
#     interactive = true
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

VARIANT GROUPS -- 'variant_group { }' declared, '--variant=a,b'
selected (RATIONALE E-9).

CHOICES: declared, selected, refused, vocabulary;

declared    'variant_group { }' in 'hwut.conf': every group, every
            alternative, and the parameters each states. ONE NAMESPACE
            for every alternative of every group.
selected    what '--variant=gcov,slow' merges: one alternative per
            group, over the base. A variant states DIFFERENCES only;
            what it leaves unstated keeps the base's value. Order
            carries no meaning, because the groups partition the
            space.
refused     an unknown name, and two alternatives of ONE group. Both
            refused BEFORE anything merges, and both name what the
            author must fix.
vocabulary  a declaration that cannot be read: a group that is no
            scope, an alternative that is no scope, an unknown key
            inside one, and ONE NAME IN TWO GROUPS -- which would make
            '--variant' ambiguous.
______________________________________________________________________________
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

import config                                                    # noqa F401
from   config import HwutRunner                                  # noqa F401,E402

from   vut.engine.orchestrator.exploration.reader  import read_conf  # noqa E402
from   vut.engine.orchestrator.exploration.variant import (          # noqa E402
                                                    merged_parameters,
                                                    selected_tuple,
                                                    name_tuple_of,
                                                    group_db_of,
                                                    VariantError)

CONF = '''\
hwut {
    variant_group {
        cov  {
            gcov { build { executable = "cov-app.exe" }
                   caps  { memory_mb = 2048 } }
            llvm { build { executable = "app-prof.exe" }
                   caps  { memory_mb = 4096 } }
        }
        load {
            fast { caps { timeout_sec = 30 } }
            slow { caps { timeout_sec = 600 } }
        }
    }
}
'''


def banner(label):
    """RETURN: None. Section heading."""
    print()
    print("--- %s ---" % label)


def check(pair_list):
    """RETURN: True, every claim held; False, at least one did not."""
    ok = True
    for holds, claim in pair_list:
        print("  %s: %s" % ("OK  " if holds else "FAIL", claim))
        if not holds: ok = False
    return ok


def verdict(ok, sentence):
    """RETURN: None. The one closing line HWUT greps for."""
    print("%s: %s" % ("SUCCESS" if ok else "FAILURE", sentence))


def variant_db_of(text=CONF):
    """
    RETURN: [0] dict, alternative name -> Variant, as 'hwut.conf' says.
            [1] list of Fault, what the declaration got wrong.
    """
    spec, _, fault_list = read_conf(text, "hwut.conf")
    return (spec.variant_db or {}), fault_list


def refusal_of(name_text, variant_db):
    """
    RETURN: str, the refusal's own words.
            'nothing', where the selection was honoured.
    """
    try:               merged_parameters(name_tuple_of(name_text), variant_db)
    except VariantError as fault: return str(fault)
    return "nothing"


# ------------------------------------------------------------- choices

def test_declared():
    """What the declaration says."""
    variant_db, fault_list = variant_db_of()

    banner("the groups, and their alternatives")
    for group, name_tuple in group_db_of(variant_db):
        print("         %-8s %s" % (group, ", ".join(name_tuple)))

    banner("what each alternative states")
    for name in sorted(variant_db):
        variant = variant_db[name]
        target  = variant.parameters.build.executable \
                  if variant.parameters.build is not None else None
        caps    = variant.parameters.caps
        print("         %-6s of group '%-5s'  executable %-16s "
              "timeout %-6s memory %s"
              % (name, variant.group, target or "-",
                 caps.timeout_sec if caps else "-",
                 caps.memory_mb if caps else "-"))

    ok = check([
        (not fault_list, "the declaration reads without fault"),
        (sorted(variant_db) == ["fast", "gcov", "llvm", "slow"],
         "every alternative of every group stands in ONE namespace"),
        (variant_db["gcov"].group == "cov"
         and variant_db["slow"].group == "load",
         "and each knows the group it belongs to"),
        (list(group_db_of(variant_db))
         == [("cov", ("gcov", "llvm")), ("load", ("fast", "slow"))],
         "the groups are the dimensions the author drew"),
    ])
    verdict(ok, "a group is a dimension; its alternatives configure one "
                "subspace.")


def test_selected():
    """What a selection merges."""
    variant_db, _ = variant_db_of()

    banner("one alternative from each group")
    both = merged_parameters(name_tuple_of("gcov,slow"), variant_db)
    print("         --variant=gcov,slow -> executable %s  "
          "timeout %s  memory %s"
          % (both.build.executable, both.caps.timeout_sec,
             both.caps.memory_mb))

    banner("the other order says the same")
    other = merged_parameters(name_tuple_of("slow,gcov"), variant_db)
    print("         --variant=slow,gcov -> executable %s  "
          "timeout %s  memory %s"
          % (other.build.executable, other.caps.timeout_sec,
             other.caps.memory_mb))

    banner("one alone leaves the other dimension unstated")
    alone = merged_parameters(name_tuple_of("llvm"), variant_db)
    print("         --variant=llvm      -> executable %s  "
          "timeout %s" % (alone.build.executable,
                          alone.caps.timeout_sec))

    banner("no variant at all")
    none = merged_parameters((), variant_db)
    print("         --variant absent    -> build %s  caps %s"
          % (none.build, none.caps))

    ok = check([
        (both.build.executable == "cov-app.exe"
         and both.caps.timeout_sec == 600.0,
         "each dimension contributes what it states"),
        (both.caps.memory_mb == 2048,
         "and a field only one of them states survives the merge"),
        (other == both,
         "ORDER CARRIES NO MEANING: the groups partitioned the space, "
         "so the two selections cannot meet on a field"),
        (alone.caps.timeout_sec is None,
         "an unnamed dimension states nothing -- the base stands"),
        (none.build is None and none.caps is None,
         "no name, no change"),
        (len(selected_tuple(name_tuple_of("gcov,slow"), variant_db)) == 2,
         "two names, two alternatives"),
    ])
    verdict(ok, "a variant states differences; the base carries the rest.")


def test_refused():
    """What a selection may not ask for."""
    variant_db, _ = variant_db_of()

    banner("two alternatives of ONE group")
    print("         --variant=gcov,llvm")
    print("           %s" % refusal_of("gcov,llvm", variant_db))
    print("         --variant=fast,slow")
    print("           %s" % refusal_of("fast,slow", variant_db))

    banner("a name no group declares")
    print("         --variant=nope")
    print("           %s" % refusal_of("nope", variant_db))
    print("         --variant=gcov,typo")
    print("           %s" % refusal_of("gcov,typo", variant_db))

    banner("a tree that declares none")
    print("         --variant=gcov, against 'hwut { }'")
    print("           %s" % refusal_of("gcov", {}))

    ok = check([
        ("group 'cov'" in refusal_of("gcov,llvm", variant_db),
         "the refusal names the GROUP, so the author sees which "
         "dimension he asked for twice"),
        ("'gcov'" in refusal_of("gcov,llvm", variant_db)
         and "'llvm'" in refusal_of("gcov,llvm", variant_db),
         "and both alternatives"),
        ("'fast', 'gcov', 'llvm', 'slow'" in refusal_of("nope", variant_db),
         "an unknown name is answered with what IS declared"),
        (refusal_of("gcov,typo", variant_db) != "nothing",
         "a good name beside a bad one does not rescue it: the "
         "selection is refused whole, before anything merges"),
        (refusal_of("gcov,slow", variant_db) == "nothing",
         "and what is honourable is honoured"),
    ])
    verdict(ok, "the refusal is structural: two names, one group.")


def test_vocabulary():
    """A declaration that cannot be read."""
    case_list = [
        ("'variant_group' that is no scope",
         'hwut { variant_group = "gcov" }'),
        ("a group that is no scope",
         'hwut { variant_group { cov = "gcov" } }'),
        ("an alternative that is no scope",
         'hwut { variant_group { cov { gcov = "yes" } } }'),
        ("an unknown key inside an alternative",
         'hwut { variant_group { cov { gcov { bogus = 1 } } } }'),
        ("ONE NAME IN TWO GROUPS",
         'hwut { variant_group {\n'
         '    cov  { gcov { caps { timeout_sec = 30 } } }\n'
         '    load { gcov { caps { timeout_sec = 60 } } } } }'),
    ]
    banner("declarations that are refused")
    result_list = []
    for label, text in case_list:
        _, fault_list = variant_db_of(text)
        said = fault_list[0].message if fault_list else "nothing"
        print("         %-36s -> %s" % (label, said))
        result_list.append((bool(fault_list), "refused: %s" % label))

    _, twice = variant_db_of(case_list[-1][1])
    result_list.append(
        ("'cov'" in twice[0].message and "'load'" in twice[0].message,
         "the two-groups refusal names BOTH groups: every variant name "
         "is unique, so '--variant' never needs qualifying"))

    ok = check(result_list)
    verdict(ok, "what cannot be read is refused at the declaration.")


if __name__ == "__main__":
    HwutRunner(
        argv       = sys.argv,
        title      = "Variant groups: dimensions of configuration",
        choice_map = {
            "declared":   test_declared,
            "selected":   test_selected,
            "refused":    test_refused,
            "vocabulary": test_vocabulary,
        },
        happy      = "SUCCESS.*",
    ).run()
