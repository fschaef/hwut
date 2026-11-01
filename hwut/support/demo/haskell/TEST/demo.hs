-- @hwut {
--     title   = "Demo: what hwut tolerates, and where it is said"
--     build   { framework = "make", executable = "%.exe" }
--     choices {
--         plain       { features = ["demo-passes-on-every-run", "exact-comparison"] }
--         tolerance   { features = ["demo-passes-on-every-run", "equivalence-pattern", "numeric-ratio"]
--                       tolerance {
--                           eq_pattern    = ["(hello|bonjour|hallo|buongiorno|hola|ahoj)"]
--                           numeric_ratio = 0.01
--                       } }
--         constraints { features = ["demo-passes-on-every-run", "constraints"]
--                       tolerance {
--                           constraints = ["load >= 0 and load <= 100",
--                                          "even % 2 == 0",
--                                          "twice == 2 * once"]
--                       } }
--         analogies   { features = ["demo-passes-on-every-run", "analogies"] }
--         race        { features = ["demo-passes-on-every-run", "order-free-block"] }
--         pool        { features = ["demo-passes-on-every-run", "potpourri-subset-duplicates"] }
--         progress    { features = ["demo-passes-on-every-run", "visible-nothing"]
--                       tolerance { nothing = ["[.]+"] } }
--         lisp        { features = ["demo-passes-on-every-run", "analogy-markers"]
--                       tolerance { analogy = ["{", "}"] } }
--         clusters    { features = ["demo-passes-on-every-run", "point-cloud-pair-distance"] }
--     }
-- }
--
-- _____________________________________________________________________________
-- A TEST APPLICATION OF HWUT, FOR READING -- the template, in Haskell.
--
--     hwut.run                   builds 'demo.exe' (the header's 'build':
--                                'make demo.exe' here), runs every choice
--                                below, compares with GOOD/
--     hwut.play demo.hs plain    runs one choice and records it in OUT/
--     hwut.accept demo.hs plain  blesses that recording as GOOD; it runs
--                                nothing. Where a GOOD stands, the change
--                                is 'hwut.merge's -- or '--force' (also
--                                '--as-is') replaces it whole.
--     hwut.merge                 shows OUTPUT against GOOD, key by key
--     hwut.config.show demo.hs   prints what hwut READ from the header above
--
-- The header above is the whole configuration: a title, how the program is
-- built, and one scope per choice. hwut calls 'demo.exe <choice>' and
-- compares what it prints on stdout with 'GOOD/demo.hs--<choice>.txt' -- a
-- '.link' to the Python demonstration's GOOD: the same text. '<hwut-end>'
-- closes the stream: a stream without it never COMPLETED and is not
-- accepted.
--
-- Every run is seeded by the clock, so the output differs from run to run --
-- and every choice passes anyway. Each shows WHY:
--
-- plain        nothing varies; nothing is tolerated. The output must equal
--              GOOD, line by line.
--
-- tolerance    'eq_pattern': a greeting drawn at random; any greeting the
--              pattern names is EQUIVALENT to any other.
--              'numeric_ratio': a value drawn from [19.91, 20.09]. The band
--              belongs to the GOOD's number, |n| x ratio: GOOD 19.91 against
--              20.09 differs by 0.18, inside 19.91 x 0.01 = 0.1991. Every pair
--              from the interval passes; 20.30 would not.
--
-- constraints  '((name: value))' BINDS a value; the expressions under
--              'constraints' judge it, not the GOOD's value. 'load' may be
--              anything from 0 to 100; 'even' any even number; 'twice' must be
--              twice 'once', whatever 'once' is. A law over two variables is
--              checked once both are bound. A binding that breaks its law is
--              red.
--
-- race         '##! potpourri' ... '####' opens a block whose lines may arrive
--              in ANY order -- three workers print as they finish. The same
--              lines must stand on both sides, each once; the order is free.
--              The program prints the markers, and so does GOOD.
--
-- analogies    '((x))' is a placeholder: '((a7f3))' against GOOD's '((91c2))'
--              is equivalent where the mapping holds throughout the stream --
--              the same handle opened, read and closed. A handle that changes
--              in mid-stream is red.
--
-- pool         '##! potpourri subset duplicates': four workers share twelve
--              jobs; who takes how many is the scheduler's. 'subset': a
--              worker that got no job is no fault -- every line of the run
--              must stand in GOOD, not every line of GOOD in the run.
--              'duplicates': a worker named twice is one line. The GOOD was
--              recorded from a run in which all four worked.
--
-- progress     'nothing': a line made only of what the pattern names counts
--              as no line. A download prints dots while it waits -- none, or
--              a few lines of them -- and the dots are no fact.
--
-- lisp         'analogy = ["{", "}"]': the output is Lisp, where '((' is
--              syntax, so the placeholder is marked otherwise. An object is
--              printed with its address, '{10044C1F33}'; the address differs
--              per run, and must be the same object throughout.
--
-- clusters     '##! point-cloud limit=0.3 pair dist=Linf': three centroids of
--              a clustering, in whatever order the run finds them. 'pair':
--              each centroid pairs with ONE point of GOOD -- two centroids in
--              one cluster are red. 'dist=Linf': within 0.3 in x AND in y.
--
-- THE WORKERS ARE GHC THREADS ('forkIO', the threaded runtime): an MVar is
-- the lock, another each worker's 'join'.
-- _____________________________________________________________________________
module Main (main) where

