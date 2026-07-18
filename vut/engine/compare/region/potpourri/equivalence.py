from   __future__ import annotations
from   vut.engine.compare.engine.analogy_db        import AnalogyDb
import vut.engine.compare.region.potpourri.pairing as     pairing


def do(subject:    InputChunk,    #noqa F821
       nominal:    InputChunk,    #noqa F821
       analogy_db: AnalogyDb) -> tuple[bool, AnalogyDb]:

    if len(subject.analogy_line_list) != len(nominal.analogy_line_list):
         return False, analogy_db # EQUIVALENCE impossible!
    elif len(subject.non_analogy_line_list) != len(nominal.non_analogy_line_list):
         return False, analogy_db # EQUIVALENCE impossible!

    verdict,       \
    _,             \
    new_analogy_db = pairing.do(subject, nominal, analogy_db,
                                abort_early_f=True)

    if verdict: return True, new_analogy_db
    else:       return False, analogy_db

