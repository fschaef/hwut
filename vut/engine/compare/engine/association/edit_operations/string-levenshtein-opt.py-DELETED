"""SPDX-License: MIT; (C) Frank-Rene Schäfer; Project: VUT
_______________________________________________________________________________

PURPOSE: High-performance Levenshtein Edit Distance for strings.
STRATEGY: Two-row iterative DP with greedy prefix/suffix trimming.
_______________________________________________________________________________
"""

def do(s1: str, s2: str) -> int:
    if s1 == s2: return 0
    n1, n2 = len(s1), len(s2)
    
    start = 0
    while start < n1 and start < n2 and s1[start] == s2[start]: start += 1
    end1, end2 = n1 - 1, n2 - 1
    while end1 >= start and end2 >= start and s1[end1] == s2[end2]:
        end1 -= 1; end2 -= 1
        
    s1, s2 = s1[start : end1 + 1], s2[start : end2 + 1]
    n1, n2 = len(s1), len(s2)
    if   n1 == 0: return n2
    elif n2 == 0: return n1
    elif n1 < n2: s1, s2, n1, n2 = s2, s1, n2, n1

    prev_row = list(range(n2 + 1))
    for i, c1 in enumerate(s1):
        curr_row = [i + 1]
        for j, c2 in enumerate(s2):
            sub_cost = prev_row[j] if c1 == c2 else prev_row[j] + 1
            curr_row.append(min(curr_row[j] + 1, prev_row[j + 1] + 1, sub_cost))
        prev_row = curr_row
    return prev_row[-1]

def distance_relative(s1: str, s2: str) -> float:
    max_len = max(len(s1), len(s2))
    return distance(s1, s2) / max_len if max_len > 0 else 0.0
