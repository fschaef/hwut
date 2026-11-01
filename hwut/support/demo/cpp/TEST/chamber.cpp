/* @hwut {
 *     title     = "Demo: a climate chamber's step response -- regions, units, a string law"
 *     build     { framework = "make", executable = "%.exe" }
 *     tolerance { constraints = ["overshoot <= 0.5 K",
 *                                "settle <= 4 min",
 *                                "verdict == 'settled'"] }
 *     choices {
 *         heat { features = ["region-verbatim", "region-table", "region-point-cloud",
 *                            "region-ignore", "laws-in-units", "string-binding",
 *                            "test-level-tolerance", "annotation-lines"] }
 *         cool { features = ["region-verbatim", "region-table", "region-point-cloud",
 *                            "region-ignore", "laws-in-units", "string-binding",
 *                            "test-level-tolerance", "annotation-lines"] }
 *     }
 * }
 *
 * SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
 * _____________________________________________________________________________
 *
 * SUBJECT  a climate chamber driven from one temperature to another by a PI
 *          controller: its configuration, its sensors at the end, its step
 *          response, and the three numbers its requirement names.
 * REQUIREMENT  The chamber reaches the setpoint within 4 minutes, overshoots
 *              it by no more than 0.5 K, and reports itself 'settled'.
 *
 * Every run is seeded by the clock: the sensors are noisy, the four sensor
 * rows come out in a different order, the calibration stamps are today's.
 * Both choices pass on every run anyway; each part of the output says how
 * ('chamber.py' of the Python demonstration explains each at length):
 *
 * '##' lines     notes for the reader, skipped on both sides, anywhere.
 * verbatim       '##! verbatim' ... '####': YAML, nothing tolerated.
 * table          '##! table key=0 ignore=1 numeric={2:0.0005}': rows by name.
 * point-cloud    '##! point-cloud limit=0.5 constraint={...}': (t, T) points.
 * ignore         '##! ignore': a picture for the human eye.
 * units          '((settle: 150 s))' against 'settle <= 4 min'.
 * string law     '((verdict: "settled"))' judged by 'verdict == 'settled''.
 * test-level     the three laws stand ONCE, in the header's own 'tolerance'.
 *
 * CHOICES  heat  20 degC -> 40 degC.
 *          cool  40 degC -> 20 degC.
 * _____________________________________________________________________________
 */
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <ctime>
#include <random>
#include <string>
#include <utility>
#include <vector>

static const double DT_S         = 1.0;    // simulation step
static const double DURATION_S   = 400;    // simulated time
static const int    SAMPLE_S     = 20;     // one point of the cloud every 20 s
static const double BAND_K       = 0.3;    // 'settled' = within 0.3 K of the setpoint
static const double NOISE_K      = 0.02;   // sensor noise, one sigma
static const double TAU_S        = 300.0;  // the plant
static const double RATE_K_PER_S = 0.15;
static const double KP           = 0.6;    // the controller
static const double KI           = 0.01;

static const char* CONFIG_TEXT =
    "chamber:\n"
    "  plant:\n"
    "    time_constant_s: 300\n"
    "    heater_rate_K_per_s: 0.15\n"
    "  controller:\n"
    "    kind: PI\n"
    "    kp: 0.6\n"
    "    ki: 0.01\n"
    "    output: [-1.0, 1.0]\n"
    "  sensors: [top, middle, bottom, door]";

//  Offset of each sensor against the air in the middle of the chamber.
static const std::vector<std::pair<const char*, double>> SENSOR_OFFSET = {
    { "top", +0.10 }, { "middle", 0.00 }, { "bottom", -0.10 }, { "door", -0.40 }
};

using Sample = std::pair<double, double>;     // (t_s, measured_C)

static std::mt19937_64 rng;

static double gauss(double mu, double sigma)
/* RETURN: double, drawn from the normal distribution (mu, sigma). */
{ return std::normal_distribution<double>(mu, sigma)(rng); }

static std::vector<Sample> step_response(double start_C, double setpoint_C)
/* RETURN: one sample (t_s, measured_C) per simulation step, of the chamber
 *         driven from 'start_C' to 'setpoint_C' by the PI controller of
 *         CONFIG_TEXT, with sensor noise.                                */
{
    const double ambient = 20.0;
    double temp = start_C, integral = 0.0;
    std::vector<Sample> sample_list;
    for(double t = 0.0; t <= DURATION_S; t += DT_S) {
        double measured = temp + gauss(0.0, NOISE_K);
        sample_list.push_back({ t, measured });
        double error  = setpoint_C - measured;
        double output = KP * error + KI * integral;
        if( -1.0 < output && output < 1.0 ) integral += error * DT_S;   // anti-windup: integrate
        output = std::max(-1.0, std::min(1.0, output));                 // only while unsaturated
        temp += DT_S * ((ambient - temp) / TAU_S + RATE_K_PER_S * output);
    }
    return sample_list;
}

static double overshoot_K(const std::vector<Sample>& sample_list, double start_C, double setpoint_C)
/* RETURN: double, how far in K the chamber went past 'setpoint_C' in the
 *         direction of travel from 'start_C'; 0.0 where it never did.     */
{
    double sign = setpoint_C > start_C ? 1.0 : -1.0, over = 0.0;
    for(const Sample& s : sample_list) over = std::max(over, sign * (s.second - setpoint_C));
    return over;
}

