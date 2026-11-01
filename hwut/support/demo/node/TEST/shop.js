#! /usr/bin/env node
//
// @hwut {
//     title     = "Demo: a shop's stock -- what the directory's hwut.conf arranges"
//     tolerance { stderr_ignored = true }
//     choices {
//         sell   { features = ["unordered-table", "stderr-ignored", "collision"] }
//         report { features = ["output-file", "keyed-table-separator", "dependency",
//                              "frame-scripts", "test-scripts", "stderr-ignored"]
//                  output   = ["<stdout>", "stock.csv"] }
//     }
// }
//
/*
______________________________________________________________________________
SUBJECT  the stock of a small shop, kept in an SQLite database: a delivery
         comes in, three clerks sell at once, and the stock is reported.
REQUIREMENT  Every movement of the stock is journalled, so that the stock
             always ADDS UP: opening quantity plus the journal's movements.

THE DIRECTORY ARRANGES WHAT NO SINGLE TEST CAN -- in 'hwut.conf' beside
this file, read it first. hwut, when it enters this directory:

    on_entry        'fixture.js open': a fresh 'TMP/shop.db', stocked
    on_before_test  'fixture.js check before $HWUT_TEST $HWUT_CHOICE',
    on_after_test   'fixture.js check after ...': around every test run,
                    whether the stock adds up, into 'TMP/frame.log' --
                    hwut sets the two variables for the run
    on_exit         'fixture.js close'
    apps            'delivery.json' is a test, though it carries no
                    header: JSON has no comment to carry one. 'admit'
                    takes it out of the files hwut ignores by default
                    ('*.json'); 'execute' says how it is run --
                    'node shop.js deliver delivery.json'.
    collision       'delivery.json' and 'shop.js sell' both write the
                    database. SQLite lets one writer at a time hold the
                    file; one that waits too long fails with 'database
                    is locked'. hwut never runs the two at once.
    dependency      'shop.js report' runs after both, whatever their
                    verdict: it reports what they left.

STDERR  Every SQL statement is logged on stderr, as a server would. A
word on stderr fails a run ('unexpected stderr') unless the header says
'stderr_ignored = true': the words there are on purpose, and no error.

CHOICES

sell     three clerks sell at once, each in a worker thread of its own
         with a connection of its own. The sales are printed as '##!
         table unordered sep={;}': rows of 'item;qty', in any order -- and
         no column is a key, 'apple;1' stands four times.

report   the stock, as '##! table key=0 sep={;}', and the same rows
         written to 'stock.csv': 'output' names the file, hwut reads it
         after the run and compares it with its own GOOD. Then the frame
         log of the shop's tests: what 'on_before_test' and 'on_after_test'
         found around the delivery and the sale ('##! potpourri': which
         ran first is free), and before this report.

deliver  (no choice -- 'execute' of 'delivery.json' calls it) books a
         delivery note: every line on the stock and into the journal, in
         one transaction.

The database is node's own SQLite ('node:sqlite'); its 'experimental'
warning is the runtime's and is kept off stderr. node:sqlite has no trace
callback: every statement is logged by 'run' below.
______________________________________________________________________________
*/
'use strict';
const fs   = require('fs');
const path = require('path');
const { Worker, isMainThread, parentPort, workerData } = require('worker_threads');

const DB_PATH  = path.join(__dirname, 'TMP', 'shop.db');
const LOG_PATH = path.join(__dirname, 'TMP', 'frame.log');

//  What each clerk sells, one item per sale.
const CLERK_DB = { anna:  ['apple', 'apple', 'pear'],
                   ben:   ['apple', 'plum'],
                   chloe: ['apple'] };

/* RETURN: class, node's 'DatabaseSync', loaded without the runtime's
 *         'SQLite is an experimental feature' warning on stderr. */
function databaseClass() {
    const emit = process.emitWarning;
    process.emitWarning = (warning, ...rest) => {
        if (!/SQLite/.test(String(warning))) emit.call(process, warning, ...rest);
    };
    try     { return require('node:sqlite').DatabaseSync; }
    finally { process.emitWarning = emit; }
}

/* RETURN: DatabaseSync, a connection to the shop's database, waiting up to
 *         10 s for a writer to let go. Exits 1 where the database does not
 *         stand: 'on_entry' writes it. */
function connect() {
    if (!fs.existsSync(DB_PATH)) {
        process.stderr.write(`shop.js: no ${DB_PATH} -- 'on_entry' writes it; by hand: `
                             + "'hwut.execute fixture open'\n");
        process.exit(1);
    }
    const DatabaseSync = databaseClass();
    const db = new DatabaseSync(DB_PATH);
    db.exec('PRAGMA busy_timeout = 10000');
    return db;
}

