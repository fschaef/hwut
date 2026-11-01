# @hwut {
#     title      = "hwut_fsm: a state machine as the test's model of the system"
#     choices {
#         dfa       { features = ["ps-fsm"] }
#         forbidden { features = ["ps-fsm"] }
#         masks     { features = ["ps-fsm"] }
#         model     { features = ["ps-fsm"] }
#         nfa       { features = ["ps-fsm"] }
#         refused   { features = ["ps-fsm"] }
#         report    { features = ["ps-fsm"] }
#         syntax    { features = ["ps-fsm"] }
#     }
#     caps        { file_size_mb = 2097152 }
#     interactive = true
# }
#
# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#_____________________________________________________________________________
#
# PURPOSE: The PowerShell port of 'python/TEST/test-hwut_fsm.py', choice for
#          choice, held against its GOOD files by '.link'.
#_____________________________________________________________________________
using module ../hwut_runner.psm1
using module ../hwut_pytext.psm1
using module ../hwut_fsm.psm1

#  THE PROTOCOL OF EVERY CHOICE: a request is waited on, granted, released;
#  a fault while busy crashes it -- which must never happen.
$PROTOCOL = @'

    initial:   idle
    forbidden: crashed
    final:     idle
    idle    ---( request )---> waiting ---( grant )---> busy
    busy    ---( release )---> idle
    :       ---( fault )--->   crashed       # the state that began line 6
    waiting ---( cancel )---> idle
'@ + "`n"

<# RETURN: nothing; a section heading on the pipeline. #>
function banner([string]$label) { ''; "--- $label ---" }

<# RETURN: string, a path as Python prints the tuple 'path_to' returns, or 'None'. #>
function pathText([object]$p) { if ($null -eq $p) { 'None' } else { [PyText]::TupleRepr($p, $true) } }

<# RETURN: whatever 'f' puts out; an FsmError it throws printed as Python's test prints it. #>
function printingFsmError([scriptblock]$f) {
    try { & $f } catch [FsmError] { "FsmError: $($_.Exception.Message)" }
}

