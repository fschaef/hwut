#! /usr/bin/env perl
#
# @hwut {
#     title     = "Demo: a climate chamber's step response -- regions, units, a string law"
#     tolerance { constraints = ["overshoot <= 0.5 K",
#                                "settle <= 4 min",
#                                "verdict == 'settled'"] }
#     choices {
#         heat { features = ["demo-perl+cover-region-verbatim", "demo-perl+cover-region-table", "demo-perl+cover-region-point-cloud",
#                            "demo-perl+cover-region-ignore", "demo-perl+cover-laws-in-units", "demo-perl+cover-string-binding",
#                            "demo-perl+cover-test-level-tolerance", "demo-perl+cover-annotation-lines"] }
#         cool { features = ["demo-perl+cover-region-verbatim", "demo-perl+cover-region-table", "demo-perl+cover-region-point-cloud",
#                            "demo-perl+cover-region-ignore", "demo-perl+cover-laws-in-units", "demo-perl+cover-string-binding",
#                            "demo-perl+cover-test-level-tolerance", "demo-perl+cover-annotation-lines"] }
#     }
# }
#
#______________________________________________________________________________
# SUBJECT  a climate chamber driven from one temperature to another by a PI
#          controller: its configuration, its sensors at the end, its step
#          response, and the three numbers its requirement names.
# REQUIREMENT  The chamber reaches the setpoint within 4 minutes, overshoots
#              it by no more than 0.5 K, and reports itself 'settled'.
#
# Every run is seeded by the clock: the sensors are noisy, the four sensor
# rows come out in a different order, the calibration stamps are today's.
# Both choices pass on every run anyway; each part of the output says how:
#
# '##' lines     notes for the reader. The comparison skips them on both
#                sides, anywhere -- even inside a region.
#
# verbatim       '##! verbatim' ... '####': the configuration as loaded. It is
#                YAML, where indentation is meaning, so nothing is tolerated:
#                no whitespace folding, no numeric band.
#
# table          '##! table key=0 ignore=1 numeric={2:0.0005}': one row per
#                sensor, matched by its NAME (column 0) whatever the order;
#                column 1, the calibration stamp, is not compared; column 2,
#                the reading in K, within 0.05 %.
#
# point-cloud    '##! point-cloud limit=0.5 constraint={...}': the step
#                response as points (t, T). Every point lies within 0.5 of a
#                point of the GOOD file ('limit'), AND every point keeps the
#                envelope stated in the region ('constraint') -- the GOOD's
#                points, too, so a GOOD that breaks its envelope is refused.
#
# ignore         '##! ignore': a picture for the human eye. One noisy sample
#                moves a star; the picture's presence is compared, its
#                contents are not.
#
# units          '((settle: 150 s))' is a quantity; the law says 'settle <= 4
#                min' and the comparison converts. A temperature DIFFERENCE is
#                printed in K, never in degC (an offset unit).
#
# string law     '((verdict: "settled"))' binds a string; 'verdict ==
#                'settled'' judges it.
#
# test-level     the three laws stand ONCE, in the header's own 'tolerance',
# tolerance      and hold for both choices.
#
# CHOICES  heat  20 degC -> 40 degC.
#          cool  40 degC -> 20 degC.
#______________________________________________________________________________
use strict;
use warnings;
use POSIX qw(strftime);
use Time::HiRes qw(time);
use List::Util qw(shuffle max min);

my $DT_S       = 1.0;                  # simulation step
my $DURATION_S = 400;                  # simulated time
my $SAMPLE_S   = 20;                   # one point of the cloud every 20 s
my $BAND_K     = 0.3;                  # 'settled' = within 0.3 K of the setpoint
my $NOISE_K    = 0.02;                 # sensor noise, one sigma
my ($TAU_S, $RATE_K_PER_S) = (300.0, 0.15);   # the plant
my ($KP, $KI)  = (0.6, 0.01);          # the controller
my $PI         = 4 * atan2(1, 1);

my $CONFIG_TEXT = sprintf(<<'YAML', $TAU_S, $RATE_K_PER_S, $KP, $KI);
chamber:
  plant:
    time_constant_s: %.0f
    heater_rate_K_per_s: %s
  controller:
    kind: PI
    kp: %s
    ki: %s
    output: [-1.0, 1.0]
  sensors: [top, middle, bottom, door]
YAML
chomp $CONFIG_TEXT;

#  Offset of each sensor against the air in the middle of the chamber.
my @SENSOR = (["top", +0.10], ["middle", 0.00], ["bottom", -0.10], ["door", -0.40]);


sub gauss {
    # RETURN: number, a draw of the normal distribution (mu, sigma), by the
    #         Box-Muller transform over 'rand'.
    my ($mu, $sigma) = @_;
    return $mu + $sigma * sqrt(-2.0 * log(1.0 - rand())) * cos(2.0 * $PI * rand());
}


sub step_response {
    # RETURN: list of [t_s, measured_C], one sample per simulation step, of
    #         the chamber driven from 'start_C' to 'setpoint_C' by the PI
    #         controller of CONFIG_TEXT, with sensor noise.
    my ($start_C, $setpoint_C) = @_;
    my $ambient  = 20.0;
    my $temp     = $start_C;
    my $integral = 0.0;
    my @sample;
    for (my $t = 0; $t <= $DURATION_S; $t += $DT_S) {
        my $measured = $temp + gauss(0.0, $NOISE_K);
        push @sample, [$t, $measured];
        my $error  = $setpoint_C - $measured;
        my $output = $KP * $error + $KI * $integral;
        #  Anti-windup: integrate only while unsaturated.
        $integral += $error * $DT_S if -1.0 < $output && $output < 1.0;
        $output = max(-1.0, min(1.0, $output));
        $temp  += $DT_S * (($ambient - $temp) / $TAU_S + $RATE_K_PER_S * $output);
    }
    return @sample;
}


