"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: 'point-cloud' region -- every line is a point in n dimensions.

    ##! point-cloud limit=0.05 [dist=...] [pair] [constraint={...}]
    0.1  0.0998
    0.2  0.1986
    ####

Each content line carries the whitespace-separated components of one
vector 'p'; p[i] is the i-th component. Comparison criteria (all governed
by the NOMINAL side's parameters -- 'nominal is authoritative'):

    limit=<float>      distance criterion: without 'pair', EVERY point of
                       either stream must have a nearest neighbour in the
                       other stream at distance <= limit (symmetric
                       coverage). With 'pair', a BIJECTIVE matching must
                       exist in which every pair is <= limit apart (equal
                       counts required; each point pairs exactly once).
    dist=<spec>        distance function: built-in 'euclidean' (default),
                       'L1', 'L2', 'Linf', or an expression over the
                       vectors x[] and y[]: dist={max(abs(x[0]-y[0]), 1)}
    pair               see 'limit'.
    constraint={expr}  property every point of BOTH streams must satisfy;
                       expression over p[] with aliases x,y,z,w = p[0..3]:
                       constraint={abs(y - sin(x)/x) < 0.01}

At least one of 'limit' / 'constraint' is required.

MALFORMED DATA -- deliberately asymmetric ('nominal is authoritative'):
a nominal line that is not a point, a nominal dimension clash, or nominal
data violating its OWN constraint is a broken specification -> loud
RegionSyntaxError. The same defect on the SUBJECT side is a test failure
-> not equivalent, shown red by the Lawyer.

The region's dimension is set by its first valid point; later lines with a
different component count are malformed.
________________________________________________________________________________
"""
from   vut.engine.compare.engine.enums               import E_Chunk
from   vut.engine.compare.reading.input_chunk   import (
                                                 AssociationRelatedInputChunk,
                                                 EquivalenceRelatedInputChunk)
from   vut.engine.compare.region.registry            import RegionSyntaxError
from   vut.engine.compare.region.point_cloud.expression import (make_dist,
                                                                make_constraint)
import vut.engine.compare.region.point_cloud.equivalence as equivalence_pc
import vut.engine.compare.region.point_cloud.associate   as association_pc


class InputChunkPointCloud(AssociationRelatedInputChunk,
                           EquivalenceRelatedInputChunk):
    def __init__(self, start_line_n, end_line_n, line_list, config,
                 params=None):
        super().__init__(E_Chunk.POINT_CLOUD, start_line_n, end_line_n,
                         line_list, config)
        params = params or {}
        self.limit          = params.get("limit")
        self.pair_f         = bool(params.get("pair"))
        self.dist_spec      = params.get("dist") or "euclidean"
        self.constraint_spec = params.get("constraint")

        # Parse-validate expressions HERE (loud on syntax garbage, even on
        # the subject side); EVALUATION happens only through the nominal's
        # compiled forms ('nominal is authoritative').
        self.dist_fn = make_dist(self.dist_spec, start_line_n)
        self.constraint_fn = (make_constraint(self.constraint_spec,
                                              start_line_n)
                              if self.constraint_spec is not None else None)

        # Parse points: [(Line, tuple-of-float | None)]; the first valid
        # point sets the region's dimension.
        self.dimension  = None
        self.point_list = []
        for line in line_list:
            point = self._parse_point(line._string)
            if point is not None:
                if self.dimension is None:
                    self.dimension = len(point)
                elif len(point) != self.dimension:
                    point = None                    # dimension clash
            self.point_list.append((line, point))

    @staticmethod
    def _parse_point(raw):
        """RETURNS: tuple of float, the point on line 'raw', if every
                    whitespace-separated field is numeric and there is at
                    least one.
                    None, else (malformed).
        """
        fields = raw.split()
        if not fields:
            return None
        try:
            return tuple(float(f) for f in fields)
        except ValueError:
            return None

    def first_malformed(self):
        """RETURNS: Line, the first line that is not a valid point of the
                    region's dimension. None, if all lines are valid.
        """
        for line, point in self.point_list:
            if point is None:
                return line
        return None

    def require_wellformed_nominal(self):
        """Raises RegionSyntaxError if this NOMINAL-side chunk carries
        malformed data -- a broken specification must fail loudly.
        """
        bad = self.first_malformed()
        if bad is not None:
            raise RegionSyntaxError(bad.line_n,
                "point-cloud NOMINAL data is not a %s-dimensional point: %r"
                % (self.dimension if self.dimension else "n", bad._string.rstrip("\n")))

    def _is_equivalent_to_nominal(self, nominal, analogy_db):
        return equivalence_pc.do(self, nominal, analogy_db)

    def _associate_with_nominal(self, nominal, analogy_db):
        return association_pc.do(self, nominal, analogy_db)
