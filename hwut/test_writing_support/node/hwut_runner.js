// SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
//_____________________________________________________________________________
//
// PURPOSE: FRONT END OF A HWUT TEST APPLICATION IN NODE.JS -- the port of
//          'python/hwut_runner.py', the same modes, the same words:
//
//     app --hwut-info      the info block; exit 0.
//     app <choice>         one choice; test output on stdout and stderr,
//                          '<hwut-end>' after it. '-' runs a choice-less test.
//     app --interactive    choices started over stdin, output into two named
//                          sink files per choice, 'done' on the original stdout.
//     app                  the choice-less test; where the application has
//                          choices, refused, naming them.
//
// USAGE:
//
//     const path = require('path');
//     const { HwutRunner } = require(path.join(__dirname, '..', 'hwut_runner.js'));
//     new HwutRunner({
//         argv:       process.argv.slice(1),      // as Python's 'sys.argv'
//         title:      "What this application tests",
//         choice_map: { plain: runPlain, tricky: runTricky },
//     }).run();
//
// 'choice_map' maps a choice name to a function -- plain or 'async' (a
// returned promise is awaited, as Python's runner runs a coroutine function
// by 'asyncio.run'); the key '-' alone stands for a choice-less test. 'happy'
// (string, RegExp, or an array of them), 'same_f' and 'parallel' ('process':
// choices run concurrently) are as in Python.
//
// THE INTERACTIVE PROTOCOL is Python's, line for line:
//     DOWN  run <choice> <sink-out> <sink-err> | info | quit | q | exit
//     UP    done <choice> <status> | fail <choice> <reason> | info: <line> | bye
//
// ONE CHILD PROCESS PER CHOICE (where node differs): node cannot point its
// own descriptors 1 and 2 at a file ('dup2' is not in its library). So in
// interactive mode every choice runs in a child -- this application again,
// 'node <app> <choice>' -- whose descriptors 1 and 2 ARE the two sinks. What
// the choice writes, and what processes it spawns write, lands in the sinks
// as in Python; 'process.exit(n)' in a choice ends that choice alone, with
// status n, as SystemExit does; an uncaught exception gives status 1 and its
// stack in the error sink. Without 'parallel' the session waits for each
// child before it reads the next command (Python's sequential scheme); with
// 'parallel: "process"' it does not, and reports 'done' as children end.
//_____________________________________________________________________________
'use strict';

const fs       = require('fs');
const os       = require('os');
const path     = require('path');
const readline = require('readline');
const { spawn } = require('child_process');

const NONE      = '-';                       // the choice-less test's key
const CHILD_ENV = 'HWUT_NODE_RUNNER_SINK';   // set for the child of a 'run'

class HwutRunner {
    /* RETURN: HwutRunner, ready for '.run()'; throws Error where 'choice_map'
     *         is missing or empty, where '-' does not stand alone, or where
     *         'parallel' is neither undefined/null nor 'process'.
     *
     * 'argv'        the command line as Python's 'sys.argv' -- the script,
     *               then the arguments (default 'process.argv.slice(1)').
     * 'title'       title line of the info block.
     * 'choice_map'  choice name -> function; '-' alone: choice-less.
     * 'happy'       pattern(s) for the info block's 'HAPPY:' lines.
     * 'same_f'      true => the info block carries 'SAME;'.
     * 'parallel'    undefined -- choices one after another; 'process' --
     *               concurrently. */
    constructor({ argv, title, choice_map, happy, same_f, parallel } = {}) {
        if (!choice_map || Object.keys(choice_map).length === 0)
            throw new Error("HwutRunner: no 'choice_map'");
        if (NONE in choice_map && Object.keys(choice_map).length > 1)
            throw new Error("HwutRunner: '-' stands for the choice-less test and stands alone");
        if (parallel !== undefined && parallel !== null && parallel !== 'process')
            throw new Error("HwutRunner: 'parallel' is undefined or 'process'");
        this.argv       = argv || process.argv.slice(1);
        this.title      = title || '';
        this.choice     = this.argv.length < 2 ? null : this.argv[1];
        this.choice_map = choice_map;
        this.parallel   = parallel || null;
        this.same_f     = !!same_f;
        const list      = happy === undefined || happy === null ? [] : Array.isArray(happy) ? happy : [happy];
        this.happy      = list.map(h => h instanceof RegExp ? h.source : String(h));
        this.sorted_choice_list = NONE in choice_map ? [NONE] : Object.keys(choice_map).sort();
        this._pending   = new Set();         // promises of running children
    }

