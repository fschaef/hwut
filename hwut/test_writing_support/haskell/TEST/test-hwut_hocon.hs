-- @hwut {
--     title      = "HOCON parser: subset (A), annotated tree"
--     build      { framework = "make", executable = "%.exe" }
--     choices {
--         comments  { features = ["haskell-hocon"] }
--         faults    { features = ["haskell-hocon"] }
--         fuzz      { features = ["haskell-hocon"] }
--         numbers   { features = ["haskell-hocon"] }
--         oneline   { features = ["haskell-hocon"] }
--         positions { features = ["haskell-hocon"] }
--         quoting   { features = ["haskell-hocon"] }
--         refused   { features = ["haskell-hocon"] }
--         scalars   { features = ["haskell-hocon"] }
--         structure { features = ["haskell-hocon"] }
--         triple    { features = ["haskell-hocon"] }
--         unclosed  { features = ["haskell-hocon"] }
--     }
--     interactive = true
-- }
--
-- SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
-- _____________________________________________________________________________
--
-- PURPOSE: The Haskell port of 'python/TEST/test-hwut_hocon.py', choice for
--          choice, held against its GOOD files by '.link'. The fuzz draws the
--          deterministic stream exactly as Python does -- the mutation is one
--          pure 'Draw' -- so it parses the same 3000 headers and gives the
--          same counts; each parse is forced under a bound ('timeout').
-- _____________________________________________________________________________
module Main (main) where