import Control.Concurrent      (forkIO, threadDelay)
import Control.Concurrent.MVar (MVar, modifyMVar, modifyMVar_, newEmptyMVar, newMVar,
                                putMVar, readMVar, takeMVar, withMVar)
import Control.Monad           (forM, forM_, replicateM_, when)
import Data.List               (minimumBy, maximumBy)
import Data.Ord                (comparing)
import System.Environment      (getArgs)
import System.Exit             (ExitCode (..), exitWith)
import System.IO               (hFlush, stdout)
import Text.Printf             (printf)

import ClockRandom

greetingList :: [String]
greetingList = ["hello", "bonjour", "hallo", "buongiorno", "hola", "ahoj"]

-- | RETURN: IO (); what never varies, printed.
plain :: Rng -> IO ()
plain _ = do
    putStrLn "the first line"
    putStrLn "the second line: 1 2 3"

-- | RETURN: IO (); a greeting and a value, both drawn at random, printed.
tolerance :: Rng -> IO ()
tolerance rng = do
    greeting <- choice rng greetingList
    value    <- uniform rng 19.91 20.09
    printf "greeting: %s, world\n" greeting
    printf "value:    %.2f\n" value

-- | RETURN: IO (); bindings, each drawn at random, each lawful, printed.
constraints :: Rng -> IO ()
constraints rng = do
    load <- uniform rng 0.0 100.0
    evenN <- (2 *) <$> randint rng 0 500
    once <- randint rng 1 50
    printf "load  ((load: %.1f)) %%\n" load
    printf "even  ((even: %d))\n" evenN
    printf "once  ((once: %d))\n" once
    printf "twice ((twice: %d))\n" (2 * once)

-- | RETURN: IO (); two handles, each drawn at random, each used
--           consistently from opening to closing, printed.
analogies :: Rng -> IO ()
analogies rng = do
    [first, second] <- sample rng 2 0x1000 0x10000
    printf "open  ((%04x)) input.txt\n" first
    printf "open  ((%04x)) output.txt\n" second
    printf "read  ((%04x)) 17 lines\n" first
    printf "write ((%04x)) 17 lines\n" second
    printf "close ((%04x))\n" first
    printf "close ((%04x))\n" second

-- | RETURN: IO (), once every thread 'start' started has ended -- each
--           given an MVar it fills when done, and that is waited for.
joinAll :: [IO ()] -> IO ()
joinAll actions = do
    doneList <- forM actions $ \action -> do
        done <- newEmptyMVar
        _ <- forkIO (action >> putMVar done ())
        return done
    mapM_ takeMVar doneList

-- | RETURN: IO (); three workers printed as they finish -- the order is the
--           scheduler's, the facts are not. The program frames the
--           unordered block itself: '##! potpourri' ... '####'.
race :: Rng -> IO ()
race rng = do
    lock <- newMVar ()
    let work (name, jobs) = do
            delay <- uniform rng 0.0 0.02
            threadDelay (round (delay * 1000000))
            withMVar lock $ \_ -> printf "worker %s done: %d jobs\n" (name :: String) (jobs :: Int) >> hFlush stdout
    putStrLn "start"
    putStrLn "##! potpourri"
    hFlush stdout
    joinAll (map work [("A", 3), ("B", 5), ("C", 2)])
    putStrLn "####"
    putStrLn "all joined"

