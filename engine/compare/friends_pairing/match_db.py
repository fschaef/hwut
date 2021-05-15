from   ut.engine.compare.engine.analogy_db import AnalogyDb

from   collections import defaultdict

class LineElementDb(dict):
    """'ia' --> list of ('ib', required analogy_db).
    """
    def __init__(self, iterable):
        dict.__init__(self, iterable)

    def pairing(self, couples, analogy_db):
        """self:    map: 'ia' --> ('ib', required analogy_db)
           couples: map: 'ia' --> 'ib' 

        That is, 'couples' captured already the individuals for which there is 
        no alternative than each other.

        RETURNS: [0] True, if solution covers all subject and nominal lines.
                     False, else.
                 [1] map: 'ia' --> 'ib'
                 [2] analogy_db 
        """
        assert set(self).isdisjoint(couples)
        for mate_list in self.values():
            assert all(bi not in couples.values() for bi, _ in mate_list)

        L = len(self) + len(couples)

        subject_singles_all = set(self)

        work_list = [ 
            (ia, couples, analogy_db) for ia in subject_singles_all
        ]
        best_size = 0; best_couples = {}; best_analogy_db = AnalogyDb()
        while work_list:
            ia, couples, analogy_db = work_list.pop()

            remaining_subject_singles = subject_singles_all.difference(couples.keys())
            remaining_subject_singles.remove(ia)
            remaining_nominal_singles = self.remaining_nominal_singles(ia, couples, analogy_db)

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

    def count_nominals(self):
        """RETURN: number of different nominals in mate lists.
        """
        found = set()
        for ia, mate_list in self.items():
            found.update(ib for ib, _ in mate_list)
        return len(found)

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

    def extract_ultimates_and_hopeless(self, analogy_db, abort_f):
        """Search for entries in 'match_db' where there is only one possible
        mate. Those entries are extracted into the 'couples' database.

        RETURNS: [0] 'couples': ia --> ib
                                for those 'ia' and 'ib' for which there is no alternative.
                     None, if there was absolutely nothing for an 'ia'.

        ADAPTS: 'analogy_db'

        The 'abort_f' controls what has to happen as soon at it becomes clear 
        that a perfect solution is impossible. If set 'True' the function 
        reacts immediately by returning '(None, None, None)'.
        """
        couples = {}
        while 1 + 1 == 2:
            ok_f, coupled_nominals = self._find_couples(couples, analogy_db)
            if abort_f and not ok_f: 
                return None
            ok_f = self._remove_nominals(coupled_nominals)
            if abort_f and not ok_f: 
                return None
            ok_f, couples = self._find_couples_inverse(couples, analogy_db)
            if abort_f and not ok_f: 
                return None

            if not coupled_nominals:
                break

        return couples

    def _find_couples(self, couples, analogy_db):
        """Find 'ia'-s which have only one possible matching 'ib'. Extract
        them into 'couples', Elements in 'couples' do not participate in the
        later matching procedure.

        RETURNS: [0] True, if 'ia' are either in match_db or couples.
                     False, some 'ia' dropped out completely
                 [1] 'ib'-s that have been coupled.

        These 'ib'-s may occur in other match entries and need now to be 
        removed from there.
        """
        ok_f = True
        nominals_coupled = set()
        for ia, mate_list in sorted(self.items()):
            if len(mate_list) > 1: 
                continue
            ib, required_analogy_db = mate_list[0]
            del self[ia]
            if ib in nominals_coupled: 
                ok_f = False
            elif not analogy_db.extend_if_consistent(required_analogy_db, ia, ib): 
                ok_f = False
            else:
                couples[ia] = ib
                nominals_coupled.add(ib)
        return ok_f, nominals_coupled

    def _find_couples_inverse(self, couples, analogy_db):
        """Find 'ib'-s that have only one possible matching 'ia'. Extract
        them from 'match_db' into 'couples'.

        RETURNS: True, if 'ia' are either in match_db or couples.
                 False, some 'ia' dropped out completely

        The found 'ib'-s occur only once in 'match_db' and are removed from
        there. No further treatment necessary.
        """
        ok_f = True
        ib_count = defaultdict(int)
        proposed = {}
        for ia, mate_list in self.items():
            for ib, required_analogy_db in mate_list:
                if ib_count[ib] == 0: proposed[ib] = (ia, required_analogy_db)
                ib_count[ib] += 1

        nominals_ultimate = [ib for ib, count in ib_count.items() if count == 1]
        for ib in nominals_ultimate:
            ia, required_analogy_db = proposed[ib]
            if ia in self:
                del self[ia] # The one and only occurence of 'ib' is removed here.
            if not analogy_db.extend_if_consistent(required_analogy_db, ia, ib): 
                ok_f = False
            else:
                couples[ia] = ib
        return ok_f, couples

    def _remove_nominals(self, nominals):
        """Remove 'nominals' from mate_lists-s.

        RETURNS: True, if 'ia' are either in match_db or couples.
                 False, some 'ia' dropped out completely
        """
        ok_f = True
        for ia, mate_list in sorted(self.items()):
            if not any(ib in nominals for ib, _ in mate_list): 
                continue
            # remove entries from 'mate_list' which contain 'nominals'.
            new_mate_list = [
                (ib, required_analogy_db) 
                for ib, required_analogy_db in mate_list if ib not in nominals
            ]
            if not new_mate_list: 
                del self[ia]   # 'ia' must be in 'match_db', see above.
                ok_f = False
            else:                 
                self[ia] = new_mate_list
        return ok_f

    def filter_analogy_interference(self, analogy_db, abort_f):
        """RETURNS: True, if there is no way to avoid analogy interference.
                    False, else.

        Combinations of (ia, ib) which are impossible without causing analogy
        interferences with others must be excluded, before diving deeper into
        possible combinations.
        """
        verdict = True
        # Avoid comparing 'list_one[i]' and 'list_two[k]' twice: list_one i = 0 .. N
        #                                                        list_two k = i+1 .. N
        for ia, mate_list in sorted(self.items()):
            new_mate_list = [
                (ib, required_analogy_db) 
                for ib, required_analogy_db in mate_list 
                if analogy_db.is_all_consistent(required_analogy_db)
            ]
            if not new_mate_list: 
                del self[ia]   # 'ia' is in 'match_db', see above.
                if abort_f: 
                    return False
                else:       
                    verdict = False
            else:                 
                self[ia] = new_mate_list

        return verdict

    def __repr__(self):
        txt = []
        for ia, entry in self.items():
            txt.extend(
                "[%02i]-[%02i]: %s" % (ia, ib, analogy_db)
                for ib, analogy_db in entry
            )
        return "\n".join(txt)
