-- SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
-- _____________________________________________________________________________
--
-- PURPOSE: The front end of a HWUT test application -- the port of
--          'python/hwut_runner.py'.
--
--     import Hwut.Runner
--
--     main :: IO ()
--     main = hwutRunner "my title" [ ("plain", plain), ("tricky", tricky) ]
--
-- The command line selects the mode:
--
--     app --hwut-info      the info block; exit 0
--     app <choice>         one choice; its output on stdout and stderr,
--                          then '<hwut-end>'
--     app --interactive    choices started by commands on stdin; each one's
--                          output in the two sink files the command names;
--                          'done' on the original stdout
--     app                  the choice-less test; where there are choices,
--                          refused, naming them (the menu is 'hwut.play's)
--
-- A CHOICE IS AN 'IO ()': the edge where a test's pure model meets its
-- output. In interactive mode each choice runs in a child process
-- ('forkProcess'), so whatever a choice does to its process -- an 'exitWith',
-- a file descriptor left open -- ends with that choice.
-- _____________________________________________________________________________
module Hwut.Runner
    ( Choices (..)
    , RunnerOptions (..)
    , defaultRunnerOptions
    , hwutRunner
    , hwutRunnerWith
    , levenshteinDistance
    , levenshteinBestMatch
    ) where

import           Control.Exception     (SomeException, fromException, try)
import           Control.Monad         (forM_, unless)
import           Data.Char             (isDigit, isSpace)
import           Data.List             (intercalate, minimumBy, sort)
import           Data.Ord              (comparing)
import           System.Directory      (getTemporaryDirectory)
import           System.Environment    (getArgs, lookupEnv)
import           System.Exit           (ExitCode (..), exitWith)
import           System.IO
import           System.Posix.IO       (OpenMode (..), closeFd, defaultFileFlags, dup, dupTo,
                                        fdToHandle, handleToFd, openFd, stdError, stdOutput,
                                        trunc)
import           System.Posix.Process  (ProcessStatus (..), exitImmediately, forkProcess,
                                        getProcessStatus)
import           System.Posix.Temp     (mkstemps)
import           System.Posix.Types    (Fd)

-- | What the application offers: named choices, or one choice-less test
--   (listed as '-').
data Choices = Choices [(String, IO ())]
             | ChoiceLess (IO ())

-- | What the info block says beyond title and choices.
data RunnerOptions = RunnerOptions
    { happyList :: [String]     -- ^ patterns of the 'HAPPY:' lines
    , sameF     :: Bool         -- ^ True: the block says 'SAME;'
    }

-- | RETURN: RunnerOptions, no 'HAPPY:' pattern, no 'SAME;'.
defaultRunnerOptions :: RunnerOptions
defaultRunnerOptions = RunnerOptions [] False

-- | RETURN: IO (), once the mode the command line selects has run; a
--           refusal exits with status 1. 'title' heads the info block,
--           'choiceList' names each choice's action.
hwutRunner :: String -> [(String, IO ())] -> IO ()
hwutRunner title choiceList = hwutRunnerWith defaultRunnerOptions title (Choices choiceList)

