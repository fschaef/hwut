-- @hwut {
--     title      = "A terminal's screen read by a test: libvterm through the FFI."
--     build      { framework = "make", target = "%.exe" }
--     choices {
--         attributes { features = ["haskell-vterm"] }
--         colours    { features = ["haskell-vterm"] }
--         events     { features = ["haskell-vterm"] }
--         keys       { features = ["haskell-vterm"] }
--         missing    { features = ["haskell-vterm"] }
--         regions    { features = ["haskell-vterm"] }
--         screen     { features = ["haskell-vterm"] }
--         text       { features = ["haskell-vterm"] }
--         unnoticed  { features = ["haskell-vterm"] }
--     }
--     interactive = true
-- }
--
-- SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
-- _____________________________________________________________________________
--
-- PURPOSE: The Haskell port of 'python/TEST/test-hwut_vterm.py', choice for
--          choice, held against its GOOD files by '.link'. WANTS libvterm --
--          found at run time. The two APPLICATIONS a Terminal runs here are
--          the Python test's, unchanged, run by 'python3': they are the
--          system under test, and what they print is in the shared GOOD
--          files.
-- _____________________________________________________________________________
module Main (main) where

import           Control.Exception  (catch, throwIO)
import           Control.Monad      (forM_, unless, void)
import           Data.IORef
import           Data.List          (isInfixOf)
import           System.Environment (setEnv)
import           Text.Printf        (printf)

import           Hwut.PyText
import           Hwut.Runner
import           Hwut.Vterm

-- | RETURN: IO (); every row that holds something, framed, then the cursor.
shown :: ScreenLike s => s -> IO ()
shown screen = do
    rows <- lineList screen
    forM_ (zip [0 :: Int ..] rows) $ \(r, l) -> unless (null l) (printf "    %d |%s|\n" r l)
    (r, c) <- cursor screen
    printf "    cursor (%d, %d)\n" r c

-- | RETURN: IO (), 'action' run on a library that is there; one line where
--           it is not.
probe :: IO () -> IO ()
probe action = action `catch` \problem -> case problem of
    LibraryMissing m -> putStrLn ("NOT PROBED: " ++ m)
    other            -> throwIO other

-- | RETURN: String, 's' filled with blanks to 'n' characters, as '%-<n>s'.
padded :: Int -> String -> String
padded n s = s ++ replicate (n - length s) ' '

-- | RETURN: IO (); the text fed as UTF-8, the count of bytes dropped.
feedS :: ScreenLike s => s -> String -> IO ()
feedS s = void . feedText s

-- | The escape character.
esc :: String
esc = "\ESC"

-- ------------------------------------------------------------------ Screen

-- | RETURN: IO (); plain bytes, UTF-8, a wide character, a wrapped line.
runText :: IO ()
runText = do
    withScreen 4 12 $ \s -> do
        putStrLn "-- plain, then carriage return and line feed"
        feedS s "hello\r\nworld"
        shown s
    withScreen 4 12 $ \s -> do
        putStrLn "-- UTF-8: two bytes, one cell; a wide character, two"
        feedS s "ä日x"
        shown s
        forM_ [0 .. 3] $ \c -> do
            x <- cell s 0 c
            printf "    column %d: %s width %d\n" c (padded 6 (pyRepr (cellText x))) (width x)
    withScreen 3 5 $ \s -> do
        putStrLn "-- seven characters on five columns: the line wraps"
        feedS s "abcdefg"
        shown s
    withScreen 2 4 $ \s -> do
        putStrLn "-- a str is sent as UTF-8; the bytes taken are counted"
        feedText s "aä" >>= printf "    taken: %d\n"
        putStrLn "-- a place off the screen"
        void (cell s 2 0) `catch` \problem -> case problem of
            IndexError m -> putStrLn ("    IndexError: " ++ m)
            other        -> throwIO other

