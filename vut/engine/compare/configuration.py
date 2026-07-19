"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: Configuration of the compar module.

________________________________________________________________________________
"""

import os

from dataclasses import dataclass, field

@dataclass
class ConfigurationPatternFinder:
    strip_whitespace_f:           bool  = True
    analogy_f:                    bool  = True
    constraint_f:                 bool  = True   # '((name: value))' bindings
    whitespace_f:                 bool  = True
    backslash_f:                  bool  = True
    numeric_tolerance_ratio:      float = 0      # [0:1] 0=perfect fit; 1=any number works
    equivalent_pattern_list:      list  = field(default_factory=list)
    visible_nothing_pattern_list: list  = field(default_factory=list)
    ignored_line_begin_marker:    str   = "##"
    ignored_line_end_marker:      str   = "##"
    analogy_begin_marker:         str   = "(("
    analogy_end_marker:           str   = "))"
        
class Configuration(object):
    __slots__ = ("pattern_finder",
                 "region",
                 "constraint_db",
                 "cross_check_f")

    def __init__(self):
        self.pattern_finder = ConfigurationPatternFinder()
        # STATEFUL CONSTRAINTS: variable name -> constraint expression (or a
        # list of expressions). A binding element '((name: value))' in the
        # sequential outer text enters 'name' into the constraint space and
        # checks all its constraints -- see 'engine/constraints.py'.
        # Example: {"y": "y >= x", "t": "t > 0 and t < 100"}
        self.constraint_db = {}
        # Handler-scoped region configuration: shebang name -> {param: value}.
        # A shebang parameter ('##! potpourri max_comparisons=64') overrides
        # the section; the section overrides the handler's spec default.
        # Valid parameter names: see 'region/registry.py'.
        self.region = {
            "potpourri": {"max_comparisons": 128},
        }
        # Debug mode: every 'is_equivalent' call ALSO derives the verdict via
        # the Lawyer's full association and asserts agreement (THE LAW, see
        # 'engine/semantics.py'). Costly; buffers input streams entirely.
        # Never enable in production.
        self.cross_check_f = os.environ.get("VUT_COMPARE_CROSS_CHECK",
                                            "") in ("1", "true", "yes")


