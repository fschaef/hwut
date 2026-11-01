-- SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
-- _____________________________________________________________________________
--
-- PURPOSE: TEXT AS PYTHON PRINTS IT -- so a Haskell test and a Python test of
--          the same module print the same bytes and share one GOOD file by a
--          '.link' (bookkeeper B-32). The twin of 'c/hwut_pytext.c'.
--
--     pyRepr (0.1 :: Double)          "0.1"      the shortest text that reads
--     pyRepr (1e-5 :: Double)         "1e-05"    back; exponential below 1e-4
--     pyRepr "it's"                   "\"it's\"" Python's choice of quotes
--     pyRepr (Bytes "\x1b[A")         "b'\\x1b[A'"
--     pyRepr True                     "True"
--     pyRepr (Nothing :: Maybe Int)   "None"
--     pyRepr [1, 2 :: Int]            "[1, 2]"
--     pyRepr ("a", 1 :: Int)          "('a', 1)"
--
-- A CLASS, AS 'Show' IS ONE -- and with Show's trick for strings: 'pyReprList'
-- is a method, so '[Char]' prints as a str literal while every other list
-- prints as a list, without overlapping instances.
-- _____________________________________________________________________________
module Hwut.PyText
    ( PyRepr (..)
    , Bytes (..)
    , PyTuple (..)
    , floatRepr
    , strRepr
    , bytesRepr
    , pyBool
    ) where

import qualified Data.ByteString as B
import           Data.Char       (isPrint, ord)
import           Data.List       (intercalate)
import           Numeric         (showHex)

-- | A byte string printed as Python prints 'bytes'.
newtype Bytes = Bytes B.ByteString

-- | A list printed as Python prints a tuple: '()', '(x,)', '(x, y)'.
newtype PyTuple a = PyTuple [a]

