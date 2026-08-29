from   __future__ import annotations
from   vut.engine.compare.contract.analogy_db        import AnalogyDb
import vut.engine.compare.region.potpourri.pairing as     pairing
from   vut.engine.compare.region.potpourri.variants import VariantView
from   vut.engine.compare.engine                    import constraints


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
    # Constraint bindings need line sequentiality -- a potpourri has none
    # by construction. A NOMINAL binding here is a broken specification
    # (loud); a subject-side one is a plain mismatch (kind MISFIT).
    constraints.check_no_bindings_nominal(nominal.line_list, "potpourri")

    # NOMINAL IS AUTHORITATIVE for the variant flags (registry rule).
    subset_f     = nominal.subset_f
    duplicates_f = nominal.duplicates_f
    subject_v    = VariantView(subject, duplicates_f)
    nominal_v    = VariantView(nominal, duplicates_f)

    def counts_impossible(s_list, n_list):
        if subset_f: return len(s_list) >  len(n_list)
        else:        return len(s_list) != len(n_list)

    if counts_impossible(subject_v.analogy_line_list,
                         nominal_v.analogy_line_list):
         return False, analogy_db # EQUIVALENCE impossible!
    elif counts_impossible(subject_v.non_analogy_line_list,
                           nominal_v.non_analogy_line_list):
         return False, analogy_db # EQUIVALENCE impossible!

    # REGION-LOCAL: the matching starts from an EMPTY local frame, not from
    # the global db; the local frame is dropped afterwards.
    verdict, \
    _,       \
    _        = pairing.do(subject_v, nominal_v, AnalogyDb(),
                          abort_early_f=True, subset_f=subset_f)

    return verdict, analogy_db

