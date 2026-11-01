-- @hwut {
--     title      = "DeterministicStream RNG and SelectionMarker spread"
--     build      { framework = "make", executable = "%.exe" }
--     choices {
--         gauss      { features = ["haskell-random"] }
--         primitives { features = ["haskell-random"] }
--         ranges     { features = ["haskell-random"] }
--         sample     { features = ["haskell-random"] }
--         seed_sweep { features = ["haskell-random"] }
--         select     { features = ["haskell-random"] }
--         unchosen   { features = ["haskell-random"] }
--     }
--     interactive = true
-- }
--
-- SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
-- _____________________________________________________________________________
--
-- PURPOSE: The Haskell port of 'python/TEST/test-deterministic-random.py',
--          held against its GOOD files by '.link'. Every draw is a pure
--          'Draw' run on a stream value; what a choice prints is computed
--          first and printed at the edge.
-- _____________________________________________________________________________
module Main (main) where

import Control.Monad.State (evalState, replicateM)
import Text.Printf         (printf)

import Hwut.DeterministicRandom
import Hwut.PyText
import Hwut.Runner

-- | The seed of every choice but seed_sweep.
seed :: Int
seed = 0x42

-- | RETURN: a, what 'draw' gives on a fresh stream of 'seed'.
drawn :: Draw a -> a
drawn draw = evalState draw (deterministicStream seed)

-- | RETURN: IO (); a section heading printed.
banner :: String -> IO ()
banner label = putStrLn "" >> putStrLn ("--- " ++ label ++ " ---")

toleranceRegionBegin, regionEnd :: String
toleranceRegionBegin = "##! table numeric={1:1e-12}"
regionEnd            = "####"

-- | RETURN: IO (); each value on a line of its own, '[ii] value'.
numbered :: [String] -> IO ()
numbered values = mapM_ (\(i, v) -> printf "[%02d] %s\n" (i :: Int) v) (zip [0 ..] values)

-- | RETURN: IO (); the bare generator printed: nextInt, nextFloat, coin.
runPrimitives :: IO ()
runPrimitives = do
    banner "next_int(0, 1000000) -- first 20"
    numbered (map show (drawn (replicateM 20 (nextInt 0 1000000))))
    banner "next_float -- first 10 (full precision)"
    numbered (map floatRepr (drawn (replicateM 10 nextFloat)))
    banner "coin(0.5) -- 40 draws"
    putStrLn (unwords [ if c then "T" else "F" | c <- drawn (replicateM 40 (coin 0.5)) ])

-- | RETURN: IO (); nextInt over small and degenerate ranges printed.
runRanges :: IO ()
runRanges = do
    banner "next_int(0, 9) -- 30 draws"
    putStrLn (unwords (map show (drawn (replicateM 30 (nextInt 0 9)))))
    banner "next_int(5, 5) -- degenerate range returns the bound"
    putStrLn (unwords (map show (drawn (replicateM 5 (nextInt 5 5)))))
    banner "next_int(-3, 3) -- spanning zero"
    putStrLn (unwords (map (printf "%+d") (drawn (replicateM 20 (nextInt (-3) 3))) :: [String]))

-- | RETURN: IO (); the libm path printed: gauss, clamped gauss, gaussInt --
--           the two full-precision blocks framed as a tolerated table region.
runGauss :: IO ()
runGauss = do
    banner "gauss(0, 1) -- 10 draws (full precision)"
    putStrLn toleranceRegionBegin
    numbered (map floatRepr (drawn (replicateM 10 (gauss 0 1))))
    putStrLn regionEnd
    banner "gauss(0, 1) clamped to [-1, 1]"
    putStrLn toleranceRegionBegin
    numbered (map floatRepr (drawn (replicateM 10 (gaussClipped 0 1 (-1) 1))))
    putStrLn regionEnd
    banner "gauss_int(100, 15) -- 20 draws"
    putStrLn (unwords (map show (drawn (replicateM 20 (gaussInt 100 15)))))

