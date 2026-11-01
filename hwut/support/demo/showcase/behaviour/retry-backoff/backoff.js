// backoff.js -- retry delays: exponential backoff with "equal jitter".
//
// The delay before retry k (k = 0, 1, ...) is drawn uniformly from
// [w/2, w] with w = min(cap, base * 2^k): it grows, it never exceeds the
// cap, and clients that failed together do not retry together.
//
// CLI:  node backoff.js <policy.json> <sequences> [seed]
//       prints one line per sequence: the delays in ms. With a seed, the
//       draw is reproducible (mulberry32); without one, Math.random.
"use strict";
const fs = require("fs");

function delays(policy, rng) {
    const out = [];
    for (let k = 0; k < policy.attempts; ++k) {
        const w = Math.min(policy.cap_ms, policy.base_ms * 2 ** k);
        out.push(Math.round(w / 2 + rng() * (w / 2)));
    }
    return out;
}

function mulberry32(seed) {
    return function () {
        seed = (seed + 0x6D2B79F5) | 0;
        let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
        t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
        return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
}

module.exports = { delays, mulberry32 };

if (require.main === module) {
    const policy = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
    const n = parseInt(process.argv[3], 10);
    const rng = process.argv[4] !== undefined ? mulberry32(parseInt(process.argv[4], 10)) : Math.random;
    for (let i = 0; i < n; ++i) console.log(delays(policy, rng).join(" "));
}
