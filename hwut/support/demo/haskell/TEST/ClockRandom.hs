-- SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
-- _____________________________________________________________________________
--
-- PURPOSE: A random generator SEEDED BY THE CLOCK -- what Python's 'random'
--          is to the Python demonstration, for the tests here whose runs
--          differ from run to run on purpose. No test; a module the tests
--          import ('hwut.conf' ignores it).
--
--     rng <- newRng
--     x   <- uniform rng 19.91 20.09
--
-- GHC ships no 'random' package (it is Hackage's), and the support's
-- 'DeterministicStream' is the opposite of what is wanted here: the same
-- everywhere. So: SplitMix64 over an IORef, stepped atomically -- several
-- threads may draw from one generator.
-- _____________________________________________________________________________
module ClockRandom
    ( Rng
    , newRng
    , random
    , uniform
    , randint
    , gauss
    , choice
    , shuffle
    , sample
    ) where

import Data.Bits             (shiftR, xor)
import Data.IORef            (IORef, atomicModifyIORef', newIORef)
import Data.Time.Clock.POSIX (getPOSIXTime)
import Data.Word             (Word64)

-- | A generator: its state, shared by whoever holds it.
newtype Rng = Rng (IORef Word64)

-- | RETURN: IO Rng, a generator seeded by the clock's nanoseconds.
newRng :: IO Rng
newRng = do
    now <- getPOSIXTime
    Rng <$> newIORef (floor (now * 1000000000))

-- | RETURN: IO Word64, the next 64 bits of SplitMix64.
next64 :: Rng -> IO Word64
next64 (Rng ref) = atomicModifyIORef' ref $ \s ->
    let s' = s + 0x9e3779b97f4a7c15
        z1 = (s' `xor` (s' `shiftR` 30)) * 0xbf58476d1ce4e5b9
        z2 = (z1 `xor` (z1 `shiftR` 27)) * 0x94d049bb133111eb
    in  (s', z2 `xor` (z2 `shiftR` 31))

-- | RETURN: IO Double, a number in [0, 1), 53 bits of it drawn.
random :: Rng -> IO Double
random rng = (\w -> fromIntegral (w `shiftR` 11) / 9007199254740992) <$> next64 rng

-- | RETURN: IO Double, a number in [low, high] (Python's 'uniform').
uniform :: Rng -> Double -> Double -> IO Double
uniform rng low high = (\r -> low + (high - low) * r) <$> random rng

-- | RETURN: IO Int, an integer in [low, high], both included.
randint :: Rng -> Int -> Int -> IO Int
randint rng low high = (\w -> low + fromIntegral (w `mod` fromIntegral (high - low + 1))) <$> next64 rng

-- | RETURN: IO Double, a draw of the normal distribution (mu, sigma), by
--           the Box-Muller transform.
gauss :: Rng -> Double -> Double -> IO Double
gauss rng mu sigma = do
    u1 <- random rng
    u2 <- random rng
    return (mu + sigma * sqrt (-2 * log (1 - u1)) * cos (2 * pi * u2))

-- | RETURN: IO a, an element of the non-empty 'candidates', drawn uniformly.
choice :: Rng -> [a] -> IO a
choice rng candidates = (candidates !!) <$> randint rng 0 (length candidates - 1)

-- | RETURN: IO [a], 'items' in an order drawn uniformly.
shuffle :: Rng -> [a] -> IO [a]
shuffle _   []    = return []
shuffle rng items = do
    i <- randint rng 0 (length items - 1)
    let (before, picked : after) = splitAt i items
    (picked :) <$> shuffle rng (before ++ after)

-- | RETURN: IO [Int], 'k' distinct integers of [low, high), drawn uniformly
--           (Python's 'sample(range(low, high), k)'); a draw already taken
--           is drawn again.
sample :: Rng -> Int -> Int -> Int -> IO [Int]
sample rng k low high = go []
  where
    go taken
        | length taken == k = return (reverse taken)
        | otherwise         = do
            x <- randint rng low (high - 1)
            go (if x `elem` taken then taken else x : taken)
