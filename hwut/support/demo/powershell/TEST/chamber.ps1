#! /usr/bin/env pwsh
#
# @hwut {
#     title     = "Demo: a climate chamber's step response -- regions, units, a string law"
#     tolerance { constraints = ["overshoot <= 0.5 K",
#                                "settle <= 4 min",
#                                "verdict == 'settled'"] }
#     choices {
#         heat { features = ["region-verbatim", "region-table", "region-point-cloud",
#                            "region-ignore", "laws-in-units", "string-binding",
#                            "test-level-tolerance", "annotation-lines"] }
#         cool { features = ["region-verbatim", "region-table", "region-point-cloud",
#                            "region-ignore", "laws-in-units", "string-binding",
#                            "test-level-tolerance", "annotation-lines"] }
#     }
# }
#
<#
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
#>
. "$PSScriptRoot/hwut_support.ps1"

$DT_S         = 1.0                 # simulation step
$DURATION_S   = 400                 # simulated time
$SAMPLE_S     = 20                  # one point of the cloud every 20 s
$BAND_K       = 0.3                 # 'settled' = within 0.3 K of the setpoint
$NOISE_K      = 0.02                # sensor noise, one sigma
$TAU_S, $RATE_K_PER_S = 300.0, 0.15 # the plant
$KP, $KI      = 0.6, 0.01           # the controller

$CONFIG_TEXT = @"
chamber:
  plant:
    time_constant_s: $('{0:F0}' -f $TAU_S)
    heater_rate_K_per_s: $RATE_K_PER_S
  controller:
    kind: PI
    kp: $KP
    ki: $KI
    output: [-1.0, 1.0]
  sensors: [top, middle, bottom, door]
"@

#  Offset of each sensor against the air in the middle of the chamber.
$SENSOR_OFFSET_DB = [ordered]@{ top = 0.10; middle = 0.00; bottom = -0.10; door = -0.40 }

$script:rng = [Random]::new([int]([DateTime]::UtcNow.Ticks % [int]::MaxValue))

<# RETURN: double, drawn from the normal distribution of 'mu' and 'sigma' (Box-Muller). #>
function gauss([double]$mu, [double]$sigma) {
    $u = 1.0 - $script:rng.NextDouble()
    $mu + $sigma * [Math]::Sqrt(-2.0 * [Math]::Log($u)) * [Math]::Cos(2.0 * [Math]::PI * $script:rng.NextDouble())
}

<#
RETURN: list of @(t_s, measured_C), one sample per simulation step, of the
        chamber driven from 'start_C' to 'setpoint_C' by the PI controller of
        CONFIG_TEXT, with sensor noise drawn at random.
#>
function step_response([double]$start_C, [double]$setpoint_C) {
    $ambient  = 20.0
    $temp     = $start_C
    $integral = 0.0
    $sample_list = [System.Collections.Generic.List[object]]::new()
    $t = 0.0
    while ($t -le $DURATION_S) {
        $measured = $temp + (gauss 0.0 $NOISE_K)
        $sample_list.Add(@($t, $measured))
        $error_K = $setpoint_C - $measured
        $output  = $KP * $error_K + $KI * $integral
        if (-1.0 -lt $output -and $output -lt 1.0) {      # anti-windup: integrate
            $integral += $error_K * $DT_S                  # only while unsaturated
        }
        $output = [Math]::Max(-1.0, [Math]::Min(1.0, $output))
        $temp  += $DT_S * (($ambient - $temp) / $TAU_S + $RATE_K_PER_S * $output)
        $t     += $DT_S
    }
    return , $sample_list
}

<#
RETURN: double, how far in K the chamber went past 'setpoint_C' in the
        direction of travel from 'start_C'; 0.0 where it never did.
#>
function overshoot_K($sample_list, [double]$start_C, [double]$setpoint_C) {
    $sign = if ($setpoint_C -gt $start_C) { 1.0 } else { -1.0 }
    $most = 0.0
    foreach ($sample in $sample_list) { $most = [Math]::Max($most, $sign * ($sample[1] - $setpoint_C)) }
    return $most
}

<#
RETURN: double, the time in s after which every sample stays within BAND_K
        of 'setpoint_C' (the step after the last one outside).
#>
function settle_s($sample_list, [double]$setpoint_C) {
    $last = $null
    foreach ($sample in $sample_list) { if ([Math]::Abs($sample[1] - $setpoint_C) -gt $BAND_K) { $last = $sample[0] } }
    if ($null -eq $last) { return 0.0 } else { return $last + $DT_S }
}

<# RETURN: nothing. Prints the configuration as loaded, byte for byte. #>
function print_config {
    Out-Py 'configuration, as loaded (YAML: whitespace is meaning):'
    Out-Py '##! verbatim'
    Out-Py ($CONFIG_TEXT -replace "`r", '')
    Out-Py '####'
}

