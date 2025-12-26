from collections import defaultdict

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

    def extract_unconstrained(self):
        """RETURNS: dict[int, set[int]] potential matches without analogy constraints
           ADAPTS:  potential_pair_db

        Extracts those candidate matches which do not depend on analogy constraints,
        and leave the remaining in 'potential_pair_db'.
        """
        result = {}
        for ia, mate_list in self.items():
            # subject_i --> set of those nominal_i without analogy_db 
            unconditional_mate_list = { 
                ib for ib, analogy_db in mate_list 
                if not analogy_db 
            }
            if not unconditional_mate_list: continue
            result[ia] = unconditional_mate_list
        return result

    def __repr__(self):
        return "\n".join(
            "[%02i]-[%02i]: %s" % (ia, ib, analogy_db)
            for ia, entry in self.items()
            for ib, analogy_db in entry
        )

