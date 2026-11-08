/* @hwut {
 *     title     = "Demo: a climate chamber's step response -- regions, units, a string law"
 *     build     { framework = "make", target = "%.exe" }
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
 * ______________________________________________________________________________
 * SUBJECT  a climate chamber driven from one temperature to another by a PI
 *          controller: its configuration, its sensors at the end, its step
 *          response, and the three numbers its requirement names.
 * REQUIREMENT  The chamber reaches the setpoint within 4 minutes, overshoots
 *              it by no more than 0.5 K, and reports itself 'settled'.
 *
 * Every run is seeded by the clock: the sensors are noisy, the four sensor
 * rows come out in a different order, the calibration stamps are today's.
 * Both choices pass on every run anyway; each part of the output says how:
 *
 * '##' lines     notes for the reader. The comparison skips them on both
 *                sides, anywhere -- even inside a region.
 *
 * verbatim       '##! verbatim' ... '####': the configuration as loaded. It is
 *                YAML, where indentation is meaning, so nothing is tolerated:
 *                no whitespace folding, no numeric band.
 *
 * table          '##! table key=0 ignore=1 numeric={2:0.0005}': one row per
 *                sensor, matched by its NAME (column 0) whatever the order;
 *                column 1, the calibration stamp, is not compared; column 2,
 *                the reading in K, within 0.05 %.
 *
 * point-cloud    '##! point-cloud limit=0.5 constraint={...}': the step
 *                response as points (t, T). Every point lies within 0.5 of a
 *                point of the GOOD file ('limit'), AND every point keeps the
 *                envelope stated in the region ('constraint') -- the GOOD's
 *                points, too, so a GOOD that breaks its envelope is refused.
 *
 * ignore         '##! ignore': a picture for the human eye. One noisy sample
 *                moves a star; the picture's presence is compared, its
 *                contents are not.
 *
 * units          '((settle: 150 s))' is a quantity; the law says 'settle <= 4
 *                min' and the comparison converts. A temperature DIFFERENCE is
 *                printed in K, never in degC (an offset unit).
 *
 * string law     '((verdict: "settled"))' binds a string; 'verdict ==
 *                'settled'' judges it.
 *
 * test-level     the three laws stand ONCE, in the header's own 'tolerance',
 * tolerance      and hold for both choices.
 *
 * CHOICES  heat  20 degC -> 40 degC.
 *          cool  40 degC -> 20 degC.
 * ______________________________________________________________________________
 */
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Random;

final class Chamber {
    static final double DT_S         = 1.0;     // simulation step
    static final double DURATION_S   = 400;     // simulated time
    static final double SAMPLE_S     = 20;      // one point of the cloud every 20 s
    static final double BAND_K       = 0.3;     // 'settled' = within 0.3 K of the setpoint
    static final double NOISE_K      = 0.02;    // sensor noise, one sigma
    static final double TAU_S        = 300.0;   // the plant
    static final double RATE_K_PER_S = 0.15;
    static final double KP           = 0.6;     // the controller
    static final double KI           = 0.01;

    static final String CONFIG_TEXT = String.join("\n",
        "chamber:",
        "  plant:",
        String.format(Locale.ROOT, "    time_constant_s: %.0f", TAU_S),
        "    heater_rate_K_per_s: " + RATE_K_PER_S,
        "  controller:",
        "    kind: PI",
        "    kp: " + KP,
        "    ki: " + KI,
        "    output: [-1.0, 1.0]",
        "  sensors: [top, middle, bottom, door]");

    //  Offset of each sensor against the air in the middle of the chamber.
    static final Map<String, Double> SENSOR_OFFSET_DB = new LinkedHashMap<>();
    static {
        SENSOR_OFFSET_DB.put("top",    +0.10);
        SENSOR_OFFSET_DB.put("middle",  0.00);
        SENSOR_OFFSET_DB.put("bottom", -0.10);
        SENSOR_OFFSET_DB.put("door",   -0.40);
    }

    /** RETURN: nothing; 'format' laid out with 'args', the decimal point a
     *          '.' whatever the locale, is printed as one line. */
    static void say(String format, Object... args) {
        System.out.println(String.format(Locale.ROOT, format, args));
    }

    /** RETURN: List<double[]>, (t_s, measured_C), one sample per simulation
     *          step, of the chamber driven from 'startC' to 'setpointC' by
     *          the PI controller of CONFIG_TEXT, with sensor noise drawn from
     *          'rng'. */
    static List<double[]> stepResponse(double startC, double setpointC, Random rng) {
        double ambient  = 20.0;
        double temp     = startC;
        double integral = 0.0;
        List<double[]> sampleList = new ArrayList<>();
        for (double t = 0.0; t <= DURATION_S; t += DT_S) {
            double measured = temp + NOISE_K * rng.nextGaussian();
            sampleList.add(new double[] { t, measured });
            double error  = setpointC - measured;
            double output = KP * error + KI * integral;
            if (-1.0 < output && output < 1.0)          // anti-windup: integrate
                integral += error * DT_S;               // only while unsaturated
            output = Math.max(-1.0, Math.min(1.0, output));
            temp += DT_S * ((ambient - temp) / TAU_S + RATE_K_PER_S * output);
        }
        return sampleList;
    }