/* RETURN: array of objects, the rows statement 'sql' returned with
 *         'parameter_list' bound -- the statement logged on stderr first. */
function run(db, sql, ...parameterList) {
    process.stderr.write(`sql: ${sql}${parameterList.length ? '  -- ' + JSON.stringify(parameterList) : ''}\n`);
    const statement = db.prepare(sql);
    return statement.columns().length ? statement.all(...parameterList) : (statement.run(...parameterList), []);
}

/* RETURN: undefined. Changes the stock of 'item' by 'delta' and journals
 *         it, in one transaction. */
function move(db, item, delta, source) {
    run(db, 'BEGIN IMMEDIATE');
    run(db, 'UPDATE stock SET qty = qty + ? WHERE item = ?', delta, item);
    run(db, 'INSERT INTO journal VALUES (?, ?, ?)', item, delta, source);
    run(db, 'COMMIT');
}

/* RETURN: undefined. Books the delivery note in 'file' and prints it. */
function deliver(file) {
    const note = JSON.parse(fs.readFileSync(file, 'utf8'));
    const db   = connect();
    run(db, 'BEGIN IMMEDIATE');
    for (const line of note.lines) {
        run(db, 'UPDATE stock SET qty = qty + ? WHERE item = ?', line.qty, line.item);
        run(db, 'INSERT INTO journal VALUES (?, ?, ?)', line.item, line.qty, note.note);
    }
    run(db, 'COMMIT');
    console.log(`delivery note ${note.note} from ${note.supplier}:`);
    for (const line of note.lines) console.log(`    ${line.item.padEnd(6)} +${line.qty}`);
}

/* RETURN: undefined. ONE CLERK, in a worker thread: sells 'item_list',
 *         each sale posted to the main thread as it is booked -- or the
 *         error that stopped it. */
function clerk({ name, item_list }) {
    try {
        const db = connect();
        for (const item of item_list) {
            move(db, item, -1, name);
            parentPort.postMessage({ sale: `${item};1` });
        }
        db.close();
    } catch (error) {
        parentPort.postMessage({ error: `${name}: ${error.message}` });
    }
}

/* RETURN: Promise of undefined. Three clerks sell at once; prints every
 *         sale in the order booked. */
async function sell() {
    const saleList = [], errorList = [];
    connect().close();
    const pool = Object.entries(CLERK_DB).map(([name, item_list]) => new Promise(resolve => {
        const worker = new Worker(__filename, { workerData: { name, item_list } });
        worker.on('message', m => m.sale ? saleList.push(m.sale) : errorList.push(m.error));
        worker.on('error', error => errorList.push(`${name}: ${error.message}`));
        worker.on('exit', resolve);
    }));
    await Promise.all(pool);
    if (errorList.length) {
        process.stderr.write(`shop.js: a sale failed -- ${errorList.join('; ')}\n`);
        process.exit(1);
    }
    console.log('sales, item;qty -- in the order the clerks booked them:');
    console.log('##! table unordered sep={;}');
    for (const row of saleList) console.log(row);
    console.log('####');
}

/* RETURN: undefined. Prints the stock and the frame log; writes
 *         'stock.csv'. */
function report() {
    const db = connect();
    const rowList = run(db, 'SELECT item, qty FROM stock ORDER BY qty, item');
    const sorted  = [...rowList].sort((a, b) => a.item < b.item ? -1 : a.item > b.item ? 1 : 0);
    fs.writeFileSync(path.join(__dirname, 'stock.csv'),
                     'item;qty\n' + sorted.map(r => `${r.item};${r.qty}\n`).join(''));
    console.log('stock, item;qty (also written to stock.csv):');
    console.log('##! table key=0 sep={;}');
    for (const r of rowList) console.log(`${r.item};${r.qty}`);
    console.log('####');
    const lineList = fs.readFileSync(LOG_PATH, 'utf8').split('\n').filter(l => l !== '').map(l => l.trimEnd());
    console.log('the frame, around the delivery and the sale:');
    console.log('##! potpourri');
    for (const line of lineList) if (!line.includes('shop.js report')) console.log(line);
    console.log('####');
    for (const line of lineList) if (line.includes('shop.js report')) console.log(line);
}

/* RETURN: Promise of undefined; the command of the command line done and
 *         '<hwut-end>' printed -- exit status 1 and the choices named, where
 *         it names none. */
async function main() {
    const command = process.argv[2] || '';
    if      (command === 'deliver') deliver(process.argv[3]);
    else if (command === 'sell')    await sell();
    else if (command === 'report')  report();
    else {
        console.log('choices: sell, report');
        process.exit(1);
    }
    console.log('<hwut-end>');
}

if (isMainThread) main();
else              clerk(workerData);
