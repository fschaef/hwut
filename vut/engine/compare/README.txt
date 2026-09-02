VUT-COMPARE(1)                                                 VUT-COMPARE(1)

NAME
    vut-compare - Semantic comparison engine for Subject and Nominal streams

SYNOPSIS
    from vut.engine.compare import main

    # The Judge: Boolean verdict
    is_ok = await main.is_equivalent(config, subject_stream, nominal_stream)

    # The Lawyer: Structural mapping for visualization
    async for chunk_pair in main.associate(config, subject_stream, nominal_stream):
        ...

DESCRIPTION
    The VUT Comparison Engine is a high-performance, asynchronous framework 
    designed to determine the equivalence of two text streams: the 'Subject' 
    (the output of a test) and the 'Nominal' (the golden reference).

    Unlike standard line-based diffing tools which are structurally brittle, 
    this engine performs a deep semantic analysis. It decomposes text into 
    lexical tokens called LineElements, applying various tolerance principles 
    to decide if two lines "mean" the same thing, even if they do not "look" 
    the same.

MODALITIES
    The engine operates in two distinct modalities depending on the user's goal:

    1. EQUIVALENCE CHECK (The Judge)
       Purpose: Rapid automated pass/fail validation.
       Behavior: Optimized for speed. The engine processes chunks in a 
       strictly linear fashion. It utilizes a "Fast-Fail" strategy, 
       terminating the moment a logical contradiction is found. This 
       minimizes resource consumption in CI/CD pipelines.

    2. ASSOCIATION (The Lawyer/Visualizer)
       Purpose: Detailed forensic analysis of differences.
       Behavior: Optimized for clarity and coverage. If a mismatch occurs, 
       instead of aborting, the engine employs complex algorithms (A* search 
       and Bipartite Matching) to find the best possible "alignment" of 
       mismatched content. This produces the data required to render a side-
       by-side visual diff that explains *how* the streams diverged.

CORE CONCEPTS
    Line Sequences vs. Potpourri
        Text is partitioned into two types of regions. By default, lines are 
        treated as a 'LineSequence', where the order of appearance is 
        imperative. However, regions framed by '||||' markers are treated as 
        a 'Potpourri'. Inside a Potpourri, lines may appear in any order; the 
        engine will solve a Constraint Satisfaction Problem (CSP) to find a 
        consistent 1-to-1 mapping between the sets.

    Analogies
        VUT supports symbolic placeholders marked by '((' and '))'. A subject 
        token '((A))' is equivalent to a nominal token '((1))' if, and only 
        if, that relationship remains consistent across the entire stream. 
        This is invaluable for comparing outputs containing randomized IDs, 
        pointers, or timestamps that change per run but must maintain 
        internal structural integrity.

    Numeric Tolerance
        Numerical values can be compared with a configurable epsilon ratio. 
        If the ratio is 0.1, then 100.0 in the subject is equivalent to 105.0 
        in the nominal.

    Visible Nothing
        Specific patterns (like "SUCCESS" or "IGNORE") can be configured as 
        'Visible Nothing'. These elements are treated as semantically 
        transparent—their presence or absence does not affect equivalence, 
        effectively allowing the engine to "see through" noise.

USE CASES
    Forensic Log Comparison
        Analyzing application logs where thread IDs or memory addresses 
        change every execution. By using Analogies, you verify the logic 
        remains identical despite the volatile identifiers.

    Scientific Output Validation
        Comparing large datasets of floating-point results where minor 
        rounding differences between CPU architectures are expected. The 
        Numeric Tolerance ensures the test passes as long as the drift is 
        within acceptable bounds.

    Unordered Set Validation
        Validating the output of a system that prints a list of items 
        retrieved from a database where the sort order is non-deterministic. 
        The Potpourri logic handles the reordering automatically.

ARCHITECTURE & PERFORMANCE
    The engine is built on sophisticated computer science foundations to ensure 
    it remains performant even with massive input streams:

    - Flyweight Pattern: The 'FrozenAnalogyDb' uses a global registry to 
      intern all strings and mappings into unique integer IDs. This transforms 
      complex string logic into O(1) integer bitmask operations.
    - A* Search: The 'edit_operations' logic uses a heuristic-driven tree 
      search to find the minimum edit distance between similar lines without 
      exploring every possible permutation.
    - CSP Solver (MRV): For complex Potpourri mapping, the engine employs a 
      Minimum Remaining Values (MRV) backtracking solver, enabling it to solve 
      "Sudoku-style" dependency traps efficiently.
    - Async I/O: The entire pipeline is non-blocking, allowing it to process 
      subject data while the test process is still generating it.

NOTES
    Software engineers should refer to 'feeder/ui.py' to see how the 'associate' 
    output is serialized for UI consumption, and 'contract/enums.py' for a 
    complete list of verdict types.

AUTHOR
    (C) Frank-Rene Schaefer, Project VUT.