-- | RETURN: IO (); four workers take twelve jobs from one queue, each
--           reporting the job it finished, printed. Who takes how many is
--           the scheduler's.
pool :: Rng -> IO ()
pool rng = do
    queue    <- newMVar [0 .. 11 :: Int]
    doneList <- newMVar []
    let work name = do
            job <- modifyMVar queue $ \q -> return (drop 1 q, take 1 q)
            when (not (null job)) $ do
                delay <- uniform rng 0.0 0.005
                threadDelay (round (delay * 1000000))
                modifyMVar_ doneList (return . (("job done by worker " ++ [name]) :))
                work name
    joinAll (map work "ABCD")
    done <- reverse <$> readMVar doneList
    putStrLn "twelve jobs, four workers:"
    putStrLn "##! potpourri subset duplicates"
    mapM_ putStrLn done
    putStrLn "####"
    printf "jobs done: %d\n" (length done)

-- | RETURN: IO (); a download that prints dots while it waits -- how many
--           is the network's.
progress :: Rng -> IO ()
progress rng = do
    putStrLn "connecting to mirror"
    n <- randint rng 0 3
    replicateM_ n $ do
        k <- randint rng 1 8
        putStrLn (replicate k '.')
    putStrLn "connected"
    putStrLn "received 1024 bytes"

-- | RETURN: IO (); a Lisp session at its prompt: two objects, each printed
--           with its address '{...}', drawn anew per run, and each used
--           again.
lisp :: Rng -> IO ()
lisp rng = do
    [table, thread] <- sample rng 2 0x1000000000 0x1100000000
    putStrLn "* (defvar *cache* (make-hash-table))"
    printf "#<HASH-TABLE :TEST EQL :COUNT 0 {%X}>\n" table
    putStrLn "* (defvar *worker* (make-thread (lambda () (loop (sleep 1))) :name \"worker\"))"
    printf "#<THREAD \"worker\" RUNNING {%X}>\n" thread
    putStrLn "* (let ((key (list 1 2))) (setf (gethash key *cache*) *worker*))"
    printf "#<THREAD \"worker\" RUNNING {%X}>\n" thread
    putStrLn "* *cache*"
    printf "#<HASH-TABLE :TEST EQL :COUNT 1 {%X}>\n" table

type Point = (Double, Double)

-- | RETURN: Double, the squared distance between 'p' and 'q'.
distance2 :: Point -> Point -> Double
distance2 (px, py) (qx, qy) = (px - qx) ^ (2 :: Int) + (py - qy) ^ (2 :: Int)

-- | RETURN: IO (); 90 noisy points clustered around three centres, the
--           centroids printed in the order the run found them.
clusters :: Rng -> IO ()
clusters rng = do
    let centreList = [(1.0, 1.0), (5.0, 4.0), (9.0, 1.0)]
    pointList <- shuffle rng =<< sequence
        [ (,) <$> ((x +) <$> gauss rng 0.0 0.3) <*> ((y +) <$> gauss rng 0.0 0.3)
        | (x, y) <- centreList, _ <- [1 .. 30 :: Int] ]
    --  The start: one point at random, then twice the point farthest from
    --  every start chosen so far -- one start per cluster.
    first <- choice rng pointList
    let farthest cs = maximumBy (comparing (\p -> minimum (map (distance2 p) cs))) pointList
        startList   = until ((== 3) . length) (\cs -> cs ++ [farthest cs]) [first]
        nearest cs p = minimumBy (comparing (\i -> distance2 p (cs !! i))) [0 .. 2]
        step cs = [ centroid [ p | p <- pointList, nearest cs p == i ] | i <- [0 .. 2] ]
        centroid ms = (sum (map fst ms) / n, sum (map snd ms) / n)
          where n = fromIntegral (length ms)
        centroidList = iterate step startList !! 10
    putStrLn "centroids (x y), in the order found:"
    putStrLn "##! point-cloud limit=0.3 pair dist=Linf"
    forM_ centroidList $ \(x, y) -> printf "    %5.2f %5.2f\n" x y
    putStrLn "####"

choiceList :: [(String, Rng -> IO ())]
choiceList = [ ("plain", plain), ("tolerance", tolerance), ("constraints", constraints)
             , ("analogies", analogies), ("race", race), ("pool", pool)
             , ("progress", progress), ("lisp", lisp), ("clusters", clusters) ]

-- | RETURN: IO (); the choice the command line names, run, then
--           '<hwut-end>'; exit 1 where none is named.
main :: IO ()
main = do
    arguments <- getArgs
    rng       <- newRng
    case arguments of
        (word : _) | Just action <- lookup word choiceList -> do
            action rng
            putStrLn "<hwut-end>"
        _ -> do
            putStrLn ("choices: " ++ foldr1 (\a b -> a ++ ", " ++ b) (map fst choiceList))
            exitWith (ExitFailure 1)
