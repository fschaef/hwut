# @hwut {
#     title      = "HOCON parser: subset (A), annotated tree"
#     choices {
#         comments  { features = ["ps-hocon"] }
#         faults    { features = ["ps-hocon"] }
#         fuzz      { features = ["ps-hocon"] }
#         numbers   { features = ["ps-hocon"] }
#         oneline   { features = ["ps-hocon"] }
#         positions { features = ["ps-hocon"] }
#         quoting   { features = ["ps-hocon"] }
#         refused   { features = ["ps-hocon"] }
#         scalars   { features = ["ps-hocon"] }
#         structure { features = ["ps-hocon"] }
#         triple    { features = ["ps-hocon"] }
#         unclosed  { features = ["ps-hocon"] }
#     }
#     caps        { file_size_mb = 2097152 }
#     interactive = true
# }
#
# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#_____________________________________________________________________________
#
# PURPOSE: The PowerShell port of 'python/TEST/test-hwut_hocon.py', choice
#          for choice, held against its GOOD files by '.link'. 'fuzz' bounds
#          each parse by running it in a second runspace, waited for at most
#          FUZZ_BOUND_MS and abandoned past it -- where Python sets an
#          interval timer.
#_____________________________________________________________________________
using module ../hwut_runner.psm1
using module ../hwut_pytext.psm1
using module ../hwut_hocon.psm1
using module ../deterministic_random.psm1

<# RETURN: nothing; a section heading on [Console]::Out. #>
function banner([string]$label) { Out-Py ''; Out-Py "--- $label ---" }

<# RETURN: string, every argument followed by a newline -- one text of lines. #>
function L { -join @(foreach ($a in $args) { $a + "`n" }) }

<# RETURN: SourceLine[], 'text' split at "`n", offsets applied uniformly. #>
function lines([string]$text, [int]$lineOffset = 0, [int]$columnOffset = 0) {
    $part = $text.Split("`n")
    $out  = [SourceLine[]]::new($part.Count)
    for ($i = 0; $i -lt $part.Count; $i++) { $out[$i] = [SourceLine]::new($part[$i], $i + 1 + $lineOffset, $columnOffset) }
    return ,$out
}

<# RETURN: nothing. Prints the annotated tree, positions included. #>
function show([object]$node, [int]$indent = 0) {
    $pad = '    ' * $indent
    if ($node -is [ObjectNode]) {
        Out-Py "$pad{ at $($node.position)"
        foreach ($entry in $node.entry_list) {
            Out-Py "$pad  key '$($entry.key)' at $($entry.key_position) ->"
            show $entry.node ($indent + 1)
        }
        Out-Py "$pad}"
    } elseif ($node -is [ListNode]) {
        Out-Py "$pad[ at $($node.position)"
        foreach ($item in $node.item_list) { show $item ($indent + 1) }
        Out-Py "$pad]"
    } else {
        Out-Py "$pad$($node.Repr()) ($($node.py_type)) at $($node.position)"
    }
}

<# RETURN: nothing. Parses 'text' and prints tree and faults. #>
function run([string]$label, [string]$text, [int]$lineOffset = 0, [int]$columnOffset = 0) {
    banner $label
    $document, $faultList = [Hocon]::Parse((lines $text $lineOffset $columnOffset), 'f.hocon')
    show $document
    foreach ($fault in $faultList) { Out-Py "FAULT $fault" }
}