-- | RETURN: IO (), as 'hwutRunner', with options and possibly a choice-less
--           application.
hwutRunnerWith :: RunnerOptions -> String -> Choices -> IO ()
hwutRunnerWith options title choices = do
    mapM_ (`hSetEncoding` utf8) [stdin, stdout, stderr]
    arguments <- getArgs
    let word = case arguments of { (w : _) -> Just w; [] -> Nothing }
    case word of
        Just w | w `elem` ["-h", "--hi", "--hwut-info", "--sos", "--wtf"] ->
            mapM_ putStrLn (infoBlockLines options title choices)
        Just "--interactive" -> modeInteractive options title choices
        Nothing -> case choices of
            ChoiceLess action -> runOne action
            Choices _         -> do
                putStrLn ("error: a choice is required: " ++ printable
                          ++ " -- name one, or let 'hwut.play' ask.")
                exitWith (ExitFailure 1)
        Just w -> case (choices, lookup w (choiceMap choices)) of
            (_, Just action)    -> runOne action
            (ChoiceLess _, _)   -> do
                putStrLn ("error: '" ++ w ++ "': this application has no choices -- call it without one.")
                exitWith (ExitFailure 1)
            (Choices _, Nothing) -> do
                putStrLn ("error: choice '" ++ w ++ "' not available.")
                putStrLn ("error: available: " ++ printable ++ ".")
                forM_ (levenshteinBestMatch w (sortedChoiceList choices)) $ \best ->
                    putStrLn ("error: did you mean '" ++ best ++ "'?")
                exitWith (ExitFailure 1)
  where
    printable = intercalate ", " (sortedChoiceList choices)

-- | RETURN: [(String, IO ())], every choice by the word that names it --
--           '-' for the choice-less test.
choiceMap :: Choices -> [(String, IO ())]
choiceMap (Choices list)      = list
choiceMap (ChoiceLess action) = [("-", action)]

-- | RETURN: [String], the choice names sorted; '-' for a choice-less one.
sortedChoiceList :: Choices -> [String]
sortedChoiceList = sort . map fst . choiceMap

-- | RETURN: IO (); the choice ran, then '<hwut-end>' (R-70) was printed.
runOne :: IO () -> IO ()
runOne action = do
    action
    putStrLn "<hwut-end>"
    hFlush stdout

-- | RETURN: [String], the lines of the info block: title, CHOICES, HAPPY,
--           SAME, INTERACTIVE.
infoBlockLines :: RunnerOptions -> String -> Choices -> [String]
infoBlockLines options title choices =
       [ if not (null title) && last title == ';' then title else title ++ ";" ]
    ++ [ "CHOICES: " ++ intercalate ", " (sortedChoiceList choices) ++ ";" | Choices _ <- [choices] ]
    ++ [ "HAPPY: " ++ h ++ ";" | h <- happyList options ]
    ++ [ "SAME;" | sameF options ]
    ++ [ "INTERACTIVE;" ]

-- ----------------------------------------------------------- interactive mode

-- | RETURN: IO (), once the session ended ('quit' or end of input). The
--           original stdout is the UP channel; fd 1 and fd 2 point at a
--           stray sink, so output outside a choice never enters the
--           protocol.
--
--   DOWN (stdin, one per line):  run <choice> <sink-out> <sink-err> | info
--                                | quit | q | exit
--   UP:                          done <choice> <status> | fail <choice>
--                                <reason> | info: <line> | bye
modeInteractive :: RunnerOptions -> String -> Choices -> IO ()
modeInteractive options title choices = do
    hFlush stdout >> hFlush stderr
    controlFd <- dup stdOutput
    control   <- fdToHandle controlFd
    hSetEncoding control utf8
    hSetBuffering control LineBuffering
    directory <- getTemporaryDirectory
    (_, strayHandle) <- mkstemps (directory ++ "/hwut_stray_") ".txt"
    strayFd <- handleToFd strayHandle
    _ <- dupTo strayFd stdOutput
    _ <- dupTo strayFd stdError
    closeFd strayFd
    let up :: String -> IO ()
        up message = hPutStrLn control message
        loop = do
            next <- readCommand
            case next of
                Nothing   -> return ()
                Just line -> do
                    continueF <- interprete up controlFd line
                    if continueF then loop else return ()
    loop
    up "bye"
  where
    interprete :: (String -> IO ()) -> Fd -> String -> IO Bool
    interprete up controlFd line = case words line of
        [w] | w `elem` ["quit", "q", "exit"] -> return False
        ["info"] -> do
            mapM_ (up . ("info: " ++)) (infoBlockLines options title choices)
            up "done - 0"
            return True
        ["run", token, sinkOut, sinkErr] -> do
            case findChoice token of
                Nothing     -> up ("fail " ++ token ++ " unknown-choice")
                Just action -> do
                    status <- runIntoSinks controlFd action sinkOut sinkErr
                    up ("done " ++ token ++ " " ++ show status)
            return True
        _ -> up "fail - bad-command" >> return True

    findChoice token = case lookup token (choiceMap choices) of
        Just action -> Just action
        Nothing
            | not (null token) && all isDigit token ->
                let sorted = sortedChoiceList choices
                    i      = read token :: Integer
                in if i < fromIntegral (length sorted)
                       then lookup (sorted !! fromIntegral i) (choiceMap choices)
                       else Nothing
            | otherwise -> Nothing

