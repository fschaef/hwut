import vut.engine.compare.region.potpourri.best_match  as     potpourri_association
from   vut.engine.compare.engine.analogy_db            import AnalogyDb


def do(subject, nominal, analogy_db):
    """RETURNS: [0] list of 'LinePair'-s, sorted in document order.
                [1] 'analogy_db' -- the global db, UNCHANGED.

    ANALOGY SCOPE RULE (same as the equivalence face, THE LAW): every region
    has its own analogy db. The association is computed under an EMPTY
    region-local frame; the global db is neither consulted nor extended.
    """
    result, \
    _       = potpourri_association.do(subject, nominal,
                                       AnalogyDb(),
                                       subject.configuration.potpourri_max_comparison_count)

    def key(x):
        """Sorting the line pairs by subject line number, if present,
        else use nominal line number.
        """
        return (1, x.nominal_line_n) if x.subject_line_n == -1 else (0, x.subject_line_n)

    return sorted(result, key= key), analogy_db
