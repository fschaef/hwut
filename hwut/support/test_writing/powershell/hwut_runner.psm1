# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#_____________________________________________________________________________
#
# PURPOSE: FRONT END OF A HWUT TEST APPLICATION IN POWERSHELL -- the port of
#          'python/hwut_runner.py', the same modes, the same words:
#
#     app --hwut-info      the info block; exit 0.
#     app <choice>         one choice; test output on stdout and stderr,
#                          '<hwut-end>' after it. '-' runs a choice-less test.
#     app --interactive    choices started over stdin, output into two named
#                          sink files per choice, 'done' on the original stdout.
#     app                  the choice-less test; where the application has
#                          choices, refused, naming them.
#
# USAGE (a test 'test-x.ps1', run by 'pwsh test-x.ps1 <choice>'):
#
#     using module ../hwut_runner.psm1
#     [HwutRunner]::new(@{
#         argv       = @($PSCommandPath) + $args      # as Python's 'sys.argv'
#         title      = 'What this application tests'
#         choice_map = @{ plain = { Out-Py 'plain' }; tricky = { ... } }
#     }).Run()
#
# 'choice_map' maps a choice name to a script block; the key '-' alone stands
# for a choice-less test. 'happy' (string, regex, or an array of them),
# 'same_f' and 'parallel' ('process': choices run concurrently) are as in
# Python. 'Run()' ENDS THE PROCESS with the mode's status, as Python's
# 'sys.exit' does.
#
# OUTPUT GOES THROUGH [Console]::Out. Everything a choice block writes to
# the pipeline is written there line by line (as text: '"$_"'); 'Out-Py'
# writes there directly -- the one route that also works inside a class
# method, where the pipeline is not heard. [Console]::Error is the error
# stream; an exception leaving a choice is printed there, status 1.
#
# THE INTERACTIVE PROTOCOL is Python's, line for line:
#     DOWN  run <choice> <sink-out> <sink-err> | info | quit | q | exit
#     UP    done <choice> <status> | fail <choice> <reason> | info: <line> | bye
#
# IN ONE PROCESS (Python's sequential scheme): PowerShell cannot point its own
# descriptors 1 and 2 at a file without a foreign call, and a child per choice
# costs a pwsh start (about 0.5 s). So a 'run' points [Console]::Out and
# [Console]::Error at the two sinks ('Console.SetOut'/'SetError') for the
# choice's span; the UP channel is the writer [Console]::Out was before the
# session. What a choice writes through PowerShell or .NET lands in the sinks;
# what a NATIVE process it spawns writes on an inherited descriptor 1 or 2
# lands in the session's stray sink -- a choice that runs one redirects it
# (the vterm test's applications write onto a pseudo-terminal, not stdout).
# 'exit n' in a choice ends that choice with status n (PowerShell's 'exit' is
# caught at the block's end as SystemExit is). With 'parallel = "process"'
# each choice runs in a child pwsh whose [Console] writers are the sinks.
#_____________________________________________________________________________
Set-StrictMode -Version 3.0

$script:NONE      = '-'                        # the choice-less test's key
$script:CHILD_ENV = 'HWUT_PS_RUNNER_SINK'      # '<out>|<err>' for a child of 'parallel'

<#
RETURN: nothing; 'text' (each argument, then each pipeline item, as text) is
        written to [Console]::Out, one line each -- Python's 'print'. With no
        argument and no input, one empty line.
#>
function Out-Py {
    param([Parameter(ValueFromRemainingArguments = $true)] $Text,
          [Parameter(ValueFromPipeline = $true)]        $InputObject)
    begin   { $any = $false
              if ($null -ne $Text) { foreach ($t in $Text) { [Console]::Out.WriteLine([string]$t); $any = $true } } }
    process { if ($PSBoundParameters.ContainsKey('InputObject')) { [Console]::Out.WriteLine([string]$InputObject); $any = $true } }
    end     { if (-not $any) { [Console]::Out.WriteLine() } }
}

