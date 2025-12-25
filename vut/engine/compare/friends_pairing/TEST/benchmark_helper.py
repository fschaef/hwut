"""
NAME:
    scenario_generator - Deterministic generation of test scenarios for analogy matching.

SYNOPSIS:
    scenario(n, c_vs_uc_ratio, k_avg, ac_pp_n, ac_universe_size=100)

DESCRIPTION:
    This module provides tools to generate deterministic, solvable test cases for the 
    HWUT pairing algorithm. It creates a 'potential_pair_db' (subject_idx -> list 
    of nominal partners) that contains a guaranteed 1-to-1 matching "backbone."
    
    The generator partitions the subject space into a 'constrained' block (using 
    AnalogyDb constraints) and an 'unconstrained' block (using None). This allows
    for testing the backtracking complexity of the engine under varying analogy 
    densities.

PARAMETERS:
    n                Total number of subject indices to generate.
    c_vs_uc_ratio    Ratio (0.0 to 1.0) defining the proportion of subject entries
                     carrying analogy constraints.
    k_avg            The average number of nominal partners per subject index 
                     (Gaussian distributed).
    ac_pp_n          The number of analogy constraints (mappings) per AnalogyDb.
    ac_universe_size The size of the term pool from which analogies are drawn.

RETURNS:
    A dictionary mapping subject_idx to a list of tuples: (nominal_idx, AnalogyDb|None).
"""

from vut.auxiliary.deterministic_random   import DeterministicStream
from vut.engine.compare.engine.analogy_db import AnalogyDb

from typing import Optional, Any

def scenario(n: int, 
             c_vs_uc_ratio: float, 
             k_avg: float, 
             ac_pp_n: int, 
             ac_universe_size: int = 100) -> dict[int, list[tuple[int, Optional[AnalogyDb]]]]:
    """
    Generates a combined database by partitioning 'n' into constrained and 
    unconstrained blocks based on 'c_vs_uc_ratio'.
    """
    n_c = int(round(n * c_vs_uc_ratio))  # Number of constrained subject pairs
    n_uc = n - n_c                       # Number of unconstrained subject pairs

    result_db = {}

    # Constrained portion: indices 0 to n_c - 1
    if n_c > 0:
        result_db.update(constraint_db(n_c, k_avg, ac_pp_n, ac_universe_size))

    # Unconstrained portion: indices n_c to n - 1
    if n_uc > 0:
        # Start index is offset to ensure global index uniqueness
        result_db.update(unconstraint_db(n_uc, k_avg, start_index=n_c))

    return result_db


def unconstraint_db(n: int, 
                    k_avg: float, 
                    start_index: int = 0) -> dict[int, list[tuple[int, None]]]:
    """
    Generates a solvable database without analogy constraints.
    """
    stream = DeterministicStream(seed=0x42)
    assert k_avg >= 1

    # Create the Backbone (1-to-1 Perfect Matching)
    # Mapping is subject_i -> nominal_i, shifted by start_index
    primary_partner_db = {
        subject_i_raw + start_index: nominal_i_raw + start_index
        for subject_i_raw, nominal_i_raw in enumerate(stream.sample_indices(n, n))
    }
    
    return derive_from_backbone(stream, primary_partner_db, k_avg, lambda: None, lambda: None)


def constraint_db(n: int, 
                  k_avg: float, 
                  ac_pp_n: int, 
                  ac_universe_size: int = 100) -> dict[int, list[tuple[int, Optional[AnalogyDb]]]]:
    """
    Generates a solvable pairing database with AnalogyDb objects as constraints.
    """
    assert k_avg >= 1
    stream = DeterministicStream(seed=0x42)

    def a_name(): return "A%X" % stream.next_int(0, ac_universe_size)
    def b_name(): return "B%X" % stream.next_int(0, ac_universe_size)

    # Establish the 'Ground Truth' pool (consistent) vs 'Wild' pool (potential conflicts)
    solution_analogy_set = [(a_name(), b_name()) for _ in range(ac_universe_size)]
    wild_analogy_set     = [(a_name(), b_name()) for _ in range(ac_universe_size)]

    # Generate a standard backbone for this partition
    primary_partner_db = {
        i: partner_idx for i, partner_idx in enumerate(stream.sample_indices(n, n))
    }

    def good_constraints():  return AnalogyDb(stream.sample(solution_analogy_set, ac_pp_n))
    def weird_constraints(): return AnalogyDb(stream.sample(wild_analogy_set, ac_pp_n))

    return derive_from_backbone(stream, primary_partner_db, k_avg, 
                                good_constraints, 
                                weird_constraints)


def derive_from_backbone(stream: DeterministicStream, 
                        primary_partner_db: dict[int, int], 
                        k_avg: float, 
                        good_constraints: Any, 
                        weird_constraints: Any):
    """
    Standardizes the expansion of a 1-to-1 backbone into a graph of multiple 
    potential partners using Gaussian noise.
    """
    result_db = {}
    n = len(primary_partner_db)
    sigma = k_avg / 2.0
    
    # We sort to ensure subject processing order is deterministic
    for subject_i, primary_nominal_i in sorted(primary_partner_db.items()):
        # Set up the 'solvable' primary partner
        partners = [
            (primary_nominal_i, good_constraints())
        ]
        
        # Calculate partner density for this subject
        target_n = int(round(stream.gauss(k_avg, sigma)))
        target_n = max(1, min(n, target_n))
        extra_n  = target_n - 1
        
        # Select noise partners (nominal indices) other than the primary partner
        extra_nominal_index_set = set()
        while len(extra_nominal_index_set) < extra_n:
            # Note: stream.next_int is inclusive [0, n-1]
            candidate = stream.next_int(0, n - 1)
            # Offset candidate if the backbone itself is offset (start_index)
            # Since primary_partner_db keys/values are already offset, we 
            # derive the base offset from the first available value.
            base_offset = min(primary_partner_db.values())
            candidate += base_offset
            
            if candidate != primary_nominal_i:
                extra_nominal_index_set.add(candidate)
        
        # Extend with 'weird' constraints to create distractors/conflicts
        partners.extend(
            (nominal_i, weird_constraints())
            for nominal_i in sorted(list(extra_nominal_index_set))
        )

        result_db[subject_i] = partners

    return result_db
