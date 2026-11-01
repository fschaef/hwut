-- @hwut {
--     title      = "TriggerDispatcher: schedule, priority, and the end of time"
--     build      { framework = "make", executable = "%.exe" }
--     choices {
--         abstract    { features = ["haskell-timeline"] }
--         cancel      { features = ["haskell-timeline"] }
--         edges       { features = ["haskell-timeline"] }
--         priority    { features = ["haskell-timeline"] }
--         schedule    { features = ["haskell-timeline"] }
--         stable      { features = ["haskell-timeline"] }
--         stop        { features = ["haskell-timeline"] }
--         termination { features = ["haskell-timeline"] }
--         yielding    { features = ["haskell-timeline"] }
--     }
--     interactive = true
-- }
--
-- SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
-- _____________________________________________________________________________
--
-- PURPOSE: The Haskell port of 'python/TEST/test-deterministic-timeline.py',
--          choice for choice, held against its GOOD files by '.link'. A
--          Python subclass is a record update of the base 'trigger'; what a
--          Python trigger keeps in 'self' a Haskell one keeps in an IORef.
-- _____________________________________________________________________________
module Main (main) where

import Control.Exception      (catch)
import Control.Monad.IO.Class (liftIO)
import Data.IORef
import System.IO              (fixIO)
import Text.Printf            (printf)

import Hwut.DeterministicTimeline
import Hwut.Runner

-- | RETURN: IO (); a section heading printed.
banner :: String -> IO ()
banner label = putStrLn "" >> putStrLn ("--- " ++ label ++ " ---")

-- | RETURN: Task (); the line printed, from inside a task.
say :: String -> Task ()
say = liftIO . putStrLn

-- | RETURN: IO Trigger, one that says what it is asked to do, and when --
--           its 'SETUP' line said as it is made.
speaking :: String -> String -> IO Trigger
speaking name' timeline' = do
    printf "SETUP: %-7s |%s|\n" name' timeline'
    return (speakingTrigger name' timeline')

