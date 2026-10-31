// @hwut {
//     title      = "HOCON parser: subset (A), annotated tree"
//     choices {
//         comments  { features = ["node-hocon"] }
//         faults    { features = ["node-hocon"] }
//         fuzz      { features = ["node-hocon"] }
//         numbers   { features = ["node-hocon"] }
//         oneline   { features = ["node-hocon"] }
//         positions { features = ["node-hocon"] }
//         quoting   { features = ["node-hocon"] }
//         refused   { features = ["node-hocon"] }
//         scalars   { features = ["node-hocon"] }
//         structure { features = ["node-hocon"] }
//         triple    { features = ["node-hocon"] }
//         unclosed  { features = ["node-hocon"] }
//     }
//     interactive = true
// }
//
// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
//_____________________________________________________________________________
//
// PURPOSE: The node port of 'python/TEST/test-hwut_hocon.py', choice for
//          choice, held against its GOOD files by '.link'. 'fuzz' bounds each
//          parse by a 'vm' script timeout -- node's way to interrupt running
//          code, where Python sets an interval timer.
//_____________________________________________________________________________
'use strict';
const path = require('path');
const vm   = require('vm');
const { HwutRunner } = require(path.join(__dirname, '..', 'hwut_runner.js'));
const { parse, SourceLine, ListNode, ObjectNode } = require(path.join(__dirname, '..', 'hwut_hocon.js'));
const { DeterministicStream } = require(path.join(__dirname, '..', 'deterministic_random.js'));

const say    = text => console.log(text);
const banner = label => say(`\n--- ${label} ---`);

/* RETURN: array of SourceLine, 'text' split at '\n', offsets applied uniformly. */
function lines(text, lineOffset = 0, columnOffset = 0) {
    return text.split('\n').map((line, i) => new SourceLine(line, i + 1 + lineOffset, columnOffset));
}

/* RETURN: undefined. Prints the annotated tree, positions included. */
function show(node, indent = 0) {
    const pad = '    '.repeat(indent);
    if (node instanceof ObjectNode) {
        say(`${pad}{ at ${node.position}`);
        for (const entry of node.entry_list) {
            say(`${pad}  key '${entry.key}' at ${entry.key_position} ->`);
            show(entry.node, indent + 1);
        }
        say(`${pad}}`);
    } else if (node instanceof ListNode) {
        say(`${pad}[ at ${node.position}`);
        for (const item of node.item_list) show(item, indent + 1);
        say(`${pad}]`);
    } else {
        say(`${pad}${node.repr()} (${node.py_type}) at ${node.position}`);
    }
}

/* RETURN: undefined. Parses 'text' and prints tree and faults. */
function run(label, text, lineOffset = 0, columnOffset = 0) {
    banner(label);
    const [document, faultList] = parse(lines(text, lineOffset, columnOffset), 'f.hocon');
    show(document);
    for (const fault of faultList) say(`FAULT ${fault}`);
}

function testScalars() {
    run('scalars',
        'a = bare\n'
        + 'b = "quoted \\"x\\" and \\n"\n'
        + 'c = 42\n'
        + 'd = -3.14\n'
        + 'e = 1e-6\n'
        + 'f = true\n'
        + 'g = no\n'
        + 'h = make %.exe\n'
        + 'i: "colon-bound"\n'
        + 'j = null\n'
        + 'k = nihil\n'
        + 'l =\n');
}

function testNumbers() {
    run('decimal, with sign and exponent',
        'a = 42\nb = -0.12\nc = +7e212\nd = 6.02e23\ne = .5\n');
    run('the visual helper enters no value',
        'a = 1_000\nb = 7_000.5_5\n');
    run('hexadecimal, binary, octal',
        'a = 0xDEAD_BEEF\nb = 0b0111_11_01\nc = 0o3124\nd = 0XFF\ne = -0b1010\n');
    run('roman',
        'a = 0rIV\nb = 0rMCMLXXXIV\nc = -0rX\n');
    run('a sign standing apart from its digits',
        'a = - 0.12\nb = + 7\nc = - 0xFF\nd = - -1.5e3\n');
    run('what spells no number is a string, and carries quotes',
        'a = 1.2.3\nb = 0x\nc = 0b012\nd = 1__0\ne = 0rIIII\nf = 0rVX\n');
    run('no arithmetic: this language computes nothing',
        'a = 5 - 1\n');
}

function testQuoting() {
    run('quoted: blanks, comment markers and binders are content',
        'a = "make %.exe"\nb = "not # a comment"\nc = "x = y"\nd = "yes"\n');
    run('unquoted: refused, and shown in the quotes it wants',
        'a = make\nb = strip.pype\nc = [one, two]\nd = 1\n');
}

function testStructure() {
    run('nesting and key-brace',
        'outer {\n'
        + '    inner = { deep = 1 }\n'
        + '    braced { x = 2 }\n'
        + '}\n');
    run('lists',
        'commas   = [one, two, three]\n'
        + 'newlines = [\n'
        + '    1\n'
        + '    2\n'
        + ']\n'
        + 'objects  = [ { a = 1 }, { a = 2 } ]\n'
        + 'empty    = []\n');
}

function testOneline() {
    run('two entries, one line, no comma',
        'caps { timeout_sec = 30  network = false }\n');
    run('a quoted value with blanks, beside a following key',
        'a { build = "make %.exe"  timeout_sec = 5 }\n');
    run('three entries, one line',
        'x { a = 1  b = "two"  c = { d = 3 } }\n');
}

