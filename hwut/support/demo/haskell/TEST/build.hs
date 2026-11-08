-- @hwut {
--     title   = "Demo: a recursive build, serial and parallel -- one summary, by a pype system"
--     build   { framework = "make", target = "%.exe" }
--     pype    = "build.pypes"
--     same    = true
--     choices = ["serial", "parallel"]
--     features = ["pype-in-header", "pype-system", "same-nominal", "choices-as-list",
--                 "pype-push-pop", "pype-entry-exit", "pype-import", "pype-repeat-group",
--                 "pype-quantity", "pype-anchors-globs-flush"]
--     tolerance { constraints = ["compile < 5 s", "breaches == 0"] }
-- }
--
-- _____________________________________________________________________________
-- SUBJECT  the log of a recursive build -- configure, then the directories
--          'lib', 'app' and, inside 'app', 'app/plugins' -- and the summary
--          a pype system makes of it.
-- REQUIREMENT  A parallel build builds what the serial build builds: the same
--              sources, the same warnings, the same archives and the same
--              program, linked from the same parts.
--
-- The application only REPORTS the build as it happens, as 'make -w' would.
-- The header's 'pype = "build.pypes"' puts a SYSTEM of two pype scripts
-- between it and the comparison (hwut runs it; the application prints no
-- '<hwut-end>'):
--
--     build.pypes       --> normalise.pype         stdin to the first
--                       normalise.pype --> build.pype
--     normalise.pype    a parallel build tags each line with its job,
--                       'job2: cc -c ...'; the tag goes, every other line
--                       passes unchanged ('flush')
--     build.pype        the summary, sorted -- see its own comments: modes
--                       pushed on 'Entering directory' and popped on
--                       'Leaving' (nested: 'app/plugins' inside 'app'),
--                       '<entry>'/'<exit>' around each, a vocabulary
--                       imported from 'compiler.pype', a repeat group over
--                       the parts of a link, durations read as quantities
--
-- 'same = true': BOTH CHOICES SHARE ONE GOOD, 'GOOD/build.hs.txt' (a link to
-- the Python demonstration's). Serial or parallel, the summary must be the
-- same -- that is the requirement, and the header says it once. 'choices'
-- is a list: no choice states anything of its own.
--
-- The laws: the compile times sum to under 5 s ('((compile: ...))', in
-- s, whatever unit the log used), and nothing in the log broke the build's
-- grammar ('((breaches: 0))').
--
-- A HEADER'S PYPE READS THE OUTPUT AFTER THE RUN: the whole stream at once.
-- Time as the pype sees it -- 'pype.time()', 'tick:' -- is no time of the
-- build here; a pype that judges time is fed live ('protocol.sh slow').
-- _____________________________________________________________________________
module Main (main) where

import Control.Concurrent      (forkIO, threadDelay)
import Control.Concurrent.MVar (newEmptyMVar, newMVar, putMVar, takeMVar, withMVar)
import Control.Monad           (forM, forM_)
import System.Environment      (getArgs)
import System.Exit             (ExitCode (..), exitWith)
import System.IO               (hFlush, stdout)
import Text.Printf             (printf)

import ClockRandom

-- | What one directory does: its sources, warnings and product.
data Directory = Directory
    { sourceList  :: [String]
    , warningList :: [(String, String)]
    , product'    :: String
    }

directoryList :: [(String, Directory)]
directoryList =
    [ ("lib", Directory ["lib/str.c", "lib/num.c", "lib/map.c"]
                        [("lib/num.c", "lib/num.c:14:9: warning: unused variable 'n'")]
                        "ar rcs lib/libcore.a lib/str.o lib/num.o lib/map.o")
    , ("app/plugins", Directory ["app/plugins/png.c", "app/plugins/svg.c"]
                        [("app/plugins/svg.c", "app/plugins/svg.c:3:1: warning: implicit declaration of 'xml_open'")]
                        "ar rcs app/plugins/libplug.a app/plugins/png.o app/plugins/svg.o")
    , ("app", Directory ["app/main.c", "app/cli.c"]
                        []
                        "ld -o app/demo app/main.o app/cli.o lib/libcore.a app/plugins/libplug.a") ]

-- | RETURN: Directory, the one named 'name'.
directory :: String -> Directory
directory name = maybe (error ("no directory " ++ name)) id (lookup name directoryList)

-- | RETURN: IO [String], what building directory 'name' prints, its
--           sources compiled in the time each takes.
compileLines :: Rng -> String -> IO [String]
compileLines rng name = concat <$> forM (sourceList spec) (\source -> do
    took <- uniform rng 0.04 0.12
    threadDelay (round (took * 1000000))
    let spent  = if took < 0.1 then printf "%d ms" (truncate (took * 1000) :: Int)
                               else printf "%.2f s" took
        object = take (length source - 2) source ++ ".o"
    return (printf "cc -c %s -o %s (took %s)" source object (spent :: String)
            : maybe [] (: []) (lookup source (warningList spec))))
  where spec = directory name

-- | RETURN: IO [String], the block 'make -w' prints for 'name' at 'level',
--           the block of 'inner' nested before the product.
directoryBlock :: Rng -> String -> Int -> Maybe String -> IO [String]
directoryBlock rng name level inner = do
    compiled <- compileLines rng name
    nested   <- maybe (return []) (\i -> directoryBlock rng i (level + 1) Nothing) inner
    return ([printf "make[%d]: Entering directory '%s'" level name] ++ compiled ++ nested
            ++ [product' (directory name), printf "make[%d]: Leaving directory '%s'" level name])

-- | RETURN: IO (); what 'configure' prints, and that make enters the top
--           directory, printed.
configure :: IO ()
configure = do
    putStrLn "configure: checking for cc... cc"
    putStrLn "configure: checking for ar... ar"
    putStrLn "make: Entering directory 'demo'"

-- | RETURN: IO (); one directory built after the other.
serial :: Rng -> IO ()
serial rng = do
    configure
    lib <- directoryBlock rng "lib" 1 Nothing
    app <- directoryBlock rng "app" 1 (Just "app/plugins")
    forM_ (lib ++ app) (\line -> putStrLn line >> hFlush stdout)
    putStrLn "make: Leaving directory 'demo'"

-- | RETURN: IO (); 'lib' and 'app' built at once. Each job prints its block
--           whole when done ('make -O'), every line tagged with the job;
--           which job finishes first is the scheduler's.
parallel :: Rng -> IO ()
parallel rng = do
    configure
    hFlush stdout
    lock <- newMVar ()
    doneList <- forM [(1, "lib", Nothing), (2, "app", Just "app/plugins")] $ \(slot, name, inner) -> do
        done <- newEmptyMVar
        _ <- forkIO $ do
            block <- directoryBlock rng name 1 inner
            withMVar lock $ \_ -> forM_ block $ \line ->
                printf "job%d: %s\n" (slot :: Int) line >> hFlush stdout
            putMVar done ()
        return done
    mapM_ takeMVar doneList
    putStrLn "make: Leaving directory 'demo'"

-- | RETURN: IO (); the choice the command line names, run; exit 1 where none
--           is named.
main :: IO ()
main = do
    arguments <- getArgs
    rng       <- newRng
    case arguments of
        ["serial"]   -> serial rng
        ["parallel"] -> parallel rng
        _            -> putStrLn "choices: serial, parallel" >> exitWith (ExitFailure 1)
