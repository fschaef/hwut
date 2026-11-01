-- SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
-- _____________________________________________________________________________
--
-- PURPOSE: A random stream that is the same everywhere -- the port of
--          'python/deterministic_random.py'.
--
--     import Control.Monad.State (evalState, replicateM)
--     import Hwut.DeterministicRandom
--
--     evalState (replicateM 3 (nextInt 0 9)) (deterministicStream 0x42)
--
-- THE STREAM IS A VALUE, NOT AN OBJECT. Python's 'DeterministicStream'
-- mutates its 'state' at every draw; here the state is the value
-- 'DeterministicStream', and a draw is an action of the State monad over it
-- ('Draw'): 'nextInt' returns the number AND, inside the monad, the stream
-- that follows. Two draws from the same stream value give the same number
-- -- the property the Python class promises, held by the type.
--
-- THE MARKER IS A VALUE TOO. Python keys 'SelectionMarker' on object
-- identity ('id'); Haskell values have no identity, so the marker is keyed
-- on the candidate ITSELF ('Ord a'): the candidates that are 'the same' are
-- those that are equal. For the tests' candidates -- interned strs in
-- Python -- that is the same partition. The marker is threaded beside the
-- stream: 'selectUnchosen' returns the choice and the marker that follows.
--
-- Park-Miller MINSTD: state = 48271 * state mod (2^31 - 1).
-- _____________________________________________________________________________
module Hwut.DeterministicRandom
    ( DeterministicStream (..)
    , Draw
    , deterministicStream
    , nextInt
    , nextFloat
    , coin
    , select
    , choice
    , gauss
    , gaussClipped
    , gaussInt
    , sampleIndices
    , sample
    , SelectionMarker
    , selectionMarker
    , reset
    , selectUnchosen
    ) where

import           Control.Monad.State (State, state)
import qualified Data.Sequence       as Seq
import qualified Data.Set            as Set

-- | The stream: nothing but its state.
newtype DeterministicStream = DeterministicStream { streamState :: Int }
    deriving (Eq, Show)

-- | A draw: an action that takes numbers from the stream.
type Draw = State DeterministicStream

-- | RETURN: DeterministicStream, the stream that begins at 'seed' (masked
--           to 31 bits, as Python's '& 0x7FFFFFFF').
deterministicStream :: Int -> DeterministicStream
deterministicStream seed = DeterministicStream (seed `mod` 0x80000000)

-- | RETURN: Draw Int, a number in [vMin, vMax]; the stream steps ONCE,
--           also where vMin == vMax (then vMin is the number).
nextInt :: Int -> Int -> Draw Int
nextInt vMin vMax = state $ \(DeterministicStream s) ->
    let s' = (48271 * s) `mod` 2147483647
    in  (if vMin == vMax then vMin else vMin + s' `mod` (vMax - vMin + 1), DeterministicStream s')

-- | RETURN: Draw Double, a number in [0, 1): 'nextInt 0 1000000' / 1000001.
nextFloat :: Draw Double
nextFloat = (/ 1000001.0) . fromIntegral <$> nextInt 0 1000000

-- | RETURN: Draw Bool, True with 'probability' (resolved in steps of
--           1/1000001: 'nextFloat' < 'probability'), False else.
coin :: Double -> Draw Bool
coin probability = (< probability) <$> nextFloat

-- | RETURN: Draw a, a uniformly drawn element of the non-empty 'candidates'.
--           Stateless: the same stream and candidates give the same one.
select :: [a] -> Draw a
select candidates = (candidates !!) <$> nextInt 0 (length candidates - 1)

-- | RETURN: Draw a, as 'select' (Python's 'choice').
choice :: [a] -> Draw a
choice = select

-- | RETURN: Draw Double, a draw of the normal distribution (mu, sigma) by
--           the Box-Muller transform. NOT BIT-PORTABLE: log, cos and sqrt
--           are the platform's libm, as in Python.
gauss :: Double -> Double -> Draw Double
gauss mu sigma = gaussClipped mu sigma (-1 / 0) (1 / 0)

-- | RETURN: Draw Double, 'gauss mu sigma' clipped to [lower, upper].
gaussClipped :: Double -> Double -> Double -> Double -> Draw Double
gaussClipped mu sigma lower upper = do
    u1 <- (+ 1e-9) <$> nextFloat                  -- avoid log 0
    u2 <- nextFloat
    let z0     = sqrt (-2.0 * log u1) * cos (2.0 * pi * u2)
        result = z0 * sigma + mu
    return (if result < lower then lower else if result > upper then upper else result)

-- | RETURN: Draw Int, 'gauss mu sigma' rounded to the nearest integer --
--           half to even, as Python's 'round'.
gaussInt :: Double -> Double -> Draw Int
gaussInt mu sigma = round <$> gauss mu sigma

-- | RETURN: Draw [Int], 'k' distinct indices of [0, populationSize), drawn
--           by Fisher-Yates: the i-th swaps place i with a place in
--           [i, populationSize).
sampleIndices :: Int -> Int -> Draw [Int]
sampleIndices populationSize k = go 0 (Seq.fromList [0 .. populationSize - 1])
  where
    go i indices
        | i >= k    = return []
        | otherwise = do
            j <- nextInt i (populationSize - 1)
            let a        = Seq.index indices i
                b        = Seq.index indices j
                swapped  = Seq.update j a (Seq.update i b indices)
            (b :) <$> go (i + 1) swapped

-- | RETURN: Draw [a], 'n' distinct elements of 'population', in the order
--           'sampleIndices' draws their places.
sample :: [a] -> Int -> Draw [a]
sample population n = do
    let s = Seq.fromList population
    indices <- sampleIndices (Seq.length s) n
    return (map (Seq.index s) indices)

-- | What one selection site has chosen: the candidates themselves.
newtype SelectionMarker a = SelectionMarker (Set.Set a)

-- | RETURN: SelectionMarker a, one that has seen nothing.
selectionMarker :: SelectionMarker a
selectionMarker = SelectionMarker Set.empty

-- | RETURN: SelectionMarker a, the marker that has forgotten every choice.
reset :: SelectionMarker a -> SelectionMarker a
reset _ = selectionMarker

-- | RETURN: Draw (a, SelectionMarker a), a candidate drawn uniformly among
--           those 'marker' has not seen -- among all of them, the marker
--           reset first, where it has seen every one -- and the marker that
--           has seen it too.
selectUnchosen :: Ord a => [a] -> SelectionMarker a -> Draw (a, SelectionMarker a)
selectUnchosen candidates (SelectionMarker seen) = do
    let unchosen      = [ c | c <- candidates, c `Set.notMember` seen ]
        (pool, seen') = if null unchosen then (candidates, Set.empty) else (unchosen, seen)
    picked <- select pool
    return (picked, SelectionMarker (Set.insert picked seen'))