    /** RETURN: double, how far in K the chamber went past 'setpointC' in the
     *          direction of travel from 'startC'; 0.0 where it never did. */
    static double overshootK(List<double[]> sampleList, double startC, double setpointC) {
        double sign = setpointC > startC ? 1.0 : -1.0;
        double most = 0.0;
        for (double[] s : sampleList) most = Math.max(most, sign * (s[1] - setpointC));
        return most;
    }

    /** RETURN: double, the time in s after which every sample stays within
     *          BAND_K of 'setpointC' (the step after the last one outside). */
    static double settleS(List<double[]> sampleList, double setpointC) {
        double last = -1.0;
        for (double[] s : sampleList) if (Math.abs(s[1] - setpointC) > BAND_K) last = s[0];
        return last < 0.0 ? 0.0 : last + DT_S;
    }

    /** RETURN: nothing; the configuration as loaded is printed, byte for byte. */
    static void printConfig() {
        System.out.println("configuration, as loaded (YAML: whitespace is meaning):");
        System.out.println("##! verbatim");
        System.out.println(CONFIG_TEXT);
        System.out.println("####");
    }

    /** RETURN: nothing; one row per sensor is printed, in a random order,
     *          with today's calibration stamp and the reading at the end in K. */
    static void printSensors(double setpointC, Random rng) {
        System.out.println("sensors at the end, in K (the order is the bus's):");
        System.out.println("    sensor  calibrated           reading_K");
        System.out.println("##! table key=0 ignore=1 numeric={2:0.0005}");
        List<String> nameList = new ArrayList<>(SENSOR_OFFSET_DB.keySet());
        Collections.shuffle(nameList, rng);
        String stamp = LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss"));
        for (String name : nameList) {
            double reading = setpointC + SENSOR_OFFSET_DB.get(name) + NOISE_K * rng.nextGaussian() + 273.15;
            say("    %-6s  %s  %9.2f", name, stamp, reading);
        }
        System.out.println("####");
    }

    /** RETURN: nothing; the step response is printed, one point (t_s,
     *          T_degC) every SAMPLE_S, framed with the envelope the
     *          requirement allows. */
    static void printCloud(List<double[]> sampleList, double startC, double setpointC) {
        double low = Math.min(startC, setpointC), high = Math.max(startC, setpointC);
        if (setpointC > startC) high += 0.5;
        else                    low  -= 0.5;
        //  0.1 K beyond the envelope on either side: the sensor's noise.
        say("step response, t in s against T in degC; envelope %.1f .. %.1f:", low, high);
        say("##! point-cloud limit=0.5 constraint={y >= %.1f and y <= %.1f}", low - 0.1, high + 0.1);
        for (double[] s : sampleList)
            if (s[0] % SAMPLE_S == 0) say("    %5.0f  %6.2f", s[0], s[1]);
        System.out.println("####");
    }

    /** RETURN: nothing; the step response is printed as stars, for the human
     *          eye only: one row per 40 s, one column per 0.5 K. */
    static void printPicture(List<double[]> sampleList, double startC, double setpointC) {
        double low = Math.min(startC, setpointC) - 1.0;
        System.out.println("the same, as a picture ('|' the setpoint):");
        System.out.println("##! ignore");
        for (double[] s : sampleList) {
            if (s[0] % 40 != 0) continue;
            char[] row = " ".repeat(46).toCharArray();
            row[(int) Math.rint((setpointC - low) / 0.5)] = '|';
            row[(int) Math.max(0, Math.min(45, Math.rint((s[1] - low) / 0.5)))] = '*';
            say("    %4.0f s  %s", s[0], new String(row).stripTrailing());
        }
        System.out.println("####");
    }

    /** RETURN: nothing; the chamber was driven and every part of the report
     *          printed. */
    static void run(double startC, double setpointC) {
        Random rng = new Random(System.nanoTime());
        List<double[]> sampleList = stepResponse(startC, setpointC, rng);
        say("## climate chamber, %.0f degC -> %.0f degC, one sample per second", startC, setpointC);
        System.out.println("## '##' lines are for the reader: the comparison skips them.");
        printConfig();
        printSensors(setpointC, rng);
        printCloud(sampleList, startC, setpointC);
        printPicture(sampleList, startC, setpointC);
        double over   = overshootK(sampleList, startC, setpointC);
        double settle = settleS(sampleList, setpointC);
        say("overshoot  ((overshoot: %.2f K))          law <= 0.5 K", over);
        say("settled    ((settle: %.0f s))             law <= 4 min", settle);
        String verdict = Math.abs(sampleList.get(sampleList.size() - 1)[1] - setpointC) <= BAND_K ? "settled" : "drifting";
        say("chamber    ((verdict: \"%s\"))", verdict);
    }

    public static void main(String[] args) {
        Map<String, double[]> choiceDb = new LinkedHashMap<>();
        choiceDb.put("heat", new double[] { 20.0, 40.0 });
        choiceDb.put("cool", new double[] { 40.0, 20.0 });
        String choice = args.length > 0 ? args[0] : "";
        if (!choiceDb.containsKey(choice)) {
            System.out.println("choices: " + String.join(", ", choiceDb.keySet()));
            System.exit(1);
        }
        run(choiceDb.get(choice)[0], choiceDb.get(choice)[1]);
        System.out.println("<hwut-end>");
    }
}