    /* RETURN: Promise of undefined. Dispatches on the first command line
     *         argument (see the head of this file); the process's exit
     *         status is set by the mode. */
    async run() {
        const word = this.choice;
        if (['-h', '--hi', '--hwut-info', '--sos', '--wtf'].includes(word)) return this.MODE_hwut_info();
        if (word === '--interactive')            return this.MODE_interactive();
        if (word === null)
            return NONE in this.choice_map ? this.MODE_run_test(NONE) : this.MODE_choice_missing();
        if (word in this.choice_map && Object.prototype.hasOwnProperty.call(this.choice_map, word))
            return this.MODE_run_test(word);
        return this.MODE_choice_does_not_exist(word);
    }

    /* RETURN: never; exits with status 1. The application has choices and
     *         the command line names none. */
    MODE_choice_missing() {
        writeOut(`error: a choice is required: ${this.sorted_choice_list.join(', ')}`
                 + " -- name one, or let 'hwut.play' ask.\n");
        process.exit(1);
    }

    /* RETURN: never; exits with status 1. Names the unavailable choice, the
     *         available ones and the closest by Levenshtein distance. */
    MODE_choice_does_not_exist(word) {
        if (NONE in this.choice_map) {
            writeOut(`error: '${word}': this application has no choices -- call it without one.\n`);
            process.exit(1);
        }
        writeOut(`error: choice '${word}' not available.\n`);
        writeOut(`error: available: ${this.sorted_choice_list.join(', ')}.\n`);
        const best = levenshteinBestMatch(word, this.sorted_choice_list);
        if (best !== null) writeOut(`error: did you mean '${best}'?\n`);
        process.exit(1);
    }

    /* RETURN: Promise of undefined; resolved when the choice's function (and
     *         the promise it returned) has ended, '<hwut-end>' printed after
     *         it (R-70). In the child of an interactive 'run' the token is
     *         left out where HWUT_NO_TERMINAL is set (a pype owns stdout). An
     *         exception is printed to stderr with its stack, exit status 1,
     *         and no '<hwut-end>'. */
    async MODE_run_test(choice) {
        const childF = !!process.env[CHILD_ENV];
        delete process.env[CHILD_ENV];
        try {
            await this.choice_map[choice]();
        } catch (error) {
            process.stderr.write((error && error.stack ? error.stack : String(error)) + '\n');
            process.exit(1);
        }
        if (!childF || !process.env.HWUT_NO_TERMINAL) writeOut('<hwut-end>\n');
    }

    /* RETURN: never; exits with status 0. Prints the info block. */
    MODE_hwut_info() {
        for (const line of this.info_block_lines()) writeOut(line + '\n');
        process.exit(0);
    }

    /* RETURN: array of strings, the lines of the info block: title, CHOICES,
     *         HAPPY, SAME, INTERACTIVE -- each ending in ';'. */
    info_block_lines() {
        const result = [this.title.endsWith(';') ? this.title : this.title + ';'];
        if (!(NONE in this.choice_map)) result.push('CHOICES: ' + this.sorted_choice_list.join(', ') + ';');
        for (const h of this.happy) result.push('HAPPY: ' + h + ';');
        if (this.same_f) result.push('SAME;');
        result.push('INTERACTIVE;');
        return result;
    }

    /* RETURN: Promise of undefined; resolved when the session ends ('quit'
     *         or the end of stdin) and every child is reported, 'bye' last.
     *         Descriptor 1 stays the UP channel; what this process writes to
     *         'process.stdout'/'process.stderr' during the session goes to a
     *         stray sink (a temp file), never into the protocol. */
    async MODE_interactive() {
        const strayPath = path.join(os.tmpdir(), `hwut_stray_${process.pid}_${Date.now()}.txt`);
        const strayFd   = fs.openSync(strayPath, 'w', 0o600);
        const toStray   = (chunk, encoding, callback) => {
            fs.writeSync(strayFd, typeof chunk === 'string' ? chunk : Buffer.from(chunk));
            const cb = typeof encoding === 'function' ? encoding : callback;
            if (cb) cb();
            return true;
        };
        process.stdout.write = toStray;
        process.stderr.write = toStray;

        const input = readline.createInterface({ input: process.stdin, crlfDelay: Infinity, terminal: false });
        for await (const raw of input) {
            const line = raw.trim();
            if (!line) continue;
            if (!(await this._interprete(line))) break;
        }
        input.close();
        await Promise.all([...this._pending]);
        this._up('bye');
        process.stdin.destroy();
    }

