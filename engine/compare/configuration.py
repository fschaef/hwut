
class ConfigurationPatternFinder(object):
    __slots__ = ("strip_whitespace_f",
                 "analogy_f",
                 "whitespace_f",
                 "backslash_f",
                 "numeric_tolerance_ratio",
                 "equivalent_pattern_list",
                 "visible_nothing_pattern_list",
                 "ignored_line_begin_marker",
                 "ignored_line_end_marker")
    def __init__(self):
        self.strip_whitespace_f           = True
        self.analogy_f                    = True
        self.whitespace_f                 = True
        self.backslash_f                  = True
        self.numeric_tolerance_ratio      = 0    # [0:1] 0=perfect fit; 1=any number works
        self.equivalent_pattern_list      = []
        self.visible_nothing_pattern_list = []
        self.ignored_line_begin_marker    = "##"
        self.ignored_line_end_marker      = "##"

class Configuration(object):
    __slots__ = ("pattern_finder",
                 "potpourri_max_comparison_count")

    def __init__(self):
        self.pattern_finder = ConfigurationPatternFinder()
        self.potpourri_max_comparison_count = 128


