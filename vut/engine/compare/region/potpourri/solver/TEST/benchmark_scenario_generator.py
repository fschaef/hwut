"""
PURPOSE:
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

from vut.language_support.python.deterministic_random             import DeterministicStream
from vut.engine.compare.contract.analogy_db           import AnalogyDb
from vut.engine.compare.region.potpourri.potential_pair_db import PotentialPairDb

from typing import Optional, Any

def scenario(n: int, 
             c_vs_uc_ratio: float, 
             k_avg: float, 
             ac_pp_n: int, 
             ac_universe_size: int = 100) -> PotentialPairDb:
    """RETURNS: PotentialPairDb

    Generates a combined database by partitioning 'n' into constrained and 
    unconstrained blocks based on 'c_vs_uc_ratio'.
    """
    n_c  = int(round(n * c_vs_uc_ratio))  # Number of constrained subject pairs
    n_uc = n - n_c                        # Number of unconstrained subject pairs

    result_db = {}

    # Constrained portion: indices 0 to n_c - 1
    if n_c > 0:
        result_db.update(constraint_db(n_c, k_avg, ac_pp_n, ac_universe_size))

    # Unconstrained portion: indices n_c to n - 1
    if n_uc > 0:
        # Start index is offset to ensure global index uniqueness
        result_db.update(unconstraint_db(n_uc, k_avg, start_index=n_c))

    return PotentialPairDb(result_db)

def unconstraint_db(n: int, 
                    k_avg: float, 
                    start_index: int = 0) -> dict[int, list[tuple[int, None]]]:
    """
    Generates a solvable database without analogy constraints.
    """
    stream = DeterministicStream(seed=0x42 + start_index)
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

    # 1. SOLUTION SET (The "Truth")
    # Must be Bijective (A unique <-> B unique) to guarantee the backbone is solvable.
    # If we used random pairs here, we might get A1->B1 and A1->B2, creating a 
    # backbone that contradicts itself.
    solution_analogy_set = [
        ("A%X" % i, "B%X" % i) 
        for i in range(ac_universe_size)
    ]

    # 2. NOISE GENERATORS
    # Used for non-backbone edges. We use the same term universe to ensure
    # that noise edges conflict with the solution edges (e.g. A1->B99).
    def random_a(): return "A%X" % stream.next_int(0, ac_universe_size - 1)
    def random_b(): return "B%X" % stream.next_int(0, ac_universe_size - 1)

    # Generate a standard backbone for this partition
    primary_partner_db = {
        i: partner_idx for i, partner_idx in enumerate(stream.sample_indices(n, n))
    }

    def good_constraints():  
        # Sample consistent subset from the bijective solution set
        return AnalogyDb(stream.sample(solution_analogy_set, ac_pp_n))
    
    def weird_constraints(): 
        # Sample chaotic subset to create conflicts/distractors
        result = {}
        for _ in range(ac_pp_n):
            a, b = random_a(), random_b()
            if a not in result and b not in result.values():
                result[a] = b
        return AnalogyDb(result.items())

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
        target_n = max(1, min(n, target_n)) # Clamp to valid range
        extra_n  = target_n - 1
        
        # Determine base offset to keep noise within the partition
        if n > 0:
            base_offset = min(primary_partner_db.values())
        else:
            base_offset = 0

        # Select noise partners (nominal indices) other than the primary partner
        extra_nominal_index_set = set()
        
        # Safety limit for RNG loop
        attempts = 0
        max_attempts = extra_n * 20 

        while len(extra_nominal_index_set) < extra_n and attempts < max_attempts:
            attempts += 1
            # Note: stream.next_int is inclusive [0, n-1]
            candidate = stream.next_int(0, n - 1)
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
