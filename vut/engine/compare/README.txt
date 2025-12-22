================================================================================
VUT: Visual Unit Test Comparison Engine
================================================================================

1. OVERVIEW
-----------
This module implements a tolerant, semantic comparison engine for text streams.
It is designed to validate unit test output ("subject") against reference files
("nominal").

The engine parses text into semantic tokens ("LineElements") rather than raw
strings. This allows it to distinguish between significant data errors and
acceptable variations (floating point tolerance, dynamic pointers/hashes,
formatting noise).

2. USAGE
--------
The module provides two primary entry points in `vut/engine/compare/main.py`:

    1. compare(config, subject_stream, nominal_stream) -> bool
       - Fast path. Returns True immediately if streams are equivalent.
       - Used for CI/CD pipelines or automated test verdicts.

    2. associate(config, subject_stream, nominal_stream) -> iterator
       - Yields `ChunkPair` objects containing detailed alignment data.
       - Used for building UI visualizations or Diff reports.
       - Provides `LinePair` objects with detailed `EditSequence`s.

    Prerequisites:
    The streams passed to these functions must implement a `.readline()` method.

3. ARCHITECTURE & FILE STRUCTURE
--------------------------------

A. High-Level Flow (Engine)
   The comparison is orchestrated by the components in `vut/engine/compare/engine/`.

   - vut/engine/compare/main.py
     Entry point. Sets up the generator pipeline.

   - vut/engine/compare/engine/chunk_pipe.py
     Parses raw text streams into high-level chunks:
     * `LineSequence`: Order of lines matches strictly[cite: 554].
     * `Potpourri`: Order of lines is irrelevant (delimited by `||||`)[cite: 422].

   - vut/engine/compare/engine/line_pair.py
     Defines `LinePair`, the core result object for the UI. It holds the
     association between a Subject line and a Nominal line, including the list
     of edit operations (`Edit`) required to transform one to the other.

   - vut/engine/compare/engine/analogy_db.py
     `AnalogyDb` tracks consistent substitutions (e.g., pointer addresses).
     It ensures that if 'A' maps to 'B' once, it maps to 'B' everywhere.

B. Lexical Analysis (Tolerance)
   Located in `vut/engine/compare/tolerance/`.

   - pattern_finder.py
     `PatternFinder` scans lines using Regex to identify tokens.

   - line_element.py
     Defines `LineElement` subclasses (`LineElementNumber`, `LineElementAnalogy`,
     `LineElementVisibleNothing`). These objects handle the specific equality
     checks (e.g., `abs(a-b) < epsilon`).

C. Algorithmic Core (Edit Operations)
   Located in `vut/engine/compare/edit_operations/`.
   This implements the "Best-First Search" (A*-like) to align sequences.

   - line.py
     The heavy lifter. Contains the `WorkList` and `WorkItem` classes that
     explore the edit distance matrix.
     * Key Logic: `_step_transpose` implements the asymptotic cost
       function (1 - 1/x) to prioritize moving tokens over rewriting them.

   - edit.py
     Defines `E_EditId` (GOOD, SUBSTITUTE, TRANSPOSE, etc.) and `EditSequence`.

   - line_sequence.py
     Handles the alignment of entire lines within a `LineSequence` chunk.

   - separator_adaptor.py
     Optimizes performance by stripping "Separator" tokens (whitespace) before
     comparison and re-inserting them into the result afterwards.

D. Potpourri Logic
   Located in `vut/engine/compare/friends_pairing/`.

   - match_db.py & exact.py
     Algorithms to pair lines in unordered blocks (`Potpourri`). It first
     solves for exact matches and then approximates best-fit matches for
     remaining lines.

4. KEY CONCEPTS FOR DEVELOPERS
------------------------------
* **LineElement**: The atomic unit of comparison. A line is a tuple of these.
* **WorkList**: The engine does not use a simple dynamic programming matrix
  due to the complexity of Transpositions and Analogies. It uses a priority
  queue (`WorkList`) to expand the lowest-cost alignment paths first.
* **Visible Nothing**: Elements with `E_ToleranceId.VISIBLE_NOTHING` (like
  timestamps or comments) have a near-zero cost (1e-10), ensuring they don't
  break matches but are still tracked in the edit list.

5. CONFIGURATION
----------------
Configuration logic is found in `vut/engine/compare/configuration.py`.
It controls:
- Numeric tolerance ratios.
- Regex patterns for "Visible Nothing" or "Analogy" markers (default `((...))`).
- Delimiters for Potpourri blocks (default `||||`).
