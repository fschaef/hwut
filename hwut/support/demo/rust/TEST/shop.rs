// @hwut {
//     title     = "Demo: a shop's stock -- what the directory's hwut.conf arranges"
//     build     { framework = "make", target = "%.exe"
//                 caps { timeout_sec = 900 } }
//     tolerance { stderr_ignored = true }
//     choices {
//         sell   { features = ["unordered-table", "stderr-ignored", "collision"] }
//         report { features = ["output-file", "keyed-table-separator", "dependency",
//                              "frame-scripts", "test-scripts", "stderr-ignored"]
//                  output   = ["<stdout>", "stock.csv"] }
//     }
// }
//
//______________________________________________________________________________
// SUBJECT  the stock of a small shop, kept in an SQLite database: a delivery
//          comes in, three clerks sell at once, and the stock is reported.
// REQUIREMENT  Every movement of the stock is journalled, so that the stock
//              always ADDS UP: opening quantity plus the journal's movements.
//
// THE DIRECTORY ARRANGES WHAT NO SINGLE TEST CAN -- in 'hwut.conf' beside
// this file, read it first. hwut, when it enters this directory:
//
//     on_entry        'make helpers', then 'fixture.exe open': the helper
//                     programs built, a fresh 'TMP/shop.db', stocked
//     on_before_test  'fixture.exe check before $HWUT_TEST $HWUT_CHOICE',
//     on_after_test   'fixture.exe check after ...': around every test run,
//                     whether the stock adds up, into 'TMP/frame.log'
//     on_exit         'fixture.exe close'
//     apps            'delivery.json' is a test, though it carries no
//                     header: JSON has no comment to carry one. 'admit'
//                     takes it out of the files hwut ignores by default;
//                     'execute' says how it is run -- 'shop.exe deliver
//                     delivery.json'.
//     collision       'delivery.json' and 'shop.rs sell' both write the
//                     database; SQLite lets one writer at a time hold it.
//                     hwut never runs the two at once.
//     dependency      'shop.rs report' runs after both, whatever their
//                     verdict: it reports what they left.
//
// STDERR  Every SQL statement is logged on stderr, as a server would; the
// header says 'stderr_ignored = true': the words there are on purpose.
//
// CHOICES
//
// sell     three clerks sell at once, each in a thread of its own, printed as
//          '##! table unordered sep={;}': rows of 'item;qty', in any order.
// report   the stock, as '##! table key=0 sep={;}', and the same rows written
//          to 'stock.csv' ('output' names the file; hwut compares it with its
//          own GOOD). Then the frame log of the shop's tests ('##! potpourri':
//          which ran first is free), and the line before this report.
// deliver  (no choice -- 'execute' of 'delivery.json' calls it) books a
//          delivery note: every line on the stock and into the journal, in
//          one transaction. The note is JSON, read by the few lines of
//          'Json' below: Rust's standard library reads none.
//______________________________________________________________________________
mod shop_db;

use std::sync::{Arc, Mutex};
use std::thread;

use shop_db::{db_path, log_path, quoted, Db};

//  What each clerk sells, one item per sale.
const CLERK_LIST: [(&str, &[&str]); 3] = [("anna",  &["apple", "apple", "pear"]),
                                          ("ben",   &["apple", "plum"]),
                                          ("chloe", &["apple"])];

/// RETURN: Db, connected to the shop's database, every statement logged on
///         stderr. Exits 1 where the database does not stand: 'on_entry'
///         writes it.
fn connect() -> Db {
    let path = db_path();
    if !std::path::Path::new(&path).exists() {
        eprintln!("shop.exe: no {} -- 'on_entry' writes it; by hand: 'hwut.execute fixture open'", path);
        std::process::exit(1);
    }
    Db::open(&path, true).unwrap_or_else(|error| { eprintln!("shop.exe: {}", error); std::process::exit(1) })
}

/// RETURN: Ok(()), the stock of 'item' changed by 'delta' and journalled, in
///         one transaction;
///         Err(String), SQLite's message, else.
fn shift(db: &Db, item: &str, delta: i64, source: &str) -> Result<(), String> {
    db.execute("BEGIN IMMEDIATE")?;
    db.execute(&format!("UPDATE stock SET qty = qty + {} WHERE item = {}", delta, quoted(item)))?;
    db.execute(&format!("INSERT INTO journal VALUES ({}, {}, {})", quoted(item), delta, quoted(source)))?;
    db.execute("COMMIT")?;
    Ok(())
}

