________________________________________________________________________________
VUT ENGINE: COMPARISON & MATCHING ALGORITHMS
________________________________________________________________________________

OVERVIEW
========

This directory contains a suite of algorithms designed to solve the "Bipartite 
Matching with Constraints" problem. Specifically, these modules aim to pair 
'Subject' lines with 'Nominal' lines such that:

    1. Each subject is paired with at most one nominal (Monogamy).
    2. The pairing allows for a consistent set of analogies (Logic Consistency).

The algorithms range from purely structural graph theory to advanced Constraint 
Satisfaction Problem (CSP) solvers.

IMPORTANT:
==========

The author did extensive benchmarking with the different approaches and here 
are the practical conclusions:

Best Approach: 

   'maximum_bipartite_matching.py' --> potential pairings that are unconstrained 
                                       of any analogies. 

   'csp_backtracking_mrv.py' --> for the pairings that are constrained by 
                                 analogies.

This combination can find mappings in fractions of a second for datasets of
1000 or more. Any other approach, was exponentially slower. The author left the
algorithms in place, together with the BENCHMARK suite, for further
investigations.

The currently used approach was achieved by strong improvements on the AnalogyDb
which was translated into a computationally highly efficient Flyweight-Pattern
implementation of immutable AnalogyDb-s, namely 'FrozenAnalogyDb-s'.

As said, if futuer optimizations show that any of the other algorithms are better
the stage is set to proof that.

FILE DESCRIPTIONS
=================

1. maximum_bipartite_matching.py
--------------------------------------------------------------------------------
TYPE: Structural Graph Solver

WHAT IT SOLVES:
    Determines the maximum number of pairs possible based purely on potential 
    compatibility, ignoring complex analogy constraints.

HOW IT WORKS:
    - Implements the Augmenting Path algorithm (based on Ford-Fulkerson/Berge's Lemma).
    - Uses Depth-First Search (DFS) to find paths in the bipartite graph.
    - Complexity: O(E * V).

WHEN TO USE:
    - As a "sanity check" or upper-bound calculation.
    - To quickly verify if a complete matching is topologically possible before 
      running expensive CSP solvers.
    - When analogy constraints are not required.

2. csp_backtracking_mrv.py
--------------------------------------------------------------------------------
TYPE: Heuristic CSP Solver

WHAT IT SOLVES:
    Finds a complete matching that satisfies all global analogy constraints.

HOW IT WORKS:
    - Uses Backtracking Search (DFS) with a "Sudoku Strategy" (Minimum Remaining 
      Values heuristic).
    - Sorts subjects by "constriction" (fewest available partners first) to fail-fast.
    - Checks consistency incrementally against an evolving 'AnalogyDb'.

WHEN TO USE:
    - The general-purpose choice for most constrained matching problems.
    - Best when the problem has "bottlenecks" (hard-to-match subjects) that 
      should be resolved early.

3. csp_chronological_backtracking.py
--------------------------------------------------------------------------------
TYPE: Low-Overhead CSP Solver

WHAT IT SOLVES:
    Same as above, but optimized for raw execution speed on linear problems.

HOW IT WORKS:
    - Uses Iterative Chronological Backtracking (linear order).
    - Uses an explicit state stack ('decision_vector') to avoid recursion overhead.
    - Leverages 'FrozenAnalogyDb' for O(1) consistency checks.

WHEN TO USE:
    - When the problem size is small to medium.
    - When variable ordering (MRV) adds more overhead than it saves.
    - For high-throughput scenarios where complex heuristics are unnecessary.

4. csp_arc_consistency.py (The "Lilly Pad Lane" Solver)
--------------------------------------------------------------------------------
TYPE: Advanced CSP Solver with Propagation

WHAT IT SOLVES:
    Solves complex matching problems where choices have deep, cascading "ripple 
    effects" on future availability.

HOW IT WORKS:
    - Models the problem as crossing N lanes of "lilly pads".
    - Phase 1 (Propagation): Performs Fixed-Point Iteration (like AC-3 algorithm).
      It identifies "Muritori" (pads that inevitably lead to dead ends) and 
      learns implied blockers via transitive closure.
    - Phase 2 (Refined Search): Performs bitmask-optimized backtracking on the 
      pruned search space.

WHEN TO USE:
    - For dense, highly coupled problems where selecting one pair eliminates 
      many future options.
    - When standard backtracking gets stuck in deep recursion trees.
    - "Heavy artillery" for difficult inputs.

5. lilly_pad_lanes_adapter.py
--------------------------------------------------------------------------------
TYPE: Data Adapter

WHAT IT DOES:
    Acts as a bridge between the raw Subject/Nominal data and the 'csp_arc_consistency' 
    solver.

HOW IT WORKS:
    - Linearizes the bipartite graph into sequential "lanes".
    - Pre-calculates the "Sink Database": determines exactly which future pads 
      are "sunk" (blocked) if a specific pad is chosen.
    - Handles the translation of bitmask solutions back to dictionary results.

USAGE GUIDE
===========

1. Is structural possibility in question?
   -> Run 'maximum_bipartite_matching.py'. If it returns fewer pairs than 
      required, a solution is impossible regardless of analogies.

2. Is the problem standard?
   -> Use 'csp_backtracking_mrv.py'. It offers the best balance of heuristics 
      and performance.

3. Is the problem strictly linear or simple?
   -> Use 'csp_chronological_backtracking.py' for maximum speed.

4. Is the problem complex/dense with high failure rates?
   -> Instantiate 'LillyPadLanesAdapter' to prepare the data.
   -> Run 'csp_arc_consistency.py'. The initialization time is higher due to 
      propagation, but it prunes the search tree drastically.
