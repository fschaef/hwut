-- @hwut {
--     title     = "Demo: a terminal program's screen, as a person sees it"
--     build     { framework = "make", target = "%.exe" }
--     tolerance { regions    = false
--                 comment    = false
--                 whitespace = false }
--     choices {
--         open   { features = ["demo-haskell+cover-terminal-screen", "demo-haskell+cover-screen-as-seen"] }
--         scroll { features = ["demo-haskell+cover-terminal-screen", "demo-haskell+cover-screen-as-seen"] }
--     }
-- }
--
-- _____________________________________________________________________________
-- SUBJECT  the screen of 'viewer.exe' ('viewer.hs'), a full-screen file
--          viewer, run in a terminal of 9 rows and 40 columns and driven by
--          its keys.
-- REQUIREMENT  The viewer shows a title bar in reverse video, the file's lines
--              as they fit, and a status line -- the keys flush left, the lines
--              shown flush right; 'j' and the down key go one line further,
--              'k' one back.
--
-- 'Hwut.Vterm''s Terminal runs the viewer on a pseudo-terminal: the viewer
-- cannot tell it from a real one. The test PRESSES KEYS and is told what
-- CHANGED: three regions are declared -- title, body, status -- and after
-- every key, once the viewer has gone quiet, each region whose text changed
-- is printed. A redraw that changes nothing is not told: the title is told
-- once.
--
-- THE SCREEN IS COMPARED AS A PERSON SEES IT -- three tolerances switched
-- off, in the header:
--
--     regions = false     the file shown is a GOOD file of hwut, with a
--                         '##! potpourri' ... '####' block. On this screen
--                         those are characters, not a region to open.
--     comment = false     '## ...' lines are characters too, not notes.
--     whitespace = false  the status line's two halves stand flush left and
--                         flush right: every blank between them counts. A
--                         half moved by one column is red. (A line's leading
--                         and trailing blanks are stripped all the same.)
--
-- libvterm must be installed ('apt install libvterm0'); where it is not, the
-- test prints why and probes nothing -- its output differs from GOOD and the
-- reason stands in the difference.
--
-- CHOICES  open    the viewer opened, then quit.
--          scroll  down, down, 'j', then 'k': three lines on, one back.
-- _____________________________________________________________________________
module Main (main) where

import Control.Exception  (throwIO, try)
import Control.Monad      (forM_, void)
import System.Directory   (createDirectoryIfMissing)
import System.Environment (getArgs, getExecutablePath)
import System.Exit        (ExitCode (..), exitWith)
import System.FilePath    (takeDirectory, (</>))
import System.IO          (hFlush, stdout)

import Hwut.Vterm

sampleText :: String
sampleText = unlines
    [ "## demo.py race -- three workers"
    , "start"
    , "##! potpourri"
    , "worker B done: 5 jobs"
    , "worker A done: 3 jobs"
    , "worker C done: 2 jobs"
    , "####"
    , "all joined"
    , "## the order between the markers is"
    , "## free; the lines are not." ]

-- | RETURN: IO (); one region that changed printed, its rows as they stand
--           on the screen, from the first column.
showRegion :: String -> [String] -> IO ()
showRegion name lineList = do
    putStrLn ("-- " ++ name)
    mapM_ putStrLn lineList
    hFlush stdout

-- | RETURN: IO (); the viewer run on the sample, 'keyList' pressed, quit,
--           and what changed after each step printed.
view :: [String] -> IO ()
view keyList = do
    here <- takeDirectory <$> getExecutablePath
    let path = here </> "TMP" </> "race.txt"
    createDirectoryIfMissing True (takeDirectory path)
    writeFile path sampleText
    withTerminal 9 40 0.1 $ \terminal -> do
        region terminal "title"  0    1 0 Nothing
        region terminal "body"   1    7 0 Nothing
        region terminal "status" (-1) 1 0 Nothing
        onChange terminal showRegion
        putStrLn "> viewer.exe race.txt"
        hFlush stdout
        void (run terminal [here </> "viewer.exe", path] Nothing 10.0)
        c <- cell terminal 0 1
        putStrLn ("title bar: " ++ (if null (attributeText c) then "plain" else attributeText c))
        forM_ keyList $ \key -> do
            putStrLn ("> " ++ key)
            hFlush stdout
            if length key == 1 then void (send terminal key 1.0)
                               else void (press terminal key [] 1.0)
        void (send terminal "q" 1.0)
        status <- wait terminal 10.0
        putStrLn ("> q -- exit status " ++ maybe "None" show status)

choiceList :: [(String, [String])]
choiceList = [("open", []), ("scroll", ["down", "down", "j", "k"])]

-- | RETURN: IO (); the choice the command line names, run, then
--           '<hwut-end>'; exit 1 where none is named or libvterm is missing.
main :: IO ()
main = do
    arguments <- getArgs
    case arguments of
        (word : _) | Just keyList <- lookup word choiceList -> do
            result <- try (view keyList)
            case result of
                Left (LibraryMissing m) -> putStrLn m >> exitWith (ExitFailure 1)
                Left problem            -> throwIO problem
                Right ()                -> putStrLn "<hwut-end>"
        _ -> putStrLn "choices: open, scroll" >> exitWith (ExitFailure 1)