    /* RETURN: Promise of boolean, true -- the session goes on, false -- it
     *         ends. Interpretes one DOWN command line; answers on the UP
     *         channel; never throws. */
    async _interprete(line) {
        const field = line.split(/\s+/);
        if (field.length === 1 && ['quit', 'q', 'exit'].includes(field[0])) return false;
        if (field.length === 1 && field[0] === 'info') {
            for (const l of this.info_block_lines()) this._up('info: ' + l);
            this._up('done - 0');
            return true;
        }
        if (field.length === 4 && field[0] === 'run') {
            const [, token, sinkOut, sinkErr] = field;
            const [choice, foundF] = this._find_choice(token);
            if (!foundF) { this._up(`fail ${token} unknown-choice`); return true; }
            const done = this._run_into_sinks(choice, sinkOut, sinkErr)
                             .then(status => this._up(`done ${token} ${status}`));
            if (this.parallel === 'process') {
                this._pending.add(done);
                done.then(() => this._pending.delete(done));
            } else {
                await done;
            }
            return true;
        }
        this._up('fail - bad-command');
        return true;
    }

    /* RETURN: [choice, true] where 'token' names a choice -- by name, by a
     *         decimal index into the sorted choice list, or '-' for the
     *         choice-less test; [null, false] else. */
    _find_choice(token) {
        const own = k => Object.prototype.hasOwnProperty.call(this.choice_map, k);
        if (token === NONE) return [NONE, own(NONE)];
        if (own(token))     return [token, true];
        if (/^\d+$/.test(token)) {
            const i = parseInt(token, 10);
            if (i < this.sorted_choice_list.length) return [this.sorted_choice_list[i], true];
        }
        return [null, false];
    }

    /* RETURN: Promise of integer, the exit status of the child that ran
     *         'choice' with descriptors 1 and 2 on the sink files (created,
     *         truncated): 0 where the choice returned, n where it called
     *         'process.exit(n)', 1 where it threw, minus the signal number
     *         where a signal ended it; 1 where a sink cannot be opened. When
     *         it resolves, the child has ended and both sinks are closed --
     *         the 'done' barrier. */
    _run_into_sinks(choice, sinkOut, sinkErr) {
        let outFd, errFd;
        try {
            outFd = fs.openSync(sinkOut, 'w', 0o644);
            errFd = fs.openSync(sinkErr, 'w', 0o644);
        } catch (error) {
            if (outFd !== undefined) fs.closeSync(outFd);
            return Promise.resolve(1);
        }
        return new Promise(resolve => {
            const child = spawn(process.execPath, [...process.execArgv, this.argv[0], choice], {
                stdio: ['ignore', outFd, errFd],
                env:   { ...process.env, [CHILD_ENV]: '1' },
            });
            fs.closeSync(outFd); fs.closeSync(errFd);
            child.on('error', () => resolve(1));
            child.on('exit', (code, signal) => {
                if (signal) resolve(-(os.constants.signals[signal] || 1));
                else        resolve(code === null ? 1 : code);
            });
        });
    }

    /* RETURN: undefined; 'message' is written on the UP channel (descriptor
     *         1), synchronously. */
    _up(message) { fs.writeSync(1, message + '\n'); }
}

/* RETURN: undefined; 'text' is written to descriptor 1 synchronously (so a
 *         following 'process.exit' cannot lose it). */
function writeOut(text) { process.stdout.write(text); }

/* RETURN: string, the element of 'haystack' least distant from 'needle' (the
 *         first of equal ones); null where 'needle' is null or 'haystack' is
 *         empty. */
function levenshteinBestMatch(needle, haystack) {
    if (needle === null || needle === undefined || haystack.length === 0) return null;
    if (haystack.includes(needle)) return needle;
    let bestKey = null, bestDist = null;
    for (const key of haystack) {
        const dist = levenshteinDistance(needle, key);
        if (bestDist === null || dist < bestDist) { bestDist = dist; bestKey = key; }
    }
    return bestKey;
}

/* RETURN: integer >= 0, the Levenshtein distance between 'a' and 'b'. */
function levenshteinDistance(a, b) {
    if (a === b) return 0;
    if (!a) return b.length;
    if (!b) return a.length;
    if (a.length < b.length) [a, b] = [b, a];
    let prev = Array.from({ length: b.length + 1 }, (_, i) => i);
    for (let i = 1; i <= a.length; i += 1) {
        const cur = [i];
        for (let j = 1; j <= b.length; j += 1) {
            const cost = a[i - 1] === b[j - 1] ? 0 : 1;
            cur.push(Math.min(cur[j - 1] + 1, prev[j] + 1, prev[j - 1] + cost));
        }
        prev = cur;
    }
    return prev[prev.length - 1];
}

module.exports = { HwutRunner, levenshteinBestMatch, levenshteinDistance };
