# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#_____________________________________________________________________________
#
# PURPOSE: TEXT AS PYTHON PRINTS IT -- so a PowerShell test and a Python test
#          of the same module print the same bytes, and share one GOOD file by
#          a '.link' (bookkeeper B-32). The port of 'c/hwut_pytext.c' and
#          'node/pytext.js'.
#
#     [PyText]::FloatRepr(1.0)            '1.0'          repr(1.0)
#     [PyText]::FloatRepr(0.1)            '0.1'          shortest text reading back
#     [PyText]::FloatRepr(1e-05)          '1e-05'        exponential below 1e-4 ...
#     [PyText]::FloatRepr(1e16)           '1e+16'        ... and from 1e16 on
#     [PyText]::ListRepr(@(3, 1))         '[3, 1]'       numbers bare
#     [PyText]::ListRepr(@('a'), $true)   "['a']"        strings quoted as repr does
#     [PyText]::TupleRepr(@('a'), $true)  "('a',)"       a tuple of one keeps its comma
#     [PyText]::StrRepr("it's")           "\"it's\""
#     [PyText]::BytesRepr([byte[]](27,91,65))  "b'\x1b[A'"
#     [PyText]::BoolText($true)           'True'
#     [PyText]::NoneOr($null)             'None'
#     [PyText]::Round(2.5)                2              Python's round: half to even
#
# A float is told from an integer by the caller where it matters: a [double]
# goes to 'FloatRepr', an integer prints as it stands ('Repr' decides by the
# .NET type: [double]/[single] -> FloatRepr, [string] -> StrRepr, [bool] ->
# True/False, $null -> None).
#
# THE DIGITS ARE .NET'S: 'double.ToString("R")' is the shortest round-trip
# text since .NET Core 3.0 -- the same digits Python's repr chooses; only the
# LAYOUT is rewritten ('1E+16' -> '1e+16', '1E-05' -> '1e-05', '-0' -> '-0.0',
# 'Infinity' -> 'inf').
#_____________________________________________________________________________
Set-StrictMode -Version 3.0

class PyText {
    static hidden [System.Globalization.CultureInfo] $Invariant = [System.Globalization.CultureInfo]::InvariantCulture

    <#
    RETURN: string, 'x' as Python's 'repr(float)' writes it -- the shortest
            decimal reading back to the same double, fixed notation where the
            decimal point falls in (-4, 16], exponential with a signed
            two-digit-at-least exponent else; 'nan', 'inf', '-inf', '-0.0' as
            Python writes them.
    #>
    static [string] FloatRepr([double]$x) {
        if ([double]::IsNaN($x))              { return 'nan' }
        if ([double]::IsPositiveInfinity($x)) { return 'inf' }
        if ([double]::IsNegativeInfinity($x)) { return '-inf' }
        if ($x -eq 0.0) { if ([double]::IsNegative($x)) { return '-0.0' } else { return '0.0' } }
        $text = $x.ToString('R', [PyText]::Invariant)
        $m    = [regex]::Match($text, '^(-?)(\d+)(?:\.(\d+))?(?:E([-+]\d+))?$')
        $sign = $m.Groups[1].Value
        $int  = $m.Groups[2].Value
        $frac = $m.Groups[3].Value
        $exp  = if ($m.Groups[4].Success) { [int]$m.Groups[4].Value } else { 0 }
        #  value = 0.<digits> * 10^point
        $digits = $int + $frac
        $point  = $int.Length + $exp
        $lead   = $digits.Length - $digits.TrimStart('0').Length
        $digits = $digits.Substring($lead).TrimEnd('0')
        $point -= $lead
        if ($digits.Length -eq 0) { $digits = '0' }
        if ($point -gt -4 -and $point -le 16) {
            $n = $digits.Length
            if ($point -le 0)  { return $sign + '0.' + ('0' * (-$point)) + $digits }
            if ($point -ge $n) { return $sign + $digits + ('0' * ($point - $n)) + '.0' }
            return $sign + $digits.Substring(0, $point) + '.' + $digits.Substring($point)
        }
        $mantissa = if ($digits.Length -gt 1) { $digits.Substring(0, 1) + '.' + $digits.Substring(1) } else { $digits }
        $e        = $point - 1
        $esign    = if ($e -lt 0) { '-' } else { '+' }
        return $sign + $mantissa + 'e' + $esign + ([Math]::Abs($e)).ToString('00')
    }

