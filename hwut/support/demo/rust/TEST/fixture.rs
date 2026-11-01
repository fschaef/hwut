// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
//______________________________________________________________________________
//
// THE SHOP'S FIXTURE -- no test, a helper the directory's 'hwut.conf' calls.
//
//     fixture.exe open           a fresh 'TMP/shop.db', stocked as below, and
//                                an empty 'TMP/frame.log' ('on_entry', and
//                                'hwut.execute fixture open')
//     fixture.exe close          both removed ('on_exit')
//     fixture.exe check <when> <app> [<choice>]
//                                'when' is 'before' or 'after': whether the
//                                stock adds up around the test run '<app>
//                                <choice>', appended to 'TMP/frame.log'
//                                ('on_before_test', 'on_after_test')
//
// 'hwut.conf' passes '<app>' and '<choice>' as '$HWUT_TEST $HWUT_CHOICE',
// which hwut sets for the run the check stands around; a test without
// choices has none. 'check' concerns the shop's tests alone. The stock ADDS
// UP where every item's quantity is its opening quantity plus every movement
// of the journal. Built by 'make helpers', the first word of 'on_entry'.
//______________________________________________________________________________
mod shop_db;

use std::io::Write;

use shop_db::{db_path, log_path, quoted, Db};

const OPENING_LIST: [(&str, i64); 3] = [("apple", 10), ("pear", 5), ("plum", 5)];
const SHOP_TEST_LIST: [&str; 2] = ["delivery.json", "shop.rs"];

/// RETURN: Ok(()), a fresh, stocked database and an empty log written;
///         Err(String), the reason, else.
fn open_shop() -> Result<(), String> {
    let _ = std::fs::create_dir_all(format!("{}/TMP", shop_db::here()));
    for path in [db_path(), log_path()] { let _ = std::fs::remove_file(path); }
    let db = Db::open(&db_path(), false)?;
    let mut sql = String::from("CREATE TABLE opening (item TEXT PRIMARY KEY, qty INTEGER);\
                                CREATE TABLE stock   (item TEXT PRIMARY KEY, qty INTEGER);\
                                CREATE TABLE journal (item TEXT, delta INTEGER, source TEXT);");
    for (item, qty) in OPENING_LIST {
        sql += &format!("INSERT INTO opening VALUES ({0}, {1}); INSERT INTO stock VALUES ({0}, {1});", quoted(item), qty);
    }
    db.execute(&sql)?;
    std::fs::write(log_path(), "").map_err(|e| e.to_string())
}

/// RETURN: nothing; the database and the log are removed.
fn close_shop() {
    for path in [db_path(), log_path()] { let _ = std::fs::remove_file(path); }
}

/// RETURN: Ok(true), if every item's stock is its opening quantity plus its
///                   journal's movements;
///         Ok(false), else;
///         Err(String), where the database cannot be read.
fn adds_up() -> Result<bool, String> {
    let db = Db::open(&db_path(), false)?;
    let row_list = db.execute(
        "SELECT o.item, o.qty + COALESCE(SUM(j.delta), 0), s.qty \
           FROM opening o JOIN stock s ON s.item = o.item \
           LEFT JOIN journal j ON j.item = o.item GROUP BY o.item")?;
    Ok(row_list.iter().all(|row| row[1] == row[2]))
}

/// RETURN: Ok(()), one line appended to the log for a shop test run (none
///         for another test's);
///         Err(String), the reason, else.
fn check(when: &str, test: &str, choice: &str) -> Result<(), String> {
    if !SHOP_TEST_LIST.contains(&test) { return Ok(()); }
    let run = format!("{} {}", test, choice).trim().to_string();
    let verdict = if adds_up()? { "stock adds up" } else { "STOCK BROKEN" };
    let mut log = std::fs::OpenOptions::new().append(true).create(true).open(log_path()).map_err(|e| e.to_string())?;
    writeln!(log, "{:<6} {:<15} {}", when, run, verdict).map_err(|e| e.to_string())
}

/// RETURN: never; exits 0 where the command was done, 1 where it failed, 2
///         where the command line cannot be read.
fn main() {
    let argv: Vec<String> = std::env::args().collect();
    let word = |i: usize| argv.get(i).map(String::as_str).unwrap_or("");
    let result = match word(1) {
        "open"  => open_shop(),
        "close" => { close_shop(); Ok(()) }
        "check" => check(word(2), word(3), word(4)),
        _ => {
            eprintln!("usage: fixture.exe open | close | check before|after <app> <choice>");
            std::process::exit(2);
        }
    };
    if let Err(error) = result {
        eprintln!("fixture.exe: {}", error);
        std::process::exit(1);
    }
}
