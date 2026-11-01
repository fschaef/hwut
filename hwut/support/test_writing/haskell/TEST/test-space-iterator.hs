-- @hwut {
--     title      = "space_iterator: every combination of a parameter basis"
--     build      { framework = "make", executable = "%.exe" }
--     choices {
--         product { features = ["haskell-space"] }
--         edges   { features = ["haskell-space"] }
--     }
--     interactive = true
-- }
--
-- SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
-- _____________________________________________________________________________
--
-- PURPOSE: The Haskell port of 'python/TEST/test-space-iterator.py', held
--          against its GOOD files by '.link'. Python's dimensions mix ints
--          and strs; here a dimension holds 'Value', a sum of the two.
-- _____________________________________________________________________________
module Main (main) where

import Data.List (intercalate)

import qualified Hwut.SpaceIterator as SpaceIterator
import           Hwut.Runner

-- | One value of a dimension: an int or a str, printed as Python's 'str'.
data Value = I Int | S String

-- | RETURN: String, the value as Python's 'str' prints it.
str :: Value -> String
str (I n) = show n
str (S s) = s

-- | RETURN: IO (); a section heading printed.
banner :: String -> IO ()
banner label = putStrLn "" >> putStrLn ("--- " ++ label ++ " ---")

-- | RETURN: IO (); every point of 'basis', one per line, then the count.
points :: [[Value]] -> IO ()
points basis = do
    let all' = SpaceIterator.do' basis
    mapM_ (\point -> putStrLn ("  (" ++ intercalate ", " (map str point) ++ ")")) all'
    putStrLn ("  " ++ show (length all') ++ " point(s)")

-- | RETURN: IO (); three dimensions, the rightmost changing fastest, printed.
runProduct :: IO ()
runProduct = do
    banner "[0, 2, 4] x [otto, heinz] x [1, 2] -- 3 * 2 * 2 points"
    points [map I [0, 2, 4], map S ["otto", "heinz"], map I [1, 2]]

-- | RETURN: IO (); the empty basis, an empty dimension, one dimension, printed.
runEdges :: IO ()
runEdges = do
    banner "an EMPTY basis -- one point, the empty one"
    points []
    banner "a basis with an EMPTY dimension -- nothing"
    points [map I [1, 2], [], [I 3]]
    banner "ONE dimension -- its values one by one"
    points [map S ["a", "b", "c"]]

-- | RETURN: IO (); the mode the command line selects has run.
main :: IO ()
main = hwutRunner "space_iterator: every combination of a parameter basis"
    [ ("product", runProduct)
    , ("edges",   runEdges)
    ]
