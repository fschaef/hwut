// csv2json.js -- CSV export to JSON, typed and checked against a schema.
//
//     node csv2json.js <schema.json> <file.csv>
//
// stdout: a JSON array, one object per valid row, keys in schema order,
//         typed: int/number as numbers, empty optional fields as null.
// stderr: one line per broken rule: "<file>:<line>: <column>: <what>".
//         A row with any broken rule is left out.
// exit:   0 every row valid, 1 a row was left out, 2 cannot read the input.
// CSV: comma separated, fields may be quoted, "" inside quotes is a quote.
"use strict";
const fs = require("fs");
const [schemaPath, csvPath] = process.argv.slice(2);
let schema, text;
try {
    schema = JSON.parse(fs.readFileSync(schemaPath, "utf8"));
    text = fs.readFileSync(csvPath, "utf8");
} catch (e) { console.error("csv2json: " + e.message); process.exit(2); }

function fields(line) {
    const out = [];
    let cur = "", quoted = false;
    for (let i = 0; i < line.length; i++) {
        const c = line[i];
        if (quoted) {
            if (c === '"' && line[i + 1] === '"') { cur += '"'; i++; }
            else if (c === '"') quoted = false;
            else cur += c;
        } else if (c === '"') quoted = true;
        else if (c === ",") { out.push(cur); cur = ""; }
        else cur += c;
    }
    out.push(cur);
    return out;
}

function typed(name, rule, raw) {
    if (raw === "") {
        if (rule.required) throw "required, but empty";
        return null;
    }
    switch (rule.type) {
        case "int":
            if (!/^-?\d+$/.test(raw)) throw `'${raw}' is not an integer`;
            return parseInt(raw, 10);
        case "number":
            if (!/^-?\d+(\.\d+)?$/.test(raw)) throw `'${raw}' is not a number (decimal point, no grouping)`;
            return parseFloat(raw);
        case "date": {
            const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(raw);
            if (!m) throw `'${raw}' is not a date (YYYY-MM-DD)`;
            const d = new Date(Date.UTC(+m[1], +m[2] - 1, +m[3]));
            if (d.getUTCMonth() !== +m[2] - 1 || d.getUTCDate() !== +m[3]) throw `'${raw}' is no day of the calendar`;
            return raw;
        }
        case "enum":
            if (!rule.values.includes(raw)) throw `'${raw}' is not one of ${rule.values.join("|")}`;
            return raw;
        default:
            return raw;
    }
}

const lines = text.split("\n").filter((l, i, all) => l !== "" || i < all.length - 1);
const header = fields(lines[0]);
const names = Object.keys(schema);
const result = [];
let rejected = 0;
for (const n of names) if (!header.includes(n)) { console.error(`${csvPath}:1: ${n}: column missing`); process.exit(2); }
lines.slice(1).forEach((line, k) => {
    const cells = fields(line), obj = {}, where = `${csvPath}:${k + 2}`;
    let bad = 0;
    if (cells.length !== header.length) {
        console.error(`${where}: row: ${cells.length} fields, the header has ${header.length}`);
        bad++;
    }
    for (const n of names) {
        try { obj[n] = typed(n, schema[n], cells[header.indexOf(n)] ?? ""); }
        catch (what) { console.error(`${where}: ${n}: ${what}`); bad++; }
    }
    if (bad) rejected++; else result.push(obj);
});
console.log(JSON.stringify(result, null, 1));
process.exit(rejected ? 1 : 0);
