"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: SELECTING VARIANTS -- '--variant=gcov,slow' becomes the test
         parameters those alternatives state, merged over the base
         (RATIONALE E-9).

DESCRIPTION
       A VARIANT GROUP IS A DIMENSION of configuration; its
       alternatives configure THE SAME parameters, which is what makes
       them alternatives. Two dimensions are DISJOINT SUBSPACES, which
       is what makes them combinable:

           variant_group {
               cov  { gcov { coverage { tool = "gcov" }
                             build { coverage_target = "cov-app.exe" } }
                      llvm { coverage { tool = "llvm-cov" }
                             build { coverage_target = "app-prof.exe" } } }
               load { fast { caps { timeout_sec = 30 } }
                      slow { caps { timeout_sec = 600 } } }
           }

           --variant=gcov,slow     one alternative from each group
           --variant=gcov,llvm     REFUSED: one group, twice

       THE REFUSAL IS STRUCTURAL, decided before anything is merged:
       two names, one group. So ORDER CARRIES NO MEANING -- the
       selected alternatives cannot meet on a field, because the groups
       partitioned the space. An author who wants two alternatives at
       once has drawn his partition wrongly, and the refusal says so.

       DOUBLE SPECIFICATION IS REFUSED IN GENERAL: within a group the
       alternatives are meant to state one another's fields, and across
       groups they may not.

       AN UNKNOWN NAME REFUSES, naming what IS declared. Running the
       base configuration instead would be the green-direction failure:
       a run that measured something other than what was asked, and
       said nothing.
______________________________________________________________________________
"""
from .configuration_tree import TestParameters


class VariantError(ValueError):
    """A '--variant' selection that cannot be honoured: an unknown
    name, or two alternatives of one group."""
    pass


def name_tuple_of(text):
    """
    RETURN: tuple of str, the alternative names in a '--variant' value,
            comma separated, empty words dropped.
    """
    return tuple(word.strip() for word in text.split(",") if word.strip())


def selected_tuple(name_tuple, variant_db):
    """
    RETURN: tuple of Variant, the alternatives those names stand for,
            in the order named.

    Raises VariantError naming the first fault: a name no group
    declares (naming what is declared), or two names of ONE group
    (naming the group and both names).
    """
    variant_db = variant_db or {}
    result     = []
    group_db   = {}                      # group -> the name taken from it
    for name in name_tuple:
        variant = variant_db.get(name)
        if variant is None:
            raise VariantError(
                "no variant '%s' is declared; this tree declares %s"
                % (name, ", ".join("'%s'" % k for k in sorted(variant_db))
                         or "none"))
        standing = group_db.get(variant.group)
        if standing is not None:
            raise VariantError(
                "'%s' and '%s' are both alternatives of the variant "
                "group '%s': one group configures one subspace, so one "
                "alternative of it may stand"
                % (standing, name, variant.group))
        group_db[variant.group] = name
        result.append(variant)
    return tuple(result)


def merged_parameters(name_tuple, variant_db, base=None):
    """
    RETURN: TestParameters, 'base' with every selected variant merged
            over it -- what a variant states wins, what it leaves
            unstated keeps the base's value.
            'base' itself where no name was given.

    Raises VariantError as 'selected_tuple' does. Because the selected
    alternatives belong to distinct groups, no two of them state one
    field and the order of merging carries no meaning.
    """
    if base is None: base = TestParameters()
    for variant in selected_tuple(name_tuple, variant_db):
        base = base.merged_with(variant.parameters)
    return base


def group_db_of(variant_db):
    """
    YIELD: [0] str            a variant group's name, in name order
           [1] tuple of str   its alternatives, in name order
    """
    variant_db = variant_db or {}
    group_db   = {}
    for name, variant in variant_db.items():
        group_db.setdefault(variant.group, []).append(name)
    for group in sorted(group_db):
        yield group, tuple(sorted(group_db[group]))
