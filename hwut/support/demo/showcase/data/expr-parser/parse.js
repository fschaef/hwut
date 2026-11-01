// parse.js -- integer expressions by precedence climbing; operators from a table.
//
//     node parse.js <operator-table.json> < expressions
//
// One expression per input line; one JSON object per output line:
//     {"ast": <tree>, "value": "<integer>"}     or
//     {"error": "<message>", "column": <1-based column, 0: not a place>}
// A tree is a number (as a string), ["neg", t] or [op, left, right].
// Arithmetic is exact (BigInt). Unary minus binds weaker than the operator
// of highest precedence and tighter than all others: -2^2 = -(2^2).
"use strict";
const fs = require("fs");
const OPS = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const TOP_PREC = Math.max(...Object.values(OPS).map(o => o.prec));

function tokenize(text) {
    const list = [];
    const re = /\s*(?:(\d+)|(.))/gy;
    let m;
    while (re.lastIndex < text.length && (m = re.exec(text)) !== null) {
        if (m[1] === undefined && m[2] === undefined) break;
        const column = m.index + m[0].length - (m[1] || m[2]).length + 1;
        list.push({ text: m[1] || m[2], num: m[1] !== undefined, column });
    }
    list.push({ text: "end of input", end: true, column: text.replace(/\s+$/, "").length + 1 });
    return list;
}

function parse(text) {
    const tok = tokenize(text);
    let k = 0;
    const fail = (what) => { throw { error: `expected ${what}, found ${tok[k].end ? "end of input" : "'" + tok[k].text + "'"}`, column: tok[k].column }; };
    function primary() {
        const t = tok[k];
        if (t.num) { k++; return t.text; }
        if (t.text === "(") {
            k++;
            const e = expr(1);
            if (tok[k].text !== ")") fail("')'");
            k++;
            return e;
        }
        if (t.text === "-") { k++; return ["neg", expr(TOP_PREC)]; }
        fail("a number or '('");
    }
    function expr(min_prec) {
        let left = primary();
        for (;;) {
            const op = OPS[tok[k].text];
            if (tok[k].end || op === undefined || op.prec < min_prec) return left;
            const symbol = tok[k++].text;
            const right = expr(op.assoc === "left" ? op.prec + 1 : op.prec);
            left = [symbol, left, right];
        }
    }
    const tree = expr(1);
    if (!tok[k].end) fail("an operator");
    return tree;
}

function value(t) {
    if (typeof t === "string") return BigInt(t);
    if (t[0] === "neg") return -value(t[1]);
    const a = value(t[1]), b = value(t[2]);
    switch (t[0]) {
        case "+": return a + b;
        case "-": return a - b;
        case "*": return a * b;
        case "^": if (b < 0n) throw new RangeError("negative exponent"); return a ** b;
    }
}

const lines = fs.readFileSync(0, "utf8").split("\n");
if (lines[lines.length - 1] === "") lines.pop();
for (const line of lines) {
    try {
        const ast = parse(line);
        console.log(JSON.stringify({ ast, value: value(ast).toString() }));
    } catch (e) {
        if (e instanceof RangeError) e = { error: e.message, column: 0 };
        else if (e.error === undefined) throw e;
        console.log(JSON.stringify(e));
    }
}