static double settle_s(const std::vector<Sample>& sample_list, double setpoint_C)
/* RETURN: double, the time in s after which every sample stays within
 *         BAND_K of 'setpoint_C' (the step after the last one outside).   */
{
    double settle = 0.0;
    for(const Sample& s : sample_list)
        if( std::fabs(s.second - setpoint_C) > BAND_K ) settle = s.first + DT_S;
    return settle;
}

static void print_config()
/* RETURN: nothing. Prints the configuration as loaded, byte for byte. */
{
    std::printf("configuration, as loaded (YAML: whitespace is meaning):\n");
    std::printf("##! verbatim\n");
    std::printf("%s\n", CONFIG_TEXT);
    std::printf("####\n");
}

static void print_sensors(double setpoint_C)
/* RETURN: nothing. Prints one row per sensor, in a random order, with
 *         today's calibration stamp and the reading at the end in K.     */
{
    std::printf("sensors at the end, in K (the order is the bus's):\n");
    std::printf("    sensor  calibrated           reading_K\n");
    std::printf("##! table key=0 ignore=1 numeric={2:0.0005}\n");
    auto sensor_list = SENSOR_OFFSET;
    std::shuffle(sensor_list.begin(), sensor_list.end(), rng);
    char   stamp[32];
    time_t now = std::time(nullptr);
    std::strftime(stamp, sizeof(stamp), "%Y-%m-%dT%H:%M:%S", std::localtime(&now));
    for(const auto& [name, offset] : sensor_list) {
        double reading = setpoint_C + offset + gauss(0.0, NOISE_K) + 273.15;
        std::printf("    %-6s  %s  %9.2f\n", name, stamp, reading);
    }
    std::printf("####\n");
}

static void print_cloud(const std::vector<Sample>& sample_list, double start_C, double setpoint_C)
/* RETURN: nothing. Prints the step response, one point (t_s, T_degC) every
 *         SAMPLE_S, framed with the envelope the requirement allows.     */
{
    double low = std::min(start_C, setpoint_C), high = std::max(start_C, setpoint_C);
    if( setpoint_C > start_C ) high += 0.5;
    else                       low  -= 0.5;
    //  0.1 K beyond the envelope on either side: the sensor's noise.
    std::printf("step response, t in s against T in degC; envelope %.1f .. %.1f:\n", low, high);
    std::printf("##! point-cloud limit=0.5 constraint={y >= %.1f and y <= %.1f}\n", low - 0.1, high + 0.1);
    for(const Sample& s : sample_list)
        if( (int)s.first % SAMPLE_S == 0 ) std::printf("    %5.0f  %6.2f\n", s.first, s.second);
    std::printf("####\n");
}

static void print_picture(const std::vector<Sample>& sample_list, double start_C, double setpoint_C)
/* RETURN: nothing. Prints the step response as stars, for the human eye
 *         only: one row per 40 s, one column per 0.5 K.                  */
{
    double low = std::min(start_C, setpoint_C) - 1.0;
    std::printf("the same, as a picture ('|' the setpoint):\n");
    std::printf("##! ignore\n");
    for(const Sample& s : sample_list) {
        if( (int)s.first % 40 != 0 ) continue;
        std::string row(46, ' ');
        row[(size_t)std::lround((setpoint_C - low) / 0.5)] = '|';
        row[(size_t)std::max(0L, std::min(45L, std::lround((s.second - low) / 0.5)))] = '*';
        row.erase(row.find_last_not_of(' ') + 1);
        std::printf("    %4.0f s  %s\n", s.first, row.c_str());
    }
    std::printf("####\n");
}

static void run(double start_C, double setpoint_C)
/* RETURN: nothing. Drives the chamber and prints every part of the report. */
{
    rng.seed((uint64_t)std::chrono::system_clock::now().time_since_epoch().count());
    std::vector<Sample> sample_list = step_response(start_C, setpoint_C);
    std::printf("## climate chamber, %.0f degC -> %.0f degC, one sample per second\n", start_C, setpoint_C);
    std::printf("## '##' lines are for the reader: the comparison skips them.\n");
    print_config();
    print_sensors(setpoint_C);
    print_cloud(sample_list, start_C, setpoint_C);
    print_picture(sample_list, start_C, setpoint_C);
    double over   = overshoot_K(sample_list, start_C, setpoint_C);
    double settle = settle_s(sample_list, setpoint_C);
    std::printf("overshoot  ((overshoot: %.2f K))          law <= 0.5 K\n", over);
    std::printf("settled    ((settle: %.0f s))             law <= 4 min\n", settle);
    const char* verdict = std::fabs(sample_list.back().second - setpoint_C) <= BAND_K ? "settled" : "drifting";
    std::printf("chamber    ((verdict: \"%s\"))\n", verdict);
}

int main(int argc, char** argv)
/* RETURN: 0, the choice named by 'argv[1]' printed, '<hwut-end>' after it;
 *         1, where no known choice is named (the choices are printed).   */
{
    const std::string choice = argc > 1 ? argv[1] : "";
    if     ( choice == "heat" ) run(20.0, 40.0);
    else if( choice == "cool" ) run(40.0, 20.0);
    else { std::printf("choices: heat, cool\n"); return 1; }
    std::printf("<hwut-end>\n");
    return 0;
}
