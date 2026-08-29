from vut.engine.compare.contract.frozen_analogy_db import FrozenAnalogyDb
from vut.engine.compare.contract.analogy_db        import AnalogyDb
from vut.engine.compare.contract.semantics         import analogy_commitment
from vut.engine.compare.reading.line_element       import structural_hash
from collections import defaultdict
from typeguard   import typechecked

class PotentialPairDb(dict): # dict[int, list[tuple(int, Optional[AnalogyDb])]]
    """Map: 

           subject index  --> list of tuples (nominal index, analogy constraints)

    This map indicates what subject lines may potentially be paired with what 
    lines in the nominal. The 'analogy constraints' indicate what analogies 
    need to hold in order to mate 'subject index' to 'nominal index'.
    """
    @staticmethod
    def from_raw(subject_line_list, nominal_line_list, abort_early_f,
                 subset_f=False):
        """RETURNS: PotentialPairDb, if successful.
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
            subject_hash = structural_hash(subject_le_seq.sequence)
            for nominal_le_seq in nominal_hash_db.get(subject_hash, []):
                verdict, analogy_db = subject_le_seq.compare_and_provide_analogies(nominal_le_seq)
                if verdict:
                    if analogy_db is None: analogy_db = AnalogyDb()
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
                    # Least-committal candidates FIRST (see 'semantics.
                    # analogy_commitment'): the solvers explore in list order,
                    # so among equal-cost matchings the one imposing the
                    # fewest non-trivial analogies wins -- for the Judge and
                    # the Lawyer alike.
                    mate_list.sort(key=lambda mate: (analogy_commitment(mate[1]),
                                                     mate[0]))
                    yield subject_le_seq.line_n, mate_list

        # abort construction -- attributes are set by caller (see '.from_iterable()')
        if subject_line_list is None and nominal_line_list is None:
            return None

        L_subject = 0 if not subject_line_list else len(subject_line_list)
        L_nominal = 0 if not nominal_line_list else len(nominal_line_list)

        # standard: sizes must agree; subset: subject may be smaller.
        impossible_f = (L_subject > L_nominal) if subset_f \
                       else (L_subject != L_nominal)
        if impossible_f:
            if abort_early_f: return None

        # Hash bucket => find comparison candidates quickly.
        nominal_hash_db = defaultdict(list)
        for le_sequence in nominal_line_list:
            nominal_hash_db[structural_hash(le_sequence.sequence)].append(le_sequence)

        try:
            return PotentialPairDb(_iterable(subject_line_list, nominal_hash_db, abort_early_f))
        except Exception:
            return None

    def unconstrained_clone(self) -> dict[int, set[int]]:
        """RETURNS:  subject_i -> set of nominal_i 

        The returned dictionary returns an 'analogy unconstrained' version of
        the 'self'. It may be used to check QUICKLY whether a solution exists.
        If even no unconstrained solution exists, then constrained solutions not
        possible.
        """
        return {
            ib: { ia for ia, _ in mate_list }
            for ib, mate_list in self.items()
        }

    def clone_with_FrozenAnalogyDb(self):
        result = PotentialPairDb()
        for ia, mate_list in list(self.items()):
            result[ia] = [
                (ib, FrozenAnalogyDb(analogy_db))
                for ib, analogy_db in mate_list
            ]
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
        if len(self) == 0: return ok_f, analogy_db

        nominals_coupled = set()
        for ia, mate_list in sorted(self.items()):
            if len(mate_list) != 1: continue
            # investigate the one and only equivalent partner
            ib, required_analogy_db = mate_list[0]
            del self[ia]
            if ib in nominals_coupled:
                ok_f = False
                if abort_early_f: break
            elif not (ok_f := analogy_db.extend_if_consistent(required_analogy_db)):
                if abort_early_f: break
            else:
                pair_db[ia] = ib
                nominals_coupled.add(ib)

        if ok_f:
            ok_f &= self.remove_nominals(nominals_coupled, abort_early_f)

        return ok_f, analogy_db

    def extract_ultimate_nominal_partners(self, pair_db, analogy_db, abort_early_f: bool):
        """Find 'ib'-s which have only one possible matching 'ia'. 
        
        Even if 'ia' has multiple options, if 'ib' can ONLY be matched with 
        this 'ia', then this pairing is mandatory.
        
        RETURNS: True, in case of success
                 False, else.
        """
        ok_f = True
        if len(self) == 0: return ok_f, analogy_db
        
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
            elif not (ok_f := analogy_db.extend_if_consistent(required_analogy_db)):
                if abort_early_f: break
            else:
                pair_db[ia] = ib
                nominals_coupled.add(ib)
                del self[ia] # ia is now coupled, remove from work graph

        if ok_f:
            ok_f &= self.remove_nominals(nominals_coupled, abort_early_f)

        return ok_f, analogy_db

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

    def extract_unconstrained(self):
        """RETURNS: dict[int, set[int]] potential matches without analogy constraints
           ADAPTS:  potential_pair_db

        Extracts those candidate matches which do not depend on analogy constraints,
        and leave the remaining in 'potential_pair_db'.
        """
        result = {}
        for ia, mate_list in list(self.items()):
            unconstrained_mates = [
                ib
                for ib, analogy_db in mate_list
                if not analogy_db
            ]
            if not unconstrained_mates: continue
            result[ia] = unconstrained_mates
            new_mate_list = [
                (ib, analogy_db)
                for ib, analogy_db in mate_list
                if ib not in unconstrained_mates
            ]
            if not new_mate_list: del self[ia]
            else:                 self[ia] = new_mate_list

        return result

    @typechecked
    def get_analogy_constraints(self, pair_set: set[tuple[int,int]]):
        return FrozenAnalogyDb.merge_all(
            analogy_db
            for ia, mate_list in self.items()
            for ib, analogy_db in mate_list
            if (ia, ib) in pair_set
        )

    def __repr__(self):
        return "\n".join(
            "[%02i]-[%02i]: %s" % (ia, ib, analogy_db)
            for ia, entry in self.items()
            for ib, analogy_db in entry
        )