$scalars = {
    run 'scalars' (L 'a = bare' 'b = "quoted \"x\" and \n"' 'c = 42' 'd = -3.14' 'e = 1e-6' 'f = true' 'g = no' `
                     'h = make %.exe' 'i: "colon-bound"' 'j = null' 'k = nihil' 'l =')
}

$numbers = {
    run 'decimal, with sign and exponent' (L 'a = 42' 'b = -0.12' 'c = +7e212' 'd = 6.02e23' 'e = .5')
    run 'the visual helper enters no value' (L 'a = 1_000' 'b = 7_000.5_5')
    run 'hexadecimal, binary, octal' (L 'a = 0xDEAD_BEEF' 'b = 0b0111_11_01' 'c = 0o3124' 'd = 0XFF' 'e = -0b1010')
    run 'roman' (L 'a = 0rIV' 'b = 0rMCMLXXXIV' 'c = -0rX')
    run 'a sign standing apart from its digits' (L 'a = - 0.12' 'b = + 7' 'c = - 0xFF' 'd = - -1.5e3')
    run 'what spells no number is a string, and carries quotes' (L 'a = 1.2.3' 'b = 0x' 'c = 0b012' 'd = 1__0' 'e = 0rIIII' 'f = 0rVX')
    run 'no arithmetic: this language computes nothing' (L 'a = 5 - 1')
}

$quoting = {
    run 'quoted: blanks, comment markers and binders are content' (L 'a = "make %.exe"' 'b = "not # a comment"' 'c = "x = y"' 'd = "yes"')
    run 'unquoted: refused, and shown in the quotes it wants' (L 'a = make' 'b = strip.pype' 'c = [one, two]' 'd = 1')
}

$structure = {
    run 'nesting and key-brace' (L 'outer {' '    inner = { deep = 1 }' '    braced { x = 2 }' '}')
    run 'lists' (L 'commas   = [one, two, three]' 'newlines = [' '    1' '    2' ']' 'objects  = [ { a = 1 }, { a = 2 } ]' 'empty    = []')
}

$oneline = {
    run 'two entries, one line, no comma' (L 'caps { timeout_sec = 30  network = false }')
    run 'a quoted value with blanks, beside a following key' (L 'a { build = "make %.exe"  timeout_sec = 5 }')
    run 'three entries, one line' (L 'x { a = 1  b = "two"  c = { d = 3 } }')
}

$comments = {
    run 'comments' (L '# whole line' 'a = 1   # trailing' '// slashes too' 'b = 2   // trailing slashes' 'c = bare value # comment cut')
}

$refused = {
    run 'refused, each by name' (L 'include "other.conf"' 'a = ${outside.value}' 'b += appended' 'd = survives')
}

$triple = {
    $q = '"""'
    run 'several lines: indentation and blank ends go' (L "doc = $q" '    First line.' '' '      indented more' '    last line' "    $q" 'after = 1')
    run 'on one line; beside another entry; in a list' (L "a = ${q}one line$q  b = 2" "c = [${q}x$q, `"y`"]")
    run 'as written: a quote, a backslash-n, a comment marker' (L "a = ${q}says `"no`" \n # not a comment$q")
    run 'never closed: a fault, at its beginning' (L 'a = 1' "b = ${q}open" 'c = 2')
}

$faults = {
    run 'faults accumulate' (L 'a = 1' 'a = 2' 'b = "unterminated' '}' 'c {' '    d = 3')
}

$unclosed = {
    run "a list closed by the object's brace" (L '@hwut { title = "B" choices = [ }' 'after = 1')
    run 'a stray character in a list' (L 'a = [1, ; 2]')
}

$FUZZ_SEED_TUPLE = @(
    (L '@hwut {' '    title    = "T"' '    choices  = ["a", "b"]' '    tolerance { eq_pattern = ["x.*"] }' '    n        = -1.5e3' '    f        = true' '}'),
    (L 'hwut {' '    target     { clean = "./c.sh" }' '    dependency { "a.py" = ["b.py one"] }' '    ignore     = ["x"]   // comment' '    # comment' '}'))
#  WHAT A TYPO IS MADE OF: the characters HOCON gives meaning to, a few
#  that it refuses by name, and some ordinary ones.
$FUZZ_ALPHABET = [string[]]@(foreach ($c in "{}[]`",=:#/\$ `n`t-+.eE0a".ToCharArray()) { [string]$c }) + @('"""', '${', '//', '+=')
$FUZZ_INPUT_N  = 3000
$FUZZ_BOUND_MS = 500                 # one parse takes well under a millisecond

<# RETURN: string, 'text' edited by one to four random insertions, deletions and duplications of a short stretch. #>
function mutated([DeterministicStream]$stream, [string]$text) {
    $n = $stream.NextInt(1, 4)
    for ($k = 0; $k -lt $n; $k++) {
        $i = [int]$stream.NextInt(0, $text.Length)
        switch ($stream.NextInt(0, 2)) {
            0       { $text = $text.Substring(0, $i) + $stream.Select($FUZZ_ALPHABET) + $text.Substring($i) }
            1       { $text = $text.Substring(0, $i) + $text.Substring([Math]::Min($i + 1, $text.Length)) }
            default {
                $j = [int]$stream.NextInt(0, $text.Length)
                $text = $text.Substring(0, $i) + $text.Substring($j, [Math]::Min(5, $text.Length - $j)) + $text.Substring($i)
            }
        }
    }
    return $text
}