// _____________________________________________________________________________
// THE DELIVERY NOTE, JSON
//
/// One JSON value.
enum Json { Null, Bool(bool), Number(f64), Text(String), List(Vec<Json>), Object(Vec<(String, Json)>) }

impl Json {
    /// RETURN: &Json, the member 'key' of an object; Null where none is.
    fn get(&self, key: &str) -> &Json {
        match self {
            Json::Object(member_list) => member_list.iter().find(|(k, _)| k == key).map(|(_, v)| v).unwrap_or(&Json::Null),
            _ => &Json::Null,
        }
    }

    /// RETURN: String, the text of a string value; its JSON spelling else.
    fn text(&self) -> String {
        match self {
            Json::Text(text) => text.clone(),
            Json::Number(x)  => x.to_string(),
            Json::Bool(b)    => b.to_string(),
            _                => "null".to_string(),
        }
    }
}

/// Reads one JSON text, character by character.
struct JsonReader { char_list: Vec<char>, i: usize }

impl JsonReader {
    /// RETURN: nothing; blanks skipped.
    fn blanks(&mut self) { while self.i < self.char_list.len() && self.char_list[self.i].is_whitespace() { self.i += 1; } }

    /// RETURN: Option<char>, the next character not blank, not consumed.
    fn peek(&mut self) -> Option<char> { self.blanks(); self.char_list.get(self.i).copied() }

    /// RETURN: Ok(()), 'c' was the next character and is consumed;
    ///         Err(String) naming the position, else.
    fn expect(&mut self, c: char) -> Result<(), String> {
        if self.peek() == Some(c) { self.i += 1; Ok(()) } else { Err(format!("'{}' expected at {}", c, self.i)) }
    }

    /// RETURN: Ok(String), the string literal that stands next;
    ///         Err(String), else.
    fn string(&mut self) -> Result<String, String> {
        self.expect('"')?;
        let mut text = String::new();
        while let Some(&c) = self.char_list.get(self.i) {
            self.i += 1;
            match c {
                '"'  => return Ok(text),
                '\\' => {
                    let e = *self.char_list.get(self.i).ok_or("unclosed string")?;
                    self.i += 1;
                    text.push(match e { 'n' => '\n', 't' => '\t', 'r' => '\r', other => other });
                }
                _ => text.push(c),
            }
        }
        Err("unclosed string".to_string())
    }

    /// RETURN: Ok(Json), the value that stands next;
    ///         Err(String), the reason, else.
    fn value(&mut self) -> Result<Json, String> {
        match self.peek() {
            Some('{') => {
                self.i += 1;
                let mut member_list = Vec::new();
                if self.peek() == Some('}') { self.i += 1; return Ok(Json::Object(member_list)); }
                loop {
                    let key = self.string()?;
                    self.expect(':')?;
                    member_list.push((key, self.value()?));
                    if self.peek() == Some(',') { self.i += 1; continue; }
                    self.expect('}')?;
                    return Ok(Json::Object(member_list));
                }
            }
            Some('[') => {
                self.i += 1;
                let mut item_list = Vec::new();
                if self.peek() == Some(']') { self.i += 1; return Ok(Json::List(item_list)); }
                loop {
                    item_list.push(self.value()?);
                    if self.peek() == Some(',') { self.i += 1; continue; }
                    self.expect(']')?;
                    return Ok(Json::List(item_list));
                }
            }
            Some('"') => Ok(Json::Text(self.string()?)),
            Some(_) => {
                let start = self.i;
                while self.i < self.char_list.len() && !",}] \t\r\n".contains(self.char_list[self.i]) { self.i += 1; }
                let word: String = self.char_list[start..self.i].iter().collect();
                match word.as_str() {
                    "true"  => Ok(Json::Bool(true)),
                    "false" => Ok(Json::Bool(false)),
                    "null"  => Ok(Json::Null),
                    _ => word.parse().map(Json::Number).map_err(|_| format!("'{}' is no value", word)),
                }
            }
            None => Err("a value expected at the end".to_string()),
        }
    }
}

/// RETURN: Ok(Json), the JSON text 'text' read;
///         Err(String), the reason, else.
fn json_of(text: &str) -> Result<Json, String> {
    JsonReader { char_list: text.chars().collect(), i: 0 }.value()
}

