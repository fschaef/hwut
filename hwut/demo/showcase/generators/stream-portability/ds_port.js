// ds_port.js -- DeterministicStream (hwut test_writing_support) in JavaScript,
// for a web front end replaying a recorded stream. BigInt is not needed for
// the product -- 48271 * (2^31 - 2) < 2^47 is exact in a Number (2^53) --
// it is kept so that '%' and the int conversions read as integer arithmetic.
// usage: node ds_port.js int|gauss SEED N
let state = BigInt(Number(process.argv[3]) & 0x7FFFFFFF);
function nextInt(lo, hi) {
    state = (48271n * state) % 2147483647n;
    if (lo === hi) return lo;
    return lo + Number(state % BigInt(hi - lo + 1));
}
const nextFloat = () => nextInt(0, 1000000) / 1000001.0;
function gauss(mu, sigma) {
    const u1 = nextFloat() + 1e-9, u2 = nextFloat();
    return Math.sqrt(-2.0 * Math.log(u1)) * Math.cos(2.0 * Math.PI * u2) * sigma + mu;
}
const out = [];
for (let i = 0; i < Number(process.argv[4]); ++i)
    out.push(process.argv[2] === "int" ? String(nextInt(0, 999)) : gauss(0, 1).toPrecision(17));
console.log(out.join("\n"));