    <#
    RETURN: bool, $true where the code point 'n' is one Python's
            'str.isprintable' refuses -- Unicode categories Other (Cc, Cf,
            Cs, Co, Cn) and Separator (Zs, Zl, Zp), the blank excepted --
            by .NET's Unicode tables; $false else.
    #>
    static hidden [bool] NotPrintable([int]$n) {
        if ($n -eq 0x20) { return $false }
        if ($n -ge 0xD800 -and $n -le 0xDFFF) { return $true }
        $category = [System.Globalization.CharUnicodeInfo]::GetUnicodeCategory($n)
        switch ($category) {
            'Control'            { return $true }
            'Format'             { return $true }
            'Surrogate'          { return $true }
            'PrivateUse'         { return $true }
            'OtherNotAssigned'   { return $true }
            'SpaceSeparator'     { return $true }
            'LineSeparator'      { return $true }
            'ParagraphSeparator' { return $true }
        }
        return $false
    }

    <#
    RETURN: string, the code points 'cp' in the quotes Python's repr chooses
            -- single, or double where they hold a single quote and no
            double one -- the backslash, that quote and what does not print
            escaped: '\n', '\t', '\r', and '\xNN', '\uNNNN', '\UNNNNNNNN'.
            Where 'bytesF', every code below 0x20 or from 0x7f on is '\xNN';
            else what 'NotPrintable' names.
    #>
    static hidden [string] Quoted([int[]]$cp, [bool]$bytesF) {
        $hasSingle = $cp -contains 0x27
        $hasDouble = $cp -contains 0x22
        $quote = if ($hasSingle -and -not $hasDouble) { 0x22 } else { 0x27 }
        $sb = [System.Text.StringBuilder]::new()
        [void]$sb.Append([char]$quote)
        foreach ($n in $cp) {
            if     ($n -eq 0x5C)   { [void]$sb.Append('\\') }
            elseif ($n -eq $quote) { [void]$sb.Append('\').Append([char]$quote) }
            elseif ($n -eq 0x0A)   { [void]$sb.Append('\n') }
            elseif ($n -eq 0x09)   { [void]$sb.Append('\t') }
            elseif ($n -eq 0x0D)   { [void]$sb.Append('\r') }
            elseif (($bytesF -and ($n -lt 0x20 -or $n -ge 0x7f)) -or (-not $bytesF -and [PyText]::NotPrintable($n))) {
                if     ($n -lt 0x100)   { [void]$sb.Append('\x').Append($n.ToString('x2')) }
                elseif ($n -lt 0x10000) { [void]$sb.Append('\u').Append($n.ToString('x4')) }
                else                    { [void]$sb.Append('\U').Append($n.ToString('x8')) }
            }
            else { [void]$sb.Append([char]::ConvertFromUtf32($n)) }
        }
        [void]$sb.Append([char]$quote)
        return $sb.ToString()
    }

    <#
    RETURN: int[], the code points of 's' -- a surrogate pair is one code
            point, a lone surrogate stands as itself (Python's 'surrogateescape'
            view of it).
    #>
    static hidden [int[]] CodePoints([string]$s) {
        $list = [System.Collections.Generic.List[int]]::new()
        for ($i = 0; $i -lt $s.Length; $i++) {
            if ([char]::IsHighSurrogate($s[$i]) -and $i + 1 -lt $s.Length -and [char]::IsLowSurrogate($s[$i + 1])) {
                $list.Add([char]::ConvertToUtf32($s[$i], $s[$i + 1])); $i++
            } else {
                $list.Add([int]$s[$i])
            }
        }
        return $list.ToArray()
    }

    <#
    RETURN: string, 's' as Python's 'repr(str)' writes it; "''" for $null.
    #>
    static [string] StrRepr([string]$s) {
        if ($null -eq $s) { $s = '' }
        return [PyText]::Quoted([PyText]::CodePoints($s), $false)
    }

    <#
    RETURN: string, the byte string 'b' as Python's 'repr(bytes)' writes it:
            "b'\x1b[A'".
    #>
    static [string] BytesRepr([byte[]]$b) {
        if ($null -eq $b) { $b = [byte[]]@() }
        $cp = [int[]]::new($b.Length)
        for ($i = 0; $i -lt $b.Length; $i++) { $cp[$i] = $b[$i] }
        return 'b' + [PyText]::Quoted($cp, $true)
    }

    <#
    RETURN: string, 'value' as Python's 'repr' writes a value of the same
            kind: $null -> 'None', [bool] -> 'True'/'False', [double] or
            [single] -> FloatRepr, [string] or [char] -> StrRepr, [byte[]] ->
            BytesRepr, a list -> ListRepr of the elements' Repr, an integer
            or anything else -> its invariant text.
    #>
    static [string] Repr([object]$value) {
        if ($null -eq $value)          { return 'None' }
        if ($value -is [bool])         { return [PyText]::BoolText($value) }
        if ($value -is [double])       { return [PyText]::FloatRepr($value) }
        if ($value -is [single])       { return [PyText]::FloatRepr([double]$value) }
        if ($value -is [string])       { return [PyText]::StrRepr($value) }
        if ($value -is [char])         { return [PyText]::StrRepr([string]$value) }
        if ($value -is [byte[]])       { return [PyText]::BytesRepr($value) }
        if ($value -is [System.Collections.IList]) {
            $item = foreach ($x in $value) { [PyText]::Repr($x) }
            return '[' + (@($item) -join ', ') + ']'
        }
        return [System.Convert]::ToString($value, [PyText]::Invariant)
    }

    <#
    RETURN: string, the elements of 'list' as Python prints a list -- '[a, b]';
            each element bare (its invariant text).
    #>
    static [string] ListRepr([object[]]$list) { return [PyText]::ListRepr($list, $false) }

    <#
    RETURN: string, the elements of 'list' as Python prints a list -- '[a, b]';
            each quoted as a string where 'stringsF', bare else.
    #>
    static [string] ListRepr([object[]]$list, [bool]$stringsF) {
        return '[' + ([PyText]::Items($list, $stringsF) -join ', ') + ']'
    }

    <#
    RETURN: string, the elements of 'list' as Python prints a tuple -- '()',
            '(a,)' for one element, '(a, b)'; bare.
    #>
    static [string] TupleRepr([object[]]$list) { return [PyText]::TupleRepr($list, $false) }

    <#
    RETURN: string, the elements of 'list' as Python prints a tuple -- '()',
            "('a',)" for one element, "('a', 'b')"; quoted where 'stringsF'.
    #>
    static [string] TupleRepr([object[]]$list, [bool]$stringsF) {
        $item = [PyText]::Items($list, $stringsF)
        if ($item.Count -eq 0) { return '()' }
        if ($item.Count -eq 1) { return '(' + $item[0] + ',)' }
        return '(' + ($item -join ', ') + ')'
    }

    <#
    RETURN: string[], each element of 'list' as text: StrRepr where
            'stringsF', its invariant text else; empty for $null.
    #>
    static hidden [string[]] Items([object[]]$list, [bool]$stringsF) {
        if ($null -eq $list) { return [string[]]@() }
        $out = [string[]]::new($list.Count)
        for ($i = 0; $i -lt $list.Count; $i++) {
            $out[$i] = if ($stringsF) { [PyText]::StrRepr([string]$list[$i]) }
                       else           { [System.Convert]::ToString($list[$i], [PyText]::Invariant) }
        }
        return $out
    }

    <#
    RETURN: string, 'None' where 'value' is $null, its invariant text else.
    #>
    static [string] NoneOr([object]$value) {
        if ($null -eq $value) { return 'None' }
        return [System.Convert]::ToString($value, [PyText]::Invariant)
    }

    <#
    RETURN: string, 'True' where 'value' is true, 'False' else.
    #>
    static [string] BoolText([bool]$value) { if ($value) { return 'True' } else { return 'False' } }

    <#
    RETURN: long, 'x' rounded as Python's 'round(x)' -- to the nearest
            integer, an exact half to the EVEN one.
    #>
    static [long] Round([double]$x) { return [long][Math]::Round($x, [MidpointRounding]::ToEven) }
}
