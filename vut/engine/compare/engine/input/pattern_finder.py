"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: Transform a line of text --> LineElement objects.

A 'PatternFinder' finds patterns in lines of texts and represents the text line
by a list of 'LineElement'-s (classes derived from 'LineElement').  The
understanding of a line as a sequence of 'LineElement'-s is the key for
tolerant comparison. 

 * EQUIVALENCE PATTERN: lets two strings be considered equivalent, even if 
                        they are literally not the same. 

                        Those may also defined by the user.
                        
 * NUMERIC PATTERN: may only require a certain numeric precission for 
                    equivalence. 
                    
 * ANALOGY: pattern allows for different strings to appear, as long as it is 
            always the same strings and their counterpart.

 * SLASH: the exact number of characters of that type is unimportant for 
          equivalence. The 'slash' pattern helps with output of file names 
          under different operating systems.

 * SEPERATOR: not under consideration for comparison, but sperates elements
              of the line.

 * VISIBLE_NOTHING: is completely ignored during equivalence considerations.

 Additionally, there are further configuration options:

 * .strip_whitespace_f:        
    cuts the whitespace at the begin/end of each line.

 * .numeric_tolerance_ratio:   
    defines the precision for NUMERIC.

 * .ignored_line_begin_marker, .ignored_line_end_marker:   
    define a marker at the for the begin/end of a line. If such a marker appears 
    the line is ignored.

