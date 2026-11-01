// cow.js -- the copy-on-write write path WITH the re-check (the 2016 fix).
//
// This is an ABSTRACT MODEL of a concurrency pattern, in user space: no
// kernel, no system calls, no memory devices, no exploit. One shared
// resource stands for a read-only, shared object ('orig'); a writer wants
// to end up changing only its own private copy ('copy'), never 'orig'.
//
// The pattern: a write to a read-only object first makes a private copy
// (the "fault"), then writes. Between the two a scheduling point ("settle")
// lets another actor run; that actor may discard the private copy ("zap"),
// so the resource points at the shared 'orig' again.
//
// THE GUARD (this file): the write step re-checks that it owns a private
// copy; if the resource is 'orig' again, it faults once more before writing.
// A write therefore never lands on the shared object. (This mirrors the
// public fix: the write path must verify it holds a private, writable copy.)
'use strict';

function writerSteps(s) {
    return [
        { name: "fault",  fn: () => { if (s.page === "orig") s.page = "copy"; } },
        { name: "settle", fn: () => { /* a scheduling point: another actor may run */ } },
        { name: "write",  fn: () => {
            if (s.page === "orig") s.page = "copy";   // re-check: fault again
            s.wrote = s.page;                          // the write lands here
            if (s.page === "orig") s.roWrites += 1;    // (never, with the guard)
        } },
    ];
}

function zapperSteps(s) {
    return [
        { name: "zap", fn: () => { s.page = "orig"; } },   // discard the private copy
    ];
}

module.exports = { writerSteps, zapperSteps, label: "../cow.js" };
