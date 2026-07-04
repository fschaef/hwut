"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

Maps locations in generated Luau back to locations in the original rule file.

Luau has no '#line' pragma, so provenance is tracked out of band. The transpiler
emits target text as a sequence of pieces: boilerplate it generates itself, and
fragments copied verbatim from the rule file. For every emitted fragment the
transpiler registers an interval; a lookup then resolves a target (line, column)
to the original (file, line, column), or to None when the target location lies
in generated boilerplate.

MODEL:

    Registration is sequential, in emission order. The mapper keeps a running
    target-line cursor, so the caller never computes target line numbers itself:
    it announces how many target lines each piece occupies (advance) and, for
    fragments, registers the source mapping for the lines just emitted.

    A fragment occupies the SAME number of target lines as source lines and in
    the same order (verbatim copy). That invariant makes the per-line map linear:

        source_line = target_line - target_base + source_base

    Columns shift because the fragment is indented and may sit behind a prefix
    on its first line (e.g. a guard emitted as 'if <fragment> then'). Two deltas
    capture this:

        first_line:  source_col = target_col - (indent + first_line_prefix)
        other lines: source_col = target_col -  indent

    A target line in no registered interval (boilerplate, blank lines, provenance
    comments) maps to None: it has no original, and reporting it as the nearest
    fragment would misattribute transpiler bugs to author code.
______________________________________________________________________________
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class SourceLocation:
    """A resolved point in the original rule file."""
    file:   str
    line:   int
    column: int


@dataclass(frozen=True)
class _Interval:
    """One emitted fragment's target span and its source mapping.

    Covers target lines [target_base, target_base + length). Maps linearly to
    source lines starting at source_base in 'source_file'. 'indent' is the column
    at which every emitted line of the fragment begins; 'first_line_prefix' is
    the extra width emitted before the fragment on its first line only (0 when
    the fragment starts its own line).
    """
    target_base:       int
    length:            int
    source_file:       str
    source_base:       int
    indent:            int
    first_line_prefix: int

    def contains(self, target_line):
        """RETURN: True,  if 'target_line' falls in this interval.
                  False, otherwise.
        """
        return self.target_base <= target_line < self.target_base + self.length

    def resolve(self, target_line, target_column):
        """RETURN: SourceLocation, 'target_line'/'column' mapped to source.

        Assumes 'contains(target_line)'. The column delta uses the first-line
        prefix only on the interval's first line.
        """
        offset      = target_line - self.target_base
        source_line = self.source_base + offset
        if offset == 0:
            source_col = target_column - self.indent - self.first_line_prefix
        else:
            source_col = target_column - self.indent
        if source_col < 0:
            source_col = 0
        return SourceLocation(file=self.source_file,
                              line=source_line, column=source_col)


class Source2TargetLocationMapper:
    """Builds, in emission order, the map from target Luau back to source.

    The caller drives this as it emits: 'advance' for generated boilerplate,
    'register_fragment' for a verbatim fragment copy. 'source_line_of' then
    answers lookups after emission is complete.
    """
    def __init__(self):
        """RETURN: None. Empty map, target cursor at line 0."""
        self._cursor    = 0    # next unused target line
        self._intervals = []   # sorted by target_base (emission order)

    @property
    def target_line_count(self):
        """RETURN: int, the number of target lines emitted so far."""
        return self._cursor

    def advance(self, line_count):
        """RETURN: None. Account for 'line_count' generated target lines.

        Use for boilerplate, blank lines, and provenance comments -- anything
        with no source origin. Advances the cursor without registering a
        mapping, so those lines resolve to None.
        """
        if line_count < 0:
            raise ValueError("line_count must be >= 0")
        self._cursor += line_count

    def register_fragment(self, source_file, source_line, length,
                          indent=0, first_line_prefix=0):
        """RETURN: int, the target line at which the fragment was placed.

        Registers a verbatim fragment of 'length' target lines at the current
        cursor, mapping them to source lines [source_line, source_line+length)
        in 'source_file'. 'indent' is the emit indentation; 'first_line_prefix'
        is any prefix emitted before the fragment on its first line (e.g. 3 for
        'if '). Advances the cursor by 'length'.

        The 'length == source line count' invariant is the caller's
        responsibility: a fragment must be copied verbatim and contiguously, or
        the linear map is void.
        """
        if length <= 0:
            raise ValueError("fragment length must be >= 1")
        if indent < 0 or first_line_prefix < 0:
            raise ValueError("indent and first_line_prefix must be >= 0")

        interval = _Interval(
            target_base=self._cursor, length=length,
            source_file=source_file, source_base=source_line,
            indent=indent, first_line_prefix=first_line_prefix)
        self._intervals.append(interval)
        placed_at    = self._cursor
        self._cursor += length
        return placed_at

    def source_line_of(self, target_line, target_column=0):
        """RETURN: SourceLocation, the origin of a target point, or None.

        None means the target line is generated boilerplate (in no fragment
        interval) and has no original-source counterpart.
        """
        interval = self._find(target_line)
        if interval is None:
            return None
        return interval.resolve(target_line, target_column)

    def _find(self, target_line):
        """RETURN: _Interval containing 'target_line', or None.

        Binary search over intervals, which are sorted by target_base because
        registration is sequential.
        """
        lo, hi = 0, len(self._intervals) - 1
        while lo <= hi:
            mid = (lo + hi) // 2
            iv  = self._intervals[mid]
            if target_line < iv.target_base:
                hi = mid - 1
            elif iv.contains(target_line):
                return iv
            else:
                lo = mid + 1
        return None
