// @hwut {
//     title     = "Demo: a climate chamber's step response -- regions, units, a string law"
//     build     { framework = "make", executable = "%.exe"
//                 caps { file_size_mb = 256 } }
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
// _____________________________________________________________________________
// SUBJECT  a climate chamber driven from one temperature to another by a PI
//          controller: its configuration, its sensors at the end, its step
//          response, and the three numbers its requirement names.
// REQUIREMENT  The chamber reaches the setpoint within 4 minutes, overshoots
//              it by no more than 0.5 K, and reports itself 'settled'.
//
// 'chamber.py' of the Python demonstration, in Go; its GOOD files are
// Python's, and its comment says what each part of the output shows:
// '##' notes, '##! verbatim', '##! table key=0 ignore=1 numeric={2:0.0005}',
// '##! point-cloud limit=0.5 constraint={...}', '##! ignore', laws in units
// ('((settle: 150 s))' against 'settle <= 4 min'), a string law, and the
// laws stated once, in the header's own 'tolerance'.
//
// Every run is seeded by the clock: the sensors are noisy, the four sensor
// rows come out in a different order, the calibration stamps are today's.
//
// CHOICES  heat  20 degC -> 40 degC.
//          cool  40 degC -> 20 degC.
// _____________________________________________________________________________

package main

import (
	"fmt"
	"math"
	"math/rand/v2"
	"os"
	"strings"
	"time"
)

const (
	DT_S         = 1.0   // simulation step
	DURATION_S   = 400.0 // simulated time
	SAMPLE_S     = 20    // one point of the cloud every 20 s
	BAND_K       = 0.3   // 'settled' = within 0.3 K of the setpoint
	NOISE_K      = 0.02  // sensor noise, one sigma
	TAU_S        = 300.0 // the plant
	RATE_K_PER_S = 0.15
	KP           = 0.6 // the controller
	KI           = 0.01
)

var CONFIG_TEXT = fmt.Sprintf(`chamber:
  plant:
    time_constant_s: %.0f
    heater_rate_K_per_s: %s
  controller:
    kind: PI
    kp: %s
    ki: %s
    output: [-1.0, 1.0]
  sensors: [top, middle, bottom, door]`, TAU_S, "0.15", "0.6", "0.01")

// Offset of each sensor against the air in the middle of the chamber.
var sensorNameList = []string{"top", "middle", "bottom", "door"}
var sensorOffsetDb = map[string]float64{"top": +0.10, "middle": 0.00, "bottom": -0.10, "door": -0.40}

type sample struct{ t, temp float64 }

// RETURN: float64, a draw of the normal distribution (mu, sigma) from 'rng'.
func gauss(rng *rand.Rand, mu, sigma float64) float64 {
	return mu + sigma*rng.NormFloat64()
}

// RETURN: []sample, one (t_s, measured_C) per simulation step, of the
// chamber driven from 'startC' to 'setpointC' by the PI controller of
// CONFIG_TEXT, with sensor noise drawn from 'rng'.
func stepResponse(startC, setpointC float64, rng *rand.Rand) []sample {
	ambient, temp, integral := 20.0, startC, 0.0
	var sampleList []sample
	for t := 0.0; t <= DURATION_S; t += DT_S {
		measured := temp + gauss(rng, 0.0, NOISE_K)
		sampleList = append(sampleList, sample{t, measured})
		e := setpointC - measured
		output := KP*e + KI*integral
		if -1.0 < output && output < 1.0 { // anti-windup: integrate
			integral += e * DT_S // only while unsaturated
		}
		output = math.Max(-1.0, math.Min(1.0, output))
		temp += DT_S * ((ambient-temp)/TAU_S + RATE_K_PER_S*output)
	}
	return sampleList
}

// RETURN: float64, how far in K the chamber went past 'setpointC' in the
// direction of travel from 'startC'; 0.0 where it never did.
func overshootK(sampleList []sample, startC, setpointC float64) float64 {
	sign := -1.0
	if setpointC > startC {
		sign = 1.0
	}
	result := 0.0
	for _, s := range sampleList {
		result = math.Max(result, sign*(s.temp-setpointC))
	}
	return result
}

// RETURN: float64, the time in s after which every sample stays within
// BAND_K of 'setpointC' (the step after the last one outside).
func settleS(sampleList []sample, setpointC float64) float64 {
	result := 0.0
	for _, s := range sampleList {
		if math.Abs(s.temp-setpointC) > BAND_K {
			result = s.t + DT_S
		}
	}
	return result
}

// RETURN: nothing. Prints the configuration as loaded, byte for byte.
func printConfig() {
	fmt.Println("configuration, as loaded (YAML: whitespace is meaning):")
	fmt.Println("##! verbatim")
	fmt.Println(CONFIG_TEXT)
	fmt.Println("####")
}

