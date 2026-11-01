// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
// _____________________________________________________________________________
//
// SQLITE FOR THE SHOP -- no test, the few calls of SQLite 'shop.go' and
// 'fixture.go' make, built into each ('go build shop.go sqlite.go').
//
// Go's standard library carries no SQLite; nothing is downloaded. The C
// library is LOADED at run time by 'dlopen' -- 'libsqlite3.so.0', the file
// Python's own 'sqlite3' module stands on -- so building needs a C compiler
// (cgo) and no header of SQLite. The handful of prototypes are declared here.
// _____________________________________________________________________________

package main

/*
#cgo LDFLAGS: -ldl
#include <dlfcn.h>
#include <stdlib.h>

typedef struct sqlite3      sqlite3;
typedef struct sqlite3_stmt sqlite3_stmt;

static int         (*p_open)(const char*, sqlite3**);
static int         (*p_close)(sqlite3*);
static int         (*p_busy_timeout)(sqlite3*, int);
static int         (*p_prepare_v2)(sqlite3*, const char*, int, sqlite3_stmt**, const char**);
static int         (*p_bind_int64)(sqlite3_stmt*, int, long long);
static int         (*p_bind_text)(sqlite3_stmt*, int, const char*, int, void(*)(void*));
static int         (*p_step)(sqlite3_stmt*);
static int         (*p_column_count)(sqlite3_stmt*);
static const unsigned char* (*p_column_text)(sqlite3_stmt*, int);
static int         (*p_finalize)(sqlite3_stmt*);
static const char* (*p_errmsg)(sqlite3*);

// RETURN: 1, every function found in 'name', if success;
//         0, else (the library or one of its functions is missing).
static int sq_load(const char* name) {
    void* lib = dlopen(name, RTLD_NOW | RTLD_GLOBAL);
    if (!lib) return 0;
    p_open         = dlsym(lib, "sqlite3_open");
    p_close        = dlsym(lib, "sqlite3_close");
    p_busy_timeout = dlsym(lib, "sqlite3_busy_timeout");
    p_prepare_v2   = dlsym(lib, "sqlite3_prepare_v2");
    p_bind_int64   = dlsym(lib, "sqlite3_bind_int64");
    p_bind_text    = dlsym(lib, "sqlite3_bind_text");
    p_step         = dlsym(lib, "sqlite3_step");
    p_column_count = dlsym(lib, "sqlite3_column_count");
    p_column_text  = dlsym(lib, "sqlite3_column_text");
    p_finalize     = dlsym(lib, "sqlite3_finalize");
    p_errmsg       = dlsym(lib, "sqlite3_errmsg");
    return p_open && p_close && p_busy_timeout && p_prepare_v2 && p_bind_int64
        && p_bind_text && p_step && p_column_count && p_column_text
        && p_finalize && p_errmsg;
}
static int sq_open(const char* f, sqlite3** db)        { return p_open(f, db); }
static int sq_close(sqlite3* db)                       { return p_close(db); }
static int sq_busy_timeout(sqlite3* db, int ms)        { return p_busy_timeout(db, ms); }
static int sq_prepare(sqlite3* db, const char* sql, sqlite3_stmt** st)
                                                       { return p_prepare_v2(db, sql, -1, st, 0); }
static int sq_bind_int64(sqlite3_stmt* st, int i, long long v)
                                                       { return p_bind_int64(st, i, v); }
static int sq_bind_text(sqlite3_stmt* st, int i, const char* v)
                                                       { return p_bind_text(st, i, v, -1, (void(*)(void*))-1); }
static int sq_step(sqlite3_stmt* st)                   { return p_step(st); }
static int sq_column_count(sqlite3_stmt* st)           { return p_column_count(st); }
static const char* sq_column_text(sqlite3_stmt* st, int i)
                                                       { return (const char*)p_column_text(st, i); }
static int sq_finalize(sqlite3_stmt* st)               { return p_finalize(st); }
static const char* sq_errmsg(sqlite3* db)              { return p_errmsg(db); }
*/
import "C"

