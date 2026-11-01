-- SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
-- _____________________________________________________________________________
--
-- PURPOSE: The producer 'protocol.sh clean' feeds 'protocol.pype' with -- no
--          test, a helper ('hwut.conf' ignores it; 'on_entry' builds it).
--
--     producer.exe
--
-- Five clients talk to a service at once, each in a thread of its own: a
-- request, a while, its response. Then 'shutdown'. Every line is printed as
-- it happens, under one lock, and flushed: the pype reads it live. The
-- order of the lines is the scheduler's.
-- _____________________________________________________________________________
module Main (main) where

import Control.Concurrent      (forkIO, threadDelay)
import Control.Concurrent.MVar (newEmptyMVar, newMVar, putMVar, takeMVar, withMVar)
import Control.Monad           (forM)
import System.IO               (hFlush, stdout)

import ClockRandom

-- | RETURN: IO (); the five exchanges and the shutdown, printed as they
--           happen.
main :: IO ()
main = do
    rng  <- newRng
    lock <- newMVar ()
    let say text = withMVar lock (\_ -> putStrLn text >> hFlush stdout)
        pause    = uniform rng 0.0 0.02 >>= \s -> threadDelay (round (s * 1000000))
    doneList <- forM [1 .. 5 :: Int] $ \n -> do
        done <- newEmptyMVar
        _ <- forkIO $ do
            pause >> say ("request " ++ show n)
            pause >> say ("response " ++ show n)
            putMVar done ()
        return done
    mapM_ takeMVar doneList
    say "shutdown"
