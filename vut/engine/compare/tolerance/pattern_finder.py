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
from   vut.engine.compare.configuration          import ConfigurationPatternFinder
from   vut.engine.compare.tolerance.line_element import E_ToleranceId, \
                                                        Token, \
                                                        LineElement, \
                                                        LineElementString, \
                                                        LineElementVisibleNothing
from   vut.external.quex.typed                   import typed
from   collections import namedtuple
import regex as re
from   typeguard import typechecked

TolerancePattern = namedtuple("TolerancePattern", ("id", "pattern", "pattern_index"))

class PatternFinder:
    """Maintains a list of tolerance patterns to be found in a string.

    The '.do()' function interprets a string as a sequence of 'LineElement' 
    objects.
    """
    id_counter = 0

    @typechecked
    def __init__(self, config: ConfigurationPatternFinder):
        """Setup the tolerance pattern table according to a given configuration.
        """
        def _tolerance_pattern(tolerance_id, re_str):
            if re_str is not None: pattern = re.compile(re_str)
            else:                  pattern = None

            if tolerance_id == E_ToleranceId.EQUIVALENCE_PATTERN:
                pattern_index             = PatternFinder.id_counter
                PatternFinder.id_counter += 1
            else:
                pattern_index = None

            return TolerancePattern(tolerance_id, pattern, pattern_index)

        def _build(config):

            yield _tolerance_pattern(E_ToleranceId.STRING, None)

            for pattern in config.visible_nothing_pattern_list:
                yield _tolerance_pattern(E_ToleranceId.VISIBLE_NOTHING, pattern)

            if config.analogy_f:
                re_analogy =   re.escape(config.analogy_begin_marker) \
                             + r"([^\)]|[\)][^\)])+"                \
                             + re.escape(config.analogy_end_marker)
                yield _tolerance_pattern(E_ToleranceId.ANALOGY, re_analogy)

            if config.numeric_tolerance_ratio:
                re_number = r"-?(\d+(\.\d*)?|\.\d+)([eE][-+]?\d+)?"
                yield _tolerance_pattern(E_ToleranceId.NUMERIC, re_number)

            if config.whitespace_f:
                re_whitespace = r"[ \t]+"
                yield _tolerance_pattern(E_ToleranceId.SEPERATOR, re_whitespace)

            if config.backslash_f: # back-slash is equivalent to forward-slash
                re_backslash = r"[\\/]+"
                yield _tolerance_pattern(E_ToleranceId.EQUIVALENCE_PATTERN, re_backslash)

            for pattern_index, pattern in enumerate(config.equivalent_pattern_list):
                # If subject and nominal match the same pattern, then
                # this is sufficient to say 'equivalent'.
                yield _tolerance_pattern(E_ToleranceId.EQUIVALENCE_PATTERN, pattern)

        self.strip_whitespace_f         = config.strip_whitespace_f
        self.numeric_tolerance_ratio    = config.numeric_tolerance_ratio
        self.ignored_line_begin_marker  = config.ignored_line_begin_marker
        self.ignored_line_end_marker    = config.ignored_line_end_marker
        self.potpourri_begin_end_marker = config.potpourri_begin_end_marker

        self.table = tuple(_build(config))

    def do(self, string):
        """RETURNS: sequence of 'LineElement' objects.

        Identifies tolerance patterns in 'string' and returns a sequence of
        'LineElement' objects. A 'LineElement' object carries information about the
        tolerance type (white space, number, analogy, ...) as well as the
        position and the content of the string that matches.
        """
        def _analyze(string):
            i       = 0
            useless = set()
            while 1 + 1 == 2:
                token = _find_first_match(self.table, string, i, useless)

                if token.start is None:
                    break
                elif i != token.start:
                    yield LineElementString(i, token.start, string)

                match = LineElement.from_Token(token, string, self.numeric_tolerance_ratio)
                if match is not None:
                    yield match

                i = token.end

            if i != len(string):
                yield LineElementString(i, len(string), string)

        if self.strip_whitespace_f:
            string = string.strip()

        if self.is_irrelevant(string):
            return (LineElementVisibleNothing(0, len(string), string.rstrip()),)
        else:
            return tuple(_analyze(string))

    def is_irrelevant(self, line):
        """RETURN: True, if the line does not contain content subject to comparison.
                   False, else.
        """
        if not line:
            return True
        elif line.isspace(): 
            return True
        elif any(line.startswith(m) for m in self.ignored_line_begin_marker):
            return True
        elif any(line.endswith(m) for m in self.ignored_line_end_marker):
            return True
        else:
            return False

    def is_region_delimiter(self, line):
        """RETURNS: True, if current 'line' marks the begin/end of potpourri.
                    False, else.
        """
        line = line.strip()
        return line.startswith(self.potpourri_begin_end_marker) and len(set(line)) == 1

def _find_first_match(table, string, i, useless):
    """RETURNS: [0] Index of first tolerance patterns that matched after
                          position in string 'i'.
                    Set of indices, if more than one user pattern matches
                          on the exact same span.
                [1] Span if character indices where the pattern match.
                [2] Indices of 'equivalence patterns' that matched.
    """
    best  = Token()
    for index, tolerance in enumerate(table):
        if index in useless or tolerance.id == E_ToleranceId.STRING:
            continue
        m = tolerance.pattern.search(string, i)
        if m is None:
            useless.add(index)
        elif best.start is None:
            best.set(tolerance, m.span())     # innocense always wins
        elif m.start() < best.start:
            best.set(tolerance, m.span())     # earlier wins
        elif m.start() != best.start:
            pass                              # later looses
        elif m.end() > best.end:
            best.set(tolerance, m.span())     # longer wins
        elif m.end() < best.end:
            pass                              # shorter looses
        elif tolerance.id == E_ToleranceId.EQUIVALENCE_PATTERN:
            best.add(tolerance)               # same range => try to consider all

    return best