<#
RETURN: nothing; the process is set up so PowerShell itself prints nothing
        a test did not write -- no progress records, no ANSI colour in error
        text, UTF-8 without BOM on [Console]::Out and [Console]::Error, the
        invariant culture (a '.' in a number, whatever the locale) -- and so
        an error stops the choice, as an exception does in Python
        ($ErrorActionPreference 'Stop').
#>
function Initialize-HwutConsole {
    $global:ErrorActionPreference = 'Stop'           # an error raises, as in Python
    $global:ProgressPreference    = 'SilentlyContinue'
    $global:InformationPreference = 'SilentlyContinue'
    if ($null -ne (Get-Variable -Name PSStyle -Scope Global -ErrorAction SilentlyContinue)) {
        $global:PSStyle.OutputRendering = 'PlainText'
    }
    #  Numbers print as Python prints them, not as the locale would.
    [System.Globalization.CultureInfo]::CurrentCulture   = [System.Globalization.CultureInfo]::InvariantCulture
    [System.Globalization.CultureInfo]::CurrentUICulture = [System.Globalization.CultureInfo]::InvariantCulture
    $utf8 = [System.Text.UTF8Encoding]::new($false)
    if ([Console]::OutputEncoding.WebName -ne 'utf-8' -or [Console]::OutputEncoding.GetPreamble().Length -ne 0) {
        [Console]::OutputEncoding = $utf8
    }
    $global:OutputEncoding = $utf8
}

class HwutRunner {
    [string[]]  $argv
    [string]    $title
    [object]    $choice
    [hashtable] $choice_map
    [string[]]  $happy
    [bool]      $same_f
    [object]    $parallel
    [string[]]  $sorted_choice_list
    hidden [System.IO.TextWriter] $_control
    hidden [System.IO.TextWriter] $_stray

    <#
    RETURN: HwutRunner, ready for 'Run()'; throws ArgumentException where
            'choice_map' is missing or empty, where '-' does not stand alone,
            or where 'parallel' is neither $null nor 'process'.

    'option' holds:
        argv        the command line as Python's 'sys.argv' -- the script,
                    then the arguments.
        title       title line of the info block.
        choice_map  choice name -> script block; '-' alone: choice-less.
        happy       pattern(s) for the info block's 'HAPPY:' lines.
        same_f      $true => the info block carries 'SAME;'.
        parallel    $null -- choices one after another, in this process;
                    'process' -- each in a child pwsh, concurrently.
    #>
    HwutRunner([hashtable]$option) {
        $map = $option['choice_map']
        if ($null -eq $map -or $map.PSBase.Count -eq 0) { throw [System.ArgumentException]::new("HwutRunner: no 'choice_map'") }
        if ($map.PSBase.Contains($script:NONE) -and $map.PSBase.Count -gt 1) {
            throw [System.ArgumentException]::new("HwutRunner: '-' stands for the choice-less test and stands alone")
        }
        $p = $option['parallel']
        if ($null -ne $p -and $p -ne 'process') { throw [System.ArgumentException]::new("HwutRunner: 'parallel' is `$null or 'process'") }
        $this.argv       = if ($null -ne $option['argv']) { [string[]]$option['argv'] } else { [string[]]@('') }
        $this.title      = [string]$option['title']
        $this.choice     = if ($this.argv.Count -lt 2) { $null } else { $this.argv[1] }
        $this.choice_map = [hashtable]::new([System.StringComparer]::Ordinal)   # by case, as a Python dict
        foreach ($k in $map.PSBase.Keys) { $this.choice_map[[string]$k] = $map[$k] }
        $this.parallel   = $p
        $this.same_f     = [bool]$option['same_f']
        $h = $option['happy']
        $this.happy = [string[]]@(foreach ($x in @($h)) { if ($null -ne $x) { if ($x -is [regex]) { $x.ToString() } else { [string]$x } } })
        if ($this.choice_map.ContainsKey($script:NONE)) { $this.sorted_choice_list = @($script:NONE) }
        else { $this.sorted_choice_list = [string[]]@($this.choice_map.PSBase.Keys) }
        #  Python's 'sorted' is by code point: sort ordinally.
        $list = [System.Collections.Generic.List[string]]::new([string[]]$this.sorted_choice_list)
        $list.Sort([System.StringComparer]::Ordinal)
        $this.sorted_choice_list = $list.ToArray()
    }