sub overshoot_K {
    # RETURN: number, how far in K the chamber went past 'setpoint_C' in the
    #         direction of travel from 'start_C'; 0.0 where it never did.
    my ($sample, $start_C, $setpoint_C) = @_;
    my $sign = $setpoint_C > $start_C ? 1.0 : -1.0;
    return max(0.0, map { $sign * ($_->[1] - $setpoint_C) } @$sample);
}


sub settle_s {
    # RETURN: number, the time in s after which every sample stays within
    #         BAND_K of 'setpoint_C' (the step after the last one outside).
    my ($sample, $setpoint_C) = @_;
    my @outside = map { $_->[0] } grep { abs($_->[1] - $setpoint_C) > $BAND_K } @$sample;
    return @outside ? $outside[-1] + $DT_S : 0.0;
}


sub print_config {
    # RETURN: nothing. Prints the configuration as loaded, byte for byte.
    print "configuration, as loaded (YAML: whitespace is meaning):\n";
    print "##! verbatim\n";
    print "$CONFIG_TEXT\n";
    print "####\n";
}


sub print_sensors {
    # RETURN: nothing. Prints one row per sensor, in a random order, with
    #         today's calibration stamp and the reading at the end in K.
    my ($setpoint_C) = @_;
    print "sensors at the end, in K (the order is the bus's):\n";
    print "    sensor  calibrated           reading_K\n";
    print "##! table key=0 ignore=1 numeric={2:0.0005}\n";
    my $stamp = strftime("%Y-%m-%dT%H:%M:%S", localtime);
    for my $sensor (shuffle @SENSOR) {
        my $reading = $setpoint_C + $sensor->[1] + gauss(0.0, $NOISE_K) + 273.15;
        printf "    %-6s  %s  %9.2f\n", $sensor->[0], $stamp, $reading;
    }
    print "####\n";
}


sub print_cloud {
    # RETURN: nothing. Prints the step response, one point (t_s, T_degC)
    #         every SAMPLE_S, framed with the envelope the requirement allows.
    my ($sample, $start_C, $setpoint_C) = @_;
    my ($low, $high) = sort { $a <=> $b } ($start_C, $setpoint_C);
    if ($setpoint_C > $start_C) { $high += 0.5 }
    else                        { $low  -= 0.5 }
    #  0.1 K beyond the envelope on either side: the sensor's noise.
    printf "step response, t in s against T in degC; envelope %.1f .. %.1f:\n", $low, $high;
    printf "##! point-cloud limit=0.5 constraint={y >= %.1f and y <= %.1f}\n", $low - 0.1, $high + 0.1;
    for (@$sample) {
        printf "    %5.0f  %6.2f\n", @$_ if $_->[0] % $SAMPLE_S == 0;
    }
    print "####\n";
}


sub print_picture {
    # RETURN: nothing. Prints the step response as stars, for the human eye
    #         only: one row per 40 s, one column per 0.5 K.
    my ($sample, $start_C, $setpoint_C) = @_;
    my $low = min($start_C, $setpoint_C) - 1.0;
    print "the same, as a picture ('|' the setpoint):\n";
    print "##! ignore\n";
    for my $s (@$sample) {
        next unless $s->[0] % 40 == 0;
        my @row = (" ") x 46;
        $row[sprintf("%.0f", ($setpoint_C - $low) / 0.5)] = "|";
        $row[max(0, min(45, sprintf("%.0f", ($s->[1] - $low) / 0.5)))] = "*";
        (my $text = join("", @row)) =~ s/\s+$//;
        printf "    %4.0f s  %s\n", $s->[0], $text;
    }
    print "####\n";
}


sub run {
    # RETURN: nothing. Drives the chamber and prints every part of the report.
    my ($start_C, $setpoint_C) = @_;
    srand(int(time * 1e6) % 2**31);
    my @sample = step_response($start_C, $setpoint_C);
    printf "## climate chamber, %.0f degC -> %.0f degC, one sample per second\n", $start_C, $setpoint_C;
    print "## '##' lines are for the reader: the comparison skips them.\n";
    print_config();
    print_sensors($setpoint_C);
    print_cloud(\@sample, $start_C, $setpoint_C);
    print_picture(\@sample, $start_C, $setpoint_C);
    my $over   = overshoot_K(\@sample, $start_C, $setpoint_C);
    my $settle = settle_s(\@sample, $setpoint_C);
    printf "overshoot  ((overshoot: %.2f K))          law <= 0.5 K\n", $over;
    printf "settled    ((settle: %.0f s))             law <= 4 min\n", $settle;
    my $verdict = abs($sample[-1][1] - $setpoint_C) <= $BAND_K ? "settled" : "drifting";
    print "chamber    ((verdict: \"$verdict\"))\n";
}


my %CHOICE = (heat => [20.0, 40.0], cool => [40.0, 20.0]);

my $choice = $ARGV[0] // "";
unless ($CHOICE{$choice}) {
    print "choices: heat, cool\n";
    exit 1;
}
run(@{$CHOICE{$choice}});
print "<hwut-end>\n";
