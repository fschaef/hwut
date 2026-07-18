from   __future__ import annotations
from   vut.engine.compare.engine.analogy_db        import AnalogyDb
from   vut.engine.compare.engine.frozen_analogy_db import FrozenAnalogyDb
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

    if not verdict:
        return False, analogy_db

    # The matching inner loop works on the flyweight 'FrozenAnalogyDb'. That
    # form is a potpourri-internal optimization; the cross-chunk streaming
    # contract (see 'main.is_equivalent') requires a mutable 'AnalogyDb'.
    # Thaw here so the frozen representation never leaks past this boundary.
    if isinstance(new_analogy_db, FrozenAnalogyDb):
        new_analogy_db = new_analogy_db.to_AnalogyDb()
    return True, new_analogy_db

