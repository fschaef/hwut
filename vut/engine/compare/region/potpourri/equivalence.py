from   __future__ import annotations
from   vut.engine.compare.engine.analogy_db        import AnalogyDb
from   vut.engine.compare.engine.frozen_analogy_db import FrozenAnalogyDb
import vut.engine.compare.region.potpourri.pairing as     pairing


def do(subject:    InputChunk,    #noqa F821
       nominal:    InputChunk,    #noqa F821
       analogy_db: AnalogyDb) -> tuple[bool, AnalogyDb]:
    """RETURNS: [0] True, if the region's lines can be completely paired
                    under an internally consistent, REGION-LOCAL analogy
                    frame.
                    False, else.
                [1] 'analogy_db' -- the global db, UNCHANGED.

    ANALOGY SCOPE RULE: every region has its own analogy db. The global db
    is not propagated into the region, and the region's frame is not
    propagated out. The global db develops over the outer text only,
    independent of any region's local frame.
    """
    if len(subject.analogy_line_list) != len(nominal.analogy_line_list):
         return False, analogy_db # EQUIVALENCE impossible!
    elif len(subject.non_analogy_line_list) != len(nominal.non_analogy_line_list):
         return False, analogy_db # EQUIVALENCE impossible!

    # REGION-LOCAL: the matching starts from an EMPTY local frame, not from
    # the global db; the local frame is dropped afterwards.
    verdict, \
    _,       \
    _        = pairing.do(subject, nominal, AnalogyDb(), abort_early_f=True)

    return verdict, analogy_db