The 'PatternFinder' serves as lexical analyzer for 'chunk_pipe.py'.
________________________________________________________________________________
"""
import regex as re
from functools import lru_cache
from itertools import count
from typing import Iterable, Tuple, FrozenSet

from vut.engine.compare.configuration import ConfigurationPatternFinder
from vut.engine.compare.engine.input.line_element import (E_ToleranceId,
                                                   TolerancePattern,
                                                   LineElement,
                                                   LineElementString,
                                                   LineElementVisibleNothing)

class PatternFinder:
    """Maintains a master regex to identify all tolerance patterns in one pass.
    Optimized for high-frequency matching using LRU caching for overlapping patterns.
    """
    def __init__(self, config: ConfigurationPatternFinder):
        """Setup the tolerance pattern table and compile the master regex.
        """
        # Local counter for equivalence pattern IDs
        equiv_id_gen = count(0)
        # Mapping group names (G0, G1...) back to the metadata needed for LineElements
        self._group_map = {}
        re_parts = []

        self._analogy_extractor_re = None
        self._whitespace_re        = re.compile(r"\s+")
        if config.analogy_f:
            b = re.escape(config.analogy_begin_marker)
            e = re.escape(config.analogy_end_marker)
            
            # Extractor: Capture content BETWEEN markers
            # Pattern: marker_begin + (captured_content) + marker_end
            self._analogy_extractor_re = re.compile(f"{b}(.*?){e}")

        def _register(tol_id, re_str):
            if not re_str: return
            group_name = f"G{len(self._group_map)}"
            p_idx = next(equiv_id_gen) if tol_id == E_ToleranceId.EQUIVALENCE_PATTERN else None
            
            # Create metadata object (still used for 'table' and group mapping)
            tp = TolerancePattern(tol_id, re.compile(re_str), p_idx)
            self._group_map[group_name] = tp
            
            # Add to the master regex parts
            re_parts.append(f"(?P<{group_name}>{re_str})")

        # 1. Base String (Metadata only)
        self._group_map["BASE"] = TolerancePattern(E_ToleranceId.STRING, None, None)

        # 1. Register patterns 
        for pattern in config.visible_nothing_pattern_list:
            _register(E_ToleranceId.VISIBLE_NOTHING, pattern)

        if config.analogy_f:
            b, e = re.escape(config.analogy_begin_marker), re.escape(config.analogy_end_marker)
            _register(E_ToleranceId.ANALOGY, f"{b}(?:.|\\n)+?{e}")

        if config.numeric_tolerance_ratio:
            # (?<!\w) -- at front: look behind: no 'word character directly before'
            #            at back:  look ahead: no 'word character directly after'
            _register(E_ToleranceId.NUMERIC, r"(?<!\w)-?(\d+(\.\d*)?|\.\d+)([eE][-+]?\d+)?(?!\w)")

        if config.whitespace_f:
            _register(E_ToleranceId.SEPERATOR, r"\s+")

        if config.backslash_f:
            _register(E_ToleranceId.EQUIVALENCE_PATTERN, r"[\\/]+")

        for pattern in config.equivalent_pattern_list:
            _register(E_ToleranceId.EQUIVALENCE_PATTERN, pattern)

        # Pre-filter equivalence patterns for the secondary overlap check
        self._equiv_patterns = tuple(
            (tp.pattern_index, tp.pattern)
            for tp in self._group_map.values()
            if tp.id == E_ToleranceId.EQUIVALENCE_PATTERN and tp.pattern is not None
        )

        # Configuration state
        self.backslash_f                = config.backslash_f
        self.strip_whitespace_f         = config.strip_whitespace_f
        self.whitespace_f               = config.whitespace_f
        self.numeric_tolerance_ratio    = config.numeric_tolerance_ratio
        self.ignored_line_begin_marker  = config.ignored_line_begin_marker
        self.ignored_line_end_marker    = config.ignored_line_end_marker
        self.potpourri_begin_end_marker = config.potpourri_begin_end_marker

        # Master Regex Compilation
        # <= One master regular expression where particular
        #    expressions are identified by group name: "(?P<{group_name}>{re_str})"
        master_str = "|".join(re_parts) if re_parts else r"$.^"
        self.master_re = re.compile(master_str)

        self.table = tuple(self._group_map.values()) if hasattr(self, '_group_map') else tuple(self._group_map.values())

    @lru_cache(maxsize=2048)
    def _get_matching_pattern_indices(self, matched_text: str, primary_idx: int) -> FrozenSet[int]:
        """
        Finds all equivalence pattern indices that match the text.
        The master regex only tells us ONE group that matched. This method
        checks the others and caches the result.
        """
        indices = {primary_idx}
        for p_idx, p_re in self._equiv_patterns:
            if p_idx != primary_idx and p_re.fullmatch(matched_text):
                indices.add(p_idx)
        return frozenset(indices)

    def do(self, string: str) -> Tuple[LineElement, ...]:
        """RETURNS: sequence of 'LineElement' objects.

        Identifies tolerance patterns in 'string' and returns a sequence of
        'LineElement' objects. A 'LineElement' object carries information about the
        tolerance type (white space, number, analogy, ...) as well as the
        position and the content of the string that matches.
        """
        if self.strip_whitespace_f:
            string = string.strip()

        if self.is_irrelevant(string):
            return (LineElementVisibleNothing(string.rstrip()),)

        result = []
        last_idx = 0
        
        for m in self.master_re.finditer(string):
            start, end = m.span()
            
            # Add text between matches
            if start > last_idx:
                result.append(LineElementString(string[last_idx:start]))

            group_name = m.lastgroup
            tolerance = self._group_map[group_name]
            
            pattern_indices = None
            if tolerance.id == E_ToleranceId.EQUIVALENCE_PATTERN:
                # Use the cached overlap checker
                pattern_indices = self._get_matching_pattern_indices(m.group(), tolerance.pattern_index)

            match_obj = LineElement.from_match(
                tolerance.id, 
                m.group(), 
                self.numeric_tolerance_ratio, 
                pattern_i_set=pattern_indices
            )
            
            if match_obj:
                result.append(match_obj)
            
            last_idx = end

        # Add remaining text
        if last_idx < len(string):
            result.append(LineElementString(string[last_idx:]))

        return tuple(result)

    def uniform(self, line):
        if self.strip_whitespace_f: line = line.strip()
        if self.whitespace_f:       line = self._whitespace_re.sub(" ", line)
        if self.backslash_f:        line = line.replace("\\", "/")
        return line

    def is_irrelevant(self, line):
        """RETURN: True, if the line does not contain content subject to comparison.
        """
        if not line: return True
        if line.isspace(): return True
        # startswith/endswith support single string or tuple of strings
        if line.startswith(self.ignored_line_begin_marker): return True
        if line.endswith(self.ignored_line_end_marker): return True
        return False

    def is_region_delimiter(self, line: str) -> bool:
        """RETURNS: True, if current 'line' marks the begin/end of potpourri.
        """
        line = line.strip()
        return line.startswith(self.potpourri_begin_end_marker) and len(set(line)) == 1

    def has_analogy(self, line: str) -> bool:
        """RETURNS: True, if line contains an analogy.
                    False, else.
        """
        if self._analogy_extractor_re is None: return False
        return bool(self._analogy_extractor_re.search(line))

    def extract_analogy_strings(self, line: str) -> Iterable[str]:
        """RETURNS: List of strings found inside analogy markers.
        Example: "A ((quick)) brown ((fox))" -> ['quick', 'fox']
        """
        if self._analogy_extractor_re is None: return []
        # .findall() returns the contents of the capturing group (.*?)
        return self._analogy_extractor_re.findall(line)

