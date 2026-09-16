"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: Configuration of the compare module.

Both configurations are DATACLASSES WITH SLOTS. Two things follow, and both
are wanted:

    A DEFAULT STANDS IN THE DECLARATION. 'dataclasses.fields()' reads it
    without constructing anything, so a caller -- HWUT's relation table
    among them -- learns what compare does when nothing is stated, and
    compare restates it nowhere.

    A MISSPELT FIELD IS REFUSED. 'config.numeric_tolerence_ratio = 0.01'
    raises instead of quietly creating an attribute nothing reads, which
    left an author believing a tolerance was in force when it was not.

Assignment stays as it was: these are mutable, and every existing site that
sets a field keeps working.
________________________________________________________________________________
"""

import ast
import os
import keyword

from dataclasses import dataclass, field

from vut.engine.compare.engine.constraint_namespace import (
                                            NOT_A_VARIABLE_SET)


@dataclass(slots=True)
class ConfigurationPatternFinder:
    strip_whitespace_f:           bool  = True
    ignored_line_f:               bool  = True
    #  REGION FRAMING IS A LEXICAL FEATURE LIKE THE REST, and like the
    #  rest it can be switched off (C-4). False: '##! <handler>' and
    #  '####' are ORDINARY CONTENT, compared as they stand. A text
    #  that TALKS ABOUT framing -- a test of the region handlers, a
    #  report quoting one -- needs this, and had no way to say it.
    regions_f:              bool  = True
    analogy_f:                    bool  = True
    constraint_f:                 bool  = True   # '((name: value))' bindings
    whitespace_f:                 bool  = True
    backslash_f:                  bool  = True
    numeric_tolerance_ratio:      float = 0      # [0:1] 0=equal values; 1=any number works
    equivalent_pattern_list:      list  = field(default_factory=list)
    visible_nothing_pattern_list: list  = field(default_factory=list)
    ignored_line_begin_marker:    str   = "##"
    ignored_line_end_marker:      str   = "##"
    analogy_begin_marker:         str   = "(("
    analogy_end_marker:           str   = "))"


def _cross_check_default():
    """RETURN: bool, whether the environment asks for the cross check."""
    return os.environ.get("VUT_COMPARE_CROSS_CHECK", "") in ("1", "true",
                                                             "yes")


def _region_default():
    """RETURN: dict, the handler-scoped region defaults."""
    return {"potpourri": {"max_comparisons": 128}}


@dataclass(slots=True)
class Configuration:
    """The compare module's configuration.

    'constraint_expression_list' holds the constraints AS WRITTEN --
    "x < y + 2", "abs(z) < epsilon". 'constraint_db' relates a VARIABLE
    NAME to the constraints that must hold for it, and is derived from the
    expressions by 'derive_constraint_db()'; a binding element
    '((name: value))' in the sequential outer text enters 'name' into the
    constraint space and checks all its constraints -- see
    'engine/constraints.py'.

    'region' is handler-scoped: shebang name -> {param: value}. A shebang
    parameter ('##! potpourri max_comparisons=64') overrides the section;
    the section overrides the handler's spec default. Valid parameter
    names: see 'region/registry.py'.

    'cross_check_f' is debug mode: every 'is_equivalent' call ALSO derives
    the verdict via the Lawyer's full association and asserts agreement
    (THE LAW, see 'contract/semantics.py'). Costly; buffers input streams
    entirely. Never enable in production.
    """
    pattern_finder: ConfigurationPatternFinder = \
                            field(default_factory=ConfigurationPatternFinder)
    constraint_expression_list: list = field(default_factory=list)
    constraint_db:              dict = field(default_factory=dict)
    region:                     dict = field(default_factory=_region_default)
    cross_check_f:              bool = field(
                                        default_factory=_cross_check_default)

    def derive_constraint_db(self):
        """
        RETURN: None. 'constraint_db' is rebuilt from
                'constraint_expression_list', and 'pattern_finder.
                constraint_f' says whether any constraint stands.

        Called after the expressions are set, and by anything that hands
        compare a list of expressions rather than a database.
        """
        self.constraint_db = \
                related_variable_to_constraint_expression_db(
                                            self.constraint_expression_list)
        self.pattern_finder.constraint_f = bool(self.constraint_db)


def related_variable_to_constraint_expression_db(expression_list):
    """
    RETURN: dict, variable name -> tuple of the constraint expressions
            that mention it.

    An expression is written as it stands -- "x < y + 2",
    "abs(sin(z) - x) < epsilon" -- and names whatever variables it names.
    The relation runs BOTH WAYS: one expression may constrain several
    variables, and one variable may carry several expressions. Every
    variable an expression mentions receives it, so a binding of any one
    of them brings the whole expression up for checking.

    A malformed expression contributes nothing here and is refused where
    it is compiled ('engine/happy_constraint.py'); this function does not
    raise a second time for the same fault.

    Deriving the relation is COMPARE's work and not its caller's: a
    database assembled outside could relate a variable to an expression
    that does not mention it, and nothing would notice.
    """
    result = {}
    for expression in expression_list:
        for name in sorted(_free_name_set(expression)):
            if keyword.iskeyword(name):        continue
            if name in NOT_A_VARIABLE_SET:     continue
            result[name] = result.get(name, ()) + (expression,)
    return result


def _free_name_set(expression):
    """
    RETURN: set[str], every name the expression mentions.
            set(),    the expression does not parse.
    """
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError:
        return set()
    return {node.id for node in ast.walk(tree)
            if isinstance(node, ast.Name)}
