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
from    vut.engine.compare.configuration          import ConfigurationPatternFinder
from    vut.engine.compare.tolerance.line_element import E_ToleranceId, \
                                                         TolerancePattern, \
                                                         LineElement, \
                                                         LineElementString, \
                                                         LineElementVisibleNothing
import  regex as re
from    typeguard import typechecked
from    itertools   import count

class PatternFinder:
    """Maintains a master regex to identify all tolerance patterns in one pass.
    """
    @typechecked
    def __init__(self, config: ConfigurationPatternFinder):
        """Setup the tolerance pattern table and compile the master regex.
        """
        # Local counter for equivalence pattern IDs
        equiv_id_gen = count(0)
        # Mapping group names (G0, G1...) back to the metadata needed for LineElements
        self._group_map = {}
        re_parts = []

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

        # 2. Register patterns in priority order (Specific -> General)
        for pattern in config.visible_nothing_pattern_list:
            _register(E_ToleranceId.VISIBLE_NOTHING, pattern)

        if config.analogy_f:
            b, e = re.escape(config.analogy_begin_marker), re.escape(config.analogy_end_marker)
            _register(E_ToleranceId.ANALOGY, f"{b}(?:.|\\n)+?{e}")

        if config.numeric_tolerance_ratio:
            _register(E_ToleranceId.NUMERIC, r"-?(\d+(\.\d*)?|\.\d+)([eE][-+]?\d+)?")

        if config.whitespace_f:
            _register(E_ToleranceId.SEPERATOR, r"[ \t]+")

        if config.backslash_f:
            _register(E_ToleranceId.EQUIVALENCE_PATTERN, r"[\\/]+")

        for pattern in config.equivalent_pattern_list:
            _register(E_ToleranceId.EQUIVALENCE_PATTERN, pattern)

        # Config state
        self.strip_whitespace_f         = config.strip_whitespace_f
        self.numeric_tolerance_ratio    = config.numeric_tolerance_ratio
        self.ignored_line_begin_marker  = config.ignored_line_begin_marker
        self.ignored_line_end_marker    = config.ignored_line_end_marker
        self.potpourri_begin_end_marker = config.potpourri_begin_end_marker

        # Master Regex Compilation
        master_str = "|".join(re_parts) if re_parts else r"$.^" 
        self.master_re = re.compile(master_str)

        # Legacy 'table' support for external visibility/unit tests
        self.table = tuple(self._group_mapping.values()) if hasattr(self, '_group_mapping') else tuple(self._group_map.values())

    def do(self, string):
        """RETURNS: sequence of 'LineElement' objects.

        Identifies tolerance patterns in 'string' and returns a sequence of
        'LineElement' objects. A 'LineElement' object carries information about the
        tolerance type (white space, number, analogy, ...) as well as the
        position and the content of the string that matches.
        """
        if self.strip_whitespace_f:
            string = string.strip()

        if self.is_irrelevant(string):
            return (LineElementVisibleNothing(0, len(string), string.rstrip()),)

        def _analyze_optimized(string):
            i = 0
            for m in self.master_re.finditer(string):
                start, end = m.span()
                
                if i < start: # Changed != to < for safety
                    yield LineElementString(i, start, string)

                # Correctly handle multiple equivalence groups
                pattern_indices = None
                tolerance = self._group_map[m.lastgroup]
                
                if tolerance.id == E_ToleranceId.EQUIVALENCE_PATTERN:
                    matched_text = m.group()
                    # Re-scan the table to find all overlapping equivalence IDs
                    pattern_indices = {
                        tp.pattern_index for tp in self._group_map.values()
                        if tp.id == E_ToleranceId.EQUIVALENCE_PATTERN and 
                        tp.pattern and tp.pattern.fullmatch(matched_text)
                    }

                match = LineElement.from_match(tolerance, m, string, 
                                               self.numeric_tolerance_ratio, 
                                               pattern_i_set=pattern_indices)
                if match:
                    yield match
                
                i = end

            if i < len(string):
                yield LineElementString(i, len(string), string)

        return tuple(_analyze_optimized(string))

    def is_irrelevant(self, line):
        """RETURN: True, if the line does not contain content subject to comparison.
        """
        if not line: return True
        if line.isspace(): return True
        # startswith/endswith support single string or tuple of strings
        if line.startswith(self.ignored_line_begin_marker): return True
        if line.endswith(self.ignored_line_end_marker): return True
        return False

    def is_region_delimiter(self, line):
        """RETURNS: True, if current 'line' marks the begin/end of potpourri.
        """
        line = line.strip()
        return line.startswith(self.potpourri_begin_end_marker) and len(set(line)) == 1

