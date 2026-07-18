import vut.engine.compare.region.potpourri.best_match  as     potpourri_association


def do(subject, nominal, analogy_db):
    result,    \
    analogy_db = potpourri_association.do(subject, nominal, 
                                          analogy_db,
                                          subject.configuration.potpourri_max_comparison_count)

    def key(x): 
        """Sorting the line pairs by subject line number, if present, 
        else use nominal line number.
        """
        return (1, x.nominal_line_n) if x.subject_line_n == -1 else (0, x.subject_line_n)

    return sorted(result, key= key), analogy_db
