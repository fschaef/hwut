"""
PURPOSE:
       Iteration over all possible combinations of parameters of a 
       parameter basis. Useful for function argument generation or 
       scenario parameterization in general.

SYNOPSIS:
       import hwut.language_support.python.space_iterator as generator

       basis [
           list of values for 'a',
           list of values for 'b',
           list of values for 'c',
       ]

       for a, b, c in generator.do(basis):
           ...

       yields  a0, b0, c0
               a0, b0, c1
               a0, b0, c2
               a0, b1, c0
               a0, b1, c1
               a0, b1, c2
               ...

DESCRIPTION:
       
       'do(basis)' yields the cartesian product of an orthogonal basis.

       The basis is given as a list of iterables, where each iterable
       represents one independent dimension of the search space. Each yielded
       tuple contains exactly one element from each basis dimension, in the
       same order as provided in basis.

       Iteration order follows the standard cartesian-product convention: the
       rightmost dimension changes fastest.

EXAMPLE: function argument generation

           basis = [
               [0, 2, 4, 6, 8],
               ["otto", "heinz", "frieda"],
               [1, 2, 3],
           ]

           def run_test(x, name, number):
               ...

           for x, name, number in space_iterator.do(basis):
               run_test(x, name, number)

NOTES
       - If basis is empty, generator yields exactly one tuple: ().
       - If any basis dimension is empty, generator yields nothing.

The implemention is almost trivial. The module is provided, anyways, because it is
such a powerful approach to achieve high coverage in unit testing.
"""

import itertools
from   collections.abc import Iterable, Iterator

def do(basis: list[Iterable]) -> Iterator[tuple]:
    if not basis:
        yield tuple()
        return

    pool = [tuple(dim) for dim in basis]
    if any(len(dim) == 0 for dim in pool):
        return

    yield from itertools.product(*pool)
