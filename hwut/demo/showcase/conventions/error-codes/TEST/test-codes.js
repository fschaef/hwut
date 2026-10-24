#! /usr/bin/env node
//
// @hwut {
//     title    = "Error codes: unique across C, JavaScript and Python, each in its range, each documented"
//     features = ["unique", "in-range", "documented"]
//     choices {
//         good   { tolerance { constraints = ["findings == 0"] } }
//         broken { tolerance { constraints = ["findings > 0"] } }
//     }
// }
//
// ____________________________________________________________________________
// SUBJECT  the error-code space of one C/JavaScript/Python code base
//          (good/broken): each code defined, in range, documented
// REQUIREMENT: error codes are a public interface -- a support engineer
// looks up '1004' in docs/errors.md and must find exactly one meaning.
//
//   E1  a code value is defined once in the whole code base
//   E2  a code lies in the range of the component that defines it
//       (fw 1000..1999, web 2000..2999, tools 3000..3999)
//   E3  every defined code is documented in docs/errors.md, under its name
//   E4  every documented code is defined somewhere (no ghost entries)
//
// HOW: Node.js -- hwut does not care -- reads three languages with three
// regular expressions (C '#define ERR_x n', JavaScript 'const E_x = n',
// Python enum members 'NAME = n') and the Markdown table of the docs. It
// prints
//   1. the CODE SPACE: one strip per range, one cell per code 0..15 of it
//        .  free   o  defined and documented   u  defined, undocumented
//        g  documented, defined nowhere   D  defined more than once
//   2. the CROSS REFERENCE, sorted by code: name, where defined, documented;
//   3. the findings by rule, and two counts.
//
// CHOICES
//   good     twelve codes, all unique, in range and documented.
//   broken   the web backend reuses 1004 for E_SESSION_EXPIRED (E1, E2),
//            E_RATE_LIMIT was deleted but stays documented (E4), the tools
//            gained DISK_FULL = 3003 without a line in the docs (E3); and
//            1004 is documented as ERR_NO_MEMORY, so E_SESSION_EXPIRED is
//            not documented under its own name (E3 again).
//
// HWUT CONCEPTS
//   constraints  'findings == 0' for good -- the requirement; 'findings > 0'
//                for broken -- the violation is reported, the FINDING lines
//                say which. The code count is exact text ('codes: 12').
//   exact lines  strip and table; a cell of the strip is one code.
//   language     a Node.js application with a '//' @hwut block, run through
//                its shebang.
//
// READING THE GOOD: in the strips, any letter other than 'o'; in the table,
// the right-hand column.
// ____________________________________________________________________________
'use strict';
const fs = require('fs');
const path = require('path');

const RANGE_LIST = [['fw', 1000], ['web', 2000], ['tools', 3000]];
const READER_LIST = [
    ['fw/errors.h',     /^#define\s+(ERR_\w+)\s+(\d+)/],
    ['web/errors.js',   /^const\s+(E_\w+)\s*=\s*(\d+)/],
    ['tools/errors.py', /^\s+([A-Z_]+)\s*=\s*(\d+)/],
];

function main(choice) {
    const root = path.join(__dirname, '..', choice);
    const defList = [];                                  // {code, name, where, component}
    for (const [file, rx] of READER_LIST) {
        fs.readFileSync(path.join(root, file), 'utf8').split('\n').forEach((line, i) => {
            const m = line.match(rx);
            if (m) defList.push({ code: +m[2], name: m[1], where: `${file}:${i + 1}`,
                                  component: file.split('/')[0] });
        });
    }
    const docDb = new Map();                             // code -> name
    for (const line of fs.readFileSync(path.join(root, 'docs/errors.md'), 'utf8').split('\n')) {
        const m = line.match(/^\|\s*(\d+)\s*\|\s*(\w+)\s*\|/);
        if (m) docDb.set(+m[1], m[2]);
    }
    const byCode = new Map();
    for (const d of defList) byCode.set(d.code, [...(byCode.get(d.code) || []), d]);

    console.log(`error codes of '${choice}': ${defList.length} defined, ${docDb.size} documented`);
    console.log('');
    console.log('CODE SPACE   . free  o defined+documented  u undocumented  g ghost  D defined twice');
    console.log('             r N  a code this component defines with a value N outside its range');
    console.log('             offset  0000000000111111   (decimal)');
    console.log('                     0123456789012345');
    for (const [component, base] of RANGE_LIST) {
        let strip = '';
        for (let k = 0; k < 16; k++) {
            const code = base + k, n = (byCode.get(code) || []).length;
            strip += n > 1 ? 'D' : n === 1 ? (docDb.has(code) ? 'o' : 'u') : docDb.has(code) ? 'g' : '.';
        }
        const outside = defList.filter(d => d.component === component && (d.code < base || d.code > base + 999));
        console.log(`  ${String(base).padEnd(5)} ${component.padEnd(6)} |${strip}|` +
                    outside.map(d => `  r ${d.code}`).join(''));
    }
    console.log('');
    console.log('CROSS REFERENCE (sorted by code)');
    console.log('  code  name               defined at             documented as');
    const finding = [];
    const codeList = [...new Set([...byCode.keys(), ...docDb.keys()])].sort((a, b) => a - b);
    for (const code of codeList) {
        const dList = byCode.get(code) || [{ name: '-', where: '(nowhere)' }];
        for (const d of dList) {
            const doc = docDb.has(code) ? (docDb.get(code) === d.name ? 'yes' : `as ${docDb.get(code)}`) : 'NO';
            console.log(`  ${code}  ${d.name.padEnd(18)} ${d.where.padEnd(22)} ${doc}`);
            if (d.component) {
                const [, base] = RANGE_LIST.find(([c]) => c === d.component);
                if (code < base || code > base + 999)
                    finding.push(`E2  ${d.name} = ${code} lies outside ${d.component} ${base}..${base + 999}`);
                if (!docDb.has(code))
                    finding.push(`E3  ${d.name} = ${code} is not documented`);
                else if (docDb.get(code) !== d.name)
                    finding.push(`E3  ${d.name} = ${code} is documented as ${docDb.get(code)}`);
            }
        }
        if (dList.length > 1)
            finding.push(`E1  ${code} is defined ${dList.length} times: ${dList.map(d => d.name).join(', ')}`);
        if (!byCode.has(code))
            finding.push(`E4  ${code} ${docDb.get(code)} is documented, defined nowhere`);
    }
    console.log('');
    console.log('E1 unique   E2 in its range   E3 documented   E4 no ghost entry');
    for (const f of finding.sort()) console.log('FINDING ' + f);
    console.log(`codes: ${defList.length}   ((findings: ${finding.length}))   law == 0   ` +
                (finding.length === 0 ? 'kept' : 'BROKEN'));
}

const choice = process.argv[2] || '';
if (!['good', 'broken'].includes(choice)) {
    console.log('choices: good, broken');
    process.exit(1);
}
main(choice);
console.log('<hwut-end>');
