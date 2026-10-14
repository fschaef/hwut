"""SPDX-License: MIT; (C) Frank-Rene Schäfer; Project: VUT
_______________________________________________________________________________

PURPOSE: High-performance Levenshtein Edit Distance for strings.
STRATEGY:
    1. Try to use ultra-fast compiled libraries (RapidFuzz or Levenshtein).
    2. Fallback to optimized pure Python (Two-row iterative DP with
       greedy prefix/suffix trimming).
_______________________________________________________________________________
"""
from rapidfuzz.distance import Levenshtein

do = Levenshtein.distance

## def distance(s1: str, s2: str) -> int:
##     """Returns the Levenshtein distance between s1 and s2."""
##     if s1 == s2:
##         return 0
##
##     n1, n2 = len(s1), len(s2)
##
##     # 1. Greedy Trimming: Remove common prefix and suffix
##     start = 0
##     while start < n1 and start < n2 and s1[start] == s2[start]:
##         start += 1
##
##     end1, end2 = n1 - 1, n2 - 1
##     while end1 >= start and end2 >= start and s1[end1] == s2[end2]:
##         end1 -= 1
##         end2 -= 1
##
##     s1 = s1[start : end1 + 1]
##     s2 = s2[start : end2 + 1]
##
##     n1, n2 = len(s1), len(s2)
##
##     if n1 == 0: return n2
##     if n2 == 0: return n1
##
##     # Ensure s2 is the shorter string to minimize memory
##     if n1 < n2:
##         s1, s2 = s2, s1
##         n1, n2 = n2, n1
##
##     # Optimized Two-Row DP
##     prev_row = list(range(n2 + 1))
##
##     for i, c1 in enumerate(s1):
##         curr_row = [i + 1]
##         for j, c2 in enumerate(s2):
##             # Cost of substitution
##             sub_cost = prev_row[j] if c1 == c2 else prev_row[j] + 1
##             # Minimum of (Insertion, Deletion, Substitution)
##             min_dist = min(curr_row[j] + 1, prev_row[j + 1] + 1, sub_cost)
##             curr_row.append(min_dist)
##         prev_row = curr_row
##
##     return prev_row[-1]
##
##
## def distance_relative(s1: str, s2: str) -> float:
##     """Returns the relative distance in range [0.0 ... 1.0]."""
##     max_len = max(len(s1), len(s2))
##     if max_len == 0:
##         return 0.0
##     return distance(s1, s2) / max_len
