import vut.engine.compare.region.potpourri.best_match  as     potpourri_association
from   vut.engine.compare.engine.analogy_db            import AnalogyDb
from   vut.engine.compare.region.potpourri.variants    import VariantView
from   vut.engine.compare.core.line_pair               import LinePair, display_twin
from   vut.engine.compare.core.edit_operations.edit    import Edit, E_EditId
from   vut.engine.compare.engine                       import constraints


def do(subject, nominal, analogy_db):
    """RETURNS: [0] list of 'LinePair'-s, sorted in document order.
                [1] 'analogy_db' -- the global db, UNCHANGED.

    ANALOGY SCOPE RULE (same as the equivalence face, THE LAW): every region
    has its own analogy db. The association is computed under an EMPTY
    region-local frame; the global db is neither consulted nor extended.
    """
    # Constraint bindings need line sequentiality -- a potpourri has none
    # by construction (same guard as the equivalence face, THE LAW).
    constraints.check_no_bindings_nominal(nominal.line_list, "potpourri")

    # NOMINAL IS AUTHORITATIVE for comparison-semantic parameters (see
    # region/registry.py): the nominal's max_comparisons and variant flags
    # govern.
    subject_v = VariantView(subject, nominal.duplicates_f)
    nominal_v = VariantView(nominal, nominal.duplicates_f)
    result, \
    _       = potpourri_association.do(subject_v, nominal_v,
                                       AnalogyDb(),
                                       nominal.max_comparison_count,
                                       subset_f=nominal.subset_f)

    # Collapsed duplicates ('duplicates' flag) are shown neutrally.
    result.extend(LinePair(display_twin(line), None,
                           (Edit(E_EditId.GOOD_DELETE),),
                           seq_edit_id=E_EditId.GOOD_DELETE)
                  for line in subject_v.dup_list)
    result.extend(LinePair(None, display_twin(line),
                           (Edit(E_EditId.GOOD_INSERT),),
                           seq_edit_id=E_EditId.GOOD_INSERT)
                  for line in nominal_v.dup_list)

    def key(x):
        """Sorting the line pairs by subject line number, if present,
        else use nominal line number.
        """
        return (1, x.nominal_line_n) if x.subject_line_n == -1 else (0, x.subject_line_n)

    return sorted(result, key= key), analogy_db