class PyRepr a where
    -- | RETURN: String, the value as Python's 'repr' writes it.
    pyRepr :: a -> String

    -- | RETURN: String, a list of such values as Python's 'repr' writes a
    --           list -- '[x, y]'; for Char a str literal (Show's trick).
    pyReprList :: [a] -> String
    pyReprList xs = "[" ++ intercalate ", " (map pyRepr xs) ++ "]"

instance PyRepr Char where
    pyRepr c       = strRepr [c]
    pyReprList     = strRepr

instance PyRepr a => PyRepr [a] where
    pyRepr = pyReprList

instance PyRepr Bool where
    pyRepr = pyBool

instance PyRepr Int where
    pyRepr = show

instance PyRepr Integer where
    pyRepr = show

instance PyRepr Double where
    pyRepr = floatRepr

instance PyRepr Bytes where
    pyRepr (Bytes b) = bytesRepr b

instance PyRepr a => PyRepr (Maybe a) where
    pyRepr Nothing  = "None"
    pyRepr (Just x) = pyRepr x

instance PyRepr a => PyRepr (PyTuple a) where
    pyRepr (PyTuple [x]) = "(" ++ pyRepr x ++ ",)"
    pyRepr (PyTuple xs)  = "(" ++ intercalate ", " (map pyRepr xs) ++ ")"

instance (PyRepr a, PyRepr b) => PyRepr (a, b) where
    pyRepr (a, b) = "(" ++ pyRepr a ++ ", " ++ pyRepr b ++ ")"

instance (PyRepr a, PyRepr b, PyRepr c) => PyRepr (a, b, c) where
    pyRepr (a, b, c) = "(" ++ pyRepr a ++ ", " ++ pyRepr b ++ ", " ++ pyRepr c ++ ")"

-- | RETURN: String, "True" for True, "False" else.
pyBool :: Bool -> String
pyBool True  = "True"
pyBool False = "False"

-- | RETURN: String, 'x' as Python's 'repr(float)' writes it -- the shortest
--           correctly rounded decimal that reads back to the same double
--           ('shortestDigits'), fixed notation where the decimal point falls
--           in (-4, 16], exponential '1e-05' / '1e+16' else.
floatRepr :: Double -> String
floatRepr x
    | isNaN x                   = "nan"
    | isInfinite x              = if x < 0 then "-inf" else "inf"
    | x == 0                    = if isNegativeZero x then "-0.0" else "0.0"
    | point > -4 && point <= 16 = sign ++ fixed
    | otherwise                 = sign ++ scientific
  where
    sign            = if x < 0 then "-" else ""
    (text, point)   = shortestDigits (abs x)    -- value = 0.<text> * 10^point
    n               = length text
    fixed
        | point <= 0 = "0." ++ replicate (negate point) '0' ++ text
        | point >= n = text ++ replicate (point - n) '0' ++ ".0"
        | otherwise  = take point text ++ "." ++ drop point text
    e               = point - 1
    scientific      = take 1 text ++ (if n > 1 then "." ++ drop 1 text else "")
                      ++ "e" ++ (if e < 0 then "-" else "+") ++ pad2 (show (abs e))
    pad2 s          = if length s < 2 then '0' : s else s

-- | RETURN: (String, Int), the fewest decimal digits 'd' -- and the point
--           'p', the value being 0.d * 10^p -- such that 'd' is 'x' rounded
--           correctly (half to even) to that many digits and reads back as
--           'x'; 'x' is finite and above 0.
--
-- NOT 'floatToDigits': MEASURED against Python's 'repr' on 300000 doubles,
-- 140 differ -- it is shortest, but not always the CORRECTLY ROUNDED one of
-- that length ('245010723912258.13' where Python says '.12'). This is what
-- 'c/hwut_pytext.c' does with '%.*e' and 'strtod': exact, in Rational.
shortestDigits :: Double -> (String, Int)
shortestDigits x = head [ found | p <- [1 .. 17], Just found <- [attempt p] ]
  where
    r   = toRational x
    e10 = exponentOf r
    attempt :: Int -> Maybe (String, Int)
    attempt p =
        let shift      = e10 - p + 1
            m0         = round (r / power shift) :: Integer
            (m, e')    = if m0 >= 10 ^ p then (m0 `div` 10, e10 + 1) else (m0, e10)
            shift'     = e' - p + 1
            candidate  = fromRational (fromInteger m * power shift') :: Double
            text       = dropTrailingZeros (show m)
        in if candidate == x then Just (text, e' + 1) else Nothing
    power k             = if k >= 0 then fromInteger (10 ^ k) else 1 / fromInteger (10 ^ negate k)
    dropTrailingZeros t = case reverse (dropWhile (== '0') (reverse t)) of
                              "" -> "0"
                              u  -> u
    exponentOf q = adjust (floor (logBase 10 (fromRational q :: Double)) :: Int)
      where adjust k | power k > q        = adjust (k - 1)
                     | power (k + 1) <= q = adjust (k + 1)
                     | otherwise          = k

-- | RETURN: Char, the quote Python's repr chooses for a text holding these
--           characters: '"' where it holds a single quote and no double
--           one, '\'' else.
quoteOf :: String -> Char
quoteOf s = if '\'' `elem` s && '"' `notElem` s then '"' else '\''

-- | RETURN: String, the text as Python's 'repr(str)' writes it: the quote
--           it chooses, the backslash, that quote, '\n' '\t' '\r' escaped,
--           what does not print as '\xhh', '\uhhhh' or '\Uhhhhhhhh'.
strRepr :: String -> String
strRepr s = [q] ++ concatMap escape s ++ [q]
  where
    q = quoteOf s
    escape c
        | c == '\\'                = "\\\\"
        | c == q                   = ['\\', q]
        | c == '\n'                = "\\n"
        | c == '\t'                = "\\t"
        | c == '\r'                = "\\r"
        | ord c < 0x20 || c == '\DEL' = hexEscape 'x' 2 (ord c)
        | ord c < 0x7f             = [c]
        | isPrint c                = [c]
        | ord c < 0x100            = hexEscape 'x' 2 (ord c)
        | ord c < 0x10000          = hexEscape 'u' 4 (ord c)
        | otherwise                = hexEscape 'U' 8 (ord c)

-- | RETURN: String, the bytes as Python's 'repr(bytes)' writes them: 'b',
--           the quote it chooses, every byte below 0x20 and from 0x7f on
--           escaped as '\xhh' (but '\n', '\t', '\r').
bytesRepr :: B.ByteString -> String
bytesRepr b = "b" ++ [q] ++ concatMap escape s ++ [q]
  where
    s = map (toEnum . fromIntegral) (B.unpack b) :: String
    q = quoteOf s
    escape c
        | c == '\\'                    = "\\\\"
        | c == q                       = ['\\', q]
        | c == '\n'                    = "\\n"
        | c == '\t'                    = "\\t"
        | c == '\r'                    = "\\r"
        | ord c < 0x20 || ord c >= 0x7f = hexEscape 'x' 2 (ord c)
        | otherwise                    = [c]

-- | RETURN: String, '\<letter>' and 'n' as 'width' lower-case hex digits.
hexEscape :: Char -> Int -> Int -> String
hexEscape letter width n = '\\' : letter : replicate (width - length h) '0' ++ h
  where h = showHex n ""
