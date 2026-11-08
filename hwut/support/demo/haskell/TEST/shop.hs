-- @hwut {
--     title     = "Demo: a shop's stock -- what the directory's hwut.conf arranges"
--     build     { framework = "make", target = "%.exe" }
--     tolerance { stderr_ignored = true }
--     choices {
--         sell   { features = ["unordered-table", "stderr-ignored", "collision"] }
--         report { features = ["output-file", "keyed-table-separator", "dependency",
--                              "frame-scripts", "test-scripts", "stderr-ignored"]
--                  output   = ["<stdout>", "stock.csv"] }
--     }
-- }
--
-- _____________________________________________________________________________
-- SUBJECT  the stock of a small shop, kept in an SQLite database: a delivery
--          comes in, three clerks sell at once, and the stock is reported.
-- REQUIREMENT  Every movement of the stock is journalled, so that the stock
--              always ADDS UP: opening quantity plus the journal's movements.
--
-- THE DIRECTORY ARRANGES WHAT NO SINGLE TEST CAN -- in 'hwut.conf' beside
-- this file, read it first. hwut, when it enters this directory:
--
--     on_entry        'make ... && ./fixture.exe open': the helpers built, a
--                     fresh 'TMP/shop.db', stocked
--     on_before_test  'fixture.exe check before $HWUT_TEST $HWUT_CHOICE',
--     on_after_test   'fixture.exe check after ...': around every test run,
--                     whether the stock adds up, into 'TMP/frame.log' --
--                     hwut sets the two variables for the run
--     on_exit         'fixture.exe close'
--     apps            'delivery.json' is a test, though it carries no
--                     header: JSON has no comment to carry one. 'admit'
--                     takes it out of the files hwut ignores by default
--                     ('*.json'); 'execute' says how it is run --
--                     'shop.exe deliver delivery.json'.
--     collision       'delivery.json' and 'shop.hs sell' both write the
--                     database. SQLite lets one writer at a time hold the
--                     file; one that waits too long fails with 'database
--                     is locked'. hwut never runs the two at once.
--     dependency      'shop.hs report' runs after both, whatever their
--                     verdict: it reports what they left.
--
-- STDERR  Every SQL statement is logged on stderr, as a server would. A
-- word on stderr fails a run ('unexpected stderr') unless the header says
-- 'stderr_ignored = true': the words there are on purpose, and no error.
--
-- CHOICES
--
-- sell     three clerks sell at once, each in a thread of its own. The sales
--          are printed as '##! table unordered sep={;}': rows of 'item;qty',
--          in any order -- and no column is a key, 'apple;1' stands four
--          times.
--
-- report   the stock, as '##! table key=0 sep={;}', and the same rows
--          written to 'stock.csv': 'output' names the file, hwut reads it
--          after the run and compares it with its own GOOD. Then the frame
--          log of the shop's tests: what 'on_before_test' and 'on_after_test'
--          found around the delivery and the sale ('##! potpourri': which
--          ran first is free), and before this report.
--
-- deliver  (no choice -- 'execute' of 'delivery.json' calls it) books a
--          delivery note: every line on the stock and into the journal, in
--          one transaction.
--
-- The delivery note is read by the small JSON reader below: GHC ships no
-- JSON package.
-- _____________________________________________________________________________
module Main (main) where

import Control.Concurrent      (forkIO)
import Control.Concurrent.MVar (modifyMVar_, newEmptyMVar, newMVar, putMVar, readMVar, takeMVar)
import Control.Exception       (SomeException, displayException, try)
import Control.Monad           (forM, forM_, unless)
import Data.Char               (isDigit, isSpace)
import Data.List               (intercalate, isInfixOf, sort)
import System.Directory        (doesFileExist)
import System.Environment      (getArgs, getExecutablePath)
import System.Exit             (ExitCode (..), exitWith)
import System.FilePath         (takeDirectory, (</>))
import System.IO               (hPutStrLn, stderr)
import Text.Printf             (printf)

import Sqlite