// RETURN: nothing. Prints one row per sensor, in a random order, with
// today's calibration stamp and the reading at the end in K.
func printSensors(setpointC float64, rng *rand.Rand) {
	fmt.Println("sensors at the end, in K (the order is the bus's):")
	fmt.Println("    sensor  calibrated           reading_K")
	fmt.Println("##! table key=0 ignore=1 numeric={2:0.0005}")
	nameList := append([]string(nil), sensorNameList...)
	rng.Shuffle(len(nameList), func(i, j int) { nameList[i], nameList[j] = nameList[j], nameList[i] })
	stamp := time.Now().Format("2006-01-02T15:04:05")
	for _, name := range nameList {
		reading := setpointC + sensorOffsetDb[name] + gauss(rng, 0.0, NOISE_K) + 273.15
		fmt.Printf("    %-6s  %s  %9.2f\n", name, stamp, reading)
	}
	fmt.Println("####")
}

// RETURN: nothing. Prints the step response, one point (t_s, T_degC) every
// SAMPLE_S, framed with the envelope the requirement allows.
func printCloud(sampleList []sample, startC, setpointC float64) {
	low, high := math.Min(startC, setpointC), math.Max(startC, setpointC)
	if setpointC > startC {
		high += 0.5
	} else {
		low -= 0.5
	}
	// 0.1 K beyond the envelope on either side: the sensor's noise.
	fmt.Printf("step response, t in s against T in degC; envelope %.1f .. %.1f:\n", low, high)
	fmt.Printf("##! point-cloud limit=0.5 constraint={y >= %.1f and y <= %.1f}\n", low-0.1, high+0.1)
	for _, s := range sampleList {
		if math.Mod(s.t, SAMPLE_S) == 0 {
			fmt.Printf("    %5.0f  %6.2f\n", s.t, s.temp)
		}
	}
	fmt.Println("####")
}

// RETURN: int, 'x' rounded to the nearest integer, a half to the even one --
// as Python's 'round'.
func roundEven(x float64) int {
	return int(math.RoundToEven(x))
}

// RETURN: nothing. Prints the step response as stars, for the human eye
// only: one row per 40 s, one column per 0.5 K.
func printPicture(sampleList []sample, startC, setpointC float64) {
	low := math.Min(startC, setpointC) - 1.0
	fmt.Println("the same, as a picture ('|' the setpoint):")
	fmt.Println("##! ignore")
	for _, s := range sampleList {
		if math.Mod(s.t, 40) == 0 {
			row := []byte(strings.Repeat(" ", 46))
			row[roundEven((setpointC-low)/0.5)] = '|'
			row[max(0, min(45, roundEven((s.temp-low)/0.5)))] = '*'
			fmt.Printf("    %4.0f s  %s\n", s.t, strings.TrimRight(string(row), " "))
		}
	}
	fmt.Println("####")
}

// RETURN: nothing. Drives the chamber and prints every part of the report.
func run(startC, setpointC float64) {
	seed := uint64(time.Now().UnixNano())
	rng := rand.New(rand.NewPCG(seed, seed>>32))
	sampleList := stepResponse(startC, setpointC, rng)
	fmt.Printf("## climate chamber, %.0f degC -> %.0f degC, one sample per second\n", startC, setpointC)
	fmt.Println("## '##' lines are for the reader: the comparison skips them.")
	printConfig()
	printSensors(setpointC, rng)
	printCloud(sampleList, startC, setpointC)
	printPicture(sampleList, startC, setpointC)
	over := overshootK(sampleList, startC, setpointC)
	settle := settleS(sampleList, setpointC)
	fmt.Printf("overshoot  ((overshoot: %.2f K))          law <= 0.5 K\n", over)
	fmt.Printf("settled    ((settle: %.0f s))             law <= 4 min\n", settle)
	verdict := "drifting"
	if math.Abs(sampleList[len(sampleList)-1].temp-setpointC) <= BAND_K {
		verdict = "settled"
	}
	fmt.Printf("chamber    ((verdict: \"%s\"))\n", verdict)
}

// RETURN: nothing; the choice named on the command line is run and
// '<hwut-end>' printed -- else the choices are named and the exit status
// is 1.
func main() {
	choice := ""
	if len(os.Args) > 1 {
		choice = os.Args[1]
	}
	switch choice {
	case "heat":
		run(20.0, 40.0)
	case "cool":
		run(40.0, 20.0)
	default:
		fmt.Println("choices: heat, cool")
		os.Exit(1)
	}
	fmt.Println("<hwut-end>")
}
