"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: Configuration of the compar module.

________________________________________________________________________________
"""

from dataclasses import dataclass, field

@dataclass
class ConfigurationPatternFinder:
    strip_whitespace_f:           bool  = True
    analogy_f:                    bool  = True
    whitespace_f:                 bool  = True
    backslash_f:                  bool  = True
    numeric_tolerance_ratio:      float = 0      # [0:1] 0=perfect fit; 1=any number works
    equivalent_pattern_list:      list  = field(default_factory=list)
    visible_nothing_pattern_list: list  = field(default_factory=list)
    ignored_line_begin_marker:    str   = "##"
    ignored_line_end_marker:      str   = "##"
    potpourri_begin_end_marker:   str   = "||||"
    analogy_begin_marker:         str   = "(("
    analogy_end_marker:           str   = "))"
        
class Configuration(object):
    __slots__ = ("pattern_finder",
                 "potpourri_max_comparison_count")

    def __init__(self):
        self.pattern_finder = ConfigurationPatternFinder()
        self.potpourri_max_comparison_count = 128


