-- SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
-- _____________________________________________________________________________
--
-- PURPOSE: A TERMINAL'S SCREEN, READ BY A TEST -- the port of
--          'python/hwut_vterm.py' (see '../python/README-hwut_vterm.txt').
--
--     import Hwut.Vterm
--
--     withScreen 24 80 $ \screen -> do
--         _ <- feedText screen "\ESC[1mbold\ESC[0m plain"
--         line screen 0   >>= putStrLn             -- 'bold plain'
--         cell screen 0 0 >>= print . boldF        -- True
--         cursor screen   >>= print                -- (0,10)
--
-- A BINDING, NOT A SECOND IMPLEMENTATION. Haskell's FFI cannot pass a C
-- structure BY VALUE, and libvterm takes 'VTermPos' and hands 'VTermRect' by
-- value -- so this module does not call libvterm itself: it calls the C port
-- ('../c/hwut_vterm.c', compiled with the test), which loads libvterm by
-- 'dlopen', MEASURES its cell's layout, runs the application on a
-- pseudo-terminal, and calls back. 'foreign import ccall' binds its
-- functions; its structures are read by 'hsc2hs' offsets ('#peek'), so no
-- layout is copied by hand. Callbacks ('onEvent', 'onChange') are Haskell
-- closures made C functions by a "wrapper" import, freed with the terminal.
--
-- WHAT IS HASKELL'S: the values -- 'Cell', 'Event' and its text -- the
-- exceptions ('VtermError', one constructor per Python exception), the
-- bracket ('withScreen', Python's 'with'), and the class 'ScreenLike':
-- Python's 'Terminal(Screen)' is an instance, whose 'feed' also forwards.
-- _____________________________________________________________________________
{-# LANGUAGE ForeignFunctionInterface #-}
module Hwut.Vterm
    ( VtermError (..)
    , Cell (..)
    , attributeText
    , attributeNames
    , attributeSgr
    , Event (..)
    , ScreenLike (..)
    , Screen
    , newScreen
    , closeScreen
    , withScreen
    , feedText
    , cursor
    , cell
    , line
    , lineList
    , Terminal
    , newTerminal
    , closeTerminal
    , withTerminal
    , onEvent
    , onChange
    , region
    , regionText
    , report
    , answer
    , send
    , press
    , run
    , pump
    , expect
    , wait
    , detectionText
    , resetLibrary
    , libraryVariable
    ) where

#include "hwut_vterm.h"

import           Control.Exception      (Exception, bracket, throwIO)
import           Control.Monad          (forM, when)
import qualified Data.ByteString        as B
import qualified Data.ByteString.Unsafe as BU
import           Data.IORef
import           Foreign
import           Foreign.C.String       (CString)
import           Foreign.C.Types
import qualified GHC.Foreign            as GF
import           GHC.IO.Encoding        (utf8)

-- ------------------------------------------------------------------ values

-- | What Python raises, by its name; the text is Python's 'str(error)'.
data VtermError = LibraryMissing String | IndexError String | KeyError String
                | TimeoutError String | RuntimeError String | OSError String

instance Show VtermError where
    show e = case e of
        LibraryMissing m -> m
        IndexError m     -> m
        KeyError m       -> m
        TimeoutError m   -> m
        RuntimeError m   -> m
        OSError m        -> m

instance Exception VtermError

-- | ONE CELL OF THE SCREEN, as plain values. 'cellText' is '' for a cell
--   nothing was written to, and for the right half of a wide character;
--   a colour is Nothing where the cell wears the terminal's default.
data Cell = Cell
    { cellText    :: String
    , width       :: Int
    , boldF, italicF, underlineF, blinkF, reverseF, concealF, strikeF :: Bool
    , foreground  :: Maybe (Int, Int, Int)
    , background  :: Maybe (Int, Int, Int)
    }

-- | The attributes, in their fixed order, and the SGR code of each.
attributeNames, attributeSgr :: [String]
attributeNames = ["bold", "italic", "underline", "blink", "reverse", "conceal", "strike"]
attributeSgr   = ["1", "3", "4", "5", "7", "8", "9"]

-- | RETURN: String, the attributes set, by name in the fixed order,
--           separated by blanks -- 'bold reverse'; '' where none is.
attributeText :: Cell -> String
attributeText c = unwords [ n | (n, f) <- zip attributeNames flags, f ]
  where flags = [boldF c, italicF c, underlineF c, blinkF c, reverseF c, concealF c, strikeF c]

-- | ONE THING THE TERMINAL DID, as libvterm reports it (the RAW layer).
--   'Show' is Python's 'str(event)'.
data Event = Damage   { row, column, rowEnd, columnEnd :: Int }
           | Cursor   { row, column :: Int, visibleF :: Bool }
           | Property { name :: String, propertyValue :: Maybe Int }
           | Bell

instance Show Event where
    show (Damage r c re ce) = "damage    rows " ++ show r ++ ".." ++ show re ++ "  columns "
                              ++ show c ++ ".." ++ show ce
    show (Cursor r c v)     = "cursor    (" ++ show r ++ ", " ++ show c ++ ")" ++ (if v then "" else "  hidden")
    show (Property n v)     = "property  " ++ n ++ " = " ++ maybe "None" show v
    show Bell               = "bell"

-- | The environment variable that names the library's file.
libraryVariable :: String
libraryVariable = #{const_str VTERM_LIBRARY_VARIABLE}

-- ------------------------------------------------------------ the C port

data CScreen
data CTerminal
data CError
data CCell
data CEvent

type EventF  = Ptr () -> Ptr CEvent -> IO ()
type ChangeF = Ptr () -> CString -> Ptr CString -> CSize -> IO ()

foreign import ccall "VtermScreen_new"        c_screen_new      :: CInt -> CInt -> Ptr CError -> IO (Ptr CScreen)
foreign import ccall "VtermScreen_free"       c_screen_free     :: Ptr CScreen -> IO ()
foreign import ccall "VtermScreen_feed"       c_screen_feed     :: Ptr CScreen -> Ptr CChar -> CSize -> IO CSize
foreign import ccall "VtermScreen_cursor"     c_screen_cursor   :: Ptr CScreen -> Ptr CInt -> Ptr CInt -> IO ()
foreign import ccall "VtermScreen_cell"       c_screen_cell     :: Ptr CScreen -> CInt -> CInt -> Ptr CCell -> IO CInt
foreign import ccall "VtermScreen_line"       c_screen_line     :: Ptr CScreen -> CInt -> CString -> CSize -> IO CString
foreign import ccall "Vterm_detection_text"   c_detection_text  :: CString -> CSize -> IO CString
foreign import ccall "Vterm_reset_library"    c_reset_library   :: IO ()
foreign import ccall "VtermTerminal_new"      c_terminal_new    :: CInt -> CInt -> CDouble -> Ptr CError -> IO (Ptr CTerminal)
foreign import ccall "VtermTerminal_free"     c_terminal_free   :: Ptr CTerminal -> IO ()
foreign import ccall "VtermTerminal_on_event" c_on_event        :: Ptr CTerminal -> FunPtr EventF -> Ptr () -> IO ()
foreign import ccall "VtermTerminal_on_change" c_on_change      :: Ptr CTerminal -> FunPtr ChangeF -> Ptr () -> IO ()
foreign import ccall "VtermTerminal_region"   c_region          :: Ptr CTerminal -> CString -> CInt -> CInt -> CInt -> CInt -> IO ()
foreign import ccall "VtermTerminal_region_text" c_region_text  :: Ptr CTerminal -> CString -> Ptr CSize -> IO (Ptr CString)
foreign import ccall "VtermTerminal_lines_free" c_lines_free     :: Ptr CString -> CSize -> IO ()
foreign import ccall "VtermTerminal_report"   c_report          :: Ptr CTerminal -> IO CSize
foreign import ccall "VtermTerminal_feed"     c_terminal_feed   :: Ptr CTerminal -> Ptr CChar -> CSize -> IO CSize
foreign import ccall "VtermTerminal_answer"   c_answer          :: Ptr CTerminal -> Ptr CSize -> IO (Ptr CChar)
foreign import ccall "VtermTerminal_send"     c_send            :: Ptr CTerminal -> CString -> CDouble -> IO CInt
foreign import ccall "VtermTerminal_press"    c_press           :: Ptr CTerminal -> CString -> CString -> CDouble -> IO CInt
foreign import ccall "VtermTerminal_run"      c_run             :: Ptr CTerminal -> Ptr CString -> CString -> CDouble -> IO CInt
foreign import ccall "VtermTerminal_pump"     c_pump            :: Ptr CTerminal -> CDouble -> IO CInt
foreign import ccall "VtermTerminal_expect"   c_expect          :: Ptr CTerminal -> CString -> CDouble -> Ptr CInt -> Ptr CInt -> IO CInt
foreign import ccall "VtermTerminal_wait"     c_wait            :: Ptr CTerminal -> CDouble -> Ptr CInt -> IO CInt
foreign import ccall "wrapper"                wrapEventF        :: EventF -> IO (FunPtr EventF)
foreign import ccall "wrapper"                wrapChangeF       :: ChangeF -> IO (FunPtr ChangeF)
foreign import ccall "stdlib.h free"          c_free            :: Ptr a -> IO ()

-- | RETURN: IO String, the UTF-8 text at 'p'.
peekUtf8 :: CString -> IO String
peekUtf8 = GF.peekCString utf8

-- | RETURN: IO a, 'action' given the UTF-8 C text of 's'.
withUtf8 :: String -> (CString -> IO a) -> IO a
withUtf8 = GF.withCString utf8

-- | RETURN: IO VtermError, the error the C port wrote at 'p' -- its 'kind'
--           is the Python exception's name.
peekError :: Ptr CError -> IO VtermError
peekError p = do
    k <- peekUtf8 (#{ptr VtermError, kind} p)
    m <- peekUtf8 (#{ptr VtermError, message} p)
    return $ case k of
        "LibraryMissing" -> LibraryMissing m
        "IndexError"     -> IndexError m
        "KeyError"       -> KeyError m
        "TimeoutError"   -> TimeoutError m
        "OSError"        -> OSError m
        _                -> RuntimeError m

-- | RETURN: IO VtermError, the error the screen at 'p' holds.
screenError :: Ptr CScreen -> IO VtermError
screenError p = peekError (#{ptr VtermScreen, error} p)

-- ------------------------------------------------------------------ Screen

-- | A TERMINAL OF 'row_n' ROWS AND 'column_n' COLUMNS that draws what it is
--   fed and lets its cells be read: Python's 'Screen'.
data Screen = Screen { screenRef :: IORef (Ptr CScreen), sRowN, sColumnN :: Int }

-- | What every screen does: Python's 'Screen', which 'Terminal' derives.
class ScreenLike s where
    -- | RETURN: IO (Ptr ...), the C screen; raises RuntimeError once closed.
    screenPointer :: s -> IO (Ptr CScreen)
    -- | RETURN: Int, the number of rows.
    rowN          :: s -> Int
    -- | RETURN: Int, the number of columns.
    columnN       :: s -> Int
    -- | RETURN: IO Int, the number of bytes the terminal took of what a
    --           program wrote -- all of them, where it works as documented.
    feed          :: s -> B.ByteString -> IO Int

instance ScreenLike Screen where
    screenPointer s = readIORef (screenRef s) >>= alive
    rowN            = sRowN
    columnN         = sColumnN
    feed s bytes    = do
        p <- screenPointer s
        BU.unsafeUseAsCStringLen bytes $ \(d, n) -> fromIntegral <$> c_screen_feed p d (fromIntegral n)

-- | RETURN: IO (Ptr a), 'p' where it is not null; raises RuntimeError else.
alive :: Ptr a -> IO (Ptr a)
alive p = if p == nullPtr then throwIO (RuntimeError "the terminal is closed") else return p

-- | RETURN: IO Screen, blank, the cursor at (0, 0); raises LibraryMissing
--           where libvterm is not found.
newScreen :: Int -> Int -> IO Screen
newScreen rows columns = allocaBytes #{size VtermError} $ \e -> do
    p <- c_screen_new (fromIntegral rows) (fromIntegral columns) e
    when (p == nullPtr) (peekError e >>= throwIO)
    ref <- newIORef p
    return (Screen ref rows columns)

-- | RETURN: IO (); the terminal's memory freed; a second call does nothing.
closeScreen :: Screen -> IO ()
closeScreen s = do
    p <- readIORef (screenRef s)
    when (p /= nullPtr) (c_screen_free p >> writeIORef (screenRef s) nullPtr)

-- | RETURN: IO a, what 'action' returns on a new screen, closed after it --
--           whatever way it is left (Python's 'with Screen(...)').
withScreen :: Int -> Int -> (Screen -> IO a) -> IO a
withScreen rows columns = bracket (newScreen rows columns) closeScreen

-- | RETURN: IO Int, 'feed' of the text sent as UTF-8.
feedText :: ScreenLike s => s -> String -> IO Int
feedText s t = GF.withCStringLen utf8 t $ \(d, n) -> do
    bytes <- B.packCStringLen (d, n)
    feed s bytes

-- | RETURN: IO (Int, Int), the cursor's row and column, from 0.
cursor :: ScreenLike s => s -> IO (Int, Int)
cursor s = do
    p <- screenPointer s
    alloca $ \r -> alloca $ \c -> do
        c_screen_cursor p r c
        (,) <$> (fromIntegral <$> peek r) <*> (fromIntegral <$> peek c)

-- | RETURN: IO Cell, what stands at that place; raises IndexError where the
--           place is not on the screen.
cell :: ScreenLike s => s -> Int -> Int -> IO Cell
cell s r c = do
    p <- screenPointer s
    allocaBytes #{size VtermCell} $ \q -> do
        status <- c_screen_cell p (fromIntegral r) (fromIntegral c) q
        when (status /= 0) (screenError p >>= throwIO)
        let flag :: CInt -> Bool
            flag = (/= 0)
            rgb :: Ptr Word8 -> IO (Int, Int, Int)
            rgb x = (,,) <$> byte x 0 <*> byte x 1 <*> byte x 2
            byte x i = fromIntegral <$> (peekByteOff x i :: IO Word8)
            colour setF x = if flag setF then Just <$> rgb x else return Nothing
        t      <- peekUtf8 (#{ptr VtermCell, text} q)
        w      <- #{peek VtermCell, width} q :: IO CInt
        flags  <- forM [ #{offset VtermCell, bold_f}, #{offset VtermCell, italic_f}
                       , #{offset VtermCell, underline_f}, #{offset VtermCell, blink_f}
                       , #{offset VtermCell, reverse_f}, #{offset VtermCell, conceal_f}
                       , #{offset VtermCell, strike_f} ] (\o -> flag <$> (peekByteOff q o :: IO CInt))
        fgF    <- #{peek VtermCell, foreground_f} q
        bgF    <- #{peek VtermCell, background_f} q
        fg     <- colour fgF (#{ptr VtermCell, foreground} q)
        bg     <- colour bgF (#{ptr VtermCell, background} q)
        case flags of
            [b, i, u, k, v, h, x] -> return (Cell t (fromIntegral w) b i u k v h x fg bg)
            _                     -> throwIO (RuntimeError "cell: seven attributes expected")

-- | RETURN: IO String, the row's characters, blanks at its end dropped; a
--           cell nothing was written to reads as a blank.
line :: ScreenLike s => s -> Int -> IO String
line s r = do
    p <- screenPointer s
    allocaBytes 16384 $ \b -> c_screen_line p (fromIntegral r) b 16384 >>= peekUtf8

-- | RETURN: IO [String], every row as 'line' gives it, top first.
lineList :: ScreenLike s => s -> IO [String]
lineList s = mapM (line s) [0 .. rowN s - 1]

-- ---------------------------------------------------------------- Terminal

-- | A TERMINAL AN APPLICATION RUNS IN, OBSERVED BY CALLBACKS: Python's
--   'Terminal'. Its C structure begins with its screen.
data Terminal = Terminal
    { terminalRef :: IORef (Ptr CTerminal)
    , tRowN       :: Int
    , tColumnN    :: Int
    , wrapperRef  :: IORef [FunPtr ()]      -- the callbacks, freed on close
    }

instance ScreenLike Terminal where
    screenPointer t = castPtr <$> terminalPointer t
    rowN            = tRowN
    columnN         = tColumnN
    --  THE RAW EVENTS of what was fed fire before this returns; what the
    --  terminal answered goes to the application, where one runs.
    feed t bytes    = do
        p <- terminalPointer t
        BU.unsafeUseAsCStringLen bytes $ \(d, n) -> fromIntegral <$> c_terminal_feed p d (fromIntegral n)

-- | RETURN: IO (Ptr CTerminal), the C terminal; raises RuntimeError once
--           closed.
terminalPointer :: Terminal -> IO (Ptr CTerminal)
terminalPointer t = readIORef (terminalRef t) >>= alive

-- | RETURN: IO VtermError, the error the terminal holds.
terminalError :: Terminal -> IO VtermError
terminalError t = terminalPointer t >>= screenError . castPtr

-- | RETURN: IO Terminal, blank, nothing running in it; raises
--           LibraryMissing where libvterm is not found. 'settleS' is how
--           long the application must write nothing before its screen is
--           taken as drawn.
newTerminal :: Int -> Int -> Double -> IO Terminal
newTerminal rows columns settleS = allocaBytes #{size VtermError} $ \e -> do
    p <- c_terminal_new (fromIntegral rows) (fromIntegral columns) (realToFrac settleS) e
    when (p == nullPtr) (peekError e >>= throwIO)
    Terminal <$> newIORef p <*> pure rows <*> pure columns <*> newIORef []

-- | RETURN: IO (); an application still running is killed, the
--           pseudo-terminal closed, the memory and the callbacks freed; a
--           second call does nothing.
closeTerminal :: Terminal -> IO ()
closeTerminal t = do
    p <- readIORef (terminalRef t)
    when (p /= nullPtr) $ do
        c_terminal_free p
        writeIORef (terminalRef t) nullPtr
        readIORef (wrapperRef t) >>= mapM_ freeHaskellFunPtr
        writeIORef (wrapperRef t) []

-- | RETURN: IO a, what 'action' returns on a new terminal, closed after it.
withTerminal :: Int -> Int -> Double -> (Terminal -> IO a) -> IO a
withTerminal rows columns settleS = bracket (newTerminal rows columns settleS) closeTerminal

-- | RETURN: IO (); 'callback' is called with every raw Event from now on.
onEvent :: Terminal -> (Event -> IO ()) -> IO ()
onEvent t callback = do
    p <- terminalPointer t
    f <- wrapEventF $ \_ e -> readEvent e >>= callback
    modifyIORef (wrapperRef t) (castFunPtr f :)
    c_on_event p f nullPtr

-- | RETURN: IO Event, the C port's event at 'e'.
readEvent :: Ptr CEvent -> IO Event
readEvent e = do
    k <- #{peek VtermEvent, kind} e >>= peekUtf8
    let int o = fromIntegral <$> (peekByteOff e o :: IO CInt)
    r  <- int #{offset VtermEvent, row}
    c  <- int #{offset VtermEvent, column}
    re <- int #{offset VtermEvent, row_end}
    ce <- int #{offset VtermEvent, column_end}
    vf <- int #{offset VtermEvent, value_f} :: IO Int
    v  <- int #{offset VtermEvent, value}
    case k of
        "damage"   -> return (Damage r c re ce)
        "cursor"   -> return (Cursor r c (v /= 0))
        "property" -> do
            n <- #{peek VtermEvent, name} e >>= peekUtf8
            return (Property n (if vf /= 0 then Just v else Nothing))
        _          -> return Bell

-- | RETURN: IO (); 'callback name lines' is called for every region whose
--           text changed, once the screen is quiet.
onChange :: Terminal -> (String -> [String] -> IO ()) -> IO ()
onChange t callback = do
    p <- terminalPointer t
    f <- wrapChangeF $ \_ n ls k -> do
        regionName <- peekUtf8 n
        texts      <- peekArray (fromIntegral k) ls >>= mapM peekUtf8
        callback regionName texts
    modifyIORef (wrapperRef t) (castFunPtr f :)
    c_on_change p f nullPtr

-- | RETURN: IO (); the rectangle 'regionName' is observed from now on:
--           'rows' rows from 'r', 'columns' columns from 'c' (to the right
--           edge where Nothing). A NEGATIVE 'r' counts from the bottom.
region :: Terminal -> String -> Int -> Int -> Int -> Maybe Int -> IO ()
region t regionName r rows c columns = do
    p <- terminalPointer t
    withUtf8 regionName $ \n ->
        c_region p n (fromIntegral r) (fromIntegral rows) (fromIntegral c) (maybe (-1) fromIntegral columns)

-- | RETURN: IO [String], the region's rows as they stand now, blanks at each
--           row's end dropped; raises KeyError where no such region was
--           declared.
regionText :: Terminal -> String -> IO [String]
regionText t regionName = do
    p <- terminalPointer t
    withUtf8 regionName $ \n -> alloca $ \k -> do
        ls <- c_region_text p n k
        when (ls == nullPtr) (terminalError t >>= throwIO)
        count <- fromIntegral <$> peek k
        texts <- peekArray count ls >>= mapM peekUtf8
        c_lines_free ls (fromIntegral count)
        return texts

-- | RETURN: IO Int, how many regions differ from what was last told -- each
--           told to every 'onChange' callback, in the order of declaration.
report :: Terminal -> IO Int
report t = terminalPointer t >>= fmap fromIntegral . c_report

-- | RETURN: IO B.ByteString, what the terminal said since the last call and
--           no application took.
answer :: Terminal -> IO B.ByteString
answer t = do
    p <- terminalPointer t
    alloca $ \k -> do
        d <- c_answer p k
        n <- fromIntegral <$> peek k
        bytes <- if d == nullPtr then return B.empty else B.packCStringLen (d, n)
        c_free d
        return bytes

-- | RETURN: IO Bool, True where the application still runs after 'text'
--           was typed, character by character, and the screen was given
--           'reactS' to begin answering and read until quiet.
send :: Terminal -> String -> Double -> IO Bool
send t text reactS = do
    p <- terminalPointer t
    withUtf8 text $ \s -> (== 1) <$> c_send p s (realToFrac reactS)

-- | RETURN: IO Bool, True where the application still runs after 'key' --
--           'enter', 'up', 'f5', ... or one character -- was pressed with
--           the modifiers ('shift', 'alt', 'ctrl'); raises KeyError where a
--           name is none of them.
press :: Terminal -> String -> [String] -> Double -> IO Bool
press t key modifiers reactS = do
    p <- terminalPointer t
    status <- withUtf8 key $ \k -> withUtf8 (unwords modifiers) $ \m -> c_press p k m (realToFrac reactS)
    when (status < 0) (terminalError t >>= throwIO)
    return (status == 1)

-- | RETURN: IO Bool, True where the application 'argv' still runs once its
--           first screen stands -- started on a pseudo-terminal of this
--           size, its controlling one, TERM 'xterm-256color', LINES and
--           COLUMNS taken out; raises RuntimeError where one already runs.
run :: Terminal -> [String] -> Maybe FilePath -> Double -> IO Bool
run t argv cwd startS = do
    p <- terminalPointer t
    texts <- mapM (GF.newCString utf8) argv
    status <- withArray0 nullPtr texts $ \a -> case cwd of
        Nothing -> c_run p a nullPtr (realToFrac startS)
        Just d  -> withUtf8 d $ \w -> c_run p a w (realToFrac startS)
    mapM_ free texts
    when (status < 0) (terminalError t >>= throwIO)
    return (status == 1)

-- | RETURN: IO Bool, True where the application still runs, after reading
--           until quiet: up to 'firstS' for it to write at all, then on until
--           it wrote nothing for the settle time; the changed regions told.
pump :: Terminal -> Double -> IO Bool
pump t firstS = terminalPointer t >>= \p -> (== 1) <$> c_pump p (realToFrac firstS)

-- | RETURN: IO (Int, Int), the row and column where 'text' stands, once it
--           does; raises TimeoutError, carrying the screen, where it does not
--           within 'timeoutS'.
expect :: Terminal -> String -> Double -> IO (Int, Int)
expect t text timeoutS = do
    p <- terminalPointer t
    withUtf8 text $ \s -> alloca $ \r -> alloca $ \c -> do
        status <- c_expect p s (realToFrac timeoutS) r c
        when (status /= 0) (terminalError t >>= throwIO)
        (,) <$> (fromIntegral <$> peek r) <*> (fromIntegral <$> peek c)

-- | RETURN: IO (Maybe Int), Just the application's exit status (minus the
--           signal that ended it) once it ended and its last words are on
--           the screen; Nothing where none was run; raises TimeoutError
--           where it still runs after 'timeoutS' -- it is killed first.
wait :: Terminal -> Double -> IO (Maybe Int)
wait t timeoutS = do
    p <- terminalPointer t
    alloca $ \s -> do
        status <- c_wait p (realToFrac timeoutS) s
        case status of
            1 -> Just . fromIntegral <$> peek s
            0 -> return Nothing
            _ -> terminalError t >>= throwIO

-- | RETURN: IO String, 'libvterm found: <name>' where the library loads; the
--           text of LibraryMissing -- what is wrong, how to install it --
--           else.
detectionText :: IO String
detectionText = allocaBytes 4096 $ \b -> c_detection_text b 4096 >>= peekUtf8

-- | RETURN: IO (); the library is looked for again at the next screen.
resetLibrary :: IO ()
resetLibrary = c_reset_library
