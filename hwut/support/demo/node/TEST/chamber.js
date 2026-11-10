#! /usr/bin/env node
//
// @hwut {
//     title     = "Demo: a climate chamber's step response -- regions, units, a string law"
//     tolerance { constraints = ["overshoot <= 0.5 K",
//                                "settle <= 4 min",
//                                "verdict == 'settled'"] }
//     choices {
//         heat { features = ["demo-node+cover-region-verbatim", "demo-node+cover-region-table", "demo-node+cover-region-point-cloud",
//                            "demo-node+cover-region-ignore", "demo-node+cover-laws-in-units", "demo-node+cover-string-binding",
//                            "demo-node+cover-test-level-tolerance", "demo-node+cover-annotation-lines"] }
//         cool { features = ["demo-node+cover-region-verbatim", "demo-node+cover-region-table", "demo-node+cover-region-point-cloud",
//                            "demo-node+cover-region-ignore", "demo-node+cover-laws-in-units", "demo-node+cover-string-binding",
//                            "demo-node+cover-test-level-tolerance", "demo-node+cover-annotation-lines"] }
//     }
// }
//
/*
______________________________________________________________________________
SUBJECT  a climate chamber driven from one temperature to another by a PI
         controller: its configuration, its sensors at the end, its step
         response, and the three numbers its requirement names.
REQUIREMENT  The chamber reaches the setpoint within 4 minutes, overshoots
             it by no more than 0.5 K, and reports itself 'settled'.

Every run is seeded by the clock: the sensors are noisy, the four sensor
rows come out in a different order, the calibration stamps are today's.
Both choices pass on every run anyway; each part of the output says how:

'##' lines     notes for the reader. The comparison skips them on both
               sides, anywhere -- even inside a region.

verbatim       '##! verbatim' ... '####': the configuration as loaded. It is
               YAML, where indentation is meaning, so nothing is tolerated:
               no whitespace folding, no numeric band.

table          '##! table key=0 ignore=1 numeric={2:0.0005}': one row per
               sensor, matched by its NAME (column 0) whatever the order;
               column 1, the calibration stamp, is not compared; column 2,
               the reading in K, within 0.05 %.

point-cloud    '##! point-cloud limit=0.5 constraint={...}': the step
               response as points (t, T). Every point lies within 0.5 of a
               point of the GOOD file ('limit'), AND every point keeps the
               envelope stated in the region ('constraint') -- the GOOD's
               points, too, so a GOOD that breaks its envelope is refused.

ignore         '##! ignore': a picture for the human eye. One noisy sample
               moves a star; the picture's presence is compared, its
               contents are not.

units          '((settle: 150 s))' is a quantity; the law says 'settle <= 4
               min' and the comparison converts. A temperature DIFFERENCE is
               printed in K, never in degC (an offset unit).

string law     '((verdict: "settled"))' binds a string; 'verdict ==
               'settled'' judges it.

test-level     the three laws stand ONCE, in the header's own 'tolerance',
tolerance      and hold for both choices.

CHOICES  heat  20 degC -> 40 degC.
         cool  40 degC -> 20 degC.
______________________________________________________________________________
*/
'use strict';

const DT_S        = 1.0;               // simulation step
const DURATION_S  = 400;               // simulated time
const SAMPLE_S    = 20;                // one point of the cloud every 20 s
const BAND_K      = 0.3;               // 'settled' = within 0.3 K of the setpoint
const NOISE_K     = 0.02;              // sensor noise, one sigma
const TAU_S = 300.0, RATE_K_PER_S = 0.15;   // the plant
const KP = 0.6, KI = 0.01;                  // the controller

const CONFIG_TEXT = [
    'chamber:',
    '  plant:',
    `    time_constant_s: ${TAU_S.toFixed(0)}`,
    `    heater_rate_K_per_s: ${RATE_K_PER_S}`,
    '  controller:',
    '    kind: PI',
    `    kp: ${KP}`,
    `    ki: ${KI}`,
    '    output: [-1.0, 1.0]',
    '  sensors: [top, middle, bottom, door]'].join('\n');

//  Offset of each sensor against the air in the middle of the chamber.
const SENSOR_OFFSET_DB = { top: +0.10, middle: 0.00, bottom: -0.10, door: -0.40 };

const say   = text => console.log(text);
/* RETURN: string, 'x' with 'digits' decimals, right-aligned in 'width'
 *         columns -- Python's '%<width>.<digits>f'. */
const fixed = (x, digits, width = 0) => x.toFixed(digits).padStart(width);

/* RETURN: number, a float drawn from the normal distribution of 'mu' and
 *         'sigma' (Box-Muller over 'Math.random', seeded by the clock). */
function gauss(mu, sigma) {
    const u = 1.0 - Math.random(), v = Math.random();
    return mu + sigma * Math.sqrt(-2.0 * Math.log(u)) * Math.cos(2.0 * Math.PI * v);
}

/* RETURN: array of [t_s, measured_C], one sample per simulation step, of the
 *         chamber driven from 'start_C' to 'setpoint_C' by the PI controller
 *         of CONFIG_TEXT, with sensor noise drawn at random. */
function stepResponse(start_C, setpoint_C) {
    const ambient = 20.0;
    let temp = start_C, integral = 0.0;
    const sampleList = [];
    for (let t = 0.0; t <= DURATION_S; t += DT_S) {
        const measured = temp + gauss(0.0, NOISE_K);
        sampleList.push([t, measured]);
        const error = setpoint_C - measured;
        let output = KP * error + KI * integral;
        if (-1.0 < output && output < 1.0)          // anti-windup: integrate
            integral += error * DT_S;               // only while unsaturated
        output = Math.max(-1.0, Math.min(1.0, output));
        temp += DT_S * ((ambient - temp) / TAU_S + RATE_K_PER_S * output);
    }
    return sampleList;
}

