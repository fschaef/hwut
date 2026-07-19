"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: Fixed-radius neighbour index for the 'point-cloud' region.

The region's queries are FIXED-RADIUS ("is there a neighbour within
'limit'?", "which points lie within 'limit'?") -- never k-nearest. For
that, a UNIFORM GRID with cell edge = limit beats tree structures
(k-d tree, BVH) in simplicity and constant factor:

    cell(p) = tuple(floor(p[i] / limit))

    |a - b| <= limit  per coordinate  =>  cell coordinates differ by <= 1.

Since L-inf <= L1 and L-inf <= L2, ANY point within 'limit' under a
built-in metric lies in one of the 3^d adjacent cells of the query point's
cell -- the candidate set is EXACT (a superset filtered by the true
distance), so results are byte-identical to the brute-force scan:

  - existence within limit: identical truth value;
  - nearest-within-candidates == TRUE nearest whenever any point is
    within limit (the true nearest is then itself within limit, hence in
    the candidate cells) -- which is every verdict-relevant case. Ties
    break by lowest point index, exactly like the brute-force scan.

APPLICABILITY: built-in metrics only (euclidean, L1, L2, Linf) and
dimension <= MAX_GRID_DIMENSION. An EXPRESSION metric ('dist={...}') need
not satisfy the triangle inequality -- no spatial structure can prune it
correctly; such regions use the exact brute-force scan (see 'core.py').
________________________________________________________________________________
"""
from itertools import product
from math import floor


MAX_GRID_DIMENSION = 6      # 3^d candidate cells per query; 3^6 = 729.


class FixedRadiusIndex:
    """Uniform grid over a point list, cell edge = 'limit'."""

    def __init__(self, point_list, limit):
        """RETURNS: (constructor). 'point_list' entries may be None
        (excluded points keep their index, carry no cell).
        """
        assert limit > 0
        self.limit   = limit
        self.point_list = point_list
        self._cell_db = {}
        for i, p in enumerate(point_list):
            if p is None:
                continue
            self._cell_db.setdefault(self._cell(p), []).append(i)

    def _cell(self, p):
        return tuple(int(floor(c / self.limit)) for c in p)

    def candidates(self, p):
        """YIELDS: int, the indices of all points that COULD be within
        'limit' of 'p' (exact superset; ascending index order per cell
        visit -- the caller's min() with index tie-break restores full
        determinism).
        """
        base = self._cell(p)
        for offset in product((-1, 0, 1), repeat=len(base)):
            cell = tuple(b + o for b, o in zip(base, offset))
            for i in self._cell_db.get(cell, ()):
                yield i

    def nearest_within(self, p, dist):
        """RETURNS: [0] int, index of the nearest point within 'limit' of
                        'p' under 'dist' (ties: lowest index).
                    [1] float, its distance.
                    (None, None), if no point lies within 'limit'.
        """
        best_i, best_d = None, None
        for i in self.candidates(p):
            d = dist(p, self.point_list[i])
            if d <= self.limit and (best_d is None
                                    or d < best_d
                                    or (d == best_d and i < best_i)):
                best_i, best_d = i, d
        return best_i, best_d

    def all_within(self, p, dist):
        """RETURNS: set of int, indices of ALL points within 'limit' of
        'p' under 'dist' (adjacency for 'pair' mode).
        """
        return {i for i in self.candidates(p)
                if dist(p, self.point_list[i]) <= self.limit}


def is_applicable(dist_spec, dimension):
    """RETURNS: True, if the grid index may replace the brute-force scan:
                      built-in metric AND known dimension within bounds.
                False, else (expression metrics have no guaranteed
                      triangle inequality -- nothing can prune them).
    """
    from vut.engine.compare.region.point_cloud.expression import BUILTIN_DIST_DB
    return (dist_spec in BUILTIN_DIST_DB
            and dimension is not None
            and dimension <= MAX_GRID_DIMENSION)