    <#
    RETURN: never; dispatches on the first command line argument (see the
            head of this file) and ends the process with the mode's status.
    #>
    [void] Run() {
        Initialize-HwutConsole
        $status = $this.Dispatch()
        [Console]::Out.Flush(); [Console]::Error.Flush()
        [System.Environment]::Exit($status)
    }

    <#
    RETURN: int, the exit status of the mode the command line selects.
    #>
    [int] Dispatch() {
        $word = $this.choice
        if ($word -in @('-h', '--hi', '--hwut-info', '--sos', '--wtf')) { return $this.MODE_hwut_info() }
        if ($word -ceq '--interactive') { return $this.MODE_interactive() }
        $sink = [System.Environment]::GetEnvironmentVariable($script:CHILD_ENV)
        if ($null -ne $sink -and $null -ne $word) {
            [System.Environment]::SetEnvironmentVariable($script:CHILD_ENV, $null)
            $part = $sink.Split('|')
            $hwutEnd = -not [System.Environment]::GetEnvironmentVariable('HWUT_NO_TERMINAL')
            return $this.RunIntoSinks($word, $part[0], $part[1], $hwutEnd)
        }
        if ($null -eq $word) {
            if ($this.choice_map.ContainsKey($script:NONE)) { return $this.MODE_run_test($script:NONE) }
            return $this.MODE_choice_missing()
        }
        if ($this.choice_map.ContainsKey($word) -and $this.HasChoice($word)) { return $this.MODE_run_test($word) }
        return $this.MODE_choice_does_not_exist($word)
    }

    <#
    RETURN: bool, $true where 'word' is a key of the choice map spelt as it
            stands (PowerShell's hashtable compares without case; Python's
            dict does not); $false else.
    #>
    hidden [bool] HasChoice([string]$word) {
        foreach ($k in $this.choice_map.PSBase.Keys) { if ($k -ceq $word) { return $true } }
        return $false
    }

    <#
    RETURN: int, 1. The application has choices and the command line names
            none; says so on stdout.
    #>
    [int] MODE_choice_missing() {
        [Console]::Out.WriteLine("error: a choice is required: $($this.sorted_choice_list -join ', ') -- name one, or let 'hwut.play' ask.")
        return 1
    }

    <#
    RETURN: int, 1. Names the unavailable choice 'word', the available ones
            and the closest by Levenshtein distance, on stdout.
    #>
    [int] MODE_choice_does_not_exist([string]$word) {
        if ($this.choice_map.ContainsKey($script:NONE)) {
            [Console]::Out.WriteLine("error: '$word': this application has no choices -- call it without one.")
            return 1
        }
        [Console]::Out.WriteLine("error: choice '$word' not available.")
        [Console]::Out.WriteLine("error: available: $($this.sorted_choice_list -join ', ').")
        $best = [HwutRunner]::LevenshteinBestMatch($word, $this.sorted_choice_list)
        if ($null -ne $best) { [Console]::Out.WriteLine("error: did you mean '$best'?") }
        return 1
    }

    <#
    RETURN: int, the status of the choice: 0 where its block ended, n where
            it said 'exit n', 1 where an exception left it (printed to
            stderr, no '<hwut-end>'). '<hwut-end>' follows a block that
            ended or said 'exit 0' (R-70).
    #>
    [int] MODE_run_test([string]$name) {
        $status = $this.RunChoice($name)
        if ($status -eq 0) { [Console]::Out.WriteLine('<hwut-end>') }
        return $status
    }

    <#
    RETURN: int, 0. Prints the info block.
    #>
    [int] MODE_hwut_info() {
        foreach ($line in $this.InfoBlockLines()) { [Console]::Out.WriteLine($line) }
        return 0
    }