-- | RETURN: IO (); the sequences a full-screen program writes, and the screen after.
runScreen :: IO ()
runScreen = withScreen 5 20 $ \s -> do
    putStrLn "-- three lines, then '<esc>[2;4H' (it counts from 1) and 'X'"
    feedS s "first line\r\nsecond line\r\nthird line"
    feedS s (esc ++ "[2;4H" ++ "X")
    shown s
    putStrLn "-- erase to the end of that line"
    feedS s (esc ++ "[K")
    shown s
    putStrLn "-- clear the screen, home, one word"
    feedS s (esc ++ "[2J" ++ esc ++ "[H" ++ "clean")
    shown s

-- | RETURN: IO (); each attribute by its SGR code, then all at once, then reset.
runAttributes :: IO ()
runAttributes = withScreen 3 20 $ \s -> do
    forM_ (zip attributeNames attributeSgr) $ \(n, code) ->
        feedS s (esc ++ "[" ++ code ++ "m" ++ take 1 n ++ esc ++ "[0m")
    putStrLn "-- one cell per attribute, set by its own code"
    forM_ (zip [0 ..] attributeNames) $ \(c, n) -> do
        x <- cell s 0 c
        --  'conceal' IS NOT KNOWN TO EVERY LIBRARY: said, not pinned.
        let said | n == "conceal"          = "conceal, or (none) on libvterm 0.1"
                 | null (attributeText x)  = "(none)"
                 | otherwise               = attributeText x
        putStrLn ("    " ++ pyRepr (cellText x) ++ "  " ++ said)
    putStrLn "-- bold, underline and reverse at once; then reset"
    feedS s ("\r\n" ++ esc ++ "[1;4;7mA" ++ esc ++ "[0mB")
    forM_ [0, 1] $ \c -> do
        x <- cell s 1 c
        putStrLn ("    " ++ pyRepr (cellText x) ++ "  " ++ (if null (attributeText x) then "(none)" else attributeText x))
    putStrLn "-- double underline (SGR 21) is underlined"
    feedS s (esc ++ "[21mD")
    x <- cell s 1 2
    putStrLn ("    " ++ pyRepr "D" ++ "  " ++ attributeText x)

-- | RETURN: IO (); the default, an indexed, a palette and a direct colour.
runColours :: IO ()
runColours = withScreen 2 20 $ \s -> do
    feedS s ("d" ++ esc ++ "[31mr" ++ esc ++ "[0m" ++ esc ++ "[38;5;196mp" ++ esc ++ "[0m"
             ++ esc ++ "[38;2;10;20;30mt" ++ esc ++ "[0m")
    feedS s (esc ++ "[48;2;1;2;3mb" ++ esc ++ "[0m")
    forM_ (zip [0 ..] ["default", "indexed 31", "palette 196", "direct 10;20;30", "background 1;2;3"]) $ \(c, what) -> do
        x <- cell s 0 c
        --  THE EIGHT NAMED COLOURS ARE THE LIBRARY'S OWN PALETTE: that one
        --  is a colour and mostly red is the claim, not its shade.
        let said = case (what, foreground x) of
                ("indexed 31", Just (r, g, b)) -> "fg mostly red: " ++ pyBool (r > 2 * max g b)
                _ -> "fg " ++ pyRepr (fmap rgb (foreground x)) ++ "  bg " ++ pyRepr (fmap rgb (background x))
            rgb (r, g, b) = PyTuple [r, g, b]
        printf "    %-18s %s  %s\n" what (pyRepr (cellText x)) said

