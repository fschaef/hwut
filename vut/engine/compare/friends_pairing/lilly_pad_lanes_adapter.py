"""
PURPOSE: Re-interpretation of the analogy constraint matching database
         in terms of 'lanes of lilly pads'.
"""
from typing import Iterable
from .potential_pair_db import PotentialPairDb
from vut.engine.compare.engine.analogy_db import AnalogyDb

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
        # Find mappings for 'sidx <--> subject_i'
        # => sidx = 0 ... N-1 (while the subject_i-s may be anything)
        subject_indices   = set(db)
        subject_i_by_sidx = sorted(subject_indices)
        sidx_by_subject_i = { subject_i: sidx for sidx, subject_i in enumerate(subject_i_by_sidx) }

        pad_id_to_pair_db = []  # pad_id          --> sidx, nominal_i
        pair_to_pad_id_db = {}  # sidx, nominal_i --> pad_id
        pad_id = 0
        for sidx, subject_i in enumerate(subject_i_by_sidx):
            for nominal_i, analogy_db in sorted(db[subject_i]):
                pad_id_to_pair_db.append((sidx, nominal_i))
                pair_to_pad_id_db[(sidx, nominal_i)] = pad_id
                pad_id += 1
                
        # pad_db[pad_id] --> list of pads that are blocked by 'pad_id'
        pad_db = {}
        pad_id = 0
        for sidx, subject_i in enumerate(subject_i_by_sidx):
            for nominal_i, analogy_db in sorted(db[subject_i]):
                pad_db[pad_id] = find_blocked_pads_beyond_sidx(db, sidx, nominal_i, analogy_db,
                                                               subject_i_by_sidx,
                                                               pair_to_pad_id_db)
                pad_id += 1

        self.pad_db            = pad_db
        self.pad_id_to_pair_db = pad_id_to_pair_db
        self.subject_i_by_sidx = subject_i_by_sidx
        self.potential_pair_db = db

    def prepare_problem(self):
        """RETURNS: 

           [0] pad_db:             pad_id -> set[blocked_pad_ids] when 'pad_id' is touched
           [1] pad_ids_by_lane_db: sidx   -> list[pad_ids]  of the lane 'sidx'
        """
        lane_n             = len(self.subject_i_by_sidx)
        pad_ids_by_lane_db = [[] for _ in range(lane_n)]
        
        for p_id, (sidx, _) in enumerate(self.pad_id_to_pair_db):
            pad_ids_by_lane_db[sidx].append(p_id)
            
        return self.pad_db, pad_ids_by_lane_db

    def interprete_solution(self, lilly_pad_path: Iterable[int]) -> tuple[dict[int, int], AnalogyDb]:
        """RETURNS: dict: subject_i --> paired nominal_i

        Takes the path over the lilly pad lanes and interprets it as a set of pairings
        between subject_i-s and nominal_i-s.
        """
        def interprete(pad_id):
            sidx, nominal_i = self.pad_id_to_pair_db[pad_id]
            subject_i       = self.subject_i_by_sidx[sidx]
            return subject_i, nominal_i

        pair_db = set(interprete(pad_id) for pad_id in lilly_pad_path)

        analogy_db = self.potential_pair_db.get_analogy_constraints(pair_db)

        return dict(pair_db), analogy_db


def find_blocked_pads_beyond_sidx(db, 
                                  current_sidx, 
                                  current_nominal_i, 
                                  current_analogy_db, 
                                  subject_i_by_sidx, pair_to_pad_id_db):
    """
    RETURNS: set of pad_id-s in FUTURE lanes that become impossible (sink).
    
    PURPOSE: Pruning the search space by identifying which future lilly pads 
             'sink' as a result of stepping on the current pad.
    """
    def consistent(adb_0, adb_1):
        if   not adb_1: return True
        elif not adb_0: return True
        else:           return adb_0.is_all_consistent(adb_1)
    
    # We only look at strictly future lanes (sidx > current_sidx)
    result = set()
    for sidx in range(current_sidx + 1, len(subject_i_by_sidx)):
        subject_i = subject_i_by_sidx[sidx]
        for nominal_i, analogy_db in sorted(db[subject_i]):
            if nominal_i == current_nominal_i:
                # Monogamie constraint: This nominal_i is now taken
                result.add(pair_to_pad_id_db[(sidx, nominal_i)])
            elif not consistent(current_analogy_db, analogy_db):
                # Analogy constraint: This future pad's rules conflict with ours
                result.add(pair_to_pad_id_db[(sidx, nominal_i)])
    return result

        
