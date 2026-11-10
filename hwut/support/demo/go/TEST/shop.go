// @hwut {
//     title     = "Demo: a shop's stock -- what the directory's hwut.conf arranges"
//     build     { framework = "make", target = "%.exe"
//                 caps { file_size_mb = 256 } }
//     tolerance { stderr_ignored = true }
//     choices {
//         sell   { features = ["demo-go+cover-unordered-table", "demo-go+cover-stderr-ignored", "demo-go+cover-collision"] }
//         report { features = ["demo-go+cover-output-file", "demo-go+cover-keyed-table-separator", "demo-go+cover-dependency",
//                              "demo-go+cover-frame-scripts", "demo-go+cover-test-scripts", "demo-go+cover-stderr-ignored"]
//                  output   = ["<stdout>", "stock.csv"] }
//     }
// }
//
// _____________________________________________________________________________
// SUBJECT  the stock of a small shop, kept in an SQLite database: a delivery
//          comes in, three clerks sell at once, and the stock is reported.
// REQUIREMENT  Every movement of the stock is journalled, so that the stock
//              always ADDS UP: opening quantity plus the journal's movements.
//
// 'shop.py' of the Python demonstration, in Go. THE DIRECTORY ARRANGES WHAT NO
// SINGLE TEST CAN -- in 'hwut.conf' beside this file, read it first:
//
//     on_entry        'make -s helpers' -- the programs that are no test --
//                     then 'fixture.exe open': a fresh 'TMP/shop.db', stocked
//     on_before_test  'fixture.exe check before $HWUT_TEST $HWUT_CHOICE',
//     on_after_test   'fixture.exe check after ...': around every test run,
//                     whether the stock adds up, into 'TMP/frame.log'
//     on_exit         'fixture.exe close'
//     apps            'delivery.json' is a test, though it carries no
//                     header; 'execute' runs 'shop.exe deliver delivery.json'
//     collision       'delivery.json' and 'shop.go sell' both write the
//                     database; hwut never runs the two at once.
//     dependency      'shop.go report' runs after both, whatever their
//                     verdict: it reports what they left.
//
// STDERR  Every SQL statement is logged on stderr, as a server would; the
// header says 'stderr_ignored = true'.
//
// SQLITE  Go's standard library has none: 'sqlite.go', built into this
// program, loads 'libsqlite3.so.0' at run time -- the library Python's
// 'sqlite3' stands on.
//
// CHOICES
//
// sell     three clerks sell at once, each in a goroutine and a connection of
//          its own: '##! table unordered sep={;}', rows of 'item;qty'.
// report   the stock, as '##! table key=0 sep={;}', and the same rows written
//          to 'stock.csv' ('output'); then the frame log of the shop's tests.
// deliver  (no choice -- 'execute' of 'delivery.json' calls it) books a
//          delivery note: every line on the stock and into the journal, in
//          one transaction.
// _____________________________________________________________________________

package main

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"sync"
)

// What each clerk sells, one item per sale.
var clerkList = []struct {
	name     string
	itemList []string
}{
	{"anna", []string{"apple", "apple", "pear"}},
	{"ben", []string{"apple", "plum"}},
	{"chloe", []string{"apple"}},
}

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

// RETURN: *sqliteDB, to the shop's database, every statement it executes
// logged on stderr. Exits 1 where the database does not stand: 'on_entry'
// writes it.
func connect() *sqliteDB {
	if _, err := os.Stat(dbPath); err != nil {
		fmt.Fprintf(os.Stderr, "shop.go: no %s -- 'on_entry' writes it; by hand: 'hwut.execute fixture open'\n", dbPath)
		os.Exit(1)
	}
	db, err := sqliteOpen(dbPath, 10000)
	if err != nil {
		fmt.Fprintf(os.Stderr, "shop.go: %s\n", err)
		os.Exit(1)
	}
	db.trace = func(sql string) { fmt.Fprintf(os.Stderr, "sql: %s\n", sql) }
	return db
}

// RETURN: nil, the stock of 'item' changed by 'delta' and journalled, in one
// transaction, if success; error, else.
func move(db *sqliteDB, item string, delta int, source string) error {
	for _, step := range []struct {
		sql     string
		argList []any
	}{
		{"BEGIN IMMEDIATE", nil},
		{"UPDATE stock SET qty = qty + ? WHERE item = ?", []any{delta, item}},
		{"INSERT INTO journal VALUES (?, ?, ?)", []any{item, delta, source}},
		{"COMMIT", nil},
	} {
		if err := db.Exec(step.sql, step.argList...); err != nil {
			return err
		}
	}
	return nil
}