function testComments() {
    run('comments',
        '# whole line\n'
        + 'a = 1   # trailing\n'
        + '// slashes too\n'
        + 'b = 2   // trailing slashes\n'
        + 'c = bare value # comment cut\n');
}

function testRefused() {
    run('refused, each by name',
        'include "other.conf"\n'
        + 'a = ${outside.value}\n'
        + 'b += appended\n'
        + 'd = survives\n');
}

function testTriple() {
    const q = '"""';
    run('several lines: indentation and blank ends go',
        `doc = ${q}\n`
        + '    First line.\n'
        + '\n'
        + '      indented more\n'
        + '    last line\n'
        + `    ${q}\n`
        + 'after = 1\n');
    run('on one line; beside another entry; in a list',
        `a = ${q}one line${q}  b = 2\n`
        + `c = [${q}x${q}, "y"]\n`);
    run('as written: a quote, a backslash-n, a comment marker',
        `a = ${q}says "no" \\n # not a comment${q}\n`);
    run('never closed: a fault, at its beginning',
        'a = 1\n'
        + `b = ${q}open\n`
        + 'c = 2\n');
}

function testFaults() {
    run('faults accumulate',
        'a = 1\n'
        + 'a = 2\n'
        + 'b = "unterminated\n'
        + '}\n'
        + 'c {\n'
        + '    d = 3\n');
}

function testUnclosed() {
    run("a list closed by the object's brace",
        '@hwut { title = "B" choices = [ }\n'
        + 'after = 1\n');
    run('a stray character in a list',
        'a = [1, ; 2]\n');
}

const FUZZ_SEED_TUPLE = [
    '@hwut {\n'
    + '    title    = "T"\n'
    + '    choices  = ["a", "b"]\n'
    + '    tolerance { eq_pattern = ["x.*"] }\n'
    + '    n        = -1.5e3\n'
    + '    f        = true\n'
    + '}\n',
    'hwut {\n'
    + '    target     { clean = "./c.sh" }\n'
    + '    dependency { "a.py" = ["b.py one"] }\n'
    + '    ignore     = ["x"]   // comment\n'
    + '    # comment\n'
    + '}\n'];
//  WHAT A TYPO IS MADE OF: the characters HOCON gives meaning to, a few
//  that it refuses by name, and some ordinary ones.
const FUZZ_ALPHABET = [...'{}[]",=:#/\\$ \n\t-+.eE0a', '"""', '${', '//', '+='];
const FUZZ_INPUT_N  = 3000;
const FUZZ_BOUND_MS = 500;            // one parse takes well under a millisecond

/* RETURN: string, 'text' edited by one to four random insertions, deletions
 *         and duplications of a short stretch. */
function mutated(stream, text) {
    const n = stream.next_int(1, 4);
    for (let k = 0; k < n; k += 1) {
        const i = stream.next_int(0, text.length);
        switch (stream.next_int(0, 2)) {
        case 0:  text = text.slice(0, i) + stream.select(FUZZ_ALPHABET) + text.slice(i); break;
        case 1:  text = text.slice(0, i) + text.slice(i + 1); break;
        default: {
            const j = stream.next_int(0, text.length);
            text = text.slice(0, i) + text.slice(j, j + 5) + text.slice(i);
        }
        }
    }
    return text;
}

function testFuzz() {
    //  THE BOUND: a 'vm' script with a timeout interrupts even a parse that
    //  loops -- node's counterpart of Python's SIGALRM.
    const context = vm.createContext({ parse, lines, text: '', result: null });
    const script  = new vm.Script('result = parse(lines(text), "f.hocon")');
    const stream  = new DeterministicStream(4711);
    const tally   = { 'clean': 0, 'with faults': 0, 'hang': 0, 'exception': 0 };
    const example = {};
    for (let k = 0; k < FUZZ_INPUT_N; k += 1) {
        const text = mutated(stream, stream.select(FUZZ_SEED_TUPLE));
        context.text = text;
        try {
            script.runInContext(context, { timeout: FUZZ_BOUND_MS });
            const [, faultList] = context.result;
            tally[faultList.length ? 'with faults' : 'clean'] += 1;
        } catch (error) {
            if (error && error.code === 'ERR_SCRIPT_EXECUTION_TIMEOUT') {
                tally.hang += 1;
                if (!('hang' in example)) example.hang = text;
            } else {
                tally.exception += 1;
                if (!('exception' in example))
                    example.exception = `${error && error.name}: ${error && error.message}\n${text}`;
            }
        }
    }
    banner(`${FUZZ_INPUT_N} mutated headers`);
    for (const [key, n] of Object.entries(tally)) say(`    ${key.padEnd(12)} ${n}`);
    for (const [key, text] of Object.entries(example)) say(`FIRST ${key.toUpperCase()}:\n${text}`);
}

function testPositions() {
    const text = '@hwut {\n'
               + '    title = "T"\n'
               + '}';
    run('plain: as its own file', text);
    run('offset: same text, region begins at line 40, 3 columns stripped', text, 39, 3);
}

new HwutRunner({
    argv:       process.argv.slice(1),
    title:      'HOCON parser: subset (A), annotated tree;',
    choice_map: {
        scalars:   testScalars,
        numbers:   testNumbers,
        quoting:   testQuoting,
        structure: testStructure,
        oneline:   testOneline,
        comments:  testComments,
        refused:   testRefused,
        triple:    testTriple,
        unclosed:  testUnclosed,
        fuzz:      testFuzz,
        faults:    testFaults,
        positions: testPositions,
    },
}).run();
