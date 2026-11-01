-- @hwut {
--     title    = "Demo: a garage's space counter -- a space, a stream and races, generated"
--     build    { framework = "make", executable = "%.exe" }
--     interactive = true
--     choices {
--         space       { features = ["space-from-hocon", "space-iterator", "hwut-runner"]
--                       tolerance { constraints = ["mismatches == 0"] } }
--         random      { features = ["deterministic-stream", "hwut-runner"]
--                       tolerance { constraints = ["mismatches == 0"] } }
--         race-naive  { features = ["deterministic-timeline", "space-iterator", "hwut-runner"]
--                       tolerance { constraints = ["overbooked > 0"] } }
--         race-atomic { features = ["deterministic-timeline", "space-iterator", "hwut-runner"]
--                       tolerance { constraints = ["overbooked == 0"] } }
--     }
-- }
--
-- _____________________________________________________________________________
-- SUBJECT  the counter of free spaces at a garage's gates: which cars it
--          admits, which it refuses, and how many stand inside.
-- REQUIREMENT  The garage admits a car only while a space is free, lets a car
--              out only while one stands inside, and never holds more cars
--              than it has spaces -- also when two gates admit at once.
--
-- No choice writes its cases out by hand. Each GENERATES them, with one of
-- hwut's helpers for writing tests (hwut/support/test_writing/haskell):
--
-- space        'garage-space.hocon' states the tested space -- capacities,
--              cars arriving, cars leaving -- in hwut's HOCON, read by
--              'Hwut.Hocon'. A reviewer edits the space without reading
--              Haskell. 'SpaceIterator.do'' walks every combination: 3 x 5 x
--              4 = 60 cases. Each is printed as one cell of a matrix, and
--              checked against the model: admitted = min(arriving,
--              capacity), out = min(leaving, admitted).
--
-- random       'deterministicStream 4711' draws 1000 cars arriving and
--              leaving at a garage of 5. The draw is the same on every
--              machine and in every language hwut supports -- the stream is
--              a linear congruential generator -- so the GOOD is exact (the
--              Python demonstration's, by link), and a failing run can be
--              replayed by its seed.
--
-- race-naive   two gates, one free space. A gate CHECKS whether a space is
--              free, and later ADMITS its car. 'Hwut.DeterministicTimeline'
--              runs the two gates as Triggers on timelines drawn as
--              strings -- '1 1 ' fires at tick 0 and tick 2 -- so every
--              interleaving is played exactly, not hoped for with sleeps.
--              'SpaceIterator' generates all six interleavings of two
--              two-step gates in four ticks. Where both gates check before
--              either admits, both admit: the garage is overbooked. The law
--              is 'overbooked > 0': the GOOD is the accepted violation
--              report.
--
-- race-atomic  the same six interleavings, the gate checking and admitting
--              in ONE step under the counter's lock. 'overbooked == 0'.
--
-- THE FRONT END is hwut's runner, 'Hwut.Runner': the choice map below is the
-- whole command line, '--hwut-info' included. The header says
-- 'interactive = true': hwut starts the application ONCE and asks for the
-- choices one after another in that one process -- an accelerator only: a
-- choice's output equals what it prints when run alone.
--
-- THE GARAGE IS A VALUE: 'arrive' and 'leave' are steps of the State monad
-- over it. Where two gates share one garage -- the race -- it is an IORef,
-- and each gate's own state (its step, what it saw) too.
-- _____________________________________________________________________________
module Main (main) where

import           Control.Monad             (forM_, replicateM)
import           Control.Monad.IO.Class    (liftIO)
import           Control.Monad.State       (State, evalState, execState, get, put, runState)
import           Data.IORef                (IORef, modifyIORef, newIORef, readIORef, writeIORef)
import           Data.List                 (intercalate, nub)
import qualified Data.Map.Strict           as Map
import           System.Environment        (getExecutablePath)
import           System.FilePath           (takeDirectory, takeFileName, (</>))
import           Text.Printf               (printf)

import           Hwut.DeterministicRandom  (coin, deterministicStream)
import           Hwut.DeterministicTimeline
import qualified Hwut.Hocon                as Hocon
import           Hwut.Runner               (hwutRunner)
import qualified Hwut.SpaceIterator        as SpaceIterator

-- | The unit under test: a counter of the spaces a garage has.
data Garage = Garage { capacity :: Int, occupied :: Int }

-- | RETURN: Garage, an empty one of 'n' spaces.
newGarage :: Int -> Garage
newGarage n = Garage n 0

-- | RETURN: Int, the number of spaces free now -- negative where the garage
--           is overbooked.
free :: Garage -> Int
free g = capacity g - occupied g

-- | RETURN: State Garage Bool, True: a car was admitted, if a space was
--           free; False, else (the car is refused).
arrive :: State Garage Bool
arrive = do
    g <- get
    if free g <= 0 then return False else put g { occupied = occupied g + 1 } >> return True

-- | RETURN: State Garage Bool, True: a car drove out, if one stood inside;
--           False, else.
leave :: State Garage Bool
leave = do
    g <- get
    if occupied g == 0 then return False else put g { occupied = occupied g - 1 } >> return True

-- | RETURN: String, the integers as Python prints a list of them.
listText :: [Integer] -> String
listText xs = "[" ++ intercalate ", " (map show xs) ++ "]"

-- ____________________________________________________________________________
-- space -- the tested space from HOCON, walked by SpaceIterator
--
-- | RETURN: IO [(String, [Integer])], the dimensions of the space in 'path',
--           in the order written: (name, values). Every fault the HOCON
--           reader found is printed with '!!' first.
readSpace :: FilePath -> IO [(String, [Integer])]
readSpace path = do
    content <- readFile path
    let sourceList        = [ Hocon.SourceLine t i 0 | (i, t) <- zip [1 ..] (lines content) ]
        (document, faults) = Hocon.parse sourceList (takeFileName path)
    forM_ faults (\f -> putStrLn ("!! " ++ show f))
    let Just space = Hocon.get "space" document
    return [ (Hocon.key e, [ n | Hocon.ScalarNode (Hocon.Int n) _ <- Hocon.itemList (Hocon.node e) ])
           | e <- Hocon.entryList (Hocon.node space) ]

-- | RETURN: IO (); every case of the space printed as a matrix cell.
space :: FilePath -> IO ()
space here = do
    dimensionList <- readSpace (here </> "garage-space.hocon")
    let valueList = map snd dimensionList
        [capacities, _, leavings] = valueList
    printf "space: %s\n" (intercalate "  x  " [ n ++ " " ++ listText v | (n, v) <- dimensionList ])
    putStrLn "cell: cars inside / cars refused at the gate ('!!' differs from the model)"
    let case' [c, a, l] =
            let (refused, g) = runState (length . filter not <$> replicateM (fromIntegral a) arrive)
                                        (newGarage (fromIntegral c))
                g'       = execState (replicateM (fromIntegral l) leave) g
                admitted = min a c
                expected = (admitted - min l admitted, a - admitted)
                got      = (fromIntegral (occupied g'), fromIntegral refused)
                mark     = if got == expected then "  " else "!!" :: String
            in  ((c, a), printf "%d/%d%s" (fst got) (snd got) mark :: String, got /= expected)
        case' _ = error "a point of three dimensions"
        caseList   = map case' (SpaceIterator.do' valueList)
        rowMap     = Map.fromListWith (flip (++)) [ (k, [cell]) | (k, cell, _) <- caseList ]
        mismatchN  = length [ () | (_, _, True) <- caseList ]
        rstrip     = reverse . dropWhile (== ' ') . reverse
    forM_ capacities $ \c -> do
        putStrLn (rstrip (printf "capacity %d   %s" c (intercalate "  " [ printf "leave %-3d" l | l <- leavings ])))
        forM_ (valueList !! 1) $ \a ->
            putStrLn (rstrip (printf "  arrive %d   %s" a (intercalate "  " [ printf "%-9s" cell | cell <- rowMap Map.! (c, a) ])))
    printf "cases %d, differing from the model ((mismatches: %d))\n" (Map.size rowMap * length leavings) mismatchN

-- ____________________________________________________________________________
-- random -- a deterministic stream of arrivals and departures
--
-- | What the stream walk counts.
data Count = Count { arrivals, refusals, departures, empties :: Int }

-- | RETURN: IO (); the summary of 1000 drawn cars, model-checked, printed.
randomStream :: IO ()
randomStream = do
    let coinList = evalState (replicateM 1000 (coin 0.55)) (deterministicStream 4711)
        step (g, model, count, history) arriving
            | arriving  = let (ok, g') = runState arrive g
                          in  (g', min 5 (model + 1), count { arrivals = arrivals count + 1
                                                             , refusals = refusals count + fromEnum (not ok) }, (g', min 5 (model + 1)) : history)
            | otherwise = let (ok, g') = runState leave g
                          in  (g', max 0 (model - 1), count { departures = departures count + 1
                                                             , empties = empties count + fromEnum (not ok) }, (g', max 0 (model - 1)) : history)
        (_, _, count, history) = foldl step (newGarage 5, 0 :: Int, Count 0 0 0 0, []) coinList
        mismatchN = length [ () | (g, model) <- history, occupied g /= model ]
        histogram = [ length [ () | (g, _) <- history, occupied g == n ] | n <- [0 .. 5] ]
        strip     = [ if c then '+' else '-' | c <- coinList ]
    putStrLn "seed 4711, garage of 5, 1000 cars drawn: '+' arrives, '-' leaves"
    putStrLn ("first 60: " ++ take 60 strip)
    printf "arrivals %d, refused %d; departures %d, from an empty garage %d\n"
           (arrivals count) (refusals count) (departures count) (empties count)
    putStrLn "cars inside after each event:"
    forM_ (zip [0 :: Int ..] histogram) $ \(n, k) -> printf "    %d  %4d  %s\n" n k (replicate (k `div` 10) '#')
    printf "steps differing from the model ((mismatches: %d))\n" mismatchN

-- ____________________________________________________________________________
-- race -- two gates on drawn timelines
--
-- | RETURN: IO Trigger, a gate on 'line': its first tick checks, its second
--           admits -- in one step under the counter's lock where 'atomic'.
--           What it does is appended to 'logRef'.
gate :: String -> String -> IORef Garage -> Bool -> IORef [String] -> IO Trigger
gate gateName line garageRef atomic logRef = do
    stepRef    <- newIORef (0 :: Int)
    sawFreeRef <- newIORef False
    let say text = modifyIORef logRef (++ [gateName ++ " " ++ text])
        fireOnce _ = liftIO $ do
            step    <- readIORef stepRef
            garage  <- readIORef garageRef
            sawFree <- readIORef sawFreeRef
            case () of
                _ | step == 0 && atomic -> do
                        let (ok, g') = runState arrive garage
                        writeIORef garageRef g' >> writeIORef sawFreeRef ok
                        say (if ok then "checks+admits" else "refuses")
                  | step == 0 -> do
                        writeIORef sawFreeRef (free garage > 0)
                        say (printf "sees %d free" (free garage))
                  | atomic -> say (if sawFree then "opens" else "stays shut")
                  | sawFree -> do
                        writeIORef garageRef garage { occupied = occupied garage + 1 }  -- the naive admit
                        say "admits"
                  | otherwise -> say "refuses"
            writeIORef stepRef (step + 1)
    return (trigger line gateName) { fire = fireOnce }

-- | RETURN: [(String, String)], every pair of timelines in four ticks in
--           which each of two gates fires twice, never at the same tick:
--           gate A's and gate B's.
interleavingList :: [(String, String)]
interleavingList =
    [ (line a1 a2, line b1 b2)
    | [a1, a2, b1, b2] <- SpaceIterator.do' (replicate 4 [0 .. 3 :: Int])
    , a1 < a2, b1 < b2, length (nub [a1, a2, b1, b2]) == 4 ]
  where line x y = [ if t == x || t == y then '1' else ' ' | t <- [0 .. 3] ]

-- | RETURN: IO (); every interleaving of two gates at one space played and
--           printed.
race :: Bool -> IO ()
race atomic = do
    putStrLn "one free space, two gates, one car at each; timelines: a digit fires"
    putStrLn "    gate A  gate B  what happens                                    inside"
    overbookedList <- mapM play interleavingList
    printf "interleavings overbooking the garage ((overbooked: %d)) of %d\n"
           (length (filter id overbookedList)) (length interleavingList)
  where
    play (lineA, lineB) = do
        garageRef <- newIORef (newGarage 1)
        logRef    <- newIORef []
        gateList  <- sequence [gate "A" lineA garageRef atomic logRef, gate "B" lineB garageRef atomic logRef]
        dispatcher <- newTriggerDispatcher gateList
        runTask (run dispatcher)
        garage    <- readIORef garageRef
        eventList <- readIORef logRef
        let overbooked = occupied garage > capacity garage
            text = printf "    \"%s\"  \"%s\"  %-46s  %d %s" lineA lineB (intercalate ", " eventList)
                          (occupied garage) (if overbooked then "!!" else "  " :: String)
        putStrLn (reverse (dropWhile (== ' ') (reverse text)))
        return overbooked

-- | RETURN: IO (); the runner over the four choices.
main :: IO ()
main = do
    here <- takeDirectory <$> getExecutablePath
    hwutRunner "Demo: a garage's space counter -- a space, a stream and races, generated;"
        [ ("space",       space here)
        , ("random",      randomStream)
        , ("race-naive",  race False)
        , ("race-atomic", race True) ]