import (
	"errors"
	"fmt"
	"os"
	"sync"
	"unsafe"
)

const (
	sqliteRow  = 100
	sqliteDone = 101
)

var (
	sqliteOnce   sync.Once
	sqliteLoaded bool
)

// sqliteDB is one connection; 'trace', where set, is told every statement.
type sqliteDB struct {
	handle *C.sqlite3
	trace  func(sql string)
}

// RETURN: (*sqliteDB, nil), a connection to the database file 'path' (made
//         where it does not stand) that waits up to 'timeoutMs' for a lock,
//         if success;
//         (nil, error), else -- the library missing, or the file not to be
//         opened.
func sqliteOpen(path string, timeoutMs int) (*sqliteDB, error) {
	sqliteOnce.Do(func() {
		name := C.CString("libsqlite3.so.0")
		defer C.free(unsafe.Pointer(name))
		sqliteLoaded = C.sq_load(name) == 1
	})
	if !sqliteLoaded {
		return nil, errors.New("libsqlite3.so.0 not found (Debian: apt install libsqlite3-0)")
	}
	cPath := C.CString(path)
	defer C.free(unsafe.Pointer(cPath))
	var handle *C.sqlite3
	if C.sq_open(cPath, &handle) != 0 {
		message := C.GoString(C.sq_errmsg(handle))
		C.sq_close(handle)
		return nil, errors.New(message)
	}
	C.sq_busy_timeout(handle, C.int(timeoutMs))
	return &sqliteDB{handle: handle}, nil
}

// RETURN: nothing; the connection is closed.
func (self *sqliteDB) Close() {
	C.sq_close(self.handle)
}

// RETURN: ([][]string, nil), the rows 'sql' yields with 'argList' bound to
//         its '?' (int and string), each column as text, if success -- none
//         for a statement that yields none;
//         (nil, error), SQLite's message, else.
func (self *sqliteDB) Query(sql string, argList ...any) ([][]string, error) {
	if self.trace != nil {
		self.trace(sql)
	}
	cSql := C.CString(sql)
	defer C.free(unsafe.Pointer(cSql))
	var statement *C.sqlite3_stmt
	if C.sq_prepare(self.handle, cSql, &statement) != 0 {
		return nil, errors.New(C.GoString(C.sq_errmsg(self.handle)))
	}
	defer C.sq_finalize(statement)
	for i, arg := range argList {
		switch value := arg.(type) {
		case int:
			C.sq_bind_int64(statement, C.int(i+1), C.longlong(value))
		case string:
			cValue := C.CString(value)
			C.sq_bind_text(statement, C.int(i+1), cValue)
			C.free(unsafe.Pointer(cValue))
		default:
			return nil, fmt.Errorf("no binding for %T", arg)
		}
	}
	var rowList [][]string
	for {
		switch C.sq_step(statement) {
		case sqliteRow:
			n := int(C.sq_column_count(statement))
			row := make([]string, n)
			for k := 0; k < n; k++ {
				row[k] = C.GoString(C.sq_column_text(statement, C.int(k)))
			}
			rowList = append(rowList, row)
		case sqliteDone:
			return rowList, nil
		default:
			return nil, errors.New(C.GoString(C.sq_errmsg(self.handle)))
		}
	}
}

// RETURN: nil, 'sql' executed with 'argList' bound, if success; error, else.
func (self *sqliteDB) Exec(sql string, argList ...any) error {
	_, err := self.Query(sql, argList...)
	return err
}

// RETURN: nothing, 'sql' executed, if success;
//         else the program ends with status 1, SQLite's message on stderr.
func (self *sqliteDB) MustExec(sql string, argList ...any) {
	if err := self.Exec(sql, argList...); err != nil {
		fmt.Fprintf(os.Stderr, "sqlite: %s: %s\n", sql, err)
		os.Exit(1)
	}
}
