-- SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
-- _____________________________________________________________________________
--
-- PURPOSE: Races drawn as strings -- the port of
--          'python/deterministic_timeline.py'.
--
--     import Hwut.DeterministicTimeline
--
--     main = do
--         dispatcher <- newTriggerDispatcher
--             [ (trigger "1 1 3 1   1" "SUB") { fire = \t -> liftIO (print t) }
--             , (trigger "2  121  1  " "NOM") { fire = \t -> liftIO (print t) } ]
--         runTask (run dispatcher)
--
-- A digit's POSITION in a timeline is its tick; within one tick the LOWER
-- digit fires first, equal digits in registration order. When the last tick
-- has passed every trigger is told 'onTermination endTick' -- 'endTick' the
-- length of the longest timeline. 'stop' leaves early and still announces;
-- a CANCELLED run announces nothing.
--
-- NO ASYNCIO: A TASK IS A SUSPENDED COMPUTATION. 'Task' is a coroutine monad
-- of its own: 'resume' runs a task to its next 'yield' and hands back what is
-- left of it ('Suspended') or its result ('Done'). The scheduler is explicit:
--
--     runTask t        resume until done                (asyncio.run)
--     gather [a, b]    resume a, then b, round by round   (asyncio.gather)
--     yield            hand control back                 (asyncio.sleep(0))
--     a cancellation   DROPPING the suspended rest -- nothing more is run,
--                      nothing announced; 'runSteps' says Nothing
--
-- 'gather' resumes its tasks in the order given, each to its next yield, as
-- asyncio's ready queue does: the interleaving is the Python test's, step
-- for step.
--
-- A TRIGGER IS A RECORD OF FUNCTIONS: 'trigger' gives the base -- 'fire'
-- refuses with 'NotImplementedError' (it is abstract), 'onTermination' does
-- nothing -- and a test overrides a field by record update. An unnamed
-- trigger (name "") is named by its place in the dispatcher, 'trigger-<i>':
-- a Haskell value has no address to be named by.
-- _____________________________________________________________________________
module Hwut.DeterministicTimeline
    ( -- * the coroutine
      Task
    , Step (..)
    , resume
    , yield
    , runTask
    , runSteps
    , gather
      -- * triggers and their dispatcher
    , Trigger (..)
    , NotImplementedError (..)
    , trigger
    , TriggerDispatcher
    , newTriggerDispatcher
    , schedule
    , endTick
    , stop
    , run
    ) where

import Control.Exception      (Exception, throwIO)
import Control.Monad          (ap, forM_, liftM, when)
import Control.Monad.IO.Class (MonadIO (..))
import Data.Char              (isDigit, ord)
import Data.IORef             (IORef, newIORef, readIORef, writeIORef)
import Data.List              (intercalate, sortOn)

-- ------------------------------------------------------------- the coroutine

-- | A computation that may hand control back ('yield') before it is done.
newtype Task a = Task { resume :: IO (Step a) }

-- | What one 'resume' leaves: the result, or the rest of the task.
data Step a = Done a | Suspended (Task a)

instance Functor Task where
    fmap = liftM

instance Applicative Task where
    pure x = Task (return (Done x))
    (<*>)  = ap

instance Monad Task where
    Task first >>= next = Task $ do
        step <- first
        case step of
            Done x         -> resume (next x)
            Suspended rest -> return (Suspended (rest >>= next))

instance MonadIO Task where
    liftIO action = Task (Done <$> action)

-- | RETURN: Task (), one that hands control back once, then is done.
yield :: Task ()
yield = Task (return (Suspended (pure ())))

-- | RETURN: IO a, the task's result, once it has been resumed to its end.
runTask :: Task a -> IO a
runTask task = do
    step <- resume task
    case step of
        Done x         -> return x
        Suspended rest -> runTask rest

-- | RETURN: IO (Maybe a), Just the result where the task ends within 'n'
--           resumptions; Nothing where it does not -- then it is CANCELLED:
--           its rest is dropped, never run.
runSteps :: Int -> Task a -> IO (Maybe a)
runSteps n task
    | n <= 0    = return Nothing
    | otherwise = do
        step <- resume task
        case step of
            Done x         -> return (Just x)
            Suspended rest -> runSteps (n - 1) rest

