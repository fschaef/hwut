// @hwut {
//     title     = "Demo: a climate chamber's step response -- regions, units, a string law"
//     build     { framework = "make", target = "%.exe"
//                 caps { timeout_sec = 900 } }
//     tolerance { constraints = ["overshoot <= 0.5 K",
//                                "settle <= 4 min",
//                                "verdict == 'settled'"] }
//     choices {
//         heat { features = ["region-verbatim", "region-table", "region-point-cloud",
//                            "region-ignore", "laws-in-units", "string-binding",
//                            "test-level-tolerance", "annotation-lines"] }
//         cool { features = ["region-verbatim", "region-table", "region-point-cloud",
//                            "region-ignore", "laws-in-units", "string-binding",
//                            "test-level-tolerance", "annotation-lines"] }
//     }
// }
//
//______________________________________________________________________________
// SUBJECT  a climate chamber driven from one temperature to another by a PI
//          controller: its configuration, its sensors at the end, its step
//          response, and the three numbers its requirement names.
// REQUIREMENT  The chamber reaches the setpoint within 4 minutes, overshoots
//              it by no more than 0.5 K, and reports itself 'settled'.
//
// Every run is seeded by the clock: the sensors are noisy, the four sensor
// rows come out in a different order, the calibration stamps are today's.
// Both choices pass on every run anyway; each part of the output says how:
//
// '##' lines     notes for the reader, skipped on both sides, anywhere.
// verbatim       '##! verbatim': the configuration as loaded -- YAML, where
//                indentation is meaning: nothing is tolerated.
// table          '##! table key=0 ignore=1 numeric={2:0.0005}': one row per
//                sensor, matched by its NAME whatever the order; the stamp
//                not compared; the reading in K within 0.05 %.
// point-cloud    '##! point-cloud limit=0.5 constraint={...}': the step
//                response as points (t, T), each within 0.5 of a GOOD point
//                AND inside the envelope -- the GOOD's points too.
// ignore         '##! ignore': a picture for the human eye; its presence is
//                compared, its contents are not.
// units          '((settle: 150 s))' against 'settle <= 4 min': converted.
//                A temperature DIFFERENCE is printed in K, never in degC.
// string law     '((verdict: "settled"))' judged by 'verdict == 'settled''.
// test-level     the three laws stand ONCE, in the header's own 'tolerance',
// tolerance      and hold for both choices.
//
// CHOICES  heat  20 degC -> 40 degC.
//          cool  40 degC -> 20 degC.
//______________________________________________________________________________
mod clock_random;

use clock_random::Random;

const DT_S: f64         = 1.0;     // simulation step
const DURATION_S: f64   = 400.0;   // simulated time
const SAMPLE_S: f64     = 20.0;    // one point of the cloud every 20 s
const BAND_K: f64       = 0.3;     // 'settled' = within 0.3 K of the setpoint
const NOISE_K: f64      = 0.02;    // sensor noise, one sigma
const TAU_S: f64        = 300.0;   // the plant
const RATE_K_PER_S: f64 = 0.15;
const KP: f64           = 0.6;     // the controller
const KI: f64           = 0.01;

//  Offset of each sensor against the air in the middle of the chamber.
const SENSOR_OFFSET_LIST: [(&str, f64); 4] = [("top", 0.10), ("middle", 0.00), ("bottom", -0.10), ("door", -0.40)];

/// RETURN: String, the configuration as loaded, YAML.
fn config_text() -> String {
    format!("chamber:\n  plant:\n    time_constant_s: {:.0}\n    heater_rate_K_per_s: {}\n  controller:\n    \
             kind: PI\n    kp: {}\n    ki: {}\n    output: [-1.0, 1.0]\n  sensors: [top, middle, bottom, door]",
            TAU_S, RATE_K_PER_S, KP, KI)
}

extern "C" {
    fn time(t: *mut i64) -> i64;
    fn localtime_r(t: *const i64, tm: *mut u8) -> *mut u8;
    fn strftime(s: *mut u8, max: usize, format: *const u8, tm: *const u8) -> usize;
}

/// RETURN: String, the local time now as '%Y-%m-%dT%H:%M:%S'.
fn stamp_now() -> String {
    let mut tm = [0u8; 128];                 // 'struct tm': 56 bytes on glibc
    let mut text = [0u8; 64];
    unsafe {
        let now = time(std::ptr::null_mut());
        localtime_r(&now, tm.as_mut_ptr());
        let n = strftime(text.as_mut_ptr(), text.len(), b"%Y-%m-%dT%H:%M:%S\0".as_ptr(), tm.as_ptr());
        String::from_utf8_lossy(&text[..n]).into_owned()
    }
}

/// RETURN: Vec<(f64, f64)>, (t_s, measured_C), one sample per simulation
///         step, of the chamber driven from 'start_c' to 'setpoint_c' by the
///         PI controller, with sensor noise drawn from 'random'.
fn step_response(start_c: f64, setpoint_c: f64, random: &mut Random) -> Vec<(f64, f64)> {
    let ambient = 20.0;
    let mut temp = start_c;
    let mut integral = 0.0;
    let mut sample_list = Vec::new();
    let mut t = 0.0;
    while t <= DURATION_S {
        let measured = temp + random.gauss(0.0, NOISE_K);
        sample_list.push((t, measured));
        let error = setpoint_c - measured;
        let mut output = KP * error + KI * integral;
        if -1.0 < output && output < 1.0 { integral += error * DT_S; }   // anti-windup
        output = output.clamp(-1.0, 1.0);
        temp += DT_S * ((ambient - temp) / TAU_S + RATE_K_PER_S * output);
        t += DT_S;
    }
    sample_list
}