$syntax = {
    banner 'the protocol, written back'
    [FsmMachine]::FromString($PROTOCOL).ToString()
    banner "the author's form: 'state', a chain, ':', blanks around '-->'"
    [FsmMachine]::FromString(@'

        state A ---( event )---> state B
        :                ---(event2)---> state C ---(event) --> state D
        state E          # no transition yet
'@ + "`n    ").ToString()
}

$refused = {
    foreach ($text in @("A ---( x )---> B`n: ---( x )---> C",
                        'A ---(  )---> B',
                        ': ---( x )---> B',
                        'A B ---( x )---> C',
                        "initial: A, B`nA ---( x )---> B",
                        "forbidden: Q`nA ---( x )---> B",
                        '# nothing but a comment')) {
        banner $text.Replace("`n", ' | ')
        printingFsmError { $null = [FsmMachine]::FromString($text); 'accepted' }
    }
}

$dfa = {
    $m = [FsmMachine]::FromString($PROTOCOL)
    $number = 0
    foreach ($event in @('request', 'release', 'grant', 'release', 'jump', 'request')) {
        $number++
        $moved = $m.Fire($event, $number)
        '    {0,-8} -> {1,-5} now {2,-8} allowed: {3}' -f $event, [PyText]::BoolText($moved), $m.State(), ($m.Allowed() -join ', ')
    }
    banner 'questions where it stands'
    "can('grant')   $([PyText]::BoolText($m.Can('grant')))"
    "can('release') $([PyText]::BoolText($m.Can('release')))"
    "in_state('waiting') $([PyText]::BoolText($m.InState('waiting')))"
    'trace: ' + ((@(foreach ($t in $m.Trace()) { '{0}:{1}>{2}' -f [PyText]::NoneOr($t[0]), $t[2], $t[3] })) -join ' ')
}

$nfa = {
    $m = [FsmMachine]::FromString(@'

        A ---( x )---> B ---( y )---> D
        : ---( x )---> C ---( y )---> E
        C ---( z )---> F
'@ + "`n    ", @{ DFA = $false })
    foreach ($event in @('x', 'z', 'y')) {
        $null = $m.Fire($event, "t=$event")
        $now = [string[]]@($m.Current()); [Array]::Sort($now, [StringComparer]::Ordinal)
        "    after ${event}: $($now -join ', ')"
    }
    banner "'state' asked of a set"
    $m.Reset(); $null = $m.Fire('x')
    printingFsmError { $m.State() }
}

$forbidden = {
    $m = [FsmMachine]::FromString($PROTOCOL)
    $number = 0
    foreach ($event in @('request', 'grant', 'fault')) {
        $number++
        '    {0,-8} -> {1}' -f $event, [PyText]::BoolText($m.Fire($event, $number))
    }
    "now in $($m.State()) -- breaches: $($m.breach_n)"
}

$model = {
    $m = [FsmMachine]::FromString($PROTOCOL + "`n    state limbo`n    limbo ---( kick )---> idle`n")
    "check: $($m.Check())"
    banner 'path_to'
    foreach ($state in @('busy', 'crashed', 'limbo', 'idle')) {
        '    {0,-8} {1}' -f $state, (pathText $m.PathTo($state))
    }
    $null = $m.Fire('request')
    "    busy from now: $(pathText $m.PathTo('busy', 'now'))"
    "    state_reachable('idle', start='now'): $([PyText]::BoolText($m.StateReachable('idle', 'now')))"
}

$report = {
    $m = [FsmMachine]::FromString($PROTOCOL, @{ name = 'protocol' })
    foreach ($event in @('request', 'grant', 'release', 'request', 'grant')) { $null = $m.Fire($event) }
    "report returns $($m.Report())"
}

$masks = {
    $m = [FsmMachine]::FromString($PROTOCOL)
    banner "'grant' disallowed in every state, since line 2"
    $m.Disallow('grant', $null, 2)
    $null = $m.Fire('request', 3)
    "    allowed now: $($m.Allowed() -join ', ') -- can('grant'): $([PyText]::BoolText($m.Can('grant')))"
    $null = $m.Fire('grant', 4)
    "    path_to('busy'):               $(pathText $m.PathTo('busy'))"
    "    path_to('busy', masked=False): $(pathText $m.PathTo('busy', $null, $false))"
    "    check(): $($m.Check())"
    "    check(masked=False): $($m.Check($false))"
    banner "allowed again; 'busy' forbidden while standing in it"
    $m.Allow('grant', $null, 5)
    $null = $m.Fire('grant', 6)
    $m.Forbid('busy', 7)
    $null = $m.Fire('release', 8)
    $null = $m.Fire('request', 9)
    $null = $m.Fire('grant', 10)
    banner "permitted: 'busy', and the model's own 'crashed'"
    $m.Permit('busy', 11)
    $m.Permit('crashed', 12)
    "    fault -> $([PyText]::BoolText($m.Fire('fault', 13))) -- now in $($m.State())"
    banner "a phase: 'release' disallowed in 'busy' for a block"
    $m.Reset()
    $null = $m.Fire('request'); $null = $m.Fire('grant')
    $null = $m.Disallowed('release', 'busy', 'phase').Run({ $null = $m.Fire('release', 20) })
    $null = $m.Fire('release', 21)
    $m.Disallow('cancel', $null, 22)
    $null = $m.Report()
    banner 'refused: a word the model never names'
    foreach ($call in @({ $m.Disallow('jump') }, { $m.Forbid('limbo') }, { $m.Allow('grant', 'nowhere') })) {
        printingFsmError $call
    }
}

[HwutRunner]::new(@{
    argv       = @($PSCommandPath) + $args
    title      = "hwut_fsm: a state machine as the test's model of the system"
    choice_map = @{
        syntax    = $syntax
        refused   = $refused
        dfa       = $dfa
        nfa       = $nfa
        forbidden = $forbidden
        model     = $model
        report    = $report
        masks     = $masks
    }
}).Run()