-- | What each clerk sells, one item per sale.
clerkList :: [(String, [String])]
clerkList = [("anna", ["apple", "apple", "pear"]), ("ben", ["apple", "plum"]), ("chloe", ["apple"])]

-- | RETURN: IO FilePath, the directory this program stands in.
here :: IO FilePath
here = takeDirectory <$> getExecutablePath

-- | RETURN: IO Db, a connection to the shop's database, every statement it
--           executes logged on stderr. Exits 1 where the database does not
--           stand: 'on_entry' writes it.
connect :: IO Db
connect = do
    dbPath <- (</> ("TMP" </> "shop.db")) <$> here
    there  <- doesFileExist dbPath
    unless there $ do
        hPutStrLn stderr ("shop.exe: no " ++ dbPath ++ " -- 'on_entry' writes it; by hand: 'hwut.execute fixture open'")
        exitWith (ExitFailure 1)
    open dbPath 10.0 (Just (hPutStrLn stderr . ("sql: " ++)))

-- | RETURN: IO (); the stock of 'item' changed by 'delta' and journalled, in
--           one transaction.
move :: Db -> String -> Int -> String -> IO ()
move db item delta source = do
    execute db "BEGIN IMMEDIATE" []
    execute db "UPDATE stock SET qty = qty + ? WHERE item = ?" [SqlInt delta, SqlText item]
    execute db "INSERT INTO journal VALUES (?, ?, ?)" [SqlText item, SqlInt delta, SqlText source]
    execute db "COMMIT" []

-- ____________________________________________________________________________
-- JSON, as much as a delivery note needs
--
-- | A JSON value.
data Json = JObject [(String, Json)] | JArray [Json] | JString String | JNumber Int
          | JBool Bool | JNull

-- | RETURN: Maybe (Json, String), the value at the start of 'text' and what
--           follows it; Nothing where none stands there.
value :: String -> Maybe (Json, String)
value text = case dropWhile isSpace text of
    '{' : rest -> members (dropWhile isSpace rest) []
    '[' : rest -> elements (dropWhile isSpace rest) []
    '"' : rest -> (\(s, r) -> (JString s, r)) <$> string rest
    't' : 'r' : 'u' : 'e' : rest -> Just (JBool True, rest)
    'f' : 'a' : 'l' : 's' : 'e' : rest -> Just (JBool False, rest)
    'n' : 'u' : 'l' : 'l' : rest -> Just (JNull, rest)
    s@(c : _) | isDigit c || c == '-' -> let (n, r) = span (\x -> isDigit x || x == '-') s
                                         in  Just (JNumber (read n), r)
    _ -> Nothing
  where
    members ('}' : rest) acc = Just (JObject (reverse acc), rest)
    members ('"' : rest) acc = do
        (k, r1) <- string rest
        ':' : r2 <- Just (dropWhile isSpace r1)
        (v, r3) <- value r2
        case dropWhile isSpace r3 of
            ',' : r4 -> members (dropWhile isSpace r4) ((k, v) : acc)
            r4       -> members r4 ((k, v) : acc)
    members _ _ = Nothing
    elements (']' : rest) acc = Just (JArray (reverse acc), rest)
    elements s acc = do
        (v, r1) <- value s
        case dropWhile isSpace r1 of
            ',' : r2 -> elements (dropWhile isSpace r2) (v : acc)
            r2       -> elements r2 (v : acc)
    string s = go s ""
      where go ('\\' : c : r) acc = go r (c : acc)
            go ('"' : r) acc      = Just (reverse acc, r)
            go (c : r) acc        = go r (c : acc)
            go [] _               = Nothing

-- | RETURN: Json, the member 'k' of the object 'j'; JNull where none is.
member :: String -> Json -> Json
member k (JObject entries) = maybe JNull id (lookup k entries)
member _ _                 = JNull

-- | RETURN: String, the text of a JSON string; "" else.
textOf :: Json -> String
textOf (JString s) = s
textOf _           = ""

-- | RETURN: Int, the number of a JSON number; 0 else.
numberOf :: Json -> Int
numberOf (JNumber n) = n
numberOf _           = 0

