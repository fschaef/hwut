"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________
PURPOSE: The shared decision core of the 'point-cloud' region -- BOTH faces
derive their judgment from the classification computed here, so THE LAW
holds by construction (compare 'contract/semantics.py' for the general
principle).
________________________________________________________________________________
"""
from vut.engine.compare.region.registry import RegionSyntaxError
import vut.engine.compare.region.potpourri.solver.maximum_bipartite_matching \
    as solver_max_bpm
import vut.engine.compare.region.point_cloud.spatial as spatial


class Judgment:
    """The complete classification of one subject/nominal region pair.

    .verdict           bool -- THE equivalence verdict (both faces use it)
    .subject_class     list aligned with subject.point_list:
                       ('ok', nominal_index | None) or ('bad', reason)
    .nominal_uncovered set of nominal indices with no counterpart
    .pairing           dict subject_index -> nominal_index (display)
    """
    def __init__(self, subject, nominal):
        """RETURNS: (constructor). Raises RegionSyntaxError when the
        NOMINAL side is a broken specification (malformed data, no
        criterion, data violating its own constraint).
        """
        # NOMINAL IS AUTHORITATIVE: criteria come from the nominal chunk.
        limit      = nominal.limit
        pair_f     = nominal.pair_f
        dist       = nominal.dist_fn
        constraint = nominal.constraint_fn

        if limit is None and constraint is None:
            raise RegionSyntaxError(nominal.start_line_n,
                "point-cloud region declares neither 'limit' nor "
                "'constraint' -- nothing to compare")
        nominal.require_wellformed_nominal()

        n_points = [p for _, p in nominal.point_list]
        if constraint is not None:
            for line, p in nominal.point_list:
                if not constraint(p):
                    raise RegionSyntaxError(line.line_n,
                        "point-cloud NOMINAL data violates its own "
                        "constraint {%s}: %r"
                        % (nominal.constraint_spec,
                           line._string.rstrip("\n")))

        self.verdict           = True
        self.subject_class     = []
        self.nominal_uncovered = set()
        self.pairing           = {}

        dim_clash_f = (subject.dimension is not None
                       and nominal.dimension is not None
                       and subject.dimension != nominal.dimension)

        # -- subject-side point classification ----------------------------
        s_points = []
        for si, (line, p) in enumerate(subject.point_list):
            if p is None or dim_clash_f:
                self.subject_class.append(("bad", "malformed"
                                           if p is None else "dimension"))
                self.verdict = False
                s_points.append(None)
                continue
            if constraint is not None and not constraint(p):
                self.subject_class.append(("bad", "constraint"))
                self.verdict = False
                s_points.append(None)      # excluded from matching
                continue
            self.subject_class.append(None)     # decided below
            s_points.append(p)

        # -- distance criterion -------------------------------------------
        if limit is None:
            # constraint-only: counts are irrelevant; undecided subjects OK.
            for si, entry in enumerate(self.subject_class):
                if entry is None:
                    self.subject_class[si] = ("ok", None)
            return

        # Fixed-radius acceleration (built-in metrics only; an expression
        # metric has no guaranteed triangle inequality, so nothing may
        # prune it -- see 'spatial.py'). Results are byte-identical to the
        # brute-force scan.
        dimension = subject.dimension or nominal.dimension
        grid_f    = (not dim_clash_f
                     and limit > 0
                     and spatial.is_applicable(nominal.dist_spec, dimension))

        if pair_f:
            if grid_f:
                index_n = spatial.FixedRadiusIndex(n_points, limit)
                adjacency = {
                    si: index_n.all_within(sp, dist)
                    for si, sp in enumerate(s_points) if sp is not None
                }
            else:
                adjacency = {
                    si: {ni for ni, np in enumerate(n_points)
                         if np is not None and dist(sp, np) <= limit}
                    for si, sp in enumerate(s_points) if sp is not None
                }
            self.pairing = dict(solver_max_bpm.do(adjacency))
            complete_f = (len(self.pairing) == len(s_points)
                          == len(n_points)
                          and all(p is not None for p in s_points))
            if not complete_f:
                self.verdict = False
            matched_nominals = set(self.pairing.values())
            for si, entry in enumerate(self.subject_class):
                if entry is not None: continue
                if si in self.pairing:
                    self.subject_class[si] = ("ok", self.pairing[si])
                else:
                    self.subject_class[si] = ("bad", "unpaired")
            self.nominal_uncovered = {ni for ni in range(len(n_points))
                                      if ni not in matched_nominals}
        else:
            # symmetric coverage: nearest neighbour within 'limit', both
            # ways. Grid and brute produce IDENTICAL results: whenever any
            # point is within limit, the true nearest is within limit and
            # therefore among the grid's candidates; ties break by lowest
            # index in both paths.
            def nearest_within_brute(p, other):
                best_i, best_d = None, None
                for i, q in enumerate(other):
                    if q is None: continue
                    d = dist(p, q)
                    if d <= limit and (best_d is None or d < best_d):
                        best_i, best_d = i, d
                return best_i, best_d

            if grid_f:
                index_n = spatial.FixedRadiusIndex(n_points, limit)
                index_s = spatial.FixedRadiusIndex(s_points, limit)
                nearest_n = lambda p: index_n.nearest_within(p, dist)
                nearest_s = lambda p: index_s.nearest_within(p, dist)
            else:
                nearest_n = lambda p: nearest_within_brute(p, n_points)
                nearest_s = lambda p: nearest_within_brute(p, s_points)

            for si, entry in enumerate(self.subject_class):
                if entry is not None: continue
                ni, d = nearest_n(s_points[si])
                if ni is not None:
                    self.subject_class[si] = ("ok", ni)
                    self.pairing[si] = ni
                else:
                    self.subject_class[si] = ("bad", "no-neighbour")
                    self.verdict = False
            for ni, np in enumerate(n_points):
                if np is None: continue
                si, _ = nearest_s(np)
                if si is None:
                    self.nominal_uncovered.add(ni)
                    self.verdict = False
