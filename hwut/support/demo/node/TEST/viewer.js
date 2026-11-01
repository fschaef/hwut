#! /usr/bin/env node
/*
______________________________________________________________________________
A TERMINAL FILE VIEWER -- the program 'screen.js' tests; no test itself.

    node viewer.js <file>

Full screen, on the terminal's alternate screen: a title bar (reverse
video), as many lines of the file as fit, and a status line: the keys
flush left, the lines shown flush right. Keys: 'j' or down one line
further, 'k' or up one line back, 'q' quits.

Every write goes straight to fd 1 ('fs.writeSync'): the screen stands as
drawn before the next key is read.
______________________________________________________________________________
*/
'use strict';
const fs   = require('fs');
const path = require('path');

/* RETURN: undefined. Draws the whole screen with the file's line 'top'
 *         first. */
function draw(name, lineList, top, rowN, columnN) {
    const bodyN = rowN - 2;
    const shown = lineList.slice(top, top + bodyN);
    let out = '\x1b[H\x1b[2J';
    out += `\x1b[7m${(' ' + name).padEnd(columnN).slice(0, columnN)}\x1b[0m\r\n`;
    for (const line of shown) out += line.slice(0, columnN) + '\r\n';
    out += '\r\n'.repeat(bodyN - shown.length);
    const where = `lines ${top + 1}-${top + shown.length} of ${lineList.length}`;
    const keys  = 'j k q';
    out += `\x1b[${rowN};1H${keys}${where.padStart(columnN - 1 - keys.length)}`;
    fs.writeSync(1, out);
}

/* RETURN: undefined. Shows 'file' until 'q' is pressed; the process then
 *         ends with status 0, the terminal as it was. */
function main(file) {
    const lineList = fs.readFileSync(file, 'utf8').split(/\r?\n/);
    if (lineList.length && lineList[lineList.length - 1] === '') lineList.pop();
    const columnN = process.stdout.columns, rowN = process.stdout.rows;
    const name    = path.basename(file);
    let top = 0;
    process.stdin.setRawMode(true);
    fs.writeSync(1, '\x1b[?1049h');
    draw(name, lineList, top, rowN, columnN);
    process.stdin.on('data', key => {
        const text = key.toString('latin1');
        if (text === 'q') {
            fs.writeSync(1, '\x1b[?1049l');
            process.stdin.setRawMode(false);
            process.exit(0);
        }
        if (text === 'j' || text === '\x1b[B') top = Math.min(top + 1, Math.max(0, lineList.length - (rowN - 2)));
        else if (text === 'k' || text === '\x1b[A') top = Math.max(top - 1, 0);
        draw(name, lineList, top, rowN, columnN);
    });
}

main(process.argv[2]);