-- | THE APPLICATION UNDER OBSERVATION: it says what it sees, asks the
--   terminal where the cursor is, then names every key until 'q'.
seeingApp :: String
seeingApp = unlines
    [ ""
    , "import os, sys, tty, termios"
    , "print(\"streams are terminals: %s %s %s\""
    , "      % (sys.stdin.isatty(), sys.stdout.isatty(), sys.stderr.isatty()))"
    , "try:    os.close(os.open(\"/dev/tty\", os.O_RDWR)); print(\"controlling terminal: yes\")"
    , "except OSError: print(\"controlling terminal: no\")"
    , "print(\"size: %d columns, %d rows\" % tuple(os.get_terminal_size()))"
    , "print(\"TERM=%s COLUMNS=%s\" % (os.environ.get(\"TERM\"), os.environ.get(\"COLUMNS\")))"
    , "old = termios.tcgetattr(0); tty.setraw(0)"
    , "sys.stdout.write(\"\\x1b[6;9H\\x1b[6n\"); sys.stdout.flush()"
    , "reply = b\"\""
    , "while not reply.endswith(b\"R\"): reply += os.read(0, 1)"
    , "sys.stdout.write(\"\\r\\x1b[7;1Hthe terminal answered: %r\" % reply); sys.stdout.flush()"
    , "while True:"
    , "    key = os.read(0, 32)"
    , "    sys.stdout.write(\"\\x1b[9;1H\\x1b[Kread: %r\" % key); sys.stdout.flush()"
    , "    if key == b\"q\": break"
    , "termios.tcsetattr(0, termios.TCSADRAIN, old)"
    , "print(\"\\r\\nleaving\"); sys.exit(3)"
    ]

-- | AN APPLICATION WITH A HEAD, A BODY AND A FOOT: 'n' counts in the body,
--   'f' rewrites the foot, 'r' redraws everything unchanged, 'q' leaves.
drawingApp :: String
drawingApp = unlines
    [ ""
    , "import os, sys, tty, termios"
    , "old = termios.tcgetattr(0); tty.setraw(0)"
    , "count, foot = 0, \"q=quit\""
    , "def draw():"
    , "    out = \"\\x1b[2J\\x1b[1;1H\\x1b[7m the head \\x1b[0m\""
    , "    out += \"\\x1b[3;1Hcount: %d\\x1b[4;1H(press n)\" % count"
    , "    out += \"\\x1b[8;1H%s\" % foot"
    , "    sys.stdout.write(out); sys.stdout.flush()"
    , "draw()"
    , "while True:"
    , "    key = os.read(0, 1)"
    , "    if   key == b\"n\": count += 1"
    , "    elif key == b\"f\": foot = \"q=quit  f=pressed\""
    , "    elif key == b\"q\": break"
    , "    draw()"
    , "termios.tcsetattr(0, termios.TCSADRAIN, old)"
    ]

-- --------------------------------------------------------------- Terminal

-- | RETURN: IO (); what the application sees of its terminal, and its status.
runUnnoticed :: IO ()
runUnnoticed = do
    setEnv "COLUMNS" "300"
    withTerminal 10 44 0.1 $ \t -> do
        running <- run t ["python3", "-c", seeingApp] Nothing 10.0
        putStrLn ("-- still running after its first screen: " ++ pyBool running)
        shown t
        void (send t "q" 1.0)
        status <- wait t 10.0
        putStrLn ("-- after 'q': exit status " ++ maybe "None" show status)
        shown t

-- | RETURN: IO (); what the application READS for each key pressed.
runKeys :: IO ()
runKeys = withTerminal 10 44 0.1 $ \t -> do
    pressed <- newIORef "(start)"
    region t "read" 8 1 0 Nothing
    onChange t $ \_ ls -> do
        said <- readIORef pressed
        putStrLn ("    " ++ padded 22 said ++ " " ++ head ls)
    void (run t ["python3", "-c", seeingApp] Nothing 10.0)
    forM_ [ ("up", []), ("enter", []), ("tab", []), ("escape", []), ("f5", []), ("delete", [])
          , ("c", ["ctrl"]), ("x", ["alt"]), ("up", ["shift"]) ] $ \(key, modifiers) -> do
        writeIORef pressed (unwords (modifiers ++ [key]))
        void (press t key modifiers 1.0)
    writeIORef pressed "send 'ä'"
    void (send t "ä" 1.0)
    writeIORef pressed "send 'q'"
    void (send t "q" 1.0)
    void (wait t 10.0)

