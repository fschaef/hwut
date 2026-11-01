// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
// _____________________________________________________________________________
//
// THE SHOP'S FIXTURE -- no test, a helper the directory's 'hwut.conf' calls;
// 'fixture.py' of the Python demonstration, in Go ('make fixture.exe').
//
//     fixture.exe open            a fresh 'TMP/shop.db', stocked as below, and
//                                 an empty 'TMP/frame.log' ('on_entry', and
//                                 'hwut.execute fixture open')
//     fixture.exe close           both removed ('on_exit')
//     fixture.exe check <when> <app> [<choice>]
//                                 'when' is 'before' or 'after': whether the
//                                 stock adds up around the test run '<app>
//                                 <choice>', appended to 'TMP/frame.log'
//                                 ('on_before_test', 'on_after_test')
//
// 'hwut.conf' passes '<app>' and '<choice>' as '$HWUT_TEST $HWUT_CHOICE',
// which hwut sets for the run the check stands around; a test without
// choices has none. 'check' concerns the shop's tests alone. The stock ADDS
// UP where every item's quantity is its opening quantity plus every movement
// of the journal.
// _____________________________________________________________________________

package main

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

var openingList = []struct {
	item string
	qty  int
}{{"apple", 10}, {"pear", 5}, {"plum", 5}}

var shopTestSet = map[string]bool{"delivery.json": true, "shop.go": true}

// RETURN: string, the directory the executable stands in -- this test's.
func here() string {
	path, err := os.Executable()
	if err != nil {
		return "."
	}
	return filepath.Dir(path)
}

var (
	dbPath  = filepath.Join(here(), "TMP", "shop.db")
	logPath = filepath.Join(here(), "TMP", "frame.log")
)

// RETURN: *sqliteDB, open on the shop's database; else the program ends
// with status 1 and the reason on stderr.
func mustOpen() *sqliteDB {
	db, err := sqliteOpen(dbPath, 10000)
	if err != nil {
		fmt.Fprintf(os.Stderr, "fixture.go: %s\n", err)
		os.Exit(1)
	}
	return db
}

// RETURN: nothing. Writes a fresh, stocked database and an empty log.
func openShop() {
	os.MkdirAll(filepath.Dir(dbPath), 0o755)
	os.Remove(dbPath)
	os.Remove(logPath)
	db := mustOpen()
	defer db.Close()
	db.MustExec("CREATE TABLE opening (item TEXT PRIMARY KEY, qty INTEGER)")
	db.MustExec("CREATE TABLE stock   (item TEXT PRIMARY KEY, qty INTEGER)")
	db.MustExec("CREATE TABLE journal (item TEXT, delta INTEGER, source TEXT)")
	for _, entry := range openingList {
		db.MustExec("INSERT INTO opening VALUES (?, ?)", entry.item, entry.qty)
		db.MustExec("INSERT INTO stock   VALUES (?, ?)", entry.item, entry.qty)
	}
	os.WriteFile(logPath, nil, 0o644)
}

// RETURN: nothing. Removes the database and the log.
func closeShop() {
	os.Remove(dbPath)
	os.Remove(logPath)
}

// RETURN: true, if every item's stock is its opening quantity plus its
//               journal's movements;
//         false, else.
func addsUp() bool {
	db := mustOpen()
	defer db.Close()
	rowList, err := db.Query(
		"SELECT o.item, o.qty + COALESCE(SUM(j.delta), 0), s.qty" +
			"  FROM opening o JOIN stock s ON s.item = o.item" +
			"  LEFT JOIN journal j ON j.item = o.item GROUP BY o.item")
	if err != nil {
		return false
	}
	for _, row := range rowList {
		if row[1] != row[2] {
			return false
		}
	}
	return true
}

// RETURN: nothing. Appends one line to the log for a shop test run.
func check(when, test, choice string) {
	if !shopTestSet[test] {
		return
	}
	run := strings.TrimSpace(test + " " + choice)
	verdict := "STOCK BROKEN"
	if addsUp() {
		verdict = "stock adds up"
	}
	fh, err := os.OpenFile(logPath, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0o644)
	if err != nil {
		fmt.Fprintf(os.Stderr, "fixture.go: %s\n", err)
		os.Exit(1)
	}
	defer fh.Close()
	fmt.Fprintf(fh, "%-6s %-15s %s\n", when, run, verdict)
}

// RETURN: nothing; the command named is done -- else the usage is said on
// stderr and the exit status is 2.
func main() {
	argList := append(os.Args[1:], "", "", "", "")
	switch {
	case argList[0] == "open":
		openShop()
	case argList[0] == "close":
		closeShop()
	case argList[0] == "check" && len(os.Args) >= 4:
		check(argList[1], argList[2], argList[3])
	default:
		fmt.Fprintln(os.Stderr, "usage: fixture.exe open | close | check before|after <app> <choice>")
		os.Exit(2)
	}
}