-- | RETURN: IO (Maybe String), the next non-empty line of stdin, stripped;
--           Nothing at the end of input.
readCommand :: IO (Maybe String)
readCommand = do
    endF <- hIsEOF stdin
    if endF then return Nothing else do
        line <- hGetLine stdin
        let stripped = dropWhile isSpace (reverse (dropWhile isSpace (reverse line)))
        if null stripped then readCommand else return (Just stripped)

-- | RETURN: IO Int, the exit status of the child that ran 'action' with
--           fd 1 and fd 2 on the two sinks -- 0 where it returned, the code
--           of an 'exitWith', 1 where it raised (the exception on the error
--           sink), minus the signal that killed it. The child's output is
--           complete when this returns: it has ended.
runIntoSinks :: Fd -> IO () -> FilePath -> FilePath -> IO Int
runIntoSinks controlFd action sinkOut sinkErr = do
    hFlush stdout >> hFlush stderr
    pid <- forkProcess $ do
        out <- openFd sinkOut WriteOnly (Just 0o644) defaultFileFlags { trunc = True }
        err <- openFd sinkErr WriteOnly (Just 0o644) defaultFileFlags { trunc = True }
        _   <- dupTo out stdOutput
        _   <- dupTo err stdError
        closeFd out >> closeFd err >> closeFd controlFd
        result <- try action
        code <- case result of
            Right () -> do
                noTerminal <- lookupEnv "HWUT_NO_TERMINAL"
                unless (maybe False (not . null) noTerminal) (putStrLn "<hwut-end>")
                return ExitSuccess
            Left problem -> case fromException problem of
                Just exitCode -> return exitCode
                Nothing       -> do
                    hPutStrLn stderr (show (problem :: SomeException))
                    return (ExitFailure 1)
        hFlush stdout >> hFlush stderr
        exitImmediately code
    status <- getProcessStatus True False pid
    return $ case status of
        Just (Exited ExitSuccess)      -> 0
        Just (Exited (ExitFailure n))  -> n
        Just (Terminated signal _)     -> negate (fromIntegral signal)
        _                              -> 1

-- ------------------------------------------------------------ the suggestion

-- | RETURN: Int >= 0, the Levenshtein distance between 'a' and 'b'.
levenshteinDistance :: String -> String -> Int
levenshteinDistance a b
    | a == b    = 0
    | null a    = length b
    | null b    = length a
    | otherwise = last (foldl row [0 .. length short] (zip [1 ..] long))
  where
    (long, short) = if length a < length b then (b, a) else (a, b)
    row previous (i, ca) = scanl step i (zip3 short previous (tail previous))
      where step left (cb, diagonal, above) =
                minimum [left + 1, above + 1, diagonal + (if ca == cb then 0 else 1)]

-- | RETURN: Maybe String, the element of 'haystack' least distant from
--           'needle' (the first of equals); Nothing where 'haystack' is
--           empty.
levenshteinBestMatch :: String -> [String] -> Maybe String
levenshteinBestMatch _ []    = Nothing
levenshteinBestMatch needle haystack
    | needle `elem` haystack = Just needle
    | otherwise              = Just (minimumBy (comparing (levenshteinDistance needle)) haystack)
