// backoff_nojitter.js -- BROKEN FIXTURE: the "simplified" version that a
// reviewer once waved through: the jitter made the logs hard to read, so the
// delay became the window itself. Same CLI as backoff.js.
"use strict";
const real = require("./backoff.js");
const fs = require("fs");

function delays(policy, rng) {
    return real.delays(policy, () => 1.0);          // <-- always the top
}

if (require.main === module) {
    const policy = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
    for (let i = 0; i < parseInt(process.argv[3], 10); ++i) console.log(delays(policy).join(" "));
}
