{-# LANGUAGE CApiFFI #-}
-- SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
-- _____________________________________________________________________________
--
-- A TERMINAL FILE VIEWER -- the program 'screen.hs' tests; no test itself.
--
--     viewer.exe <file>
--
-- Full screen, on the terminal's alternate screen: a title bar (reverse
-- video), as many lines of the file as fit, and a status line: the keys
-- flush left, the lines shown flush right. Keys: 'j' or down one line
-- further, 'k' or up one line back, 'q' quits.
--
-- The terminal's size is asked of the terminal ('ioctl TIOCGWINSZ', by the
-- FFI's 'capi': the 'unix' package does not ask it); raw mode is what
-- Python's 'tty.setraw' sets, by 'System.Posix.Terminal'.
-- _____________________________________________________________________________
module Main (main) where

import Control.Exception     (finally)
import Foreign
import Foreign.C
import System.Environment    (getArgs)
import System.FilePath       (takeFileName)
import System.IO
import System.Posix.IO       (fdRead, stdInput, stdOutput)
import System.Posix.Terminal
import System.Posix.Types    (Fd (..))
import Text.Printf           (printf)

foreign import capi "sys/ioctl.h ioctl"              c_ioctl    :: CInt -> CULong -> Ptr () -> IO CInt
foreign import capi "sys/ioctl.h value TIOCGWINSZ"   tiocgwinsz :: CULong

-- | RETURN: IO (Int, Int), the terminal's (columns, rows) on 'fd' -- of
--           'struct winsize': ws_row, then ws_col, unsigned shorts.
terminalSize :: Fd -> IO (Int, Int)
terminalSize (Fd fd) = allocaBytes 8 $ \p -> do
    status <- c_ioctl fd tiocgwinsz p
    if status /= 0 then return (80, 24) else do
        rows    <- peekByteOff p 0 :: IO Word16
        columns <- peekByteOff p 2 :: IO Word16
        return (fromIntegral columns, fromIntegral rows)

-- | RETURN: String, 'text' cut or padded with blanks to 'n' characters.
fitted :: Int -> String -> String
fitted n text = take n (text ++ repeat ' ')

-- | RETURN: IO (); the whole screen drawn, the file's line 'top' first.
draw :: String -> [String] -> Int -> Int -> Int -> IO ()
draw name lineList top rowN columnN = do
    let bodyN = rowN - 2
        shown = take bodyN (drop top lineList)
        place = printf "lines %d-%d of %d" (top + 1) (top + length shown) (length lineList) :: String
        keys  = "j k q"
        width = columnN - 1 - length keys
    putStr "\ESC[H\ESC[2J"
    putStr ("\ESC[7m" ++ fitted columnN (' ' : name) ++ "\ESC[0m\r\n")
    mapM_ (\l -> putStr (take columnN l ++ "\r\n")) shown
    putStr (concat (replicate (bodyN - length shown) "\r\n"))
    printf "\ESC[%d;1H%s%s" rowN keys (replicate (width - length place) ' ' ++ place)
    hFlush stdout

-- | RETURN: IO (), once 'q' was pressed: the file 'path' shown and scrolled
--           by the keys read from the raw terminal.
view :: FilePath -> IO ()
view path = do
    lineList <- lines <$> readFile path
    (columnN, rowN) <- terminalSize stdOutput
    saved <- getTerminalAttributes stdInput
    let raw = foldl withoutMode saved
                  [ InterruptOnBreak, MapCRtoLF, CheckParity, StripHighBit, StartStopOutput
                  , ProcessOutput, EnableParity, EnableEcho, ProcessInput, ExtendedFunctions
                  , KeyboardInterrupts ]
    setTerminalAttributes stdInput (withTime (withMinInput (withBits raw 8) 1) 0) Immediately
    putStr "\ESC[?1049h"
    let loop top = do
            draw (takeFileName path) lineList top rowN columnN
            (key, _) <- fdRead stdInput 8
            case key of
                "q" -> return ()
                _ | key `elem` ["j", "\ESC[B"] -> loop (min (top + 1) (max 0 (length lineList - (rowN - 2))))
                  | key `elem` ["k", "\ESC[A"] -> loop (max (top - 1) 0)
                  | otherwise                  -> loop top
    loop 0 `finally` do
        putStr "\ESC[?1049l"
        hFlush stdout
        setTerminalAttributes stdInput saved WhenDrained

-- | RETURN: IO (); the file the command line names viewed.
main :: IO ()
main = do
    hSetBuffering stdout (BlockBuffering Nothing)
    [path] <- getArgs
    view path