-- | RETURN: Task [a], the results of 'tasks' in their order, once every one
--           is done. Round by round each unfinished task is resumed to its
--           next yield, in the order given, and the gathering task yields
--           between rounds -- asyncio.gather's interleaving.
gather :: [Task a] -> Task [a]
gather tasks = go (map Left tasks)
  where
    go slots
        | all finished slots = return [ x | Right x <- slots ]
        | otherwise = do
            slots' <- liftIO (mapM step slots)
            if all finished slots' then go slots' else yield >> go slots'
    step (Left task) = do
        s <- resume task
        return $ case s of
            Done x         -> Right x
            Suspended rest -> Left rest
    step done = return done
    finished = either (const False) (const True)

-- ------------------------------------------------------------------ triggers

-- | 'fire' of the base 'trigger': a trigger must say what it does.
data NotImplementedError = NotImplementedError deriving Show

instance Exception NotImplementedError

-- | A dispatchable event: where its timeline puts it, what it does then,
--   and what it does once the timeline has passed.
data Trigger = Trigger
    { timeline      :: String              -- ^ digits 0-9 mark its ticks
    , name          :: String
    , fire          :: Int -> Task ()      -- ^ at a tick its timeline marks
    , onTermination :: Int -> IO ()        -- ^ once, with the end tick
    }

-- | RETURN: Trigger, the base: 'fire' raises NotImplementedError (abstract),
--           'onTermination' does nothing (optional).
trigger :: String -> String -> Trigger
trigger timeline' name' = Trigger
    { timeline      = timeline'
    , name          = name'
    , fire          = \_ -> liftIO (throwIO NotImplementedError)
    , onTermination = \_ -> return ()
    }

-- | The triggers, their schedule built once, and whether the run goes on.
data TriggerDispatcher = TriggerDispatcher
    { triggerList :: [Trigger]
    , schedule    :: [[(Int, Trigger)]]   -- ^ per tick: (priority, trigger), in firing order
    , endTick     :: Int                  -- ^ the length of the longest timeline
    , runningRef  :: IORef Bool
    }

-- | RETURN: IO TriggerDispatcher, over 'triggers', its schedule built: per
--           tick the (priority, trigger) pairs whose timeline has a digit
--           there, sorted by priority -- stably, so equal digits keep the
--           registration order. The schedule is as long as the longest
--           timeline. A trigger named "" is named 'trigger-<i>', its place.
newTriggerDispatcher :: [Trigger] -> IO TriggerDispatcher
newTriggerDispatcher triggers = do
    ref <- newIORef True
    let named   = [ if null (name t) then t { name = "trigger-" ++ show i } else t
                  | (i, t) <- zip [0 :: Int ..] triggers ]
        end     = maximum (0 : map (length . timeline) named)
        atTick k = sortOn fst [ (ord c - ord '0', t)
                              | t <- named, (j, c) <- zip [0 ..] (timeline t), j == k, isDigit c ]
    return (TriggerDispatcher named [ atTick k | k <- [0 .. end - 1] ] end ref)

-- | RETURN: IO (); the run leaves the timeline at its next step -- and still
--           announces the end.
stop :: TriggerDispatcher -> IO ()
stop dispatcher = writeIORef (runningRef dispatcher) False

-- | RETURN: Task (), the timeline walked tick by tick: every trigger due at a
--           tick fires in order, and the run YIELDS after each one, so that a
--           consumer of what it produced may progress. Then -- walked to the
--           end or stopped -- every trigger is told 'onTermination endTick'.
--           Dropped (cancelled) before that, it tells nobody.
run :: TriggerDispatcher -> Task ()
run dispatcher = do
    walk (zip [0 ..] (schedule dispatcher))
    liftIO (forM_ (triggerList dispatcher) (\t -> onTermination t (endTick dispatcher)))
  where
    runningF = liftIO (readIORef (runningRef dispatcher))
    walk [] = return ()
    walk ((tick, due) : later) = do
        goingF <- runningF
        when goingF $ do
            fireAll tick due
            walk later
    fireAll _ [] = return ()
    fireAll tick ((_, t) : rest) = do
        goingF <- runningF
        when goingF $ do
            fire t tick
            yield
            fireAll tick rest

-- | 'show' is Python's 'repr': the schedule as built, one line per firing,
--   '[tick] (priority)name'.
instance Show TriggerDispatcher where
    show dispatcher = intercalate "\n" ("TriggerDispatcher" :
        [ "[" ++ show tick ++ "] (" ++ show priority ++ ")" ++ name t
        | (tick, due) <- zip [0 :: Int ..] (schedule dispatcher), (priority, t) <- due ])