-- | RETURN: IO (); three regions, each told once per pause, only where changed.
runRegions :: IO ()
runRegions =
    --  A LONGER PAUSE THAN THE DEFAULT: three redraws typed at once must be
    --  ONE report on a loaded machine too.
    withTerminal 8 30 0.3 $ \t -> do
        region t "head" 0 1 0 Nothing
        region t "body" 2 2 0 Nothing
        region t "foot" (-1) 1 0 Nothing
        onChange t $ \n ls -> printf "    changed  %-5s %s\n" n (pyRepr ls)
        forM_ [ ("run", void (run t ["python3", "-c", drawingApp] Nothing 10.0))
              , ("'n'", void (send t "n" 1.0)), ("'n'", void (send t "n" 1.0))
              , ("'r': a redraw, nothing new", void (send t "r" 1.0))
              , ("'f'", void (send t "f" 1.0))
              , ("'nnn', typed at once", void (send t "nnn" 1.0))
              , ("'q'", void (send t "q" 1.0)) ] $ \(said, act) -> do
            putStrLn ("-- " ++ said)
            act
        status <- wait t 10.0
        body   <- regionText t "body"
        putStrLn ("-- exit status " ++ maybe "None" show status ++ "; a region asked by name: " ++ pyRepr body)
        void (regionText t "nosuch") `catch` \problem -> case problem of
            KeyError m -> putStrLn ("-- no such region: KeyError " ++ m)
            other      -> throwIO other

-- | RETURN: IO (); the RAW layer on bytes the test feeds, and the terminal's answers.
runEvents :: IO ()
runEvents = withTerminal 4 20 0.1 $ \t -> do
    onEvent t (\e -> putStrLn ("    " ++ show e))
    forM_ [ ("'ab'", "ab"), ("a line feed and 'c'", "\r\nc")
          , ("the cursor to row 4, hidden", esc ++ "[4;1H" ++ esc ++ "[?25l")
          , ("the alternate screen", esc ++ "[?1049h"), ("the bell", "\a")
          , ("nothing that draws: a reset of attributes", esc ++ "[0m") ] $ \(said, d) -> do
        putStrLn ("-- fed: " ++ said)
        feedS t d
    putStrLn "-- asked where the cursor is, nobody running: the answer waits"
    feedS t (esc ++ "[2;5H" ++ esc ++ "[6n")
    answer t >>= \a -> putStrLn ("    answer() = " ++ pyRepr (Bytes a))
    putStrLn "-- a key pressed with nobody running"
    void (press t "f1" [] 0)
    answer t >>= \a -> putStrLn ("    answer() = " ++ pyRepr (Bytes a))

-- | RETURN: IO (); 'LibraryMissing' by name, with the hint how to install.
runMissing :: IO ()
runMissing = do
    setEnv libraryVariable "/nowhere/libvterm.so"
    resetLibrary
    (newScreen 24 80 >>= closeScreen >> putStrLn "a Screen stands on a library that is not there")
        `catch` \problem -> case problem of
            --  THE SYSTEM'S OWN WORDS for the failed load are left out; what
            --  this module says -- the line, and the way to install -- stands.
            LibraryMissing m -> case lines m of
                (first : rest) -> do
                    putStrLn ("LibraryMissing: " ++ beforeWords first)
                    mapM_ putStrLn rest
                []             -> putStrLn "LibraryMissing:"
            other -> throwIO other
  where
    beforeWords s
        | " -- " `isInfixOf` s = go s
        | otherwise            = s
      where go t@(c : cs) = if take 4 t == " -- " then "" else c : go cs
            go []         = ""

-- | RETURN: IO (); the mode the command line selects has run.
main :: IO ()
main = hwutRunner "A terminal's screen read by a test: libvterm through the FFI."
    [ ("text",       probe runText)
    , ("screen",     probe runScreen)
    , ("attributes", probe runAttributes)
    , ("colours",    probe runColours)
    , ("unnoticed",  probe runUnnoticed)
    , ("keys",       probe runKeys)
    , ("regions",    probe runRegions)
    , ("events",     probe runEvents)
    , ("missing",    runMissing)
    ]
