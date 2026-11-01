// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
//______________________________________________________________________________
//
// PURPOSE: THE SHOP'S DATABASE, SQLite -- no test, a module of 'shop.rs' and
//          'fixture.rs' ('mod shop_db;'). Rust's standard library has no
//          SQLite and this demonstration takes no crate: the five C functions
//          of libsqlite3 it calls are declared here by hand, linked by
//          '-l sqlite3' ('#[link]' below). Every value the shop writes is an
//          item name or a number of its own, so a statement is a text; a name
//          is quoted by 'quoted'.
//______________________________________________________________________________
#![allow(dead_code)]
use std::ffi::{c_char, c_int, c_void, CStr, CString};

type Callback = extern "C" fn(*mut c_void, c_int, *mut *mut c_char, *mut *mut c_char) -> c_int;

#[link(name = "sqlite3")]
extern "C" {
    fn sqlite3_open(filename: *const c_char, db: *mut *mut c_void) -> c_int;
    fn sqlite3_busy_timeout(db: *mut c_void, ms: c_int) -> c_int;
    fn sqlite3_exec(db: *mut c_void, sql: *const c_char, callback: Option<Callback>, arg: *mut c_void,
                    errmsg: *mut *mut c_char) -> c_int;
    fn sqlite3_free(p: *mut c_void);
    fn sqlite3_close(db: *mut c_void) -> c_int;
}

/// RETURN: String, the directory this program stands in -- the test
///         directory, where the Makefile built it.
pub fn here() -> String {
    std::env::current_exe().ok().and_then(|p| p.parent().map(|d| d.to_string_lossy().into_owned()))
        .unwrap_or_else(|| ".".to_string())
}

/// RETURN: String, the path of the shop's database, 'TMP/shop.db'.
pub fn db_path() -> String { format!("{}/TMP/shop.db", here()) }

/// RETURN: String, the path of the frame log, 'TMP/frame.log'.
pub fn log_path() -> String { format!("{}/TMP/frame.log", here()) }

/// RETURN: String, 'text' as an SQL string literal.
pub fn quoted(text: &str) -> String { format!("'{}'", text.replace('\'', "''")) }

/// One open connection.
pub struct Db { handle: *mut c_void, trace_f: bool }

// A connection is used by one thread at a time: each clerk opens its own.
unsafe impl Send for Db {}

/// RETURN: c_int, 0; one row of a query was appended to the Vec<Vec<String>>
///         behind 'arg' (NULL is an empty text).
extern "C" fn collect(arg: *mut c_void, n: c_int, value: *mut *mut c_char, _name: *mut *mut c_char) -> c_int {
    let row_list = unsafe { &mut *(arg as *mut Vec<Vec<String>>) };
    let row = (0..n as isize).map(|i| unsafe {
        let p = *value.offset(i);
        if p.is_null() { String::new() } else { CStr::from_ptr(p).to_string_lossy().into_owned() }
    }).collect();
    row_list.push(row);
    0
}

impl Db {
    /// RETURN: Ok(Db), connected to the database at 'path', waiting up to
    ///         10 s for a lock; where 'trace_f', every statement executed is
    ///         logged on stderr as 'sql: ...';
    ///         Err(String), the reason, else.
    pub fn open(path: &str, trace_f: bool) -> Result<Db, String> {
        let name = CString::new(path).map_err(|e| e.to_string())?;
        let mut handle = std::ptr::null_mut();
        if unsafe { sqlite3_open(name.as_ptr(), &mut handle) } != 0 {
            return Err(format!("cannot open {}", path));
        }
        unsafe { sqlite3_busy_timeout(handle, 10000); }
        Ok(Db { handle, trace_f })
    }

    /// RETURN: Ok(rows), every row the statements 'sql' returned, each a
    ///         Vec of its column texts;
    ///         Err(String), SQLite's message, else ('database is locked').
    pub fn execute(&self, sql: &str) -> Result<Vec<Vec<String>>, String> {
        if self.trace_f { eprintln!("sql: {}", sql); }
        let text = CString::new(sql).map_err(|e| e.to_string())?;
        let mut row_list: Vec<Vec<String>> = Vec::new();
        let mut error: *mut c_char = std::ptr::null_mut();
        let status = unsafe {
            sqlite3_exec(self.handle, text.as_ptr(), Some(collect),
                         &mut row_list as *mut Vec<Vec<String>> as *mut c_void, &mut error)
        };
        if status != 0 {
            let message = if error.is_null() { format!("SQLite error {}", status) }
                          else { unsafe { CStr::from_ptr(error).to_string_lossy().into_owned() } };
            unsafe { sqlite3_free(error as *mut c_void); }
            return Err(message);
        }
        Ok(row_list)
    }
}

impl Drop for Db {
    fn drop(&mut self) { unsafe { sqlite3_close(self.handle); } }
}
