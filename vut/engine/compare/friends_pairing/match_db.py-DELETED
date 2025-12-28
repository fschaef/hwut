"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________

PURPOSE: Core functionality of friends-pairing algorithm.

A 'MatchDb' maintains equivalence relationships between lines from the subject
output and the nominal lines. The main function is '.pairing()' which performs
the pairing process. This pairing, however, can be very expensive computational-
wise. For that, several steps can be applied to avoid an exhaustive pairing 
process:

  .complete_pairing_possible():
     
     tells whether with the current setup it is possible to achieve a 100% 
     pairing.

  .extract_ultimates_and_hopeless():

     extracts those entries from the database, which only have one possible 
     match and those, for which there is no possible match.

The 'MatchDb' is used by the 'exact.py' module.
________________________________________________________________________________
"""
from vut.engine.compare.engine.analogy_db import AnalogyDb
from collections import defaultdict
from dataclasses import dataclass

class PairedGraph(dict): # dict[int, int]
    """Map:

          subject index  -->  nominal index

    This indicates for a given subject index to what nominal index it is
    to be paired in the final solution.
    """
    pass

class UnpairedCandidateGraph(dict): # dict[int, list[tuple(int, Optional[AnalogyDb])]]
    """Map: 

           subject index  --> list of tuples (nominal index, analogy constraints)

    This map indicates what subject lines may potentially be paired with what 
    lines in the nominal. The 'analogy constraints' indicate what analogies 
    need to hold in order to mate 'subject index' to 'nominal index'.
    """
    @staticmethod
    def from_raw(subject_line_list, nominal_line_list, abort_early_f):
        """RETURNS: UnpairedCandidateGraph, if successful.
                    None,                   else.

        Set 'abort_early_f' = True, if further processing becomes obsolete in case 
                                    impossible success of complete matching.
                                     
                                    => in 'judgement mode' get a quick 'NO'.
        """
        def _match_candidates(subject_le_seq, nominal_hash_db):
            """YIELDS: [0] line number in nominal line list where
                           subject_le_seq is equivalent to nominal line.
                       [1] analogy_db required for the equivalence to hold.
            """
            subject_hash = hash(subject_le_seq.sequence)
            for nominal_le_seq in nominal_hash_db.get(subject_hash, []):
                verdict, analogy_db = subject_le_seq.compare(nominal_le_seq, None)
                if verdict:
                    yield nominal_le_seq.line_n, analogy_db

        def _iterable(subject_line_list, nominal_hash_db, abort_early_f):
            """YIELDS: 
                
            subject line number --> list of (nominal line number, required analogeis)
            """
            for subject_le_seq in subject_line_list:
                mate_list = list(_match_candidates(subject_le_seq, nominal_hash_db))
                # 'mate_list' = list of (nominal line number, analogy_db)
                if not mate_list:
                    if abort_early_f:
                        raise ValueError
                else:
                    yield subject_le_seq.line_n, mate_list

        # abort construction -- attributes are set by caller (see '.from_iterable()')
        if subject_line_list is None and nominal_line_list is None:
            return None

        L_subject = 0 if not subject_line_list else len(subject_line_list)
        L_nominal = 0 if not nominal_line_list else len(nominal_line_list)

        # sizes of the sets differ => complete matching is impossible.
        if L_subject != L_nominal: 
            if abort_early_f: return None

        # Hash bucket => find comparison candidates quickly.
        nominal_hash_db = defaultdict(list)
        for le_sequence in nominal_line_list:
            nominal_hash_db[hash(le_sequence.sequence)].append(le_sequence)

        result = UnpairedCandidateGraph()
        try:
            result.__init__(_iterable(subject_line_list, nominal_hash_db, abort_early_f))
        except ValueError:
            return None
        return result

    def count_nominals(self):
        """RETURN: number of different nominals in mate lists.
        """
        return len({ib for mate_list in self.values() for ib, _ in mate_list})

    def remaining_nominal_singles(self, ia, couples, analogy_db):
        """YIELDS: mate from remaining mate_list for 'ia'.

        Consider that all nominals 'ib' from the iterable 'nominals_taken are no
        longer available for 'ia' to mate. Yield each of the remaining 'ib'-s.
        """
        taken_set = set(couples.values()) # A set allows for a quick search
        for ib, required_analogy_db in sorted(self[ia]):
            if ib in taken_set: continue
            elif not analogy_db.is_all_consistent(required_analogy_db): continue
            yield ib, required_analogy_db

    def extract_ultimate_subject_partners(self, pair_db, analogy_db, abort_early_f: bool):
        """Find 'ia'-s which have only one possible matching 'ib'. Extract
        them into 'pair_db', Elements in 'pair_db' do not participate in the
        later matching procedure.

        RETURNS: True, in case of success
                 False, else.
        """
        ok_f = True
        if len(self) == 0: return ok_f

        nominals_coupled = set()
        for ia, mate_list in sorted(self.items()):
            if len(mate_list) != 1: continue
            ib, required_analogy_db = mate_list[0]
            del self[ia]
            if ok_f := (ib in nominals_coupled):
                if abort_early_f: break
            elif not (ok_f := analogy_db.extend_if_consistent(required_analogy_db, ia, ib)):
                if abort_early_f: break
            else:
                pair_db[ia] = ib
                nominals_coupled.add(ib)

        if ok_f:
            ok_f &= self.remove_nominals(nominals_coupled, abort_early_f)

        return ok_f

    def extract_ultimate_nominal_partners(self, pair_db, analogy_db, abort_early_f: bool):
        """Find 'ib'-s which have only one possible matching 'ia'. 
        
        Even if 'ia' has multiple options, if 'ib' can ONLY be matched with 
        this 'ia', then this pairing is mandatory.
        
        RETURNS: True, in case of success
                 False, else.
        """
        ok_f = True
        if len(self) == 0: return ok_f
        
        # Map each ib to the ia-s that can match it
        ib_to_ia_map = defaultdict(list)
        for ia, mate_list in self.items():
            for ib, req_adb in mate_list:
                ib_to_ia_map[ib].append((ia, req_adb))

        nominals_coupled = set()

        # Identify ib-s appearing exactly once
        # Sort by ib for deterministic behavior in tests
        for ib, mate_list in sorted(ib_to_ia_map.items()):
            if len(mate_list) != 1: continue
            
            ia, required_analogy_db = mate_list[0]

            if ok_f := (ia not in self):
                # 'ia' has been removed by another ultimate matcher
                if abort_early_f: break
            elif not (ok_f := analogy_db.extend_if_consistent(required_analogy_db, ia, ib)):
                if abort_early_f: break
            else:
                pair_db[ia] = ib
                nominals_coupled.add(ib)
                del self[ia] # ia is now coupled, remove from work graph

        if ok_f:
            ok_f &= self.remove_nominals(nominals_coupled, abort_early_f)

        return ok_f

    def remove_nominals(self, nominal_set, abort_early_f: bool):
        ok_f = True
        if len(self) == 0: return ok_f

        for ia, mate_list in sorted(self.items()):
            new_mate_list = [ 
                (ib, req_adb) 
                for ib, req_adb in mate_list 
                if ib not in nominal_set 
            ]
            if not new_mate_list:             
                # This subject now has no possible mates left
                ok_f = False
                if abort_early_f: break
            else:
                self[ia] = new_mate_list
        return ok_f

    def remove_pairs_with_analogy_interferences(self, analogy_db, abort_early_f: bool):
        """RETURNS: False, if analogy consistency requirement results in lines
                           remaining unmatched.
                    True, else.

        Combinations of (ia, ib) which are impossible without causing analogy
        interferences with others must be excluded, before diving deeper into
        possible combinations.
        """
        ok_f = True
        if len(self) == 0: return ok_f

        for ia, mate_list in sorted(self.items()):
            new_mate_list = [ 
                (ib, required_analogy_db) 
                for ib, required_analogy_db in mate_list 
                if analogy_db.is_all_consistent(required_analogy_db)
            ]
            if not new_mate_list: 
                ok_f = False
                del self[ia]
                if abort_early_f: break
            else:
                self[ia] = new_mate_list
        return ok_f

    def __repr__(self):
        return "\n".join(
            "[%02i]-[%02i]: %s" % (ia, ib, analogy_db)
            for ia, entry in self.items()
            for ib, analogy_db in entry
        )

@dataclass
class Result:
    potential_pair_db:     UnpairedCandidateGraph
    pair_db:               PairedGraph
    analogy_constraint_db: AnalogyDb       # constraints for to make 'pair_db' possible
    required_pair_n:       int
    aborted_f:             bool

def get_initial_state(subject_line_list, nominal_line_list, abort_early_f: bool) -> Result:
    potential_pair_db = UnpairedCandidateGraph.from_raw(subject_line_list, 
                                                        nominal_line_list, 
                                                        abort_early_f)
    subject_n = 0 if not subject_line_list else len(subject_line_list)
    nominal_n = 0 if not nominal_line_list else len(nominal_line_list)

    return Result(potential_pair_db     = potential_pair_db, 
                  pair_db               = PairedGraph(), 
                  analogy_constraint_db = AnalogyDb(),
                  required_pair_n       = max(subject_n, nominal_n), 
                  aborted_f             = potential_pair_db is None)

def complete_pairing_is_possible(state: Result) -> bool:
    """RETURNS: True, if a complete pairing is possible under the given 
                      cicumstances.
                False, else.
    """
    if state.aborted_f: return False

    pair_n          = len(state.pair_db)
    db              = state.potential_pair_db
    required_pair_n = state.required_pair_n
    # every subject has a counterpart?
    if   pair_n + len(db)             != required_pair_n: return False 
    # every nominal has a counterpart?
    elif pair_n + db.count_nominals() != required_pair_n: return False 
    # else: there may be a solution where all lines are matched
    else:                                                 return True

def extract_ultimates_and_hopeless(state: Result, abort_early_f: bool) -> Result:
    db         = state.potential_pair_db
    pair_db    = state.pair_db
    analogy_db = state.analogy_constraint_db

    # Iterate until no further improvements are made
    previous_pair_n = -1
    pair_n          = len(pair_db)
    ok_f            = True
    while pair_n > previous_pair_n:
        previous_pair_n = pair_n

        # Extract those pairs, for which there is no alternative
        # => constraints on analogies
        if not (ok_f := db.extract_ultimate_subject_partners(pair_db, analogy_db, abort_early_f)):
            if abort_early_f: break
        if not (ok_f := db.extract_ultimate_nominal_partners(pair_db, analogy_db, abort_early_f)):
            if abort_early_f: break

        pair_n = len(pair_db)

        # Extract those potential pairs, which interfere with imposed analogies
        if not (ok_f := db.remove_pairs_with_analogy_interferences(analogy_db, abort_early_f)):
            if abort_early_f: break

    return Result(potential_pair_db     = db,
                  pair_db               = pair_db,
                  analogy_constraint_db = analogy_db,
                  required_pair_n       = state.required_pair_n,
                  aborted_f             = not ok_f)

def pairing(state: Result) -> Result:
    # Done already?
    if not state.potential_pair_db: return state

    db                  = state.potential_pair_db
    L                   = len(db)
    subject_singles_all = set(db)
    analogy_db          = state.analogy_constraint_db

    work_list = [
        (ia, {}, analogy_db) for ia in subject_singles_all
    ]
    best_size = 0; best_couples = {}; best_analogy_db = AnalogyDb()
    while work_list:
        ia, couples, analogy_db = work_list.pop()

        remaining_subject_singles = subject_singles_all.difference(couples.keys())
        remaining_subject_singles.remove(ia)
        remaining_nominal_singles = db.remaining_nominal_singles(ia, couples, analogy_db)

        for ib, required_analogy_db in remaining_nominal_singles:
            if required_analogy_db:
                new_analogy_db = analogy_db.clone().extend(required_analogy_db, ia, ib)
            else:
                new_analogy_db = analogy_db

            new_couples     = dict(couples)  # isolate 'couple' database
            new_couples[ia] = ib

            if len(new_couples) > best_size:
                best_size       = len(new_couples)
                best_couples    = new_couples
                best_analogy_db = new_analogy_db

            if len(new_couples) == L:
                return Result(potential_pair_db     = {},
                              pair_db               = state.pair_db | new_couples, 
                              analogy_constraint_db = analogy_db,
                              required_pair_n       = state.required_pair_n,
                              aborted_f             = False)

            work_list.extend(
                (ia, new_couples, new_analogy_db)
                for ia in remaining_subject_singles
            )

    return Result(potential_pair_db     = {},
                  pair_db               = state.pair_db | best_couples, 
                  analogy_constraint_db = best_analogy_db,
                  required_pair_n       = state.required_pair_n,
                  aborted_f             = True)

