#! /usr/bin/env node
// @hwut {
//     title    = "Dirty COW (CVE-2016-5195) as a race model: a write that forgets to re-check its private copy"
//     features = ["all-interleavings", "recheck-guard"]
//     choices {
//         fixed       { features = ["all-interleavings", "recheck-guard"]
//                       tolerance { constraints = ["unfinished == 0", "ro_writes == 0"] } }
//         vulnerable  { features = ["all-interleavings", "losing-rows-named"]
//                       tolerance { constraints = ["unfinished == 0", "ro_writes > 0"] } }
//     }
// }
'use strict';
/*
______________________________________________________________________________
SUBJECT  in every interleaving of a writer's steps with a discarder's step,
         what the copy-on-write write path (../cow*.js) writes to: its own
         private copy, or the shared read-only object
REQUIREMENT  A write started against a read-only object must change only the
             writer's private copy, never the shared object -- in EVERY
             interleaving of the two actors' steps, not only the ones a
             stress run happens to hit.

CVE-2016-5195 ("Dirty COW") was a race in the copy-on-write path, latent
about nine years, that let a write reach a read-only object. This example
models the RACE LOGIC in user space -- no kernel, no system calls, no
memory devices, no exploit. One shared value stands for the read-only
object ('orig') and the writer's private copy ('copy').

THE PATTERN. To change a read-only object, the writer first makes a private
copy (step 'fault'), then writes (step 'write'); between them a scheduling
point ('settle') lets another actor run. A discarder throws the private
copy away (step 'zap'), so the resource points at 'orig' again. The guard
that makes this safe is at the WRITE: it must re-check that it still owns a
private copy and fault again if not. The public fix added exactly that
re-check; the earlier logic trusted the fault and wrote to whatever the
resource pointed at.

THE TESTED SPACE -- ALL interleavings:

    w, z  = steps of the writer and the discarder, measured alone (3 and 1)
    words = every order of w 'W' letters and z 'Z' letters       4 words
    word 'WWZW' -> writer does fault, settle, then (after zap) write

Each word is one interleaving; a letter is the actor that takes its next
atomic step at that tick. The step counts are MEASURED by running each
actor alone, so a step added to a unit lengthens the words and the matrix
stays complete: no interleaving is missing. There is no JavaScript port of
hwut's space_iterator; the enumeration below is a few lines of its own.

THE STEPS ARE A MODEL: each actor is a list of thunks stepped in the word's
order by one driver -- no threads, no shared memory, no timing. The test
proves the step logic, not a scheduler.

fixed       the write re-checks and faults again if the copy is gone: every
            interleaving writes to 'copy'. Law 'ro_writes == 0'.
vulnerable  the write trusts the fault: in every interleaving where 'zap'
            falls between 'fault' and 'write', the write lands on the shared
            'orig'. Those rows are marked '!!' and counted (2 of 4). Law
            'ro_writes > 0'.

HOW TO READ THE GOOD   The step legend heads the page. One row per
interleaving: the word, the writer's and discarder's step at each tick, the
target the write hit ('copy' or 'orig !!'), and the verdict. Below the
matrix the shortest losing interleaving is drawn as a timeline in a
'##! verbatim' region, because its columns are ticks. All exact: no
threads, no clock; 'ro_writes' and 'unfinished' are bindings judged by the
choice's laws.
______________________________________________________________________________
*/
const path = require("path");

const CHOICE_DB = { fixed: "../cow.js", vulnerable: "../cow_norecheck.js" };

function freshState() { return { page: "orig", wrote: null, roWrites: 0 }; }

//  Measure a single actor's step count by running it alone.
function stepCount(factory) {
    return factory(freshState()).length;
}