-- | RETURN: IO (); sampleIndices (Fisher-Yates) and sample printed.
runSample :: IO ()
runSample = do
    banner "sample_indices(10, 10) -- full permutation"
    putStrLn (pyRepr (drawn (sampleIndices 10 10)))
    banner "sample_indices(20, 5) -- partial draw"
    putStrLn (pyRepr (drawn (sampleIndices 20 5)))
    banner "choice from a list -- 20 draws"
    putStrLn (unwords (drawn (replicateM 20 (choice ["alpha", "beta", "gamma", "delta", "epsilon"]))))
    banner "sample(list, 4) -- unique elements"
    putStrLn (pyRepr (map (: []) (drawn (sample "ABCDEFGH" 4))))

-- | RETURN: IO (); stateless select printed: same stream, same pool, same element.
runSelect :: IO ()
runSelect = do
    banner "select over a list -- 20 draws"
    putStrLn (unwords (drawn (replicateM 20 (select ["a", "b", "c", "d"]))))
    banner "select over a tuple -- 12 draws"
    putStrLn (unwords (drawn (replicateM 12 (select ["p", "q", "r"]))))

-- | RETURN: Draw ([a], SelectionMarker a), one 'selectUnchosen' per pool of
--           'pools', the marker threaded from one to the next.
unchosenOver :: Ord a => [[a]] -> SelectionMarker a -> Draw ([a], SelectionMarker a)
unchosenOver []             marker = return ([], marker)
unchosenOver (pool : pools) marker = do
    (picked, marker')  <- selectUnchosen pool marker
    (rest, marker'')   <- unchosenOver pools marker'
    return (picked : rest, marker'')

-- | RETURN: IO (); selectUnchosen printed: a clean cycle, the same cycle over
--           fresh lists, coherence across sub-pools, reset.
runUnchosen :: IO ()
runUnchosen = do
    let pool = ["a", "b", "c", "d"]
    banner "stable pool -- three full cycles of 4 elements"
    putStrLn (unwords (fst (drawn (unchosenOver (replicate 12 pool) selectionMarker))))
    banner "FRESH container each call -- identical to the stable pool above"
    --  A FRESH LIST EVERY CALL: in Haskell a fresh list is an equal one --
    --  there is no address to tell it from the first.
    putStrLn (unwords (fst (drawn (unchosenOver [ ["a", "b", "c", "d"] | _ <- [1 .. 12 :: Int] ] selectionMarker))))
    banner "sub-pool coherence -- draw from [a,b] then the full [a,b,c,d]"
    let (first, rest) = splitAt 1 (fst (drawn (unchosenOver (["a", "b"] : replicate 3 pool) selectionMarker)))
    putStrLn ("first(from sub): " ++ concat first ++ "  then(from full): " ++ unwords rest)
    banner "reset() restarts the cycle"
    let (before, after) = drawn $ do
            (b, marker) <- unchosenOver (replicate 4 pool) selectionMarker
            (a, _)      <- unchosenOver (replicate 4 pool) (reset marker)
            return (b, a)
    putStrLn ("before reset: " ++ unwords before)
    putStrLn ("after  reset: " ++ unwords after)

-- | RETURN: IO (); the first nextInt per seed 0..15 printed.
runSeedSweep :: IO ()
runSeedSweep = do
    banner "first next_int(0, 1000000) per seed 0..15"
    mapM_ (\s -> printf "seed=%2d -> %d\n" s (evalState (nextInt 0 1000000) (deterministicStream s)))
          [0 .. 15 :: Int]

-- | RETURN: IO (); the mode the command line selects has run.
main :: IO ()
main = hwutRunner "DeterministicStream RNG and SelectionMarker spread"
    [ ("primitives", runPrimitives)
    , ("ranges",     runRanges)
    , ("gauss",      runGauss)
    , ("sample",     runSample)
    , ("select",     runSelect)
    , ("unchosen",   runUnchosen)
    , ("seed_sweep", runSeedSweep)
    ]
