#! /usr/bin/env node
/*
______________________________________________________________________________
THE SHOP'S FIXTURE -- no test, a helper the directory's 'hwut.conf' calls.

    node fixture.js open       a fresh 'TMP/shop.db', stocked as below, and
                               an empty 'TMP/frame.log' ('on_entry', and
                               'hwut.execute fixture open')
    node fixture.js close      both removed ('on_exit')
    node fixture.js check <when> <app> [<choice>]
                               'when' is 'before' or 'after': whether the
                               stock adds up around the test run '<app>
                               <choice>', appended to 'TMP/frame.log'
                               ('on_before_test', 'on_after_test')

'hwut.conf' passes '<app>' and '<choice>' as '$HWUT_TEST $HWUT_CHOICE',
which hwut sets for the run the check stands around; a test without
choices has none. 'check' concerns the shop's tests alone. The stock
ADDS UP where every item's quantity is its opening quantity plus every
movement of the journal.

The database is node's own SQLite ('node:sqlite', node 22.5 and later); its
'experimental' warning is the runtime's, no word of the fixture, and is
kept off stderr.
______________________________________________________________________________
*/
'use strict';
const fs   = require('fs');
const path = require('path');

const DB_PATH    = path.join(__dirname, 'TMP', 'shop.db');
const LOG_PATH   = path.join(__dirname, 'TMP', 'frame.log');
const OPENING_DB = { apple: 10, pear: 5, plum: 5 };
const SHOP_TEST_LIST = ['delivery.json', 'shop.js'];

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

/* RETURN: undefined. 'file' removed, where it stands. */
const removed = file => { if (fs.existsSync(file)) fs.unlinkSync(file); };

/* RETURN: undefined. Writes a fresh, stocked database and an empty log. */
function openShop() {
    fs.mkdirSync(path.dirname(DB_PATH), { recursive: true });
    removed(DB_PATH); removed(LOG_PATH);
    const DatabaseSync = databaseClass();
    const db = new DatabaseSync(DB_PATH);
    db.exec('CREATE TABLE opening (item TEXT PRIMARY KEY, qty INTEGER)');
    db.exec('CREATE TABLE stock   (item TEXT PRIMARY KEY, qty INTEGER)');
    db.exec('CREATE TABLE journal (item TEXT, delta INTEGER, source TEXT)');
    for (const [item, qty] of Object.entries(OPENING_DB)) {
        db.prepare('INSERT INTO opening VALUES (?, ?)').run(item, qty);
        db.prepare('INSERT INTO stock   VALUES (?, ?)').run(item, qty);
    }
    db.close();
    fs.writeFileSync(LOG_PATH, '');
}

/* RETURN: undefined. Removes the database and the log. */
function closeShop() {
    removed(DB_PATH); removed(LOG_PATH);
}

/* RETURN: true, if every item's stock is its opening quantity plus its
 *               journal's movements;
 *         false, else. */
function addsUp() {
    const DatabaseSync = databaseClass();
    const db = new DatabaseSync(DB_PATH);
    db.exec('PRAGMA busy_timeout = 10000');
    const rowList = db.prepare(
        'SELECT o.item, o.qty + COALESCE(SUM(j.delta), 0) AS expected, s.qty AS got'
        + '  FROM opening o JOIN stock s ON s.item = o.item'
        + '  LEFT JOIN journal j ON j.item = o.item GROUP BY o.item').all();
    db.close();
    return rowList.every(row => row.expected === row.got);
}

/* RETURN: undefined. Appends one line to the log for a shop test run;
 *         nothing for any other test. */
function check(when, test, choice = '') {
    if (!SHOP_TEST_LIST.includes(test)) return;
    const run = `${test} ${choice || ''}`.trim();
    fs.appendFileSync(LOG_PATH, `${when.padEnd(6)} ${run.padEnd(15)} ${addsUp() ? 'stock adds up' : 'STOCK BROKEN'}\n`);
}

const command = process.argv[2] || '';
if      (command === 'open')  openShop();
else if (command === 'close') closeShop();
else if (command === 'check') check(...process.argv.slice(3, 6));
else {
    process.stderr.write('usage: fixture.js open | close | check before|after <app> <choice>\n');
    process.exit(2);
}
