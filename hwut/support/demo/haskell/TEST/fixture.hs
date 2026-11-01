-- SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
-- _____________________________________________________________________________
--
-- THE SHOP'S FIXTURE -- no test, a helper the directory's 'hwut.conf' calls.
--
--     fixture.exe open           a fresh 'TMP/shop.db', stocked as below, and
--                                an empty 'TMP/frame.log' ('on_entry', and
--                                'hwut.execute fixture open')
--     fixture.exe close          both removed ('on_exit')
--     fixture.exe check <when> <app> [<choice>]
--                                'when' is 'before' or 'after': whether the
--                                stock adds up around the test run '<app>
--                                <choice>', appended to 'TMP/frame.log'
--                                ('on_before_test', 'on_after_test')
--
-- 'hwut.conf' passes '<app>' and '<choice>' as '$HWUT_TEST $HWUT_CHOICE',
-- which hwut sets for the run the check stands around; a test without
-- choices has none. 'check' concerns the shop's tests alone. The stock
-- ADDS UP where every item's quantity is its opening quantity plus every
-- movement of the journal.
--
-- 'on_entry' builds this program before it runs it ('make fixture.exe').
-- _____________________________________________________________________________
module Main (main) where

import Control.Monad      (forM_, when)
import System.Directory   (createDirectoryIfMissing, doesFileExist, removeFile)
import System.Environment (getArgs, getExecutablePath)
import System.Exit        (ExitCode (..), exitWith)
import System.FilePath    (takeDirectory, (</>))
import System.IO          (hPutStrLn, stderr)
import Text.Printf        (printf)

import Sqlite

openingList :: [(String, Int)]
openingList = [("apple", 10), ("pear", 5), ("plum", 5)]

shopTestList :: [String]
shopTestList = ["delivery.json", "shop.hs"]

-- | RETURN: IO (FilePath, FilePath), the database and the frame log, in
--           'TMP/' beside this program.
paths :: IO (FilePath, FilePath)
paths = do
    here <- takeDirectory <$> getExecutablePath
    return (here </> "TMP" </> "shop.db", here </> "TMP" </> "frame.log")

-- | RETURN: IO (); 'path' removed where it stands.
removeIfThere :: FilePath -> IO ()
removeIfThere path = doesFileExist path >>= \there -> when there (removeFile path)

-- | RETURN: IO (); a fresh, stocked database and an empty log written.
openShop :: IO ()
openShop = do
    (dbPath, logPath) <- paths
    createDirectoryIfMissing True (takeDirectory dbPath)
    mapM_ removeIfThere [dbPath, logPath]
    db <- open dbPath 10.0 Nothing
    execute db "BEGIN" []
    execute db "CREATE TABLE opening (item TEXT PRIMARY KEY, qty INTEGER)" []
    execute db "CREATE TABLE stock   (item TEXT PRIMARY KEY, qty INTEGER)" []
    execute db "CREATE TABLE journal (item TEXT, delta INTEGER, source TEXT)" []
    forM_ openingList $ \(item, qty) -> do
        execute db "INSERT INTO opening VALUES (?, ?)" [SqlText item, SqlInt qty]
        execute db "INSERT INTO stock   VALUES (?, ?)" [SqlText item, SqlInt qty]
    execute db "COMMIT" []
    close db
    writeFile logPath ""

-- | RETURN: IO (); the database and the log removed.
closeShop :: IO ()
closeShop = paths >>= \(dbPath, logPath) -> mapM_ removeIfThere [dbPath, logPath]

-- | RETURN: IO Bool, True if every item's stock is its opening quantity plus
--           its journal's movements; False, else.
addsUp :: IO Bool
addsUp = do
    (dbPath, _) <- paths
    db <- open dbPath 10.0 Nothing
    rowList <- query db ("SELECT o.item, o.qty + COALESCE(SUM(j.delta), 0), s.qty"
                         ++ "  FROM opening o JOIN stock s ON s.item = o.item"
                         ++ "  LEFT JOIN journal j ON j.item = o.item GROUP BY o.item") []
    close db
    return (and [ expected == got | [_, expected, got] <- rowList ])

-- | RETURN: IO (); one line appended to the log for a shop test run.
check :: String -> String -> String -> IO ()
check when' test choice = when (test `elem` shopTestList) $ do
    (_, logPath) <- paths
    ok <- addsUp
    let runName = unwords (words (test ++ " " ++ choice))
    appendFile logPath (printf "%-6s %-15s %s\n" when' runName
                               (if ok then "stock adds up" else "STOCK BROKEN" :: String))

-- | RETURN: IO (); the command the command line names, done; exit 2 where
--           none is named.
main :: IO ()
main = do
    arguments <- getArgs
    case arguments of
        ["open"]                  -> openShop
        ["close"]                 -> closeShop
        ["check", w, t]           -> check w t ""
        ["check", w, t, c]        -> check w t c
        _ -> do
            hPutStrLn stderr "usage: fixture.exe open | close | check before|after <app> <choice>"
            exitWith (ExitFailure 2)