-- | RETURN: Trigger, the speaking one, made silently.
speakingTrigger :: String -> String -> Trigger
speakingTrigger name' timeline' = (trigger timeline' name')
    { fire          = \t -> say (printf "  [t:%d] %s fires" t name')
    , onTermination = \end -> printf "  [end:%d] %s notified\n" end name'
    }

-- | RETURN: IO Trigger, one that fires and keeps the base's silent
--           'onTermination'.
mute :: String -> String -> IO Trigger
mute name' timeline' = do
    printf "SETUP: %-7s |%s|  (no on_termination override)\n" name' timeline'
    return (trigger timeline' name') { fire = \t -> say (printf "  [t:%d] %s fires" t name') }

-- | RETURN: IO (); a dispatcher over the triggers, run to completion.
dispatch :: [IO Trigger] -> IO ()
dispatch makers = do
    triggers <- sequence makers
    dispatcher <- newTriggerDispatcher triggers
    runTask (run dispatcher)

-- | RETURN: IO (); a digit's position is its tick -- shown.
runSchedule :: IO ()
runSchedule = do
    banner "staggered: A at 0, B at 2, C at 4"
    dispatch [speaking "A" "1    ", speaking "B" "  1  ", speaking "C" "    1"]
    banner "a SHORT timeline stops contributing; the long one goes on"
    dispatch [speaking "SHORT" "11", speaking "LONG" "111111"]
    banner "the SCHEDULE as built -- '[tick] (priority)name'"
    triggers <- sequence [speaking "A" "12", speaking "B" "21"]
    newTriggerDispatcher triggers >>= print

-- | RETURN: IO (); the lower digit first within one tick -- shown.
runPriority :: IO ()
runPriority = do
    banner "digits swap between ticks: B leads at 0, A leads at 1"
    dispatch [speaking "A" "21", speaking "B" "12"]
    banner "0 is the strongest digit, 9 the weakest"
    dispatch [speaking "WEAK" "9", speaking "STRONG" "0"]

-- | RETURN: IO (); equal digits fire in registration order -- shown.
runStable :: IO ()
runStable = do
    banner "three triggers, all digit 1 at tick 0"
    dispatch [speaking "first" "1", speaking "second" "1", speaking "third" "1"]
    banner "registered BACKWARDS -- the order follows registration, not the name"
    dispatch [speaking "third" "1", speaking "second" "1", speaking "first" "1"]

-- | RETURN: IO (); the end of the timeline is an event with a stated tick -- shown.
runTermination :: IO ()
runTermination = do
    banner "end_tick is the LENGTH -- 5 characters, last firing at tick 0"
    dispatch [speaking "EARLY" "1    "]
    banner "a trigger that NEVER fires is notified all the same"
    dispatch [speaking "FIRES" "1  ", speaking "SILENT" "   "]
    banner "the LONGEST timeline sets end_tick for everybody"
    dispatch [speaking "SHORT" "1", speaking "LONG" "1      "]
    banner "a trigger that does not override is simply silent at the end"
    dispatch [speaking "SPEAKS" "1 ", mute "MUTE" "1 "]

-- | THE YIELD IS WHAT THE DISPATCHER IS FOR: the producer prepares one item
--   per tick, the consumer -- gathered beside the run -- takes it before the
--   next tick prepares another.
runYielding :: IO ()
runYielding = do
    banner "producer fires at every tick; consumer waits between them"
    item     <- newIORef Nothing
    finished <- newIORef False
    printf "SETUP: %-7s |%s|\n" "PROD" "111"
    let producer = (trigger "111" "PROD")
            { fire = \t -> do
                  let prepared = "item@" ++ show t
                  liftIO (writeIORef item (Just prepared))
                  say (printf "  [t:%d] %s prepared %s" t "PROD" prepared)
            , onTermination = \end -> do
                  writeIORef finished True
                  printf "  [end:%d] %s announced end-of-stream\n" end "PROD"
            }
        consume :: Int -> Task ()
        consume taken = do
            waiting <- liftIO (readIORef item)
            case waiting of
                Just it -> do
                    say ("        consumer took " ++ it)
                    liftIO (writeIORef item Nothing)
                    consume (taken + 1)
                Nothing -> do
                    endF <- liftIO (readIORef finished)
                    if endF
                        then say (printf "  consumer saw end-of-stream after %d item(s)" taken)
                        else yield >> consume taken
    dispatcher <- newTriggerDispatcher [producer]
    _ <- runTask (gather [run dispatcher, consume 0])
    putStrLn ""
    putStrLn "Each item was taken BEFORE the next tick prepared one: the run yields."

-- | THE KNOT: the stopping trigger needs the dispatcher it is part of --
--   'fixIO' ties it, lazily, where Python assigns 'stopper.dispatcher' after.
runStop :: IO ()
runStop = do
    banner "stop() after the first tick -- ticks 1.. are not walked, the announcement still comes"
    printf "SETUP: %-7s |%s|\n" "STOPPER" "1111"
    printf "SETUP: %-7s |%s|\n" "OTHER" "1111"
    dispatcher <- fixIO $ \self ->
        newTriggerDispatcher
            [ (speakingTrigger "STOPPER" "1111")
                  { fire = \t -> do
                        fire (speakingTrigger "STOPPER" "1111") t
                        say "  ... asks the dispatcher to stop"
                        liftIO (stop self) }
            , speakingTrigger "OTHER" "1111" ]
    runTask (run dispatcher)
    putStrLn ""
    putStrLn "end_tick is still the timeline's length, not the tick the run stopped at."

-- | A CANCELLATION IS DROPPING THE REST: the run is resumed once -- one tick
--   passes -- and what is left of it is never run.
runCancel :: IO ()
runCancel = do
    banner "cancel() the task carrying run() -- no announcement follows"
    t <- speaking "A" "1111111111"
    dispatcher <- newTriggerDispatcher [t]
    result <- runSteps 1 (run dispatcher)
    case result of
        Nothing -> putStrLn "  run() was cancelled"
        Just () -> putStrLn "  run() ended"
    putStrLn ""
    putStrLn "No '[end:..]' line above: the triggers were abandoned, not ended."

-- | RETURN: IO (); degenerate timelines announce and do not fail -- shown.
runEdges :: IO ()
runEdges = do
    banner "an EMPTY timeline -- end_tick 0"
    dispatch [speaking "EMPTY" ""]
    banner "a timeline of BLANKS -- no digit, so nothing fires"
    dispatch [speaking "BLANK" "    "]
    banner "NO TRIGGERS at all -- nothing to announce, and no failure"
    dispatch []
    putStrLn "  (dispatcher ran; nothing was scheduled)"
    banner "a timeline of blanks beside one that fires"
    dispatch [speaking "BLANK" "   ", speaking "FIRES" " 1 "]

-- | RETURN: IO (); 'fire' refuses, 'onTermination' is silent -- shown.
runAbstract :: IO ()
runAbstract = do
    banner "the BASE 'fire' is abstract -- it refuses"
    dispatch [return (trigger "1" "BARE")]
        `catch` \NotImplementedError ->
            putStrLn "  NotImplementedError -- as owed: a trigger must say what it does"
    banner "the BASE 'on_termination' is optional -- it is silent"
    onTermination (trigger "" "BARE") 0
    putStrLn "  returned quietly; nothing raised, nothing printed"
    banner "a NAME given is the name kept"
    putStrLn ("  name: " ++ name (trigger "1" "GIVEN"))

-- | RETURN: IO (); the mode the command line selects has run.
main :: IO ()
main = hwutRunner "TriggerDispatcher: schedule, priority, and the end of time"
    [ ("schedule",    runSchedule)
    , ("priority",    runPriority)
    , ("stable",      runStable)
    , ("termination", runTermination)
    , ("yielding",    runYielding)
    , ("stop",        runStop)
    , ("cancel",      runCancel)
    , ("edges",       runEdges)
    , ("abstract",    runAbstract)
    ]