// _____________________________________________________________________________
// THE CHOICES
//
/// RETURN: Ok(()), the delivery note in 'path' booked and printed;
///         Err(String), the reason, else.
fn deliver(path: &str) -> Result<(), String> {
    let note = json_of(&std::fs::read_to_string(path).map_err(|e| format!("{}: {}", path, e))?)?;
    let Json::List(line_list) = note.get("lines") else { return Err("no 'lines' in the note".to_string()) };
    let quantity = |line: &Json| match line.get("qty") { Json::Number(x) => *x as i64, _ => 0 };
    let db = connect();
    db.execute("BEGIN IMMEDIATE")?;
    for line in line_list {
        let item = line.get("item").text();
        db.execute(&format!("UPDATE stock SET qty = qty + {} WHERE item = {}", quantity(line), quoted(&item)))?;
        db.execute(&format!("INSERT INTO journal VALUES ({}, {}, {})", quoted(&item), quantity(line),
                            quoted(&note.get("note").text())))?;
    }
    db.execute("COMMIT")?;
    println!("delivery note {} from {}:", note.get("note").text(), note.get("supplier").text());
    for line in line_list { println!("    {:<6} +{}", line.get("item").text(), quantity(line)); }
    Ok(())
}

/// RETURN: Ok(()), three clerks sold at once and every sale was printed;
///         Err(String), the failed sales, else.
fn sell() -> Result<(), String> {
    let sale_list = Arc::new(Mutex::new(Vec::<String>::new()));
    let error_list = Arc::new(Mutex::new(Vec::<String>::new()));
    drop(connect());
    let pool: Vec<_> = CLERK_LIST.iter().map(|(name, item_list)| {
        let (sale_list, error_list) = (sale_list.clone(), error_list.clone());
        thread::spawn(move || {
            let db = connect();
            for item in item_list.iter() {
                match shift(&db, item, -1, name) {
                    Ok(())     => sale_list.lock().unwrap().push(format!("{};1", item)),
                    Err(error) => { error_list.lock().unwrap().push(format!("{}: {}", name, error)); return; }
                }
            }
        })
    }).collect();
    for clerk in pool { let _ = clerk.join(); }
    let error_list = error_list.lock().unwrap();
    if !error_list.is_empty() { return Err(format!("a sale failed -- {}", error_list.join("; "))); }
    println!("sales, item;qty -- in the order the clerks booked them:");
    println!("##! table unordered sep={{;}}");
    for row in sale_list.lock().unwrap().iter() { println!("{}", row); }
    println!("####");
    Ok(())
}

/// RETURN: Ok(()), the stock and the frame log printed and 'stock.csv'
///         written;
///         Err(String), the reason, else.
fn report() -> Result<(), String> {
    let db = connect();
    let row_list = db.execute("SELECT item, qty FROM stock ORDER BY qty, item")?;
    let mut sorted_list = row_list.clone();
    sorted_list.sort();
    let mut csv = String::from("item;qty\n");
    for row in &sorted_list { csv += &format!("{};{}\n", row[0], row[1]); }
    std::fs::write(format!("{}/stock.csv", shop_db::here()), csv).map_err(|e| e.to_string())?;
    println!("stock, item;qty (also written to stock.csv):");
    println!("##! table key=0 sep={{;}}");
    for row in &row_list { println!("{};{}", row[0], row[1]); }
    println!("####");
    let log = std::fs::read_to_string(log_path()).map_err(|e| e.to_string())?;
    let line_list: Vec<&str> = log.lines().map(str::trim_end).collect();
    println!("the frame, around the delivery and the sale:");
    println!("##! potpourri");
    for line in line_list.iter().filter(|l| !l.contains("shop.rs report")) { println!("{}", line); }
    println!("####");
    for line in line_list.iter().filter(|l| l.contains("shop.rs report")) { println!("{}", line); }
    Ok(())
}

/// RETURN: never; exits 0 once the command named on the command line was
///         done and '<hwut-end>' printed; 1 where it failed or is no choice.
fn main() {
    let argv: Vec<String> = std::env::args().collect();
    let result = match argv.get(1).map(String::as_str) {
        Some("deliver") => deliver(argv.get(2).map(String::as_str).unwrap_or("")),
        Some("sell")    => sell(),
        Some("report")  => report(),
        _ => { println!("choices: sell, report"); std::process::exit(1); }
    };
    if let Err(error) = result {
        eprintln!("shop.exe: {}", error);
        std::process::exit(1);
    }
    println!("<hwut-end>");
}
