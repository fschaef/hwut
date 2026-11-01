-- SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
-- _____________________________________________________________________________
--
-- PURPOSE: The HOCON subset of the specification language, parsed into the
--          ANNOTATED TREE -- the port of 'python/hwut_hocon.py' (see
--          '../python/README-hwut_hocon.txt'). Every key, value and block
--          carries its file-relative position.
--
--     import Hwut.Hocon
--
--     let (document, faultList) = parse [SourceLine "a = 1" 1 0] "f.hocon"
--
-- THE SUBSET: nested objects, lists, numbers in every radix ('_' between
-- digits a visual helper), true/false/yes/no, the spellings of nothing, '#'
-- and '//' comments, '=' or ':' before a value, a brace directly after a key.
-- A STRING VALUE IS WRITTEN IN DOUBLE QUOTES; a text of several lines in
-- triple quotes, laid out as Python's 'inspect.cleandoc' lays it out.
-- 'include', '${...}' and '+=' are refused by name.
--
-- A PURE FUNCTION. 'parse' takes lines and gives the tree AND the faults: it
-- never raises, it accumulates faults and recovers at the next line. Inside,
-- the parser is a small hand-written combinator over the State monad 'P' --
-- the cursor and the faults so far are its state; 'fault' records one,
-- 'skipLine' recovers. Parsec ships with GHC, but its model (consume or
-- fail, one error) is not this parser's (record and go on, many faults, the
-- recovery at the next line): the Python parser's every step, recovery
-- included, is what the 3000-input fuzz holds the port to.
-- _____________________________________________________________________________
module Hwut.Hocon
    ( E_ParseFault (..)
    , Position (..)
    , ParseFault (..)
    , SourceLine (..)
    , Value (..)
    , Node (..)
    , Entry (..)
    , parse
    , get
    , keys
    , typeName
    , cleandoc
    ) where