-- ____________________________________________________________________________
-- the commands
--
-- | RETURN: IO (); the delivery note in 'path' booked and printed.
deliver :: FilePath -> IO ()
deliver path = do
    text <- readFile path
    note <- case value text of
        Just (j, _) -> return j
        Nothing     -> hPutStrLn stderr ("shop.exe: " ++ path ++ " is no JSON") >> exitWith (ExitFailure 1)
    let lineList = case member "lines" note of { JArray xs -> xs; _ -> [] }
        noteId   = textOf (member "note" note)
    db <- connect
    execute db "BEGIN IMMEDIATE" []
    forM_ lineList $ \l -> do
        execute db "UPDATE stock SET qty = qty + ? WHERE item = ?" [SqlInt (numberOf (member "qty" l)), SqlText (textOf (member "item" l))]
        execute db "INSERT INTO journal VALUES (?, ?, ?)" [SqlText (textOf (member "item" l)), SqlInt (numberOf (member "qty" l)), SqlText noteId]
    execute db "COMMIT" []
    printf "delivery note %s from %s:\n" noteId (textOf (member "supplier" note))
    forM_ lineList $ \l -> printf "    %-6s +%d\n" (textOf (member "item" l)) (numberOf (member "qty" l))

-- | RETURN: IO (); three clerks sell at once, every sale printed.
sell :: IO ()
sell = do
    saleList  <- newMVar []
    errorList <- newMVar []
    connect >>= close
    doneList <- forM clerkList $ \(name, itemList) -> do
        done <- newEmptyMVar
        _ <- forkIO $ do
            result <- try $ do
                db <- connect
                forM_ itemList $ \item -> do
                    move db item (-1) name
                    modifyMVar_ saleList (return . ((item ++ ";1") :))
                close db
            case result of
                Left problem -> modifyMVar_ errorList (return . ((name ++ ": " ++ displayException (problem :: SomeException)) :))
                Right ()     -> return ()
            putMVar done ()
        return done
    mapM_ takeMVar doneList
    errors <- readMVar errorList
    unless (null errors) $ do
        hPutStrLn stderr ("shop.exe: a sale failed -- " ++ intercalate "; " errors)
        exitWith (ExitFailure 1)
    sales <- reverse <$> readMVar saleList
    putStrLn "sales, item;qty -- in the order the clerks booked them:"
    putStrLn "##! table unordered sep={;}"
    mapM_ putStrLn sales
    putStrLn "####"

-- | RETURN: IO (); the stock and the frame log printed; 'stock.csv' written.
report :: IO ()
report = do
    directory <- here
    db <- connect
    rowList <- query db "SELECT item, qty FROM stock ORDER BY qty, item" []
    close db
    writeFile (directory </> "stock.csv")
              (unlines ("item;qty" : [ item ++ ";" ++ qty | [item, qty] <- sort rowList ]))
    putStrLn "stock, item;qty (also written to stock.csv):"
    putStrLn "##! table key=0 sep={;}"
    forM_ rowList $ \[item, qty] -> putStrLn (item ++ ";" ++ qty)
    putStrLn "####"
    lineList <- map (reverse . dropWhile isSpace . reverse) . lines
                <$> readFile (directory </> "TMP" </> "frame.log")
    length lineList `seq` putStrLn "the frame, around the delivery and the sale:"
    putStrLn "##! potpourri"
    mapM_ putStrLn [ l | l <- lineList, not ("shop.hs report" `isInfixOf` l) ]
    putStrLn "####"
    mapM_ putStrLn [ l | l <- lineList, "shop.hs report" `isInfixOf` l ]

-- | RETURN: IO (); the command the command line names, done, then
--           '<hwut-end>'; exit 1 where none is named.
main :: IO ()
main = do
    arguments <- getArgs
    case arguments of
        ["deliver", path] -> deliver path
        ["sell"]          -> sell
        ["report"]        -> report
        _                 -> putStrLn "choices: sell, report" >> exitWith (ExitFailure 1)
    putStrLn "<hwut-end>"
