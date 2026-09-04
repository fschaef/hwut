"""
PURPOSE: Re-interpretation of the analogy constraint matching database
         in terms of 'lanes of lilly pads'.
"""
from typing import Iterable
from vut.engine.compare.region.potpourri.potential_pair_db import PotentialPairDb
from vut.engine.compare.contract.analogy_db           import AnalogyDb

class LillyPadLanesAdapter:
    """
    Adapts a constrained matching problem into a linearized state-space search
    modeled as a traversal across sequential 'lily pad lanes'. The pairing of
    two elements is translated into a 'lilly pad'. The consistency constraint
    of a pairing (=pad) is translated into an interferring consistency blocks
    the according pad.

    VISUAL MODEL (The 'Lanes'):

    [s0] --> [n3, adb3]    [n18, adb18]  [n2, adb2]  (Lane 0)
    [s1] --> [n1, adb1]    [n8, adb8]                (Lane 1)
    [s2] --> [n18, adb18]  [n4, adb4]                (Lane 2)
    ...
    [si] --> [nk, adbk]    [nq, adbq]    [nl, adbl]  (Lane i)

    FORMALISM:

    The problem is a Stage-Based Constraint Satisfaction Problem (CSP).
    Occupying a 'pad' at Lane 'i' triggers a 'sink' event, disabling
    incompatible pads in all future lanes 'k > i'.

    LOGIC OF INTERFERENCE (The 'Sink'):

    If pad [n3, adb3] in Lane 0 is incompatible with [n18, adb18] in Lane 2,
    stepping on the former 'sinks' the latter. A pad is sunk if:
    1. Uniqueness Violation: Nominal 'n' is already assigned to a previous lane.
    2. Analogy Inconsistency: The pad's adb conflicts with a previously committed adb.

    OBJECTIVE:

    Find a traversal path selecting exactly one pad per lane such that no
    future lane suffers a 'domain wipe-out' (all pads sunk). This transforms
    the matching problem into a depth-first search with forward-checking pruning.

    NOTE:

    It is sufficient to determine if a pad-touched blocks a pad ahead. What
    the analogy requires is that on the path (set of all pairings) there are
    no two pairings (=two pads) with interferring consistencies. This is
    implemented by preventing the blocked pad to be accepted on the path
    when the blocking pad is touched.
    """

    def __init__(self, db: PotentialPairDb):
        self.subject_i_by_sidx = sorted(db.keys())

        self.potential_pair_db = db.clone_with_FrozenAnalogyDb()

        # 1. Coordinate Mapping: Convert DB to flat list of 'Pads'
        # pad_info[pad_id] -> (sidx, nominal_i, frozen_adb)
        self.pad_info = self._linearize_board(self.potential_pair_db)

        # 2. Constraint Mapping: Identify 'Sinks'
        # pad_db[pad_id] -> set of blocked future pad_ids
        self.pad_db = self._build_sink_database()

    def _linearize_board(self, db):
        """Map subject/nominal pairs to sequential pad_ids."""
        pad_info = []
        for sidx, subject_i in enumerate(self.subject_i_by_sidx):
            for nominal_i, adb in sorted(db[subject_i]):
                # Assume adb is already frozen or freeze it here
                frozen_adb = adb.freeze() if hasattr(adb, 'freeze') else adb
                pad_info.append((sidx, nominal_i, frozen_adb))
        return pad_info

    def _build_sink_database(self):
        """Calculate the ripple effect (sink) for every pad."""
        pad_db = {}
        total_pads = len(self.pad_info)

        # Monogamy Index: Map nominal_i -> list of pad_ids that use it
        nom_map = {}
        for p_id, (_, nominal_i, _) in enumerate(self.pad_info):
            nom_map.setdefault(nominal_i, []).append(p_id)

        for p_id in range(total_pads):
            pad_db[p_id] = self._find_sinks_for_pad(p_id, nom_map)
        return pad_db

    def _find_sinks_for_pad(self, p_id, nom_map):
        """Finds all future pads sunk by p_id (Monogamy + Analogy)."""
        sidx, nominal_i, f_adb = self.pad_info[p_id]
        blocked = set()

        # 1. Sink future pads sharing the same nominal (Monogamy)
        for target_pid in nom_map.get(nominal_i, []):
            if target_pid > p_id and self.pad_info[target_pid][0] > sidx:
                blocked.add(target_pid)

        # 2. Sink future pads with conflicting analogies
        if f_adb:
            for t_id in range(p_id + 1, len(self.pad_info)):
                t_sidx, t_nom, t_f_adb = self.pad_info[t_id]
                if t_sidx > sidx and t_id not in blocked:
                    if t_f_adb and not f_adb.is_all_consistent(t_f_adb):
                        blocked.add(t_id)
        return blocked

    def prepare_problem(self):
        """RETURNS: [0] pad_db, [1] pad_ids_by_lane_db"""
        lane_n = len(self.subject_i_by_sidx)
        pad_ids_by_lane_db = [[] for _ in range(lane_n)]

        for p_id, (sidx, _, _) in enumerate(self.pad_info):
            pad_ids_by_lane_db[sidx].append(p_id)

        return self.pad_db, pad_ids_by_lane_db

    def interprete_solution(self, lilly_pad_path: Iterable[int]) -> tuple[dict[int, int], AnalogyDb]:
        """Convert lilly_pad_path back to subject_i -> nominal_i."""
        raw_pairs = []
        for p_id in lilly_pad_path:
            sidx, nominal_i, _ = self.pad_info[p_id]
            raw_pairs.append((self.subject_i_by_sidx[sidx], nominal_i))

        pair_dict = dict(raw_pairs)
        analogy_db = self.potential_pair_db.get_analogy_constraints(set(raw_pairs))
        return pair_dict, analogy_db