// RETURN: nothing. Books the delivery note in 'path' and prints it.
func deliver(path string) {
	var note struct {
		Note     string `json:"note"`
		Supplier string `json:"supplier"`
		Lines    []struct {
			Item string `json:"item"`
			Qty  int    `json:"qty"`
		} `json:"lines"`
	}
	data, err := os.ReadFile(path)
	if err == nil {
		err = json.Unmarshal(data, &note)
	}
	if err != nil {
		fmt.Fprintf(os.Stderr, "shop.go: %s\n", err)
		os.Exit(1)
	}
	db := connect()
	db.MustExec("BEGIN IMMEDIATE")
	for _, line := range note.Lines {
		db.MustExec("UPDATE stock SET qty = qty + ? WHERE item = ?", line.Qty, line.Item)
		db.MustExec("INSERT INTO journal VALUES (?, ?, ?)", line.Item, line.Qty, note.Note)
	}
	db.MustExec("COMMIT")
	fmt.Printf("delivery note %s from %s:\n", note.Note, note.Supplier)
	for _, line := range note.Lines {
		fmt.Printf("    %-6s +%d\n", line.Item, line.Qty)
	}
}

// RETURN: nothing. Three clerks sell at once; prints every sale.
func sell() {
	var lock sync.Mutex
	var group sync.WaitGroup
	var saleList, errorList []string
	connect().Close()
	for _, clerk := range clerkList {
		group.Add(1)
		go func(name string, itemList []string) {
			defer group.Done()
			db := connect()
			defer db.Close()
			for _, item := range itemList {
				if err := move(db, item, -1, name); err != nil {
					lock.Lock()
					errorList = append(errorList, name+": "+err.Error())
					lock.Unlock()
					return
				}
				lock.Lock()
				saleList = append(saleList, item+";1")
				lock.Unlock()
			}
		}(clerk.name, clerk.itemList)
	}
	group.Wait()
	if len(errorList) != 0 {
		fmt.Fprintf(os.Stderr, "shop.go: a sale failed -- %s\n", strings.Join(errorList, "; "))
		os.Exit(1)
	}
	fmt.Println("sales, item;qty -- in the order the clerks booked them:")
	fmt.Println("##! table unordered sep={;}")
	for _, row := range saleList {
		fmt.Println(row)
	}
	fmt.Println("####")
}

// RETURN: nothing. Prints the stock and the frame log; writes 'stock.csv'.
func report() {
	db := connect()
	rowList, err := db.Query("SELECT item, qty FROM stock ORDER BY qty, item")
	if err != nil {
		fmt.Fprintf(os.Stderr, "shop.go: %s\n", err)
		os.Exit(1)
	}
	sortedList := append([][]string(nil), rowList...)
	sort.Slice(sortedList, func(i, j int) bool { return sortedList[i][0] < sortedList[j][0] })
	var csv strings.Builder
	csv.WriteString("item;qty\n")
	for _, row := range sortedList {
		qty, _ := strconv.Atoi(row[1])
		fmt.Fprintf(&csv, "%s;%d\n", row[0], qty)
	}
	if err := os.WriteFile(filepath.Join(here(), "stock.csv"), []byte(csv.String()), 0o644); err != nil {
		fmt.Fprintf(os.Stderr, "shop.go: %s\n", err)
		os.Exit(1)
	}
	fmt.Println("stock, item;qty (also written to stock.csv):")
	fmt.Println("##! table key=0 sep={;}")
	for _, row := range rowList {
		fmt.Printf("%s;%s\n", row[0], row[1])
	}
	fmt.Println("####")
	data, err := os.ReadFile(logPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "shop.go: %s\n", err)
		os.Exit(1)
	}
	var lineList []string
	for _, line := range strings.Split(strings.TrimRight(string(data), "\n"), "\n") {
		lineList = append(lineList, strings.TrimRight(line, " \t"))
	}
	fmt.Println("the frame, around the delivery and the sale:")
	fmt.Println("##! potpourri")
	for _, line := range lineList {
		if !strings.Contains(line, "shop.go report") {
			fmt.Println(line)
		}
	}
	fmt.Println("####")
	for _, line := range lineList {
		if strings.Contains(line, "shop.go report") {
			fmt.Println(line)
		}
	}
}

// RETURN: nothing; the command named is done and '<hwut-end>' printed --
// else the choices are named and the exit status is 1.
func main() {
	command := ""
	if len(os.Args) > 1 {
		command = os.Args[1]
	}
	switch {
	case command == "deliver" && len(os.Args) > 2:
		deliver(os.Args[2])
	case command == "sell":
		sell()
	case command == "report":
		report()
	default:
		fmt.Println("choices: sell, report")
		os.Exit(1)
	}
	fmt.Println("<hwut-end>")
}