/* RETURN: number, how far in K the chamber went past 'setpoint_C' in the
 *         direction of travel from 'start_C'; 0.0 where it never did. */
function overshootK(sampleList, start_C, setpoint_C) {
    const sign = setpoint_C > start_C ? 1.0 : -1.0;
    return Math.max(0.0, ...sampleList.map(([, temp]) => sign * (temp - setpoint_C)));
}

/* RETURN: number, the time in s after which every sample stays within
 *         BAND_K of 'setpoint_C' (the step after the last one outside). */
function settleS(sampleList, setpoint_C) {
    const outside = sampleList.filter(([, temp]) => Math.abs(temp - setpoint_C) > BAND_K).map(([t]) => t);
    return outside.length ? outside[outside.length - 1] + DT_S : 0.0;
}

/* RETURN: undefined. Prints the configuration as loaded, byte for byte. */
function printConfig() {
    say('configuration, as loaded (YAML: whitespace is meaning):');
    say('##! verbatim');
    say(CONFIG_TEXT);
    say('####');
}

/* RETURN: string, the local time now as '%Y-%m-%dT%H:%M:%S'. */
function stampNow() {
    const d = new Date(), two = n => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${two(d.getMonth() + 1)}-${two(d.getDate())}`
         + `T${two(d.getHours())}:${two(d.getMinutes())}:${two(d.getSeconds())}`;
}

/* RETURN: undefined. Prints one row per sensor, in a random order, with
 *         today's calibration stamp and the reading at the end in K. */
function printSensors(setpoint_C) {
    say("sensors at the end, in K (the order is the bus's):");
    say('    sensor  calibrated           reading_K');
    say('##! table key=0 ignore=1 numeric={2:0.0005}');
    const nameList = Object.keys(SENSOR_OFFSET_DB);
    for (let i = nameList.length - 1; i > 0; i -= 1) {
        const j = Math.floor(Math.random() * (i + 1));
        [nameList[i], nameList[j]] = [nameList[j], nameList[i]];
    }
    const stamp = stampNow();
    for (const name of nameList) {
        const reading = setpoint_C + SENSOR_OFFSET_DB[name] + gauss(0.0, NOISE_K) + 273.15;
        say(`    ${name.padEnd(6)}  ${stamp}  ${fixed(reading, 2, 9)}`);
    }
    say('####');
}

/* RETURN: undefined. Prints the step response, one point (t_s, T_degC)
 *         every SAMPLE_S, framed with the envelope the requirement allows. */
function printCloud(sampleList, start_C, setpoint_C) {
    let [low, high] = [start_C, setpoint_C].sort((a, b) => a - b);
    if (setpoint_C > start_C) high += 0.5;
    else                      low  -= 0.5;
    //  0.1 K beyond the envelope on either side: the sensor's noise.
    say(`step response, t in s against T in degC; envelope ${fixed(low, 1)} .. ${fixed(high, 1)}:`);
    say(`##! point-cloud limit=0.5 constraint={y >= ${fixed(low - 0.1, 1)} and y <= ${fixed(high + 0.1, 1)}}`);
    for (const [t, temp] of sampleList)
        if (t % SAMPLE_S === 0) say(`    ${fixed(t, 0, 5)}  ${fixed(temp, 2, 6)}`);
    say('####');
}

/* RETURN: undefined. Prints the step response as stars, for the human eye
 *         only: one row per 40 s, one column per 0.5 K. */
function printPicture(sampleList, start_C, setpoint_C) {
    const low = Math.min(start_C, setpoint_C) - 1.0;
    say("the same, as a picture ('|' the setpoint):");
    say('##! ignore');
    for (const [t, temp] of sampleList) {
        if (t % 40 !== 0) continue;
        const row = new Array(46).fill(' ');
        row[Math.round((setpoint_C - low) / 0.5)] = '|';
        row[Math.max(0, Math.min(45, Math.round((temp - low) / 0.5)))] = '*';
        say(`    ${fixed(t, 0, 4)} s  ${row.join('').trimEnd()}`);
    }
    say('####');
}

/* RETURN: undefined. Drives the chamber and prints every part of the
 *         report. */
function run(start_C, setpoint_C) {
    const sampleList = stepResponse(start_C, setpoint_C);
    say(`## climate chamber, ${fixed(start_C, 0)} degC -> ${fixed(setpoint_C, 0)} degC, one sample per second`);
    say("## '##' lines are for the reader: the comparison skips them.");
    printConfig();
    printSensors(setpoint_C);
    printCloud(sampleList, start_C, setpoint_C);
    printPicture(sampleList, start_C, setpoint_C);
    const over   = overshootK(sampleList, start_C, setpoint_C);
    const settle = settleS(sampleList, setpoint_C);
    say(`overshoot  ((overshoot: ${fixed(over, 2)} K))          law <= 0.5 K`);
    say(`settled    ((settle: ${fixed(settle, 0)} s))             law <= 4 min`);
    const verdict = Math.abs(sampleList[sampleList.length - 1][1] - setpoint_C) <= BAND_K ? 'settled' : 'drifting';
    say(`chamber    ((verdict: "${verdict}"))`);
}

const CHOICE_DB = { heat: [20.0, 40.0], cool: [40.0, 20.0] };

const word = process.argv[2] || '';
if (!Object.prototype.hasOwnProperty.call(CHOICE_DB, word)) {
    say(`choices: ${Object.keys(CHOICE_DB).join(', ')}`);
    process.exit(1);
}
run(...CHOICE_DB[word]);
say('<hwut-end>');
