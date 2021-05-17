"""SPDX-Linces: MIT; Project HWUT; (C) Frank-Rene Schaefer
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
from ut.engine.compare.engine.analogy_db import AnalogyDb
from collections import defaultdict

class MatchDb(dict):
    """Maintains a map:

    subject line number --> list of (nominal line number, required analogy_db)

    That is, it lists for each subject line number the possible 'mates' from
    the nominal line number list together with the required analogies. 

    Required analogies: A set of paired terms that must always appear side-by-
    side in subject and nominal. If for example '((frieda))' in subject
    appears once instead of '((olga))' in nominal, but later '((frieda))'
    appears instead of '((vera))', then this breaks the analogy and the
    equivalence cannot hold.
    """

    def __init__(self, subject_line_list, nominal_line_list, abort_f):
        """Set 'abort_f' = True, if further processing becomes obsolete in case 
                                 impossible success of complete matching.
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

        def _iterable(subject_line_list, nominal_hash_db, abort_f):
            """YIELDS: 
                
            subject line number --> list of (nominal line number, required analogeis)
            """
            for subject_le_seq in subject_line_list:
                mate_list = list(_match_candidates(subject_le_seq, nominal_hash_db))
                # 'mate_list' = list of (nominal line number, analogy_db)
                if not mate_list:
                    if abort_f:
                        raise ValueError
                else:
                    yield subject_le_seq.line_n, mate_list

        # abort construction -- attributes are set by caller (see '.from_iterable()')
        if subject_line_list is None and nominal_line_list is None and abort_f is None:
            return

        L_subject     = len(subject_line_list)
        L_nominal     = len(nominal_line_list)
        self.max_size = max(L_subject, L_nominal)

        # sizes of the sets differ => complete matching is impossible.
        if abort_f and L_subject != L_nominal: return 

        # Hash bucket => find comparison candidates quickly.
        nominal_hash_db = defaultdict(list)
        for le_sequence in nominal_line_list:
            nominal_hash_db[hash(le_sequence.sequence)].append(le_sequence)

        try:
            dict.__init__(self, _iterable(subject_line_list, nominal_hash_db, abort_f))
        except ValueError:
            pass

    def clone(self):
        """RETURNS: clone of 'self'
        """
        return MatchDb.from_iterable(self)

    @staticmethod
    def from_iterable(iterable):
        """RETURNS: 'MatchDb' constructed from iterable of pairs shown below
            
                (subject line number, list of (nominal line number, analogy_db))

        This function fills the underlying dictionary directly.
        """
        result = MatchDb(None, None, None)
        dict.__init__(result, iterable)
        L_subject = len(result)
        L_nominal = result._count_nominals()
        result.max_size = max(L_subject, L_nominal)
        return result

    def pairing(self, analogy_db):
        """The 'couples' dictionary maps: map 'ia' --> 'ib'. It contains
        information about lines, that have already been paired.

        RETURNS: [0] True, if solution covers all subject and nominal lines.
                     False, else.
                 [1] map: 'ia' --> 'ib'
                 [2] analogy_db
        """
        L = len(self)

        subject_singles_all = set(self)

        work_list = [
            (ia, {}, analogy_db) for ia in subject_singles_all
        ]
        best_size = 0; best_couples = {}; best_analogy_db = AnalogyDb()
        while work_list:
            ia, couples, analogy_db = work_list.pop()

            remaining_subject_singles = subject_singles_all.difference(couples.keys())
            remaining_subject_singles.remove(ia)
            remaining_nominal_singles = self._remaining_nominal_singles(ia, couples, analogy_db)

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
                    return True, new_couples, new_analogy_db

                work_list.extend(
                    (ia, new_couples, new_analogy_db)
                    for ia in remaining_subject_singles
                )

        return False, best_couples, best_analogy_db

    def extract_ultimates_and_hopeless(self, analogy_db, abort_f):
        """Search for entries in 'match_db' where there is only one possible
        mate. Those entries are extracted into the 'couples' database.

        RETURNS: [0] 'couples': ia --> ib
                                for those 'ia' and 'ib' for which there is no alternative.

        ADAPTS: 'analogy_db'

        The 'abort_f' controls what has to happen as soon at it becomes clear
        that a perfect solution is impossible. If set 'True' the function
        reacts immediately by returning '(None, None, None)'.
        """
        couples = {}
        while 1 + 1 == 2:
            ok_f, coupled_nominals = self._find_couples(couples, analogy_db, abort_f)
            if not ok_f: 
                break
            elif not self._remove_nominals(coupled_nominals, abort_f):
                break
            elif not self._find_couples_inverse(couples, analogy_db, abort_f):
                break
            elif not self._filter_analogy_interference(analogy_db, abort_f):
                break
            elif not coupled_nominals: 
                break

        return couples

    def complete_pairing_possible(self, couple_n=0):
        """RETURNS: True, if a complete pairing is possible under the given 
                          cicumstances.
                    False, else.
        """
        # every subject has a counterpart?
        if   couple_n + len(self)             != self.max_size: return False 
        # every nominal has a counterpart?
        elif couple_n + self._count_nominals() != self.max_size: return False 
        # else: there may be a solution where all lines are matched
        else:                                                  return True

    def _count_nominals(self):
        """RETURN: number of different nominals in mate lists.
        """
        found = set()
        for ia, mate_list in self.items():
            found.update(ib for ib, _ in mate_list)
        return len(found)

    def _remaining_nominal_singles(self, ia, couples, analogy_db):
        """YIELDS: mate from remaining mate_list for 'ia'.

        Consider that all nominals 'ib' from the iterable 'nominals_taken are no
        longer available for 'ia' to mate. Yield each of the remaining 'ib'-s.
        """
        taken_set = set(couples.values()) # A set allows for a quick search
        for ib, required_analogy_db in sorted(self[ia]):
            if ib in taken_set: continue
            elif not analogy_db.is_all_consistent(required_analogy_db): continue
            yield ib, required_analogy_db

    def _find_couples(self, couples, analogy_db, abort_f):
        """Find 'ia'-s which have only one possible matching 'ib'. Extract
        them into 'couples', Elements in 'couples' do not participate in the
        later matching procedure.

        RETURNS: [0] True, if 'ia' are either in match_db or couples.
                     False, some 'ia' dropped out completely
                 [1] 'ib'-s that have been coupled.

        These 'ib'-s may occur in other match entries and need now to be
        removed from there.
        """
        ok_f             = True
        nominals_coupled = set()
        for ia, mate_list in sorted(self.items()):
            if len(mate_list) > 1:
                continue
            ib, required_analogy_db = mate_list[0]
            del self[ia]
            if ib in nominals_coupled:
                ok_f = False
                if abort_f: break
            elif not analogy_db.extend_if_consistent(required_analogy_db, ia, ib):
                ok_f = False
                if abort_f: break
            else:
                couples[ia] = ib
                nominals_coupled.add(ib)
        return ok_f, nominals_coupled

    def _find_couples_inverse(self, couples, analogy_db, abort_f):
        """Find 'ib'-s that have only one possible matching 'ia'. Extract
        them from 'match_db' into 'couples'.

        RETURNS: True, if 'ia' are either in match_db or couples.
                 False, some 'ia' dropped out completely

        The found 'ib'-s occur only once in 'match_db' and are removed from
        there. No further treatment necessary.
        """
        ok_f = True
        ib_mate_count = defaultdict(int)
        proposed = {}
        for ia, mate_list in self.items():
            for ib, required_analogy_db in mate_list:
                if ib_mate_count[ib] == 0: proposed[ib] = (ia, required_analogy_db)
                ib_mate_count[ib] += 1

        # consider nominals that only have one possible mate
        nominals_ultimate = [ib for ib, count in ib_mate_count.items() if count == 1]
        for ib in nominals_ultimate:
            ia, required_analogy_db = proposed[ib]
            if ia in self:
                del self[ia] # The one and only occurence of 'ib' is removed here.
            if not analogy_db.extend_if_consistent(required_analogy_db, ia, ib):
                ok_f = False
                if abort_f: break
            else:
                couples[ia] = ib

        return ok_f

    def _remove_nominals(self, nominals, abort_f):
        """Remove already coupled 'nominals' from mate_lists-s.

        RETURNS: True, if 'ia' are either in match_db or couples.
                 False, if some 'ia' dropped out completely
        """
        nominal_available = lambda ib, required_analogy_db: \
                            ib not in nominals

        ok_f = True
        for ia, mate_list in sorted(self.items()):
            if not any(ib in nominals for ib, _ in mate_list):
                continue
            # remove entries from 'mate_list' where the nominals are already coupled.
            elif not self._filter_mate_list(ia, mate_list, nominal_available):
                ok_f = False
                if abort_f: break

        return ok_f

    def _filter_analogy_interference(self, analogy_db, abort_f):
        """RETURNS: False, if analogy consistency requirement results in lines
                           remaining unmatched.
                    True, else.

        Combinations of (ia, ib) which are impossible without causing analogy
        interferences with others must be excluded, before diving deeper into
        possible combinations.
        """
        consistent_with_analogy_db = lambda ib, required_analogy_db: \
                                     analogy_db.is_all_consistent(required_analogy_db)

        ok_f = True
        for ia, mate_list in sorted(self.items()):
            # remove entries from 'mate_list' which are inconsistent with analogy_db
            if not self._filter_mate_list(ia, mate_list, consistent_with_analogy_db):
                ok_f = False
                if abort_f: break
        return ok_f

    def _filter_mate_list(self, ia, mate_list, condition):
        """RETURNS: True, if filtering left at least one entry in 'self[ia]'.
                    False, else.
        """
        new_mate_list = [
            (ib, required_analogy_db)
            for ib, required_analogy_db in mate_list
            if condition(ib, required_analogy_db)
        ]
        if not new_mate_list:
            del self[ia]      
            return False
        else:
            self[ia] = new_mate_list
            return True

    def __repr__(self):
        txt = []
        for ia, entry in self.items():
            txt.extend(
                "[%02i]-[%02i]: %s" % (ia, ib, analogy_db)
                for ib, analogy_db in entry
            )
        return "\n".join(txt)