    <#
    RETURN: string[], the lines of the info block: title, CHOICES, HAPPY,
            SAME, INTERACTIVE -- each ending in ';'.
    #>
    [string[]] InfoBlockLines() {
        $result = [System.Collections.Generic.List[string]]::new()
        $result.Add($(if ($this.title.EndsWith(';')) { $this.title } else { $this.title + ';' }))
        if (-not $this.choice_map.ContainsKey($script:NONE)) { $result.Add('CHOICES: ' + ($this.sorted_choice_list -join ', ') + ';') }
        foreach ($h in $this.happy) { $result.Add('HAPPY: ' + $h + ';') }
        if ($this.same_f) { $result.Add('SAME;') }
        $result.Add('INTERACTIVE;')
        return $result.ToArray()
    }

    <#
    RETURN: int, the status of the choice's block run in this process: 0
            where it ended, n where it said 'exit n' (a non-integer word:
            1), 1 where an exception left it -- its record printed to
            [Console]::Error. What the block puts on the pipeline is written
            to [Console]::Out as it comes, as text.
    #>
    hidden [int] RunChoice([string]$name) {
        $block    = $this.choice_map[$name]
        $returned = [ref]$false
        $ps       = $null
        try {
            #  A NESTED PIPELINE on this runspace: 'exit n' inside the block
            #  ends that pipeline alone -- caught here as SystemExit is in
            #  Python -- where '&' in this method would end the process.
            $global:LASTEXITCODE = 0
            $ps = [powershell]::Create([System.Management.Automation.RunspaceMode]::CurrentRunspace)
            [void]$ps.AddScript('param($b, $r) & $b | ForEach-Object { [Console]::Out.WriteLine([string]$_) }; $r.Value = $true', $true)
            [void]$ps.AddArgument($block).AddArgument($returned)
            $null = $ps.Invoke()
            if ($ps.Streams.Error.Count -gt 0) {
                foreach ($e in $ps.Streams.Error) { [Console]::Error.WriteLine([HwutRunner]::ErrorText($e)) }
                return 1
            }
            if ($returned.Value) { return 0 }
            $code = $global:LASTEXITCODE
            if ($code -is [int]) { return $code }
            return 1
        } catch {
            [Console]::Error.WriteLine([HwutRunner]::ErrorText($_))
            return 1
        } finally {
            if ($null -ne $ps) { $ps.Dispose() }
            [Console]::Out.Flush(); [Console]::Error.Flush()
        }
    }

    <#
    RETURN: string, the error record 'e' as a traceback-like text: the
            exception's type and message, then PowerShell's script stack.
    #>
    static hidden [string] ErrorText([System.Management.Automation.ErrorRecord]$e) {
        $record = $e
        $x      = $e.Exception
        while ($null -ne $x.InnerException -and
               ($x -is [System.Management.Automation.MethodInvocationException] -or
                $x -is [System.Management.Automation.CmdletInvocationException] -or
                $x.GetType() -eq [System.Management.Automation.RuntimeException])) {
            $x = $x.InnerException
            if ($x -is [System.Management.Automation.IContainsErrorRecord] -and $x.ErrorRecord.ScriptStackTrace) { $record = $x.ErrorRecord }
        }
        if ($x -is [System.Management.Automation.IContainsErrorRecord] -and $x.ErrorRecord.ScriptStackTrace) { $record = $x.ErrorRecord }
        $text = 'Traceback (PowerShell):'
        if ($record.ScriptStackTrace) { $text += "`n" + $record.ScriptStackTrace }
        if ($record.InvocationInfo -and $record.InvocationInfo.PositionMessage) { $text += "`n" + $record.InvocationInfo.PositionMessage }
        return $text + "`n" + $x.GetType().FullName + ': ' + $x.Message
    }

