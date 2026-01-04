"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________
"""
from   vut.engine.compare.engine.association.chunk_pair import ChunkPair

from   collections import defaultdict
from   typeguard   import typechecked

class ChunkPairList(list):
    """List of ChunkPair objects.

    Provides functions to extract LinePairs of error,
    analogy errors, and tolerated deviations.  It maintains a list of
    'ChunkPair' objects. It provides a convenient interface to
    filter on the level of chunks while investigating 'LinePair'
    objects.  All filter functions provide a list of tuples:

           (chunk, concerned list of LinePair indices)

    where the 'chunk' is the chunk where the LinePair-s occur and
    the list reports the indices of concerned LinePair-s. 
    """
    def __init__(self, iterable):
        list.__init__(self, iterable)
        assert all(x.__class__ == ChunkPair for x in self)

    def plain(self):
        """RETURNS: list of (chunk, lina index list)

        """
        return [ 
            (chunk, chunk.indices_plain())
            for _, chunk in enumerate(self)
        ]

    def errors(self):
        """RETURNS: list of (chunk, lina index list)

        where 'chunk' is the chunk of LinePair-s where the errors occur
        and 'lina index list' is the list of indices of LinePair which
        are concerned.
        """
        return [
            (chunk, chunk.indices_error())
            for chunk in self
        ]

    def errors_and_tolerated(self):
        """RETURNS: list of (chunk, lina index list)

        where 'chunk' is the chunk of LinePair-s where the errors or 
        tolerated deviations occur and 'lina index list' is the list of indices 
        of LinePair which are concerned.
        """
        return [
            (chunk, chunk.indices_error_and_tolerated())
            for chunk in self
        ]

    @typechecked
    def analogy_errors(self, errors_f: bool, definitions_f: bool, verbosity_level):
        """RETURNS: list of (chunk, lina index list)

        where 'chunk' is the chunk of LinePair-s where the analgy error
        or according definition occurs and 'lina index list' is the list of 
        indices of LinePair which are concerned.
        
        Each 'LinePair' contains the association of a subject and a nominal 
        line which is concerned with an analogy error. 
        
        errors_f:       report 'LinePair' containing analogy errors.
        definitions_f:  report 'LinePair' containing lines where analogies are
                        defined that later cause errors.
        """
        assert errors_f or definitions_f
        if not len(self): 
            return []

        analogy_db = self[-1].analogy_db()

        error_info_db = defaultdict(set)
        subject_nominal_set = set()
        for i, chunk in enumerate(self):
            new_index_set, \
            new_subject_nominal_set = chunk.analogy_errors(errors_f) 

            subject_nominal_set.update(new_subject_nominal_set)
            error_info_db[i] = set(new_index_set)

        if definitions_f:
            for i, chunk in enumerate(self):
                error_info_db[i].update(
                    chunk.indices_analogy_definitions(analogy_db, subject_nominal_set)
                )

        return [
            (self[i], index_set) 
            for i, index_set in error_info_db.items()
        ]

