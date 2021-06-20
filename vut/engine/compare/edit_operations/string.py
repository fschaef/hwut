"""SPDX License: MIT; (C) Frank-Rene Schäfer; Project: hwut
_______________________________________________________________________________
PURPOSE: Determine edit distance between two character strings.

'Edit distance' is a metric which expresses the difference between two strings
by means of the required edit operations to transform one string into the
other. The edit distance applied here is the so called 'Leventshtein
distance' (https://en.wikipedia.org/wiki/Levenshtein_distance).

ALGORITHM:

The problem with the Levenshtein distance is its computational complexity
O(n^2). In order to avoid a computational overload, a string is split up
into words of a maximum size. This makes the result less precise for larger
errors. In domains of large error, however, precision has few  importance.
For larger strings of size 'M', the complexity becomes 'O(m1^2 + m2^2 ...)'
instead of 'O((m1+m2 ...)^2)'.
_______________________________________________________________________________
"""
from itertools import zip_longest
from functools import lru_cache


max_sub_word_size = 16 # number of character for which the computational
#                      # complexity O(n^2) of the Levenshtein algorithm
#                      # is considered to be tolerable.

@lru_cache(maxsize=8192)
def do(a, b):
    """RETURNS: Measure of difference between string 'a' and string 'b'.

    Determines a 'Levenshtein' based edit distance between two given strings.
    """
    n = max_sub_word_size

    if a == b:
        result = 0
    elif len(a) < n and len(b) < n:
        result = _levenshtein(a, b)
    else:
        a_word_list = _split_iterable(a, n)
        b_word_list = _split_iterable(b, n)
        result      = 0
        work_list   = list(zip_longest(a_word_list, b_word_list, fillvalue=""))
        while work_list:
            a_word, b_word = work_list.pop()
            result += _levenshtein(a_word, b_word)

    return result


def _split_iterable(string, max_length):
    """YIELDS: fragments of 'word' of size 'max_length' (or smaller).

    The last fragement is only as large as the remaining number of characters.
    """
    for word in string.split():
        L = len(word)
        for i in range(0, L, max_length):
            yield word[i:min(L,i+max_length)]


def _levenshtein(s, t):
    """Implementation of the Levenshtein Algorithm to determine the edit distance
    between two character strings 's' and 't'.

    Author:  Christopher P. Matthews;
             christophermatthews1985@gmail.com;
             Sacramento, CA, USA
    Source:  https://en.wikibooks.org/wiki/Algorithm_Implementation/Strings/Levenshtein_distance#Python
    License: (CC-BY-SA-3.0) Creative Commons
    """
    if s == t: return 0
    elif len(s) == 0: return len(t)
    elif len(t) == 0: return len(s)
    v0 = [None] * (len(t) + 1)
    v1 = [None] * (len(t) + 1)
    for i in range(len(v0)):
        v0[i] = i
    for i in range(len(s)):
        v1[0] = i + 1
        for j in range(len(t)):
            cost = 0 if s[i] == t[j] else 1
            v1[j + 1] = min(v1[j] + 1, v0[j + 1] + 1, v0[j] + cost)
        for j in range(len(v0)):
            v0[j] = v1[j]

    return v1[len(t)]

