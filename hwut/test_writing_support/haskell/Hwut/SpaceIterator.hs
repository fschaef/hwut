-- SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
-- _____________________________________________________________________________
--
-- PURPOSE: Every combination of a parameter basis -- the port of
--          'python/space_iterator.py'.
--
--     import qualified Hwut.SpaceIterator as SpaceIterator
--
--     forM_ (SpaceIterator.do' [[0, 2, 4], [1, 2]]) $ \[x, n] -> ...
--
-- yields [0,1], [0,2], [2,1], [2,2], [4,1], [4,2]: the cartesian product,
-- the RIGHTMOST dimension changing fastest. An empty basis yields one point,
-- the empty one; a basis with an empty dimension yields nothing.
--
-- THE ITERATOR IS A LAZY LIST, and the product is the list monad's own
-- 'sequence': Python's generator, its two edges included, is what the
-- language already has. A point is a list, not a tuple -- a basis of
-- unequal TYPES is a basis of one sum type the caller declares.
-- _____________________________________________________________________________
module Hwut.SpaceIterator
    ( do'
    ) where

-- | RETURN: [[a]], every point of the basis -- one value from each
--           dimension, in the dimensions' order -- lazily, the rightmost
--           dimension fastest; [[]] for an empty basis, [] where a
--           dimension is empty.
do' :: [[a]] -> [[a]]
do' = sequence
