# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#_____________________________________________________________________________
#
# THE SHOP'S DATABASE, for 'shop.ps1' and 'fixture.ps1' -- no test, a helper
# they dot-source. SQLite through P/Invoke straight to 'libsqlite3': .NET
# carries no SQLite, as Python carries 'sqlite3', and no package is fetched
# (RATIONALE DEMO-POWERSHELL-4). The C# below is compiled by Add-Type once
# per process, in memory -- no file is written, so two tests building at
# once share nothing.
#
#     . "$PSScriptRoot/shop_db.ps1"
#     $db = [ShopDb]::new($path, 10000, $true)      # wait 10 s for a lock; trace
#     [void]$db.Execute('UPDATE stock SET qty = qty + ? WHERE item = ?', @(1, 'pear'))
#     $row_list = $db.Execute('SELECT item, qty FROM stock', @())   # string[] each
#     $db.Close()
#
# Statements run in autocommit, as Python's 'isolation_level=None': a
# transaction is the caller's 'BEGIN IMMEDIATE' ... 'COMMIT'. A fault throws
# with SQLite's own message ('database is locked', ...). With 'trace' every
# statement, its parameters filled in, is written on stderr as 'sql: ...' --
# Python's 'set_trace_callback'.
#_____________________________________________________________________________
if (-not ('ShopDb' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;

public sealed class ShopDb {
    const string LIB = "libsqlite3.so.0";
    const int SQLITE_ROW = 100, SQLITE_DONE = 101;
    static readonly IntPtr TRANSIENT = new IntPtr(-1);

    [DllImport(LIB)] static extern int    sqlite3_open(byte[] path, out IntPtr db);
    [DllImport(LIB)] static extern int    sqlite3_close(IntPtr db);
    [DllImport(LIB)] static extern int    sqlite3_busy_timeout(IntPtr db, int ms);
    [DllImport(LIB)] static extern IntPtr sqlite3_errmsg(IntPtr db);
    [DllImport(LIB)] static extern int    sqlite3_prepare_v2(IntPtr db, byte[] sql, int n, out IntPtr stmt, IntPtr tail);
    [DllImport(LIB)] static extern int    sqlite3_bind_text(IntPtr stmt, int i, byte[] text, int n, IntPtr destructor);
    [DllImport(LIB)] static extern int    sqlite3_bind_int64(IntPtr stmt, int i, long value);
    [DllImport(LIB)] static extern int    sqlite3_step(IntPtr stmt);
    [DllImport(LIB)] static extern int    sqlite3_column_count(IntPtr stmt);
    [DllImport(LIB)] static extern IntPtr sqlite3_column_text(IntPtr stmt, int i);
    [DllImport(LIB)] static extern IntPtr sqlite3_expanded_sql(IntPtr stmt);
    [DllImport(LIB)] static extern void   sqlite3_free(IntPtr p);
    [DllImport(LIB)] static extern int    sqlite3_finalize(IntPtr stmt);

    IntPtr handle;
    readonly bool trace;

    static byte[] Utf8z(string s) { return Encoding.UTF8.GetBytes(s + "\0"); }

    /* RETURN: string, SQLite's message for the last fault of the connection. */
    string Fault() { return Marshal.PtrToStringUTF8(sqlite3_errmsg(handle)); }

    /* RETURN: ShopDb, a connection to the database at 'path', waiting up to
               'timeout_ms' for a lock, tracing where 'trace';
               throws, else, with SQLite's message. */
    public ShopDb(string path, int timeout_ms, bool trace) {
        this.trace = trace;
        if (sqlite3_open(Utf8z(path), out handle) != 0) {
            string m = handle == IntPtr.Zero ? "out of memory" : Fault();
            throw new Exception(path + ": " + m);
        }
        sqlite3_busy_timeout(handle, timeout_ms);
    }

    /* RETURN: List of string[], every row the statement 'sql' with the
               parameters 'value' returned (none for a statement without
               rows); throws, else, with SQLite's message. */
    public List<string[]> Execute(string sql, object[] value) {
        IntPtr stmt;
        if (sqlite3_prepare_v2(handle, Utf8z(sql), -1, out stmt, IntPtr.Zero) != 0) throw new Exception(Fault());
        try {
            for (int i = 0; value != null && i < value.Length; i++) {
                object v = value[i];
                if (v is int || v is long) sqlite3_bind_int64(stmt, i + 1, Convert.ToInt64(v));
                else { byte[] b = Encoding.UTF8.GetBytes(Convert.ToString(v)); sqlite3_bind_text(stmt, i + 1, b, b.Length, TRANSIENT); }
            }
            if (trace) {
                IntPtr x = sqlite3_expanded_sql(stmt);
                Console.Error.WriteLine("sql: " + Marshal.PtrToStringUTF8(x));
                sqlite3_free(x);
            }
            var row_list = new List<string[]>();
            for (;;) {
                int code = sqlite3_step(stmt);
                if (code == SQLITE_DONE) return row_list;
                if (code != SQLITE_ROW)  throw new Exception(Fault());
                var row = new string[sqlite3_column_count(stmt)];
                for (int c = 0; c < row.Length; c++) row[c] = Marshal.PtrToStringUTF8(sqlite3_column_text(stmt, c));
                row_list.Add(row);
            }
        } finally { sqlite3_finalize(stmt); }
    }

    /* RETURN: nothing. The connection is closed; a second call does nothing. */
    public void Close() { if (handle != IntPtr.Zero) { sqlite3_close(handle); handle = IntPtr.Zero; } }
}
'@
}