    <#
    RETURN: int, 0 once the session has ended ('quit' or the end of stdin),
            every choice reported, 'bye' last. The UP channel is the writer
            [Console]::Out is on entry; what is written outside a running
            choice goes to a stray sink (a temp file), never into the
            protocol.
    #>
    [int] MODE_interactive() {
        $this._control = [Console]::Out
        $origErr       = [Console]::Error
        $strayPath = [System.IO.Path]::Combine([System.IO.Path]::GetTempPath(),
                         "hwut_stray_$([System.Environment]::ProcessId)_$([System.Environment]::TickCount64).txt")
        $this._stray = [System.IO.StreamWriter]::new($strayPath, $false, [System.Text.UTF8Encoding]::new($false))
        $this._stray.AutoFlush = $true
        [Console]::SetOut($this._stray)
        [Console]::SetError($this._stray)
        $pending = [System.Collections.Generic.List[object]]::new()
        $stdin = [Console]::In
        while ($true) {
            $raw = $stdin.ReadLine()
            if ($null -eq $raw) { break }
            $line = $raw.Trim()
            if ($line.Length -eq 0) { continue }
            if (-not $this.Interprete($line, $pending)) { break }
        }
        $this.Drain($pending, $true)
        $this.Up('bye')
        [Console]::SetOut($this._control); [Console]::SetError($origErr)
        $this._stray.Dispose()
        return 0
    }

    <#
    RETURN: bool, $true -- the session goes on, $false -- it ends.
            Interpretes one DOWN command line; answers on the UP channel;
            never throws.
    #>
    hidden [bool] Interprete([string]$line, [System.Collections.Generic.List[object]]$pending) {
        $field = [regex]::Split($line, '\s+')
        if ($field.Count -eq 1 -and $field[0] -cin @('quit', 'q', 'exit')) { return $false }
        if ($field.Count -eq 1 -and $field[0] -ceq 'info') {
            foreach ($l in $this.InfoBlockLines()) { $this.Up('info: ' + $l) }
            $this.Up('done - 0')
            return $true
        }
        if ($field.Count -eq 4 -and $field[0] -ceq 'run') {
            $token = $field[1]
            $found = $this.FindChoice($token)
            if ($null -eq $found) { $this.Up("fail $token unknown-choice"); return $true }
            if ($this.parallel -eq 'process') {
                $pending.Add($this.StartChild($token, $found, $field[2], $field[3]))
                $this.Drain($pending, $false)
            } else {
                $status = $this.RunIntoSinks($found, $field[2], $field[3], $true)
                $this.Up("done $token $status")
            }
            return $true
        }
        $this.Up('fail - bad-command')
        return $true
    }

    <#
    RETURN: string, the choice 'token' names -- by name, by a decimal index
            into the sorted choice list, or '-' for the choice-less test;
            $null where it names none.
    #>
    hidden [object] FindChoice([string]$token) {
        if ($token -ceq $script:NONE) {
            if ($this.choice_map.ContainsKey($script:NONE)) { return $script:NONE }
            return $null
        }
        if ($this.HasChoice($token)) { return $token }
        if ($token -match '^[0-9]+$') {
            $i = 0
            if ([int]::TryParse($token, [ref]$i) -and $i -lt $this.sorted_choice_list.Count) { return $this.sorted_choice_list[$i] }
        }
        return $null
    }

    <#
    RETURN: int, the status of 'name' run with [Console]::Out and
            [Console]::Error on the two sink files (created, truncated): as
            'RunChoice', '<hwut-end>' after it where 'hwutEnd' and it
            succeeded and HWUT_NO_TERMINAL is unset; 1 where a sink cannot be
            opened. On return both sinks are flushed and closed and the
            writers are back -- the 'done' barrier.
    #>
    hidden [int] RunIntoSinks([string]$name, [string]$sinkOut, [string]$sinkErr, [bool]$hwutEnd) {
        $utf8 = [System.Text.UTF8Encoding]::new($false)
        $out = $null; $err = $null
        try {
            $out = [System.IO.StreamWriter]::new($sinkOut, $false, $utf8)
            $err = [System.IO.StreamWriter]::new($sinkErr, $false, $utf8)
        } catch {
            if ($null -ne $out) { $out.Dispose() }
            return 1
        }
        $out.AutoFlush = $true; $err.AutoFlush = $true
        $savedOut = [Console]::Out; $savedErr = [Console]::Error
        [Console]::SetOut($out); [Console]::SetError($err)
        $status = 1
        try {
            $status = $this.RunChoice($name)
            if ($status -eq 0 -and $hwutEnd -and -not [System.Environment]::GetEnvironmentVariable('HWUT_NO_TERMINAL')) {
                [Console]::Out.WriteLine('<hwut-end>')
            }
        } finally {
            [Console]::SetOut($savedOut); [Console]::SetError($savedErr)
            $out.Dispose(); $err.Dispose()
        }
        return $status
    }