<#
RETURN: Runspace, open, its global 'Parse-Text' parsing a text as the fuzz
        does -- returning the number of faults. The parser's classes carry
        [NoRunspaceAffinity()], so they run on the thread that calls them.
#>
function New-ParseRunspace([string]$module) {
    $runspace = [runspacefactory]::CreateRunspace()
    $runspace.Open()
    $setup = [powershell]::Create()
    $setup.Runspace = $runspace
    [void]$setup.AddScript("using module '$module'
        function global:Parse-Text([string]`$text) {
            `$part = `$text.Split(`"``n`")
            `$out  = [SourceLine[]]::new(`$part.Count)
            for (`$i = 0; `$i -lt `$part.Count; `$i++) { `$out[`$i] = [SourceLine]::new(`$part[`$i], `$i + 1, 0) }
            `$document, `$faultList = [Hocon]::Parse(`$out, 'f.hocon')
            `$faultList.Count
        }")
    [void]$setup.Invoke()
    $setup.Dispose()
    return $runspace
}

$fuzz = {
    #  THE BOUND: each parse runs in a second runspace, abandoned where it
    #  outlasts FUZZ_BOUND_MS -- PowerShell's counterpart of Python's SIGALRM.
    $module   = Join-Path $PSScriptRoot '../hwut_hocon.psm1'
    $runspace = New-ParseRunspace $module

    $stream  = [DeterministicStream]::new(4711)
    $tally   = [ordered]@{ 'clean' = 0; 'with faults' = 0; 'hang' = 0; 'exception' = 0 }
    $example = [ordered]@{}
    for ($k = 0; $k -lt $FUZZ_INPUT_N; $k++) {
        $text = mutated $stream $stream.Select($FUZZ_SEED_TUPLE)
        $ps = [powershell]::Create()
        $ps.Runspace = $runspace
        [void]$ps.AddCommand('Parse-Text').AddArgument($text)
        $async = $ps.BeginInvoke()
        if (-not $async.AsyncWaitHandle.WaitOne($FUZZ_BOUND_MS)) {
            #  A parse that loops is abandoned with its runspace, unwaited
            #  for; the next parse gets a fresh one.
            [void]$ps.BeginStop($null, $null)
            $runspace = New-ParseRunspace $module
            $tally['hang']++
            if (-not $example.Contains('hang')) { $example['hang'] = $text }
        } else {
            try {
                $result = $ps.EndInvoke($async)
                if ($ps.Streams.Error.Count -gt 0) { throw $ps.Streams.Error[0].Exception }
                if ([int]$result[0] -gt 0) { $tally['with faults']++ } else { $tally['clean']++ }
            } catch {
                $tally['exception']++
                if (-not $example.Contains('exception')) { $example['exception'] = "$($_.Exception.GetType().Name): $($_.Exception.Message)`n$text" }
            }
        }
        if ($async.IsCompleted) { $ps.Dispose() }
    }
    $runspace.Dispose()
    banner "$FUZZ_INPUT_N mutated headers"
    foreach ($key in $tally.Keys) { Out-Py ('    {0,-12} {1}' -f $key, $tally[$key]) }
    foreach ($key in $example.Keys) { Out-Py "FIRST $($key.ToUpper()):`n$($example[$key])" }
}

$positions = {
    $text = "@hwut {`n    title = `"T`"`n}"
    run 'plain: as its own file' $text
    run 'offset: same text, region begins at line 40, 3 columns stripped' $text 39 3
}

[HwutRunner]::new(@{
    argv       = @($PSCommandPath) + $args
    title      = 'HOCON parser: subset (A), annotated tree;'
    choice_map = @{
        scalars   = $scalars
        numbers   = $numbers
        quoting   = $quoting
        structure = $structure
        oneline   = $oneline
        comments  = $comments
        refused   = $refused
        triple    = $triple
        unclosed  = $unclosed
        fuzz      = $fuzz
        faults    = $faults
        positions = $positions
    }
}).Run()