import           Control.Monad       (unless, when)
import           Control.Monad.State (State, runState, gets, modify)
import           Data.Array          (Array, listArray, (!))
import           Data.Array.Unboxed  (UArray, bounds)
import qualified Data.Array.Unboxed  as U
import           Data.Char           (isSpace, digitToInt)
import           Data.List           (find, isInfixOf, isPrefixOf, foldl')
import qualified Data.Map.Strict     as Map
import           Data.Ratio          ((%))

import           Hwut.PyText         (floatRepr, strRepr, pyBool)

-- | What a fault is.
data E_ParseFault = SYNTAX      -- ^ the text does not parse
                  | REFUSED     -- ^ a construct that does not exist here, by name
    deriving (Eq, Show)

-- | One place in one file; 1-based, as an editor counts.
data Position = Position { line :: Int, column :: Int }
    deriving Eq

instance Show Position where
    show (Position l c) = show l ++ ":" ++ show c

-- | One fault of the parse, where it stands and what it is.
data ParseFault = ParseFault
    { kind     :: E_ParseFault
    , file     :: String
    , position :: Position
    , message  :: String
    }

instance Show ParseFault where
    show f = file f ++ ":" ++ show (position f) ++ ": " ++ show (kind f) ++ ": " ++ message f

-- | One line as the parser reads it; 'columnOffset' counts what was removed
--   before 'text' begins.
data SourceLine = SourceLine { text :: String, lineNumber :: Int, columnOffset :: Int }

-- | A scalar: Python's None, bool, int, float or str.
data Value = Null | Bool Bool | Int Integer | Float Double | Str String
    deriving Eq

instance Show Value where
    -- | Python's 'repr' of the value.
    show Null      = "None"
    show (Bool b)  = pyBool b
    show (Int n)   = show n
    show (Float x) = floatRepr x
    show (Str s)   = strRepr s

-- | RETURN: String, the name of the value's Python type.
typeName :: Value -> String
typeName Null      = "NoneType"
typeName (Bool _)  = "bool"
typeName (Int _)   = "int"
typeName (Float _) = "float"
typeName (Str _)   = "str"

-- | A node of the tree.
data Node = ScalarNode { value :: Value, nodePosition :: Position }
          | ListNode   { itemList :: [Node], nodePosition :: Position }
          | ObjectNode { entryList :: [Entry], nodePosition :: Position }

-- | One key with its value inside an object.
data Entry = Entry { key :: String, keyPosition :: Position, node :: Node }

-- | RETURN: Maybe Entry, the entry named 'k' of the object; Nothing where
--           there is none, or the node is no object.
get :: String -> Node -> Maybe Entry
get k (ObjectNode entries _) = find ((== k) . key) entries
get _ _                      = Nothing

-- | RETURN: [String], the object's keys in written order.
keys :: Node -> [String]
keys (ObjectNode entries _) = map key entries
keys _                      = []

-- ---------------------------------------------------------------- the cursor

-- | The parser's state: the lines, where it stands, the faults so far.
data PState = PState
    { lineArray :: Array Int (UArray Int Char)
    , infoArray :: Array Int SourceLine
    , lineN     :: Int
    , iLine     :: Int
    , iCol      :: Int
    , faultsR   :: [ParseFault]     -- reversed
    , fileName  :: String
    }

type P = State PState

-- | RETURN: P (UArray Int Char), the current line's text; empty beyond the
--           last line.
currentText :: P (UArray Int Char)
currentText = do
    s <- gets id
    return (if iLine s < lineN s then lineArray s ! iLine s else emptyText)

-- | The text of no line: beyond the last one.
emptyText :: UArray Int Char
emptyText = U.listArray (0, -1) []

-- | RETURN: Int, the number of characters of 'a'.
size :: UArray Int Char -> Int
size a = let (lo, hi) = bounds a in hi - lo + 1

-- | RETURN: P Bool, True where no character remains.
atEnd :: P Bool
atEnd = gets (\s -> iLine s >= lineN s)

-- | RETURN: P (Maybe Char), the character 'ahead' places from here on this
--           line; '\n' at the line's end; Nothing beyond the last line.
peek :: Int -> P (Maybe Char)
peek ahead = do
    endF <- atEnd
    if endF then return Nothing else do
        t <- currentText
        i <- gets ((+ ahead) . iCol)
        return (Just (if i < size t then t U.! i else '\n'))

-- | RETURN: P (); 'n' characters stepped WITHIN the line.
skip :: Int -> P ()
skip n = modify (\s -> s { iCol = iCol s + n })

-- | RETURN: P (); the cursor at the beginning of the next line.
skipLine :: P ()
skipLine = modify (\s -> s { iLine = iLine s + 1, iCol = 0 })

-- | RETURN: P Position, file-relative, of the character at the cursor;
--           beyond the last line, one past the last line's end.
here :: P Position
here = do
    s <- gets id
    return $ if iLine s >= lineN s
        then if lineN s == 0 then Position 1 1
             else let lastLine = infoArray s ! (lineN s - 1)
                  in Position (lineNumber lastLine) (columnOffset lastLine + length (text lastLine) + 1)
        else let current = infoArray s ! iLine s
             in Position (lineNumber current) (columnOffset current + iCol s + 1)

-- | RETURN: P (); the fault recorded.
fault :: E_ParseFault -> Position -> String -> P ()
fault k at m = modify (\s -> s { faultsR = ParseFault k (fileName s) at m : faultsR s })

-- | RETURN: P String, the characters of the current line from 'i' on (none
--           where 'i' is past its end) while 'keep' holds.
spanFrom :: Int -> (Char -> Bool) -> P String
spanFrom i keep = do
    t <- currentText
    return (takeWhile keep [ t U.! j | j <- [i .. size t - 1] ])

-- | RETURN: Bool, True for what Python's '\s' and 'str.isspace' take as blank.
pySpace :: Char -> Bool
pySpace c = isSpace c || (c >= '\x1c' && c <= '\x1f') || c == '\x85'

-- | RETURN: Bool, True for a character a TOKEN may hold: none that binds,
--           opens, closes, separates, or is blank.
tokenChar :: Char -> Bool
tokenChar c = not (pySpace c) && c `notElem` "{}[]=,:\"#"

-- | RETURN: P String, the token from column 'i': the run of 'tokenChar's.
tokenAt :: Int -> P String
tokenAt i = spanFrom i tokenChar

-- ---------------------------------------------------------------- the parse

-- | RETURN: (Node, [ParseFault]), the document -- an ObjectNode of every
--           entry of the outermost level, possibly empty -- and every fault
--           found, in order; [] on a clean parse. 'name' names the file in
--           the faults.
parse :: [SourceLine] -> String -> (Node, [ParseFault])
parse sourceLines name = (document, reverse (faultsR final))
  where
    n     = length sourceLines
    start = PState
        { lineArray = listArray (0, n - 1) [ U.listArray (0, length (text l) - 1) (text l) | l <- sourceLines ]
        , infoArray = listArray (0, n - 1) sourceLines
        , lineN = n, iLine = 0, iCol = 0, faultsR = [], fileName = name }
    (document, final) = runState (parseBody Nothing) start

-- | RETURN: P Node, the ObjectNode of the entries up to 'terminator' ('}',
--           or Nothing for the end of the text); its position is where its
--           first entry may begin.
parseBody :: Maybe Char -> P Node
parseBody terminator = do
    at <- here
    entries <- loop []
    return (ObjectNode (reverse entries) at)
  where
    loop entries = do
        skipBlank
        endF <- atEnd
        if endF
            then do
                forM_' terminator $ \t -> do
                    p <- here
                    fault SYNTAX p ("unterminated object: '" ++ [t] ++ "' missing")
                return entries
            else do
                c <- peek 0
                case c of
                    Just x | Just x == terminator -> skip 1 >> return entries
                    Just '}' -> do
                        p <- here
                        fault SYNTAX p "unmatched '}'"
                        skip 1
                        loop entries
                    _ -> parseEntry entries >>= loop

-- | RETURN: P (), 'action' run on the value, where there is one.
forM_' :: Maybe a -> (a -> P ()) -> P ()
forM_' Nothing  _      = return ()
forM_' (Just x) action = action x

-- | RETURN: P [Entry], 'entries' (reversed) with the 'key = value' pair here
--           before them, where it parses and its key is new; a fault
--           recovers at the next line.
parseEntry :: [Entry] -> P [Entry]
parseEntry entries = do
    keyAt <- here
    found <- parseKey
    case found of
        Nothing -> skipLine >> return entries
        Just "include" -> do
            fault REFUSED keyAt "'include' does not exist here: a specification refers to nothing outside its file"
            skipLine
            return entries
        Just k -> do
            skipSpace
            c  <- peek 0
            c1 <- peek 1
            bound <- case c of
                Just x | x == '=' || x == ':' -> skip 1 >> skipSpace >> return True
                Just '{' -> return True
                Just '+' | c1 == Just '=' -> do
                    p <- here
                    fault REFUSED p "'+=' does not exist here"
                    skipLine
                    return False
                _ -> do
                    p <- here
                    fault SYNTAX p ("expected '=', ':' or '{' after key '" ++ k ++ "'")
                    skipLine
                    return False
            if not bound then return entries else do
                parsed <- parseValue False
                case parsed of
                    Nothing -> return entries
                    Just v
                        | any ((== k) . key) entries -> do
                            fault SYNTAX keyAt ("duplicate key '" ++ k ++ "'; the first stands, this one is refused")
                            return entries
                        | otherwise -> return (Entry k keyAt v : entries)

-- | RETURN: P (Maybe String), the key here -- quoted, or a token; Nothing
--           where none stands (fault recorded).
parseKey :: P (Maybe String)
parseKey = do
    c <- peek 0
    if c == Just '"' then parseQuoted else do
        token <- gets iCol >>= tokenAt
        if null token
            then do
                p <- here
                fault SYNTAX p ("expected a key, found '" ++ stripped c ++ "'")
                return Nothing
            else skip (length token) >> return (Just token)

-- | RETURN: String, the peeked character as Python's 'peek().strip()': ''
--           for a blank, the line's end, or the end of the text.
stripped :: Maybe Char -> String
stripped (Just c) | not (pySpace c) = [c]
stripped _                          = ""

-- | RETURN: P (Maybe Node), the value here; Nothing where nothing usable
--           stands (fault recorded). 'inListF': an empty value is a fault,
--           not null -- inside a list there is no key it could belong to.
parseValue :: Bool -> P (Maybe Node)
parseValue inListF = do
    skipSpace
    at <- here
    c  <- peek 0
    c1 <- peek 1
    c2 <- peek 2
    case c of
        Just '{' -> skip 1 >> Just <$> parseBody (Just '}')
        Just '[' -> skip 1 >> Just <$> parseList at
        Just '"' | c1 == Just '"' && c2 == Just '"' -> fmap (\s -> ScalarNode (Str s) at) <$> parseTripleQuoted
        Just '"' -> fmap (\s -> ScalarNode (Str s) at) <$> parseQuoted
        Just '$' | c1 == Just '{' -> do
            fault REFUSED at "substitutions '${...}' do not exist here: a specification refers to nothing outside its file"
            skipLine
            return Nothing
        _ -> parseBare at inListF

-- | RETURN: P Node, the ListNode of the items up to ']'; a '}' ends it too,
--           the ']' said missing, the brace left to its object.
parseList :: Position -> P Node
parseList at = loop []
  where
    loop items = do
        skipBlank
        endF <- atEnd
        if endF
            then do
                p <- here
                fault SYNTAX p "unterminated list: ']' missing"
                done items
            else do
                c <- peek 0
                case c of
                    Just ']' -> skip 1 >> done items
                    Just ',' -> skip 1 >> loop items
                    Just '}' -> do
                        p <- here
                        fault SYNTAX p "unterminated list: ']' missing before '}'"
                        done items
                    _ -> do
                        before <- gets (\s -> (iLine s, iCol s))
                        item   <- parseValue True
                        after  <- gets (\s -> (iLine s, iCol s))
                        --  NO VALUE AND NOTHING CONSUMED: step over it, or the
                        --  loop never ends.
                        case item of
                            Just x  -> loop (x : items)
                            Nothing -> when (before == after) (skip 1) >> loop items
    done items = return (ListNode (reverse items) at)

-- | RETURN: P (Maybe String), the text from three double quotes to the next
--           three, over as many lines as it takes, AS WRITTEN, laid out by
--           'cleandoc'; Nothing where no closing quotes stand (fault
--           recorded at the opening ones).
parseTripleQuoted :: P (Maybe String)
parseTripleQuoted = do
    begin <- here
    skip 3
    let loop pieces = do
            endF <- atEnd
            if endF
                then do
                    fault SYNTAX begin "unterminated triple-quoted string: closing '\"\"\"' missing"
                    return Nothing
                else do
                    i <- gets iCol
                    rest <- spanFrom i (const True)
                    case findTriple rest of
                        Just k  -> do
                            skip (k + 3)
                            return (Just (cleandoc (joinLines (reverse (take k rest : pieces)))))
                        Nothing -> skipLine >> loop (rest : pieces)
    loop []
  where
    findTriple s = go 0 s
      where go k t | "\"\"\"" `isPrefixOf` t = Just k
                   | null t                    = Nothing
                   | otherwise                 = go (k + 1) (tail t)
    joinLines = foldr1' (\a b -> a ++ "\n" ++ b)
    foldr1' _ [] = ""
    foldr1' f xs = foldr1 f xs

-- | RETURN: P (Maybe String), the quoted string here, escapes resolved
--           ('\n' '\t' '\"' '\\'; any other escaped character stands for
--           itself); Nothing where it is unterminated at its line's end
--           (fault recorded at its opening quote).
parseQuoted :: P (Maybe String)
parseQuoted = do
    begin <- here
    t <- currentText
    i0 <- gets ((+ 1) . iCol)
    let n = size t
        at j = t U.! j
        go i acc
            | i >= n = Left i
            | otherwise = case at i of
                '"'  -> Right (i + 1, reverse acc)
                '\\' -> let escaped = if i + 1 < n then [at (i + 1)] else ""
                        in go (i + 2) (reverse (resolve escaped) ++ acc)
                c    -> go (i + 1) (c : acc)
        resolve "n" = "\n"
        resolve "t" = "\t"
        resolve e   = e
    case go i0 [] of
        Right (end, s) -> modify (\st -> st { iCol = end }) >> return (Just s)
        Left end -> do
            fault SYNTAX begin "unterminated string"
            modify (\st -> st { iCol = end })
            return Nothing

-- | RETURN: P (Maybe Node), the bare token here as a ScalarNode -- a
--           boolean, a number, a spelling of nothing, or null where the
--           value is empty (a fault inside a list); Nothing where it is none
--           of those (fault recorded): a string carries quotes.
parseBare :: Position -> Bool -> P (Maybe Node)
parseBare at inListF = do
    i   <- gets iCol
    raw <- tokenAt i
    joined <- if raw /= "+" && raw /= "-" then return Nothing else do
        --  A SIGN STANDING APART from its digits; the two must make ONE
        --  number ('- -1.5e3' does not).
        afterAt <- blankEnd (i + 1)
        after   <- tokenAt afterAt
        case (number after, number (raw ++ after)) of
            (Just _, Just x) | not (null after) -> do
                modify (\s -> s { iCol = afterAt + length after })
                return (Just x)
            _ -> return Nothing
    case joined of
        Just x -> return (Just (ScalarNode x at))
        Nothing
            | "${" `isPrefixOf` raw -> do
                p <- here
                fault REFUSED p "substitutions '${...}' do not exist here"
                skipLine
                return Nothing
            | otherwise -> do
                let cut = cutComment raw
                skip (length cut)
                c <- peek 0
                if null cut
                    then if inListF
                        then fault SYNTAX at ("expected a value, found '" ++ stripped c ++ "'") >> return Nothing
                        else return (Just (ScalarNode Null at))
                    else case interpret cut of
                        Just x  -> return (Just (ScalarNode x at))
                        Nothing -> do
                            fault SYNTAX at ("a string is written in double quotes: \"" ++ cut ++ "\"")
                            return Nothing
  where
    cutComment s = case findSub "//" s of
        Just k  -> take k s
        Nothing -> s
    findSub needle s = go 0 s
      where go k t | needle `isPrefixOf` t = Just k
                   | null t                = Nothing
                   | otherwise             = go (k + 1) (tail t)

-- | RETURN: P Int, the first column at or after 'i' that is no blank.
blankEnd :: Int -> P Int
blankEnd i = do
    t <- currentText
    let go j | j < size t && (t U.! j == ' ' || t U.! j == '\t') = go (j + 1)
             | otherwise = j
    return (go i)

-- | RETURN: P (); blanks and a comment skipped on the current line.
skipSpace :: P ()
skipSpace = do
    i <- gets iCol
    j <- blankEnd i
    modify (\s -> s { iCol = j })
    t <- currentText
    when (j < size t && (t U.! j == '#' || (t U.! j == '/' && j + 1 < size t && t U.! (j + 1) == '/'))) skipLine

-- | RETURN: P (); blanks, line ends, commas and comments skipped.
skipBlank :: P ()
skipBlank = do
    endF <- atEnd
    unless endF $ do
        t <- currentText
        i <- gets iCol
        let n = size t
            go j | j < n && t U.! j `elem` " \t," = go (j + 1)
                 | otherwise = j
            j' = go i
        if j' >= n then skipLine >> skipBlank else do
            modify (\s -> s { iCol = j' })
            let c = t U.! j'
            when (c == '#' || (c == '/' && j' + 1 < n && t U.! (j' + 1) == '/')) (skipLine >> skipBlank)

-- ---------------------------------------------------------------- the values

-- | RETURN: Maybe Value, what the bare text says -- Null for the spellings
--           of nothing, a Bool, a number; Nothing where it is an unquoted
--           string, which this language has not.
interpret :: String -> Maybe Value
interpret raw
    | raw `elem` ["null", "nil", "none", "nihil"] = Just Null
    | raw `elem` ["true", "yes"]                  = Just (Bool True)
    | raw `elem` ["false", "no"]                  = Just (Bool False)
    | otherwise                                   = number raw

-- | RETURN: Maybe Value, the Int or Float the text spells in whatever radix
--           -- '0x' '0b' '0o' '0r' (roman), or decimal -- '_' between digits
--           entering no value; Nothing where it spells no number.
number :: String -> Maybe Value
number raw = case take 2 body of
    p | p `elem` ["0r", "0R"] -> (\v -> Int (sign * v)) <$> roman (drop 2 body)
    p | Just radix <- lookup p radixList -> do
        digits <- withoutHelper (drop 2 body) (digitsOf radix)
        return (Int (sign * foldl' (\acc c -> acc * radix + fromIntegral (digitToInt c)) 0 digits))
    _ | decimalF raw -> Just (decimal (filter (/= '_') raw))
      | otherwise    -> Nothing
  where
    (sign, body) = case raw of
        ('-' : rest) -> (-1, rest)
        ('+' : rest) -> (1, rest)
        _            -> (1, raw)
    radixList = [("0x", 16), ("0X", 16), ("0b", 2), ("0B", 2), ("0o", 8), ("0O", 8)]
    digitsOf :: Integer -> String
    digitsOf 16 = "0123456789abcdefABCDEF"
    digitsOf 2  = "01"
    digitsOf _  = "01234567"

-- | RETURN: Maybe String, the digits with every '_' removed; Nothing where
--           there is no digit, a character that is no digit of the radix,
--           or an '_' that separates nothing.
withoutHelper :: String -> String -> Maybe String
withoutHelper t digitSet
    | null t || head t == '_' || last t == '_' = Nothing
    | "__" `isInfixOf` t                       = Nothing
    | null s                                   = Nothing
    | any (`notElem` digitSet) s               = Nothing
    | otherwise                                = Just s
  where s = filter (/= '_') t

-- | RETURN: Bool, True where the text is a decimal number: sign, digits
--           with '_' between them, a point, an exponent -- Python's
--           '_DECIMAL_RE', written out.
decimalF :: String -> Bool
decimalF s0 = case mantissa (optionalSign s0) of
    Just rest -> exponentPart rest == Just ""
    Nothing   -> False
  where
    optionalSign (c : cs) | c `elem` "+-" = cs
    optionalSign cs                       = cs
    digitRun (c : cs) | isDigit' c = Just (more cs)
    digitRun _                     = Nothing
    more ('_' : c : cs) | isDigit' c = more cs
    more (c : cs) | isDigit' c       = more cs
    more cs                          = cs
    mantissa s@(c : _) | isDigit' c = do
        rest <- digitRun s
        case rest of
            ('.' : afterPoint) -> Just (maybe afterPoint id (digitRun afterPoint))
            _                  -> Just rest
    mantissa ('.' : s) = digitRun s
    mantissa _         = Nothing
    exponentPart (e : s) | e `elem` "eE" = digitRun (optionalSign s)
    exponentPart s                       = Just s
    isDigit' c = c >= '0' && c <= '9'

-- | RETURN: Value, the decimal text (no '_' left) as Python reads it: a
--           Float where it holds '.', 'e' or 'E' -- correctly rounded, as
--           Python's 'float' -- an Int else.
decimal :: String -> Value
decimal t
    | any (`elem` ".eE") t = Float (applySign (toDouble mantissaDigits (exponent' - fractionN)))
    | otherwise            = Int (signValue * read (dropSign t))
  where
    negativeF  = take 1 t == "-"
    signValue  = if negativeF then -1 else 1
    applySign x = if negativeF then negate x else x
    dropSign s = case s of { (c : cs) | c `elem` "+-" -> cs; _ -> s }
    unsigned   = dropSign t
    (mantissaText, exponentText) = break (`elem` "eE") unsigned
    (whole, fraction) = case break (== '.') mantissaText of
        (w, '.' : f) -> (w, f)
        (w, _)       -> (w, "")
    fractionN      = length fraction
    mantissaDigits = read ('0' : whole ++ fraction) :: Integer
    exponent'      = case exponentText of
        (_ : '-' : ds) -> negate (read ds)
        (_ : '+' : ds) -> read ds
        (_ : ds)       -> read ds
        _              -> 0
    --  BOUNDED: past 10^400 every double is infinity, below 10^-400 zero --
    --  an exponent typed long is no reason to compute a huge power.
    toDouble :: Integer -> Int -> Double
    toDouble 0 _ = 0
    toDouble m e
        | e + digitN > 400    = 1 / 0
        | e + digitN < -400   = 0
        | e >= 0              = fromRational (fromInteger (m * 10 ^ e))
        | otherwise           = fromRational (m % (10 ^ negate e))
      where digitN = length (show m)

-- | RETURN: Maybe Integer, the number the strict roman numeral spells
--           (1 to 3999: 'IIII' and 'VX' spell none); Nothing else.
roman :: String -> Maybe Integer
roman t = Map.lookup t romanDb

-- | Every strict roman numeral, by its text -- what Python's '_ROMAN_RE'
--   accepts, except the empty one.
romanDb :: Map.Map String Integer
romanDb = Map.fromList [ (spell n, n) | n <- [1 .. 3999] ]
  where
    spell n = concat [ replicate (fromIntegral (n `div` 1000)) 'M'
                     , digit 'C' 'D' 'M' ((n `div` 100) `mod` 10)
                     , digit 'X' 'L' 'C' ((n `div` 10) `mod` 10)
                     , digit 'I' 'V' 'X' (n `mod` 10) ]
    digit one five ten d = case d of
        4 -> [one, five]
        9 -> [one, ten]
        _ -> (if d >= 5 then [five] else []) ++ replicate (fromIntegral (d `mod` 5)) one

-- | RETURN: String, the text laid out as Python 3.13's 'inspect.cleandoc':
--           tabs expanded, the blank indentation common to the lines after
--           the first removed, the first line's leading blanks removed, empty
--           lines at both ends dropped.
cleandoc :: String -> String
cleandoc doc = joinWith (trimEnds (firstLine : map (drop margin) rest))
  where
    allLines        = splitLines (expandTabs doc)
    (firstRaw, rest) = case allLines of
        (f : r) -> (f, r)
        []      -> ("", [])
    firstLine = dropWhile (== ' ') firstRaw
    indents   = [ length l - length content | l <- rest, let content = dropWhile (== ' ') l, not (null content) ]
    margin    = if null indents then 0 else minimum indents
    trimEnds  = dropWhile null . reverse . dropWhile null . reverse
    joinWith []       = ""
    joinWith (x : xs) = x ++ concatMap ('\n' :) xs
    splitLines s = case break (== '\n') s of
        (a, [])      -> [a]
        (a, _ : b)   -> a : splitLines b
    expandTabs = go 0
      where go _ [] = []
            go col (c : cs)
                | c == '\t'              = let k = 8 - col `mod` 8 in replicate k ' ' ++ go (col + k) cs
                | c == '\n' || c == '\r' = c : go 0 cs
                | otherwise              = c : go (col + 1) cs
