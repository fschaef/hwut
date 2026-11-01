-- @hwut {
--     title      = "hwut_fsm: a state machine as the test's model of the system"
--     build      { framework = "make", executable = "%.exe" }
--     choices {
--         syntax    { features = ["haskell-fsm"] }
--         refused   { features = ["haskell-fsm"] }
--         dfa       { features = ["haskell-fsm"] }
--         nfa       { features = ["haskell-fsm"] }
--         forbidden { features = ["haskell-fsm"] }
--         model     { features = ["haskell-fsm"] }
--         report    { features = ["haskell-fsm"] }
--         masks     { features = ["haskell-fsm"] }
--     }
--     interactive = true
-- }
--
-- SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
-- _____________________________________________________________________________
--
-- PURPOSE: The Haskell port of 'python/TEST/test-hwut_fsm.py', choice for
--          choice, held against its GOOD files by '.link'. Every choice is
--          ONE pure run of the machine ('execFsm'): the test's own lines are
--          written into the machine's log ('write') between the machine's
--          breach lines, and the whole log is printed at the end.
-- _____________________________________________________________________________
module Main (main) where

import           Control.Monad  (forM_, void)
import           Data.List      (intercalate)
import qualified Data.Set       as Set
import           Text.Printf    (printf)

import           Hwut.Fsm
import           Hwut.PyText
import           Hwut.Runner

-- | THE PROTOCOL OF EVERY CHOICE: a request is waited on, granted,
--   released; a fault while busy crashes it -- which must never happen.
protocol :: String
protocol = unlines
    [ ""
    , "    initial:   idle"
    , "    forbidden: crashed"
    , "    final:     idle"
    , "    idle    ---( request )---> waiting ---( grant )---> busy"
    , "    busy    ---( release )---> idle"
    , "    :       ---( fault )--->   crashed       # the state that began line 6"
    , "    waiting ---( cancel )---> idle"
    ]

-- | RETURN: Fsm (); a section heading written into the log.
banner :: String -> Fsm ()
banner label = write "" >> write ("--- " ++ label ++ " ---")

-- | RETURN: Machine, the model 'text' states -- the tests' models are meant.
machineOf :: Options -> String -> Machine
machineOf options text = either (error . show) id (fromString options text)

-- | RETURN: IO (); the run of 'action' on the machine of 'text', its log
--           printed.
running :: Options -> String -> Fsm a -> IO ()
running options text action = mapM_ putStrLn (execFsm (machineOf options text) action)

-- | RETURN: Fsm a, a question of the machine as it stands.
asked :: (Machine -> a) -> Fsm a
asked question = question <$> getMachine

-- | RETURN: String, Python's 'repr' of a path: a tuple of str, or None.
pathRepr :: Maybe [String] -> String
pathRepr = pyRepr . fmap PyTuple

-- | RETURN: IO (); models read from text and written back, printed.
runSyntax :: IO ()
runSyntax = do
    putStrLn "" >> putStrLn "--- the protocol, written back ---"
    putStrLn (toString (machineOf defaultOptions protocol))
    putStrLn "" >> putStrLn "--- the author's form: 'state', a chain, ':', blanks around '-->' ---"
    putStrLn $ toString $ machineOf defaultOptions $ unlines
        [ ""
        , "        state A ---( event )---> state B"
        , "        :                ---(event2)---> state C ---(event) --> state D"
        , "        state E          # no transition yet"
        , "    " ]

-- | RETURN: IO (); each model that cannot be meant, and why, printed.
runRefused :: IO ()
runRefused = forM_ texts $ \text -> do
    putStrLn "" >> putStrLn ("--- " ++ intercalate " | " (lines text) ++ " ---")
    putStrLn $ case fromString defaultOptions text of
        Left problem -> "FsmError: " ++ show problem
        Right _      -> "accepted"
  where
    texts = [ "A ---( x )---> B\n: ---( x )---> C"
            , "A ---(  )---> B"
            , ": ---( x )---> B"
            , "A B ---( x )---> C"
            , "initial: A, B\nA ---( x )---> B"
            , "forbidden: Q\nA ---( x )---> B"
            , "# nothing but a comment" ]

-- | RETURN: IO (); events fired at one machine, and its answers, printed.
runDfa :: IO ()
runDfa = running defaultOptions protocol $ do
    forM_ (zip [1 ..] ["request", "release", "grant", "release", "jump", "request"]) $ \(number, event) -> do
        moved <- fire event (Line number)
        now   <- state
        names <- asked allowed
        write (printf "    %-8s -> %-5s now %-8s allowed: %s" event (pyBool moved) now (intercalate ", " names))
    banner "questions where it stands"
    asked (can "grant")   >>= \x -> write ("can('grant')   " ++ pyBool x)
    asked (can "release") >>= \x -> write ("can('release') " ++ pyBool x)
    asked (inState "waiting") >>= \x -> write ("in_state('waiting') " ++ pyBool x)
    steps <- asked trace
    write ("trace: " ++ unwords [ whereStr w ++ ":" ++ e ++ ">" ++ t | (w, _, e, t) <- steps ])
  where
    whereStr (Line n)  = show n
    whereStr (Place s) = s
    whereStr Nowhere   = "None"

