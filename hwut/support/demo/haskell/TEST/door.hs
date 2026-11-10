-- @hwut {
--     title   = "Demo: a door's state machine, watched by a pype"
--     build   { framework = "make", target = "%.exe" }
--     pype    = "door.pype"
--     choices {
--         kept   { features = ["demo-haskell", "demo-haskell+cover-fsm-law-kept"] }
--         broken { features = ["demo-haskell", "demo-haskell+cover-fsm-law-broken"] }
--     }
-- }
--
-- _____________________________________________________________________________
-- A DOOR CONTROLLER THAT REPORTS WHAT IT DOES -- and a model that says what it
-- may do.
--
-- The application prints its log as it happens: noise, and a line 'door:
-- <event>' for each thing the door does. It prints no '<hwut-end>': the
-- header names 'door.pype', which stands between it and the comparison and
-- closes the stream at '<eof>'.
--
-- 'door.pype' parses the log and fires every event into a state machine
-- ('hwut_fsm'). The pype is a Python script whatever language the program
-- is written in: the model it builds is the Python support's
-- ('support/test_writing/python'), the program here only prints.
--
--     closed ---( open )---> open ---( close )---> closed
--     closed ---( lock )---> locked ---( unlock )---> closed
--     open   ---( slam )---> jammed          # forbidden
--
-- kept     the door does what the model allows; the report shows which
--          transitions were taken and which not, and 'ended in closed'.
-- broken   the controller locks an open door, slams it into a jam and
--          tries to unlock it: each surprise is ONE 'BREACH' line in the
--          output, the jam included, and the end outside the final states
--          is one more. The GOOD file holds them and a run that stops
--          breaching -- or breaches differently -- shows up as a difference.
--
-- Both choices pass on every run: what they print does not depend on time.
-- _____________________________________________________________________________
module Main (main) where

import Control.Monad      (forM_)
import System.Environment (getArgs)
import System.Exit        (ExitCode (..), exitWith)
import Text.Printf        (printf)

storyList :: [(String, [String])]
storyList = [ ("kept",   ["open", "close", "lock", "unlock", "open", "close"])
            , ("broken", ["open", "lock", "slam", "unlock"]) ]

-- | RETURN: IO (); the log of the door for the story 'eventList', printed.
door :: [String] -> IO ()
door eventList = do
    putStrLn "controller 2.1 up"
    forM_ (zip [1 :: Int ..] eventList) $ \(number, event) -> do
        printf "tick %d: sensors read\n" number
        putStrLn ("door: " ++ event)
    putStrLn "controller down"

-- | RETURN: IO (); the story the command line names, printed; exit 1 where
--           none is named.
main :: IO ()
main = do
    arguments <- getArgs
    case arguments of
        [word] | Just eventList <- lookup word storyList -> door eventList
        _ -> do
            putStrLn "error: a choice is required: broken, kept"
            exitWith (ExitFailure 1)