//  All orders of w 'W' letters and z 'Z' letters (the complete interleaving
//  set); space_iterator has no JavaScript port, so this stands in for it.
function interleavings(w, z) {
    const out = [];
    (function rec(prefix, nw, nz) {
        if (nw === 0 && nz === 0) { out.push(prefix); return; }
        if (nw > 0) rec(prefix + "W", nw - 1, nz);
        if (nz > 0) rec(prefix + "Z", nw, nz - 1);
    })("", w, z);
    return out;
}

//  Run one interleaving: step the writer on 'W', the discarder on 'Z'.
function run(unit, word) {
    const s = freshState();
    const w = unit.writerSteps(s), z = unit.zapperSteps(s);
    let iw = 0, iz = 0;
    const trace = [];
    for (const c of word) {
        if (c === "W") { const st = w[iw++]; st.fn(); trace.push(st.name); }
        else { const st = z[iz++]; st.fn(); trace.push("zap"); }
    }
    const unfinished = (iw < w.length ? 1 : 0) + (iz < z.length ? 1 : 0);
    return { target: s.wrote, breach: s.roWrites > 0, unfinished, trace };
}

function main(choice) {
    const unit = require(path.join(__dirname, CHOICE_DB[choice]));
    const w = stepCount(unit.writerSteps), z = stepCount(unit.zapperSteps);
    const words = interleavings(w, z);

    console.log("unit:      %s, driven by this Node test over every interleaving", unit.label);
    console.log("actors:    writer %d steps (fault, settle, write)   discarder %d step (zap)", w, z);
    console.log("space:     every order of %d + %d steps = %d interleavings", w, z, words.length);
    console.log("legend:    a row's word: 'W' the writer steps, 'Z' the discarder steps");
    console.log("           write target: 'copy' private copy (safe)   'orig !!' the shared object");
    console.log("");

    let roWrites = 0, unfinished = 0, firstLosing = null;
    const rows = [];
    for (const word of words) {
        const r = run(unit, word);
        unfinished += r.unfinished;
        const bad = r.breach;
        if (bad) { roWrites += 1; if (!firstLosing) firstLosing = { word, trace: r.trace }; }
        rows.push({ word, target: bad ? "orig !!" : r.target, verdict: bad ? "LOSES" : "safe" });
    }

    const wlen = Math.max(4, ...words.map(x => x.length));
    console.log("  " + "word".padEnd(wlen) + "   target    verdict");
    for (const r of rows)
        console.log("  " + r.word.padEnd(wlen) + "   " + r.target.padEnd(7) + "   " + r.verdict);
    console.log("");

    if (firstLosing) {
        const { word, trace } = firstLosing;
        const COL = 7;
        console.log("shortest losing interleaving: %s", word);
        console.log("##! verbatim");
        const header = Array.from({ length: word.length },
                                  (_, i) => String(i + 1).padEnd(COL)).join("");
        console.log("  tick        " + header);
        const wr = [], zp = [];
        let i = 0;
        for (const c of word) {
            wr.push((c === "W" ? trace[i] : "").padEnd(COL));
            zp.push((c === "Z" ? "zap" : "").padEnd(COL));
            i += 1;
        }
        console.log("  writer      " + wr.join("").trimEnd());
        console.log("  discarder   " + zp.join("").trimEnd());
        console.log("####");
        console.log("");
        console.log("!! the discarder's 'zap' falls after 'fault' and before 'write': the private");
        console.log("!! copy is gone, and the write lands on the shared read-only object");
    }
    console.log("");
    console.log("interleavings run: %d   losing: %d", words.length, roWrites);
    console.log("writes to the shared object ((ro_writes: %d))   law == 0   %s",
                roWrites, roWrites === 0 ? "kept" : "BROKEN");
    console.log("actors left unfinished ((unfinished: %d))   law == 0   %s",
                unfinished, unfinished === 0 ? "kept" : "BROKEN");
}

const choice = process.argv[2] || "";
if (!(choice in CHOICE_DB)) { console.log("choices: " + Object.keys(CHOICE_DB).join(", ")); process.exit(1); }
main(choice);
console.log("<hwut-end>");