-- | RETURN: IO (); a machine of several states at once (DFA off), printed.
runNfa :: IO ()
runNfa = running defaultOptions { dfaF = False } model $ do
    forM_ ["x", "z", "y"] $ \event -> do
        _ <- fire event (Place ("t=" ++ event))
        now <- asked current
        write ("    after " ++ event ++ ": " ++ intercalate ", " (Set.toAscList now))
    banner "'state' asked of a set"
    reset
    _ <- fire "x" Nowhere
    (state >>= write) `catchFsm` (\problem -> write ("FsmError: " ++ show problem))
  where
    model = unlines [ ""
                    , "        A ---( x )---> B ---( y )---> D"
                    , "        : ---( x )---> C ---( y )---> E"
                    , "        C ---( z )---> F"
                    , "    " ]

-- | RETURN: IO (); a forbidden state entered, printed.
runForbidden :: IO ()
runForbidden = running defaultOptions protocol $ do
    forM_ (zip [1 ..] ["request", "grant", "fault"]) $ \(number, event) -> do
        moved <- fire event (Line number)
        write (printf "    %-8s -> %s" event (pyBool moved))
    now <- state
    n   <- asked breachN
    write ("now in " ++ now ++ " -- breaches: " ++ show n)

-- | RETURN: IO (); the questions of the model alone, printed.
runModel :: IO ()
runModel = running defaultOptions (protocol ++ "\n    state limbo\n    limbo ---( kick )---> idle\n") $ do
    n <- check True
    write ("check: " ++ show n)
    banner "path_to"
    forM_ ["busy", "crashed", "limbo", "idle"] $ \s -> do
        path <- asked (pathTo FromInitial True s)
        write (printf "    %-8s %s" s (pathRepr path))
    _ <- fire "request" Nowhere
    asked (pathTo FromNow True "busy") >>= \path -> write ("    busy from now: " ++ pathRepr path)
    asked (stateReachable FromNow True "idle") >>= \x ->
        write ("    state_reachable('idle', start='now'): " ++ pyBool x)

-- | RETURN: IO (); the coverage report and an end outside the final states, printed.
runReport :: IO ()
runReport = running defaultOptions { machineName = "protocol" } protocol $ do
    mapM_ (\event -> fire event Nowhere) ["request", "grant", "release", "request", "grant"]
    n <- report
    write ("report returns " ++ show n)

-- | RETURN: IO (); the law changing while the machine runs, printed.
runMasks :: IO ()
runMasks = running defaultOptions protocol $ do
    banner "'grant' disallowed in every state, since line 2"
    disallow "grant" Nothing (Line 2)
    _ <- fire "request" (Line 3)
    names <- asked allowed
    granting <- asked (can "grant")
    write ("    allowed now: " ++ intercalate ", " names ++ " -- can('grant'): " ++ pyBool granting)
    _ <- fire "grant" (Line 4)
    asked (pathTo FromInitial True "busy")  >>= \p -> write ("    path_to('busy'):               " ++ pathRepr p)
    asked (pathTo FromInitial False "busy") >>= \p -> write ("    path_to('busy', masked=False): " ++ pathRepr p)
    check True  >>= \n -> write ("    check(): " ++ show n)
    check False >>= \n -> write ("    check(masked=False): " ++ show n)
    banner "allowed again; 'busy' forbidden while standing in it"
    allow "grant" Nothing (Line 5)
    _ <- fire "grant" (Line 6)
    forbid "busy" (Line 7)
    _ <- fire "release" (Line 8)
    _ <- fire "request" (Line 9)
    _ <- fire "grant" (Line 10)
    banner "permitted: 'busy', and the model's own 'crashed'"
    permit "busy" (Line 11)
    permit "crashed" (Line 12)
    moved <- fire "fault" (Line 13)
    now <- state
    write ("    fault -> " ++ pyBool moved ++ " -- now in " ++ now)
    banner "a phase: 'release' disallowed in 'busy' for a block"
    reset
    _ <- fire "request" Nowhere
    _ <- fire "grant" Nowhere
    _ <- disallowed "release" (Just "busy") (Place "phase") (fire "release" (Line 20))
    _ <- fire "release" (Line 21)
    disallow "cancel" Nothing (Line 22)
    void report
    banner "refused: a word the model never names"
    forM_ [ disallow "jump" Nothing Nowhere, forbid "limbo" Nowhere, allow "grant" (Just "nowhere") Nowhere ] $
        \call -> call `catchFsm` (\problem -> write ("FsmError: " ++ show problem))

-- | RETURN: IO (); the mode the command line selects has run.
main :: IO ()
main = hwutRunner "hwut_fsm: a state machine as the test's model of the system"
    [ ("syntax",    runSyntax)
    , ("refused",   runRefused)
    , ("dfa",       runDfa)
    , ("nfa",       runNfa)
    , ("forbidden", runForbidden)
    , ("model",     runModel)
    , ("report",    runReport)
    , ("masks",     runMasks)
    ]
