-- SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
-- _____________________________________________________________________________
--
-- PURPOSE: SQLite for the shop -- no test, a module 'shop.hs' and
--          'fixture.hs' import ('hwut.conf' ignores it). What Python's
--          'sqlite3' module gives the Python demonstration, bound here to
--          the C library ('-lsqlite3') by GHC's FFI: GHC ships no database
--          package.
--
--     db   <- open path 10.0 (Just (hPutStrLn stderr . ("sql: " ++)))
--     execute db "UPDATE stock SET qty = qty + ? WHERE item = ?" [SqlInt 1, SqlText "pear"]
--     rows <- query db "SELECT item, qty FROM stock" []
--     close db
--
-- Every statement is executed by itself: no implicit transaction (Python's
-- 'isolation_level=None'); 'BEGIN IMMEDIATE' ... 'COMMIT' are statements of
-- the caller. The TRACE, where given, is told each statement with its
-- values bound, as SQLite expands it -- Python's 'set_trace_callback'.
-- A failing call raises an IOError carrying SQLite's own message
-- ('database is locked', ...). The calls are 'safe': a connection waiting
-- for the lock blocks its OS thread, not the runtime.
-- _____________________________________________________________________________
module Sqlite
    ( Db
    , SqlValue (..)
    , open
    , close
    , execute
    , query
    ) where

import Control.Exception  (bracket)
import Control.Monad      (forM, forM_, unless, when)
import Foreign
import Foreign.C

data CDb
data CStmt

-- | A connection, and what it tells each statement it executes to.
data Db = Db (Ptr CDb) (Maybe (String -> IO ()))

-- | A value bound to a '?' of a statement.
data SqlValue = SqlInt Int | SqlText String

foreign import ccall safe "sqlite3_open_v2"      c_open      :: CString -> Ptr (Ptr CDb) -> CInt -> CString -> IO CInt
foreign import ccall safe "sqlite3_close"        c_close     :: Ptr CDb -> IO CInt
foreign import ccall safe "sqlite3_busy_timeout" c_busy      :: Ptr CDb -> CInt -> IO CInt
foreign import ccall safe "sqlite3_errmsg"       c_errmsg    :: Ptr CDb -> IO CString
foreign import ccall safe "sqlite3_prepare_v2"   c_prepare   :: Ptr CDb -> CString -> CInt -> Ptr (Ptr CStmt) -> Ptr CString -> IO CInt
foreign import ccall safe "sqlite3_bind_int64"   c_bindInt   :: Ptr CStmt -> CInt -> Int64 -> IO CInt
foreign import ccall safe "sqlite3_bind_text"    c_bindText  :: Ptr CStmt -> CInt -> CString -> CInt -> FunPtr (Ptr () -> IO ()) -> IO CInt
foreign import ccall safe "sqlite3_step"         c_step      :: Ptr CStmt -> IO CInt
foreign import ccall safe "sqlite3_column_count" c_columnN   :: Ptr CStmt -> IO CInt
foreign import ccall safe "sqlite3_column_text"  c_column    :: Ptr CStmt -> CInt -> IO CString
foreign import ccall safe "sqlite3_finalize"     c_finalize  :: Ptr CStmt -> IO CInt
foreign import ccall safe "sqlite3_expanded_sql" c_expanded  :: Ptr CStmt -> IO CString
foreign import ccall safe "sqlite3_free"         c_free      :: Ptr a -> IO ()

-- | RETURN: IO a, never: raises the IOError of the connection's last fault.
failure :: Ptr CDb -> IO a
failure p = c_errmsg p >>= peekCString >>= ioError . userError

-- | RETURN: IO Db, a connection to the database file 'path' (made where it
--           does not stand), waiting up to 'timeoutS' for a lock another
--           connection holds; 'trace' is told every statement.
open :: FilePath -> Double -> Maybe (String -> IO ()) -> IO Db
open path timeoutS trace = withCString path $ \cPath -> alloca $ \out -> do
    status <- c_open cPath out 0x6 nullPtr        -- READWRITE | CREATE
    p      <- peek out
    when (status /= 0) (failure p)
    _ <- c_busy p (round (timeoutS * 1000))
    return (Db p trace)

-- | RETURN: IO (); the connection closed.
close :: Db -> IO ()
close (Db p _) = () <$ c_close p

-- | RETURN: IO [[String]], the rows 'sql' gives with 'values' bound to its
--           '?'s, every column as text ("" for NULL); [] for a statement
--           that gives none.
query :: Db -> String -> [SqlValue] -> IO [[String]]
query (Db p trace) sql values = withCString sql $ \cSql -> alloca $ \out -> do
    status <- c_prepare p cSql (-1) out nullPtr
    when (status /= 0) (failure p)
    stmt <- peek out
    bracket (return stmt) c_finalize $ \s -> do
        forM_ (zip [1 ..] values) $ \(i, v) -> case v of
            SqlInt n  -> c_bindInt s i (fromIntegral n)
            SqlText t -> withCString t $ \cT -> c_bindText s i cT (-1) transient
        forM_ trace $ \tell -> do
            expanded <- c_expanded s
            unless (expanded == nullPtr) (peekCString expanded >>= tell >> c_free expanded)
        let rows = do
                r <- c_step s
                case r of
                    100 -> do                              -- SQLITE_ROW
                        n   <- c_columnN s
                        row <- forM [0 .. n - 1] $ \i -> do
                            t <- c_column s i
                            if t == nullPtr then return "" else peekCString t
                        (row :) <$> rows
                    101 -> return []                       -- SQLITE_DONE
                    _   -> failure p
        rows
  where
    transient = castPtrToFunPtr (intPtrToPtr (-1))         -- SQLITE_TRANSIENT

-- | RETURN: IO (); 'sql' executed with 'values' bound to its '?'s.
execute :: Db -> String -> [SqlValue] -> IO ()
execute db sql values = () <$ query db sql values
