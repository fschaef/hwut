from vut.engine.compare.engine.analogy_db import AnalogyDb
from dataclasses                          import dataclass

from .unpaired_candidate_graph import UnpairedCandidateGraph

class PairedGraph(dict): # dict[int, int]
    """Map:

          subject index  -->  nominal index

    This indicates for a given subject index to what nominal index it is
    to be paired in the final solution.
    """
    pass

@dataclass
class Result:
    potential_pair_db:     UnpairedCandidateGraph
    pair_db:               PairedGraph
    analogy_constraint_db: AnalogyDb       # constraints for to make 'pair_db' possible
    required_pair_n:       int
    aborted_f:             bool