<#
RETURN: nothing. Prints one row per sensor, in a random order, with today's
        calibration stamp and the reading at the end in K.
#>
function print_sensors([double]$setpoint_C) {
    Out-Py 'sensors at the end, in K (the order is the bus''s):'
    Out-Py '    sensor  calibrated           reading_K'
    Out-Py '##! table key=0 ignore=1 numeric={2:0.0005}'
    $name_list = [string[]]@($SENSOR_OFFSET_DB.Keys)
    for ($i = $name_list.Count - 1; $i -gt 0; $i--) {           # Fisher-Yates
        $j = $script:rng.Next($i + 1)
        $name_list[$i], $name_list[$j] = $name_list[$j], $name_list[$i]
    }
    $stamp = (Get-Date).ToString("yyyy-MM-dd'T'HH:mm:ss")
    foreach ($name in $name_list) {
        $reading = $setpoint_C + $SENSOR_OFFSET_DB[$name] + (gauss 0.0 $NOISE_K) + 273.15
        Out-Py ('    {0,-6}  {1}  {2,9:F2}' -f $name, $stamp, $reading)
    }
    Out-Py '####'
}

<#
RETURN: nothing. Prints the step response, one point (t_s, T_degC) every
        SAMPLE_S, framed with the envelope the requirement allows.
#>
function print_cloud($sample_list, [double]$start_C, [double]$setpoint_C) {
    $low, $high = [Math]::Min($start_C, $setpoint_C), [Math]::Max($start_C, $setpoint_C)
    if ($setpoint_C -gt $start_C) { $high += 0.5 }
    else                          { $low  -= 0.5 }
    #  0.1 K beyond the envelope on either side: the sensor's noise.
    Out-Py ('step response, t in s against T in degC; envelope {0:F1} .. {1:F1}:' -f $low, $high)
    Out-Py ('##! point-cloud limit=0.5 constraint={{y >= {0:F1} and y <= {1:F1}}}' -f ($low - 0.1), ($high + 0.1))
    foreach ($sample in $sample_list) {
        if ($sample[0] % $SAMPLE_S -eq 0) { Out-Py ('    {0,5:F0}  {1,6:F2}' -f $sample[0], $sample[1]) }
    }
    Out-Py '####'
}

<#
RETURN: nothing. Prints the step response as stars, for the human eye only:
        one row per 40 s, one column per 0.5 K.
#>
function print_picture($sample_list, [double]$start_C, [double]$setpoint_C) {
    $low = [Math]::Min($start_C, $setpoint_C) - 1.0
    Out-Py 'the same, as a picture (''|'' the setpoint):'
    Out-Py '##! ignore'
    foreach ($sample in $sample_list) {
        if ($sample[0] % 40 -eq 0) {
            $row = [char[]](' ' * 46)
            $row[[int][Math]::Round(($setpoint_C - $low) / 0.5)] = '|'
            $row[[Math]::Max(0, [Math]::Min(45, [int][Math]::Round(($sample[1] - $low) / 0.5)))] = '*'
            Out-Py ('    {0,4:F0} s  {1}' -f $sample[0], ([string]::new($row)).TrimEnd())
        }
    }
    Out-Py '####'
}

<# RETURN: nothing. Drives the chamber and prints every part of the report. #>
function run([double]$start_C, [double]$setpoint_C) {
    $sample_list = step_response $start_C $setpoint_C
    Out-Py ('## climate chamber, {0:F0} degC -> {1:F0} degC, one sample per second' -f $start_C, $setpoint_C)
    Out-Py '## ''##'' lines are for the reader: the comparison skips them.'
    print_config
    print_sensors $setpoint_C
    print_cloud   $sample_list $start_C $setpoint_C
    print_picture $sample_list $start_C $setpoint_C
    $over   = overshoot_K $sample_list $start_C $setpoint_C
    $settle = settle_s    $sample_list $setpoint_C
    Out-Py ('overshoot  ((overshoot: {0:F2} K))          law <= 0.5 K' -f $over)
    Out-Py ('settled    ((settle: {0:F0} s))             law <= 4 min' -f $settle)
    $verdict = if ([Math]::Abs($sample_list[-1][1] - $setpoint_C) -le $BAND_K) { 'settled' } else { 'drifting' }
    Out-Py ('chamber    ((verdict: "{0}"))' -f $verdict)
}

$CHOICE_DB = [ordered]@{ heat = @(20.0, 40.0); cool = @(40.0, 20.0) }

$choice = if ($args.Count -gt 0) { [string]$args[0] } else { '' }
if (@($CHOICE_DB.Keys) -cnotcontains $choice) {
    Out-Py ('choices: {0}' -f (@($CHOICE_DB.Keys) -join ', '))
    exit 1
}
run $CHOICE_DB[$choice][0] $CHOICE_DB[$choice][1]
Out-Py '<hwut-end>'