    <#
    RETURN: pscustomobject { token, process }, a child pwsh started on this
            application and 'choice', its [Console] writers on the sinks
            (named by the environment, HWUT_PS_RUNNER_SINK).
    #>
    hidden [object] StartChild([string]$token, [string]$name, [string]$sinkOut, [string]$sinkErr) {
        $info = [System.Diagnostics.ProcessStartInfo]::new([System.Diagnostics.Process]::GetCurrentProcess().MainModule.FileName)
        foreach ($a in @('-NoProfile', '-NonInteractive', '-File', $this.argv[0], $name)) { $info.ArgumentList.Add($a) }
        $info.UseShellExecute = $false
        $info.RedirectStandardInput = $true
        $info.Environment[$script:CHILD_ENV] = "$sinkOut|$sinkErr"
        $child = [System.Diagnostics.Process]::Start($info)
        $child.StandardInput.Close()
        return [pscustomobject]@{ token = $token; process = $child }
    }

    <#
    RETURN: nothing; reports 'done <token> <status>' for every child in
            'pending' that has ended -- every one, waiting, where 'allF' --
            and removes it.
    #>
    hidden [void] Drain([System.Collections.Generic.List[object]]$pending, [bool]$allF) {
        foreach ($c in @($pending)) {
            if ($allF) { $c.process.WaitForExit() }
            if ($c.process.HasExited) {
                $this.Up("done $($c.token) $($c.process.ExitCode)")
                [void]$pending.Remove($c)
            }
        }
    }

    <#
    RETURN: nothing; 'message' is written and flushed on the UP channel.
    #>
    hidden [void] Up([string]$message) {
        $this._control.Write($message + "`n")
        $this._control.Flush()
    }

    <#
    RETURN: string, the element of 'haystack' least distant from 'needle'
            (the first of equal ones); $null where 'needle' is $null or
            'haystack' is empty.
    #>
    static [object] LevenshteinBestMatch([string]$needle, [string[]]$haystack) {
        if ($null -eq $needle -or $null -eq $haystack -or $haystack.Count -eq 0) { return $null }
        if ($haystack -ccontains $needle) { return $needle }
        $bestKey = $null; $bestDist = -1
        foreach ($key in $haystack) {
            $dist = [HwutRunner]::LevenshteinDistance($needle, $key)
            if ($bestDist -lt 0 -or $dist -lt $bestDist) { $bestDist = $dist; $bestKey = $key }
        }
        return $bestKey
    }

    <#
    RETURN: int >= 0, the Levenshtein distance between 'a' and 'b'.
    #>
    static [int] LevenshteinDistance([string]$a, [string]$b) {
        if ($a -ceq $b) { return 0 }
        if (-not $a) { return $b.Length }
        if (-not $b) { return $a.Length }
        if ($a.Length -lt $b.Length) { $t = $a; $a = $b; $b = $t }
        $prev = [int[]](0..$b.Length)
        for ($i = 1; $i -le $a.Length; $i++) {
            $cur = [int[]]::new($b.Length + 1)
            $cur[0] = $i
            for ($j = 1; $j -le $b.Length; $j++) {
                $cost = if ($a[$i - 1] -ceq $b[$j - 1]) { 0 } else { 1 }
                $cur[$j] = [Math]::Min([Math]::Min($cur[$j - 1] + 1, $prev[$j] + 1), $prev[$j - 1] + $cost)
            }
            $prev = $cur
        }
        return $prev[$b.Length]
    }
}

Export-ModuleMember -Function Out-Py, Initialize-HwutConsole
