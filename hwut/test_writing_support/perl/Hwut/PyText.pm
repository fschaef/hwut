# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#______________________________________________________________________________
#
# PURPOSE: TEXT AS PYTHON PRINTS IT -- so a Perl test and a Python test of the
#          same module print the same bytes, and share one GOOD file by a
#          '.link' (bookkeeper B-32).
#
#     float_repr(1.0)        '1.0'          repr(1.0)
#     float_repr(0.1)        '0.1'          the shortest text that reads back
#     float_repr(1e-05)      '1e-05'        exponential below 1e-4 ...
#     float_repr(1e16)       '1e+16'        ... and from 1e16 on
#     list_repr([3, 1])      '[3, 1]'       numbers bare
#     list_repr(['a'], 1)    "['a']"        strings quoted, as repr quotes them
#     tuple_repr(['a'], 1)   "('a',)"       a tuple of one keeps its comma
#     bytes_repr("\e[A")     "b'\x1b[A'"    a byte string, as Python's bytes
#     bool_text(1)           'True'
#     none_or(undef)         'None'
#
# A float is told from an integer by the caller: Perl has one scalar, Python
# has two types, and only the test knows which one it printed.
#______________________________________________________________________________
package Hwut::PyText;
use strict;
use warnings;
use Exporter 'import';

our @EXPORT_OK = qw(float_repr list_repr tuple_repr str_repr bytes_repr bool_text none_or py_round);


sub float_repr {
    # RETURN: string, 'x' as Python's 'repr(float)' writes it -- the shortest
    #         decimal that reads back to the same double, fixed notation where
    #         the decimal point falls in (-4, 16], exponential else.
    my ($x) = @_;
    return "nan"  if $x != $x;
    return "inf"  if $x ==  9**9**9;
    return "-inf" if $x == -9**9**9;
    return ($x < 0 || 1 / $x < 0 ? "-0.0" : "0.0") if $x == 0;
    my $text;
    for my $precision (0 .. 16) {
        $text = sprintf("%.${precision}e", $x);
        last if $text + 0 == $x;
    }
    my ($sign, $head, $tail, $exponent) =
        $text =~ /^(-?)(\d)(?:\.(\d*))?e([-+]\d+)$/ or die "float_repr: '$text'";
    my $digits = $head . ($tail // "");
    $digits =~ s/0+$//;
    $digits = "0" if $digits eq "";
    my $point = $exponent + 1;        # value = 0.<digits> * 10^point
    if ($point > -4 && $point <= 16) {
        my $n = length $digits;
        return $sign . "0." . ("0" x -$point) . $digits     if $point <= 0;
        return $sign . $digits . ("0" x ($point - $n)) . ".0" if $point >= $n;
        return $sign . substr($digits, 0, $point) . "." . substr($digits, $point);
    }
    my $mantissa = length($digits) > 1
                 ? substr($digits, 0, 1) . "." . substr($digits, 1) : $digits;
    my $e = $point - 1;
    return sprintf("%s%se%s%02d", $sign, $mantissa, $e < 0 ? "-" : "+", abs $e);
}


sub str_repr {
    # RETURN: string, 's' as Python's 'repr(str)' writes a plain string --
    #         single quotes, or double quotes where it holds a single quote
    #         and no double one; backslash and the quote escaped.
    my ($s) = @_;
    return _quoted($s, 0);
}


sub bytes_repr {
    # RETURN: string, the byte string 'b' as Python's 'repr(bytes)' writes it
    #         -- "b'\x1b[A'": printable ASCII as it stands, '\t', '\n',
    #         '\r', every other byte as '\xNN'.
    my ($b) = @_;
    return "b" . _quoted($b, 1);
}


sub _quoted {
    # RETURN: string, 's' in the quotes Python's repr chooses -- single, or
    #         double where it holds a single quote and no double one -- the
    #         backslash, that quote and what does not print escaped. Where
    #         'bytes_f', every byte from 0x7f on is escaped too; a str keeps
    #         printable non-ASCII characters as they stand.
    my ($s, $bytes_f) = @_;
    my $quote = ($s =~ /'/ && $s !~ /"/) ? '"' : "'";
    my $out = "";
    for my $c (split //, $s) {
        my $n = ord $c;
        if    ($c eq "\\")                    { $out .= "\\\\" }
        elsif ($c eq $quote)                   { $out .= "\\$quote" }
        elsif ($c eq "\n")                     { $out .= "\\n" }
        elsif ($c eq "\t")                     { $out .= "\\t" }
        elsif ($c eq "\r")                     { $out .= "\\r" }
        elsif ($n < 0x20 || ($n >= 0x7f && ($bytes_f || $n < 0xa0))) {
            $out .= sprintf("\\x%02x", $n);
        }
        else                                   { $out .= $c }
    }
    return $quote . $out . $quote;
}


sub list_repr {
    # RETURN: string, the array ref 'list' as Python prints a list -- '[a, b]';
    #         each element quoted as a string where 'strings_f', bare else.
    my ($list, $strings_f) = @_;
    return "[" . join(", ", map { $strings_f ? str_repr($_) : $_ } @$list) . "]";
}


sub tuple_repr {
    # RETURN: string, the array ref 'list' as Python prints a tuple -- '()',
    #         "('a',)" for one element (the comma Python writes), "('a', 'b')";
    #         strings quoted where 'strings_f'.
    my ($list, $strings_f) = @_;
    my @item = map { $strings_f ? str_repr($_) : $_ } @$list;
    return "()"              if !@item;
    return "($item[0],)"     if @item == 1;
    return "(" . join(", ", @item) . ")";
}


sub none_or {
    # RETURN: string, 'None' where 'value' is undef, 'value' else.
    my ($value) = @_;
    return defined $value ? $value : "None";
}


sub bool_text {
    # RETURN: string, 'True' where 'value' is true, 'False' else.
    my ($value) = @_;
    return $value ? "True" : "False";
}


sub py_round {
    # RETURN: integer, 'x' rounded as Python's 'round(x)' rounds -- to the
    #         nearest integer, a half to the EVEN one (C's printf does the
    #         same, so the two agree to the bit).
    my ($x) = @_;
    return 0 + sprintf("%.0f", $x);
}

1;