import           Control.Exception   (SomeException, evaluate, try)
import           Control.Monad       (forM_, replicateM)
import           Control.Monad.State (runState)
import           Data.List           (foldl')
import qualified Data.Map.Strict     as Map
import           System.Timeout      (timeout)
import           Text.Printf         (printf)

import           Hwut.DeterministicRandom
import           Hwut.Hocon
import           Hwut.Runner

-- | RETURN: IO (); a section heading printed.
banner :: String -> IO ()
banner label = putStrLn "" >> putStrLn ("--- " ++ label ++ " ---")

-- | RETURN: [SourceLine], 'text' split at every '\n' (as Python's 'split'),
--           the offsets applied to every line.
sourceLines :: Int -> Int -> String -> [SourceLine]
sourceLines lineOffset columnOffset t =
    [ SourceLine l (i + lineOffset) columnOffset | (i, l) <- zip [1 ..] (splitNewline t) ]
  where
    splitNewline s = case break (== '\n') s of
        (a, [])    -> [a]
        (a, _ : b) -> a : splitNewline b

-- | RETURN: IO (); the annotated tree, positions included.
showTree :: Int -> Node -> IO ()
showTree indent n = case n of
    ObjectNode entries at -> do
        putStrLn (pad ++ "{ at " ++ show at)
        forM_ entries $ \e -> do
            putStrLn (pad ++ "  key '" ++ key e ++ "' at " ++ show (keyPosition e) ++ " ->")
            showTree (indent + 1) (node e)
        putStrLn (pad ++ "}")
    ListNode items at -> do
        putStrLn (pad ++ "[ at " ++ show at)
        mapM_ (showTree (indent + 1)) items
        putStrLn (pad ++ "]")
    ScalarNode v at -> putStrLn (pad ++ show v ++ " (" ++ typeName v ++ ") at " ++ show at)
  where pad = concat (replicate indent "    ")

-- | RETURN: IO (); 'text' parsed, its tree and faults printed.
runWith :: String -> Int -> Int -> String -> IO ()
runWith label lineOffset columnOffset t = do
    banner label
    let (document, faultList) = parse (sourceLines lineOffset columnOffset t) "f.hocon"
    showTree 0 document
    mapM_ (\f -> putStrLn ("FAULT " ++ show f)) faultList

-- | RETURN: IO (); 'runWith' without offsets.
run :: String -> String -> IO ()
run label = runWith label 0 0

-- | RETURN: IO (); every scalar shape parsed and printed.
testScalars :: IO ()
testScalars = run "scalars" $ concat
    [ "a = bare\n", "b = \"quoted \\\"x\\\" and \\n\"\n", "c = 42\n", "d = -3.14\n", "e = 1e-6\n"
    , "f = true\n", "g = no\n", "h = make %.exe\n", "i: \"colon-bound\"\n", "j = null\n"
    , "k = nihil\n", "l =\n" ]

-- | RETURN: IO (); every radix, the helper and the split sign parsed and printed.
testNumbers :: IO ()
testNumbers = do
    run "decimal, with sign and exponent" "a = 42\nb = -0.12\nc = +7e212\nd = 6.02e23\ne = .5\n"
    run "the visual helper enters no value" "a = 1_000\nb = 7_000.5_5\n"
    run "hexadecimal, binary, octal" "a = 0xDEAD_BEEF\nb = 0b0111_11_01\nc = 0o3124\nd = 0XFF\ne = -0b1010\n"
    run "roman" "a = 0rIV\nb = 0rMCMLXXXIV\nc = -0rX\n"
    run "a sign standing apart from its digits" "a = - 0.12\nb = + 7\nc = - 0xFF\nd = - -1.5e3\n"
    run "what spells no number is a string, and carries quotes"
        "a = 1.2.3\nb = 0x\nc = 0b012\nd = 1__0\ne = 0rIIII\nf = 0rVX\n"
    run "no arithmetic: this language computes nothing" "a = 5 - 1\n"

-- | RETURN: IO (); the quoted string and the unquoted word parsed and printed.
testQuoting :: IO ()
testQuoting = do
    run "quoted: blanks, comment markers and binders are content"
        "a = \"make %.exe\"\nb = \"not # a comment\"\nc = \"x = y\"\nd = \"yes\"\n"
    run "unquoted: refused, and shown in the quotes it wants"
        "a = make\nb = strip.pype\nc = [one, two]\nd = 1\n"

-- | RETURN: IO (); objects, lists, nesting parsed and printed.
testStructure :: IO ()
testStructure = do
    run "nesting and key-brace" "outer {\n    inner = { deep = 1 }\n    braced { x = 2 }\n}\n"
    run "lists" $ concat
        [ "commas   = [one, two, three]\n", "newlines = [\n", "    1\n", "    2\n", "]\n"
        , "objects  = [ { a = 1 }, { a = 2 } ]\n", "empty    = []\n" ]

-- | RETURN: IO (); entries sharing a line, without commas, parsed and printed.
testOneline :: IO ()
testOneline = do
    run "two entries, one line, no comma" "caps { timeout_sec = 30  network = false }\n"
    run "a quoted value with blanks, beside a following key" "a { build = \"make %.exe\"  timeout_sec = 5 }\n"
    run "three entries, one line" "x { a = 1  b = \"two\"  c = { d = 3 } }\n"

-- | RETURN: IO (); both comment forms, whole-line and trailing, parsed and printed.
testComments :: IO ()
testComments = run "comments" $ concat
    [ "# whole line\n", "a = 1   # trailing\n", "// slashes too\n", "b = 2   // trailing slashes\n"
    , "c = bare value # comment cut\n" ]

-- | RETURN: IO (); the three constructs that do not exist here, refused by name.
testRefused :: IO ()
testRefused = run "refused, each by name"
    "include \"other.conf\"\na = ${outside.value}\nb += appended\nd = survives\n"

-- | RETURN: IO (); the text of several lines parsed and printed.
testTriple :: IO ()
testTriple = do
    let q = "\"\"\""
    run "several lines: indentation and blank ends go" $ concat
        [ "doc = ", q, "\n", "    First line.\n", "\n", "      indented more\n", "    last line\n"
        , "    ", q, "\n", "after = 1\n" ]
    run "on one line; beside another entry; in a list" $ concat
        [ "a = ", q, "one line", q, "  b = 2\n", "c = [", q, "x", q, ", \"y\"]\n" ]
    run "as written: a quote, a backslash-n, a comment marker" $
        "a = " ++ q ++ "says \"no\" \\n # not a comment" ++ q ++ "\n"
    run "never closed: a fault, at its beginning" $ "a = 1\nb = " ++ q ++ "open\nc = 2\n"

-- | RETURN: IO (); faults accumulating while the parse completes, printed.
testFaults :: IO ()
testFaults = run "faults accumulate" "a = 1\na = 2\nb = \"unterminated\n}\nc {\n    d = 3\n"

-- | RETURN: IO (); a list whose ']' was forgotten ENDS, and says so once.
testUnclosed :: IO ()
testUnclosed = do
    run "a list closed by the object's brace" "@hwut { title = \"B\" choices = [ }\nafter = 1\n"
    run "a stray character in a list" "a = [1, ; 2]\n"

-- | The valid headers the fuzz mutates.
fuzzSeedList :: [String]
fuzzSeedList =
    [ concat [ "@hwut {\n", "    title    = \"T\"\n", "    choices  = [\"a\", \"b\"]\n"
             , "    tolerance { eq_pattern = [\"x.*\"] }\n", "    n        = -1.5e3\n"
             , "    f        = true\n", "}\n" ]
    , concat [ "hwut {\n", "    target     { clean = \"./c.sh\" }\n"
             , "    dependency { \"a.py\" = [\"b.py one\"] }\n", "    ignore     = [\"x\"]   // comment\n"
             , "    # comment\n", "}\n" ] ]

-- | WHAT A TYPO IS MADE OF: the characters HOCON gives meaning to, a few it
--   refuses by name, and some ordinary ones.
fuzzAlphabet :: [String]
fuzzAlphabet = map (: []) "{}[]\",=:#/\\$ \n\t-+.eE0a" ++ ["\"\"\"", "${", "//", "+="]

-- | How many mutated headers the fuzz parses.
fuzzInputN :: Int
fuzzInputN = 3000

-- | The bound of one parse, in microseconds.
fuzzBoundUs :: Int
fuzzBoundUs = 500000           -- one parse takes well under a millisecond

-- | RETURN: Draw String, 'text' edited by one to four random insertions,
--           deletions and duplications of a short stretch.
mutated :: String -> Draw String
mutated t0 = do
    n <- nextInt 1 4
    go n t0
  where
    go :: Int -> String -> Draw String
    go 0 t = return t
    go k t = do
        i  <- nextInt 0 (length t)
        op <- nextInt 0 2
        t' <- case op of
            0 -> (\piece -> take i t ++ piece ++ drop i t) <$> select fuzzAlphabet
            1 -> return (take i t ++ drop (i + 1) t)
            _ -> (\j -> take i t ++ take 5 (drop j t) ++ drop i t) <$> nextInt 0 (length t)
        go (k - 1) t'

-- | RETURN: Int, the nodes of the tree -- counting them forces all of it.
nodeCount :: Node -> Int
nodeCount (ObjectNode entries _) = 1 + sum [ length (key e) + nodeCount (node e) | e <- entries ]
nodeCount (ListNode items _)     = 1 + sum (map nodeCount items)
nodeCount (ScalarNode v _)       = length (show v)

-- | RETURN: IO (); the counts printed: every mutated header ends and answers
--           faults -- clean, with faults, hang (past the bound), exception.
testFuzz :: IO ()
testFuzz = do
    let inputs = fst (runState (replicateM fuzzInputN (select fuzzSeedList >>= mutated)) (deterministicStream 4711))
    (tally, example) <- foldlM' inputs (Map.empty, []) $ \(tally, example) t -> do
        outcome <- try $ timeout fuzzBoundUs $ evaluate $
            let (document, faultList) = parse (sourceLines 0 0 t) "f.hocon"
            in nodeCount document + sum (map (length . show) faultList) `seq` not (null faultList)
        return $ case outcome of
            Right (Just True)  -> (Map.insertWith (+) "with faults" 1 tally, example)
            Right (Just False) -> (Map.insertWith (+) "clean" 1 tally, example)
            Right Nothing      -> (Map.insertWith (+) "hang" 1 tally, firstOf "hang" t example)
            Left problem       -> (Map.insertWith (+) "exception" (1 :: Int) tally
                                  , firstOf "exception" (show (problem :: SomeException) ++ "\n" ++ t) example)
    banner (show fuzzInputN ++ " mutated headers")
    forM_ ["clean", "with faults", "hang", "exception"] $ \k ->
        printf "    %-12s %d\n" k (Map.findWithDefault 0 k tally)
    forM_ (reverse example) $ \(k, t) -> putStrLn ("FIRST " ++ upper k ++ ":\n" ++ t)
  where
    firstOf k t example = if any ((== k) . fst) example then example else (k, t) : example
    upper = map (\c -> if c >= 'a' && c <= 'z' then toEnum (fromEnum c - 32) else c)
    foldlM' xs z f = foldl' (\acc x -> acc >>= \a -> f a x) (return z) xs

-- | RETURN: IO (); the same text at its own place and at an offset, printed.
testPositions :: IO ()
testPositions = do
    let t = "@hwut {\n    title = \"T\"\n}"
    run "plain: as its own file" t
    runWith "offset: same text, region begins at line 40, 3 columns stripped" 39 3 t

-- | RETURN: IO (); the mode the command line selects has run.
main :: IO ()
main = hwutRunner "HOCON parser: subset (A), annotated tree;"
    [ ("scalars",   testScalars)
    , ("numbers",   testNumbers)
    , ("quoting",   testQuoting)
    , ("structure", testStructure)
    , ("oneline",   testOneline)
    , ("comments",  testComments)
    , ("refused",   testRefused)
    , ("triple",    testTriple)
    , ("unclosed",  testUnclosed)
    , ("fuzz",      testFuzz)
    , ("faults",    testFaults)
    , ("positions", testPositions)
    ]