/// RETURN: f64, how far in K the chamber went past 'setpoint_c' in the
///         direction of travel from 'start_c'; 0.0 where it never did.
fn overshoot_k(sample_list: &[(f64, f64)], start_c: f64, setpoint_c: f64) -> f64 {
    let sign = if setpoint_c > start_c { 1.0 } else { -1.0 };
    sample_list.iter().map(|(_, temp)| sign * (temp - setpoint_c)).fold(0.0, f64::max)
}

/// RETURN: f64, the time in s after which every sample stays within BAND_K of
///         'setpoint_c' (the step after the last one outside).
fn settle_s(sample_list: &[(f64, f64)], setpoint_c: f64) -> f64 {
    sample_list.iter().filter(|(_, temp)| (temp - setpoint_c).abs() > BAND_K)
               .last().map(|(t, _)| t + DT_S).unwrap_or(0.0)
}

/// RETURN: nothing. Prints the configuration as loaded, byte for byte.
fn print_config() {
    println!("configuration, as loaded (YAML: whitespace is meaning):");
    println!("##! verbatim");
    println!("{}", config_text());
    println!("####");
}

/// RETURN: nothing. Prints one row per sensor, in a random order, with
///         today's calibration stamp and the reading at the end in K.
fn print_sensors(setpoint_c: f64, random: &mut Random) {
    println!("sensors at the end, in K (the order is the bus's):");
    println!("    sensor  calibrated           reading_K");
    println!("##! table key=0 ignore=1 numeric={{2:0.0005}}");
    let mut sensor_list = SENSOR_OFFSET_LIST.to_vec();
    random.shuffle(&mut sensor_list);
    let stamp = stamp_now();
    for (name, offset) in sensor_list {
        let reading = setpoint_c + offset + random.gauss(0.0, NOISE_K) + 273.15;
        println!("    {:<6}  {}  {:9.2}", name, stamp, reading);
    }
    println!("####");
}

/// RETURN: nothing. Prints the step response, one point (t_s, T_degC) every
///         SAMPLE_S, framed with the envelope the requirement allows.
fn print_cloud(sample_list: &[(f64, f64)], start_c: f64, setpoint_c: f64) {
    let (mut low, mut high) = (start_c.min(setpoint_c), start_c.max(setpoint_c));
    if setpoint_c > start_c { high += 0.5; } else { low -= 0.5; }
    //  0.1 K beyond the envelope on either side: the sensor's noise.
    println!("step response, t in s against T in degC; envelope {:.1} .. {:.1}:", low, high);
    println!("##! point-cloud limit=0.5 constraint={{y >= {:.1} and y <= {:.1}}}", low - 0.1, high + 0.1);
    for (t, temp) in sample_list {
        if t % SAMPLE_S == 0.0 { println!("    {:5.0}  {:6.2}", t, temp); }
    }
    println!("####");
}

/// RETURN: nothing. Prints the step response as stars, for the human eye
///         only: one row per 40 s, one column per 0.5 K.
fn print_picture(sample_list: &[(f64, f64)], start_c: f64, setpoint_c: f64) {
    let low = start_c.min(setpoint_c) - 1.0;
    println!("the same, as a picture ('|' the setpoint):");
    println!("##! ignore");
    for (t, temp) in sample_list {
        if t % 40.0 != 0.0 { continue; }
        let mut row = vec![' '; 46];
        row[((setpoint_c - low) / 0.5).round_ties_even() as usize] = '|';
        row[(((temp - low) / 0.5).round_ties_even() as i64).clamp(0, 45) as usize] = '*';
        let text: String = row.into_iter().collect();
        println!("    {:4.0} s  {}", t, text.trim_end());
    }
    println!("####");
}

/// RETURN: nothing. Drives the chamber and prints every part of the report.
fn run(start_c: f64, setpoint_c: f64) {
    let mut random = Random::from_clock();
    let sample_list = step_response(start_c, setpoint_c, &mut random);
    println!("## climate chamber, {:.0} degC -> {:.0} degC, one sample per second", start_c, setpoint_c);
    println!("## '##' lines are for the reader: the comparison skips them.");
    print_config();
    print_sensors(setpoint_c, &mut random);
    print_cloud(&sample_list, start_c, setpoint_c);
    print_picture(&sample_list, start_c, setpoint_c);
    let over   = overshoot_k(&sample_list, start_c, setpoint_c);
    let settle = settle_s(&sample_list, setpoint_c);
    println!("overshoot  ((overshoot: {:.2} K))          law <= 0.5 K", over);
    println!("settled    ((settle: {:.0} s))             law <= 4 min", settle);
    let last = sample_list.last().map(|(_, temp)| *temp).unwrap_or(start_c);
    let verdict = if (last - setpoint_c).abs() <= BAND_K { "settled" } else { "drifting" };
    println!("chamber    ((verdict: \"{}\"))", verdict);
}

/// RETURN: never; exits 0 once the choice named on the command line ran and
///         '<hwut-end>' was printed; 1 where no such choice is.
fn main() {
    match std::env::args().nth(1).as_deref() {
        Some("heat") => run(20.0, 40.0),
        Some("cool") => run(40.0, 20.0),
        _ => { println!("choices: heat, cool"); std::process::exit(1); }
    }
    println!("<hwut-end>");
}
