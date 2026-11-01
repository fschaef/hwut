// cow_norecheck.js -- the same pattern WITHOUT the re-check (the pre-2016
// logic). Same abstract user-space model as cow.js; the one difference is
// the write step.
//
// THE DEFECT (this file): the write step writes to whatever the resource
// points at, trusting the earlier fault. If the private copy was discarded
// ("zap") after the fault and before the write, the resource is 'orig'
// again and the write lands on the shared, read-only object. The write
// intent established at the fault is not re-verified -- it was "consumed"
// and never restored on the retry path.
'use strict';

function writerSteps(s) {
    return [
        { name: "fault",  fn: () => { if (s.page === "orig") s.page = "copy"; } },
        { name: "settle", fn: () => { /* a scheduling point: another actor may run */ } },
        { name: "write",  fn: () => {
            s.wrote = s.page;                          // the write lands here
            if (s.page === "orig") s.roWrites += 1;    // the shared object was written
        } },
    ];
}

function zapperSteps(s) {
    return [
        { name: "zap", fn: () => { s.page = "orig"; } },
    ];
}

module.exports = { writerSteps, zapperSteps, label: "../cow_norecheck.js" };
