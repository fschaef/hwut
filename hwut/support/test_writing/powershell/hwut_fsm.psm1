# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#_____________________________________________________________________________
#
# PURPOSE: A STATE MACHINE AS A TEST'S MODEL OF THE SYSTEM UNDER TEST -- the
#          port of 'python/hwut_fsm.py' (read '../python/README-hwut_fsm.txt'):
#          the states it may be in, the events that move it, the states it
#          must never reach. A test FIRES the events it observes; every event
#          the model does not allow, and every forbidden state entered, is
#          PRINTED as a line -- so it lands in the GOOD file.
#
#     using module ../hwut_fsm.psm1
#     $m = [FsmMachine]::FromString(@'
#         initial: idle
#         forbidden: crashed
#         idle    ---( request )---> waiting ---( grant )---> busy
#         busy    ---( release )---> idle
#         :       ---( fault )--->   crashed
#     '@)
#     $m.Fire('request', 1)      # $true
#     $m.Fire('release', 2)      # BREACH line 2: 'release' in 'waiting' -- allowed: grant
#     [void]$m.Report()
#
# THE NAMES are Python's in PowerShell's casing: 'from_string' is
# 'FromString', 'path_to' 'PathTo', 'in_state' 'InState', 'dead_ends'
# 'DeadEnds'; Python's properties 'state' and 'forbidden' are the methods
# 'State()' and 'Forbidden()'; the fields 'name', 'initial', 'final',
# 'breach_n', 'state_tuple', 'event_tuple' keep their names.
#
# PYTHON'S KEYWORDS are overloads, positional in Python's order --
# 'Fire(event, where)', 'Disallow(event, state, where)', 'PathTo(state,
# start, masked)', 'Check(masked)'; the options of a model are a hashtable:
# 'FromString(text, @{ DFA = $false; name = 'x'; write = { param($line) ... } })'.
# Python's None is $null.
#
# PYTHON'S 'with': '$m.Disallowed(event, state, where).Run({ ... })' and
# '$m.Forbidding(state, where).Run({ ... })' -- the mask stands while the
# block runs and is lifted whatever way it ends.
#
# A raised FsmError is thrown: 'FsmError' derives from System.Exception, its
# message Python's. Every name is compared as Python compares it: by case,
# and sorted by code point (ordinal).
#_____________________________________________________________________________
Set-StrictMode -Version 3.0

class FsmError : System.Exception {
    <# RETURN: FsmError, a model that cannot be meant; 'message' as Python's. #>
    FsmError([string]$message) : base($message) { }
}

class FsmPhase {
    hidden [scriptblock] $_enter
    hidden [scriptblock] $_leave

    <# RETURN: FsmPhase, doing 'enter' on entry and 'leave' on exit. #>
    FsmPhase([scriptblock]$enter, [scriptblock]$leave) { $this._enter = $enter; $this._leave = $leave }

    <#
    RETURN: nothing; 'block' has run -- what it puts on the pipeline written
            to [Console]::Out as it comes, as Python's 'with' body prints.
            The phase begins before 'block' and ends after it, whatever way;
            an exception passes on.
    #>
    [void] Run([scriptblock]$block) {
        & $this._enter
        try     { & $block | ForEach-Object { [Console]::Out.WriteLine([string]$_) } }
        finally { & $this._leave }
    }
}

class FsmMachine {
    [string]   $name
    [bool]     $dfa_f
    [scriptblock] $write
    [string]   $initial
    [System.Collections.Generic.HashSet[string]] $model_forbidden
    [System.Collections.Generic.HashSet[string]] $final
    [string[]] $state_tuple
    [string[]] $event_tuple
    [int]      $breach_n
    hidden [System.Collections.Generic.Dictionary[string, object]] $_edge_db   # key(state, event) -> @{ source; event; targets }
    hidden [System.Collections.Generic.Dictionary[string, object]] $_mask_db   # key(state|'', event) -> @{ state; event; since }
    hidden [System.Collections.Generic.Dictionary[string, object]] $_forbid_db # state -> since
    hidden [System.Collections.Generic.Dictionary[string, object]] $_permit_db # model-forbidden state -> since
    hidden [System.Collections.Generic.HashSet[string]]            $_current
    hidden [System.Collections.Generic.Dictionary[string, int]]    $_visit_db
    hidden [System.Collections.Generic.Dictionary[string, int]]    $_taken_db
    hidden [System.Collections.Generic.List[object]]               $_trace_list

    static hidden [string] $ARROW_RE = '-+\s*\(\s*([^()]*?)\s*\)\s*-*>'
    #  Python's '\w' on a str is a letter, a number or '_'.
    static hidden [string] $NAME_RE  = '^(?:state\s+)?([A-Za-z_][\p{L}\p{N}_.\-]*)$'
    static hidden [string] $KEY_RE   = '^(initial|forbidden|final)\s*:\s*(.*)$'

    # ------------------------------------------------------------- helpers
    <# RETURN: string, the key the parts 'part' stand under in a dictionary. #>
    static hidden [string] Key([object[]]$part) {
        return (@(foreach ($p in $part) { if ($null -eq $p) { "`u{1}" } else { [string]$p } }) -join "`u{0}")
    }

    <# RETURN: HashSet[string], empty, comparing by case (ordinal). #>
    static hidden [System.Collections.Generic.HashSet[string]] NewSet() {
        return [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
    }

    <# RETURN: string[], the strings of 'x', sorted by code point (ordinal). #>
    static hidden [string[]] Sorted([System.Collections.IEnumerable]$x) {
        $list = [System.Collections.Generic.List[string]]::new()
        if ($null -ne $x) { foreach ($s in $x) { $list.Add([string]$s) } }
        $list.Sort([System.StringComparer]::Ordinal)
        return $list.ToArray()
    }

    <#
    RETURN: int, -1, 0 or 1 -- the string arrays 'a' against 'b' element by
            element by code point, the shorter first where one is the
            other's head (Python's tuple order).
    #>
    static hidden [int] CompareTuple([string[]]$a, [string[]]$b) {
        $n = [Math]::Min($a.Count, $b.Count)
        for ($i = 0; $i -lt $n; $i++) {
            $c = [string]::CompareOrdinal($a[$i], $b[$i])
            if ($c -ne 0) { return [Math]::Sign($c) }
        }
        return [Math]::Sign($a.Count - $b.Count)
    }

    <# RETURN: object[], the string arrays of 'list', sorted as Python sorts tuples. #>
    static hidden [object[]] SortedTuples([System.Collections.IEnumerable]$list) {
        $l = [System.Collections.Generic.List[object]]::new()
        foreach ($x in $list) { $l.Add($x) }
        $l.Sort([System.Comparison[object]] { param($a, $b) [FsmMachine]::CompareTuple($a, $b) })
        return $l.ToArray()
    }

    <#
    RETURN: string, the state 'text' names -- 'A' or 'state A' -- if success;
            throws FsmError naming line 'number', else.
    #>
    static hidden [string] NameOf([string]$text, [int]$number) {
        $found = [regex]::Match($text.Trim(), [FsmMachine]::NAME_RE)
        if (-not $found.Success) {
            throw [FsmError]::new("line ${number}: '$($text.Trim())' names no state -- a state is a word ('A', 'state A')")
        }
        return $found.Groups[1].Value
    }

    <#
    RETURN: string, ' line 3' for an integer 3, ' <text>' for a text, '' for
            $null -- the place a breach line names.
    #>
    static hidden [string] WhereText([object]$where) {
        if ($null -eq $where) { return '' }
        if ($where -is [int] -or $where -is [long]) { return " line $where" }
        return " $where"
    }

    <# RETURN: string, ' since line 9', ' since <text>', or '' for $null. #>
    static hidden [string] SinceText([object]$where) {
        if ($null -eq $where) { return '' }
        return ' since' + [FsmMachine]::WhereText($where)
    }

    <# RETURN: string[], the lines of 'text' as Python's 'str.splitlines' cuts them. #>
    static hidden [string[]] SplitLines([string]$text) {
        $line = [regex]::Split($text, "\r\n|[\n\r\v\f\x1c\x1d\x1e\x85  ]")
        if ($line.Count -gt 0 -and $line[$line.Count - 1] -eq '') { $line = $line[0..($line.Count - 2)] }
        if ($line.Count -eq 1 -and $null -eq $line[0]) { return [string[]]@() }
        return [string[]]$line
    }

    # -------------------------------------------------------- construction
    <#
    RETURN: FsmMachine, standing in 'initial', if success; throws FsmError,
            else -- a DFA with two transitions for one (state, event); a
            forbidden or final state no transition names.

    'transitions' is a list of @(state, event, state) triples. 'option'
    holds 'forbidden', 'final' (lists), 'DFA' ($true), 'name' ('fsm'),
    'write' (a script block taking one line; [Console]::Out by default),
    'states' (states no transition touches yet).
    #>
    FsmMachine([object[]]$transitions, [string]$initial, [hashtable]$option) { $this.Build($transitions, $initial, $option) }

    <# RETURN: FsmMachine over 'transitions' standing in 'initial', the options defaulted. #>
    FsmMachine([object[]]$transitions, [string]$initial) { $this.Build($transitions, $initial, @{}) }

    <# RETURN: nothing; the constructors' body (see the three-argument one). #>
    hidden [void] Build([object[]]$transitions, [string]$initial, [hashtable]$option) {
        if ($null -eq $option) { $option = @{} }
        $this.name     = if ($option.ContainsKey('name') -and $null -ne $option['name']) { [string]$option['name'] } else { 'fsm' }
        $this.dfa_f    = if ($option.ContainsKey('DFA')) { [bool]$option['DFA'] } else { $true }
        $this.write    = if ($option.ContainsKey('write') -and $null -ne $option['write']) { $option['write'] } else { { param($line) [Console]::Out.WriteLine($line) } }
        $this._edge_db = [System.Collections.Generic.Dictionary[string, object]]::new([System.StringComparer]::Ordinal)
        $stateSet = [FsmMachine]::NewSet()
        [void]$stateSet.Add($initial)
        if ($option.ContainsKey('states') -and $null -ne $option['states']) { foreach ($s in $option['states']) { [void]$stateSet.Add($s) } }
        foreach ($t in @($transitions)) {
            if ($null -eq $t) { continue }
            $source = [string]$t[0]; $event = [string]$t[1]; $target = [string]$t[2]
            $k = [FsmMachine]::Key(@($source, $event))
            if (-not $this._edge_db.ContainsKey($k)) { $this._edge_db[$k] = @{ source = $source; event = $event; targets = [FsmMachine]::NewSet() } }
            $targetSet = $this._edge_db[$k].targets
            if ($this.dfa_f -and $targetSet.Count -gt 0 -and -not $targetSet.Contains($target)) {
                throw [FsmError]::new("'$source' --($event)--> '$(([FsmMachine]::Sorted($targetSet))[0])' and '$target': " +
                                      "a DFA moves one way per event -- or 'DFA=False'")
            }
            [void]$targetSet.Add($target)
            [void]$stateSet.Add($source); [void]$stateSet.Add($target)
        }
        $this.initial         = $initial
        $this.model_forbidden = [FsmMachine]::NewSet()
        $this.final           = [FsmMachine]::NewSet()
        if ($option.ContainsKey('forbidden') -and $null -ne $option['forbidden']) { foreach ($s in $option['forbidden']) { [void]$this.model_forbidden.Add($s) } }
        if ($option.ContainsKey('final') -and $null -ne $option['final'])         { foreach ($s in $option['final'])     { [void]$this.final.Add($s) } }
        foreach ($pair in @(@('forbidden', $this.model_forbidden), @('final', $this.final))) {
            $unknown = [FsmMachine]::Sorted(@(foreach ($s in $pair[1]) { if (-not $stateSet.Contains($s)) { $s } }))
            if ($unknown.Count -gt 0) {
                throw [FsmError]::new("$($pair[0]) state(s) $((@(foreach ($s in $unknown) { "'$s'" })) -join ', '): " +
                                      'named nowhere else in the model')
            }
        }
        $all = [FsmMachine]::NewSet()
        $all.UnionWith($stateSet); $all.UnionWith($this.model_forbidden)
        $this.state_tuple = [FsmMachine]::Sorted($all)
        $events = [FsmMachine]::NewSet()
        foreach ($e in $this._edge_db.Values) { [void]$events.Add($e.event) }
        $this.event_tuple = [FsmMachine]::Sorted($events)
        $this.Reset()
    }

    # ------------------------------------------------------------- reading
    <# RETURN: FsmMachine, the model the text states (options defaulted); see the overload. #>
    static [FsmMachine] FromString([string]$text) { return [FsmMachine]::FromString($text, @{}) }

    <#
    RETURN: FsmMachine, the model the text states, if success; throws
            FsmError naming the line, else. 'option': DFA, name, write.

    One statement per line; '#' starts a comment:
        initial: A              where the machine starts; default: the
                                first state the text names
        forbidden: X, Y         states the system must never enter
        final: A, B             states it may end in
        state A                 a state, transitions or not
        A ---( ev )---> B ---( ev2 )---> C     transitions, chained
        :  ---( ev )---> D      ':' is the state that began the line above
    #>
    static [FsmMachine] FromString([string]$text, [hashtable]$option) {
        if ($null -eq $option) { $option = @{} }
        $dfa = if ($option.ContainsKey('DFA')) { [bool]$option['DFA'] } else { $true }
        $tripleList   = [System.Collections.Generic.List[object]]::new()
        $declared     = [System.Collections.Generic.Dictionary[string, object]]::new([System.StringComparer]::Ordinal)
        $lineOf       = [System.Collections.Generic.Dictionary[string, object]]::new([System.StringComparer]::Ordinal)
        $first        = $null
        $previousHead = $null
        $number       = 0
        foreach ($raw in [FsmMachine]::SplitLines($text)) {
            $number++
            $line = $raw.Split('#')[0].Trim()
            if (-not $line) { continue }
            $keyFound = [regex]::Match($line, [FsmMachine]::KEY_RE)
            if ($keyFound.Success) {
                $word = $keyFound.Groups[1].Value
                $nameList = @(foreach ($p in $keyFound.Groups[2].Value.Split(',')) { if ($p.Trim()) { [FsmMachine]::NameOf($p, $number) } })
                if ($word -ceq 'initial' -and $nameList.Count -ne 1) { throw [FsmError]::new("line ${number}: 'initial:' names one state") }
                if (-not $declared.ContainsKey($word)) { $declared[$word] = [System.Collections.Generic.List[string]]::new() }
                foreach ($n in $nameList) { $declared[$word].Add($n) }
                continue
            }
            $partList = [regex]::Split($line, [FsmMachine]::ARROW_RE)
            if ($partList.Count -eq 1) {
                $head = [FsmMachine]::NameOf($line, $number)
                if ($null -eq $first) { $first = $head }
                $tripleList.Add(@($head, $null, $null))
                $previousHead = $head
                continue
            }
            for ($i = 1; $i -lt $partList.Count; $i += 2) {
                if (-not $partList[$i].Trim()) { throw [FsmError]::new("line ${number}: an arrow names no event -- '---( event )--->'") }
            }
            $headText = $partList[0].Trim()
            if ($headText -ceq ':') {
                if ($null -eq $previousHead) {
                    throw [FsmError]::new("line ${number}: ':' stands for the state of the line above, and none stands there")
                }
                $head = $previousHead
            } else {
                $head = [FsmMachine]::NameOf($headText, $number)
            }
            if ($null -eq $first) { $first = $head }
            $previousHead = $head
            $source = $head
            for ($i = 1; $i -lt $partList.Count; $i += 2) {
                $target = [FsmMachine]::NameOf($partList[$i + 1], $number)
                $event  = $partList[$i].Trim()
                $k      = [FsmMachine]::Key(@($source, $event))
                if ($dfa -and $lineOf.ContainsKey($k) -and $lineOf[$k][0] -cne $target) {
                    throw [FsmError]::new("line ${number}: '$source' --($event)--> '$target', and line " +
                                          "$($lineOf[$k][1]): --> '$($lineOf[$k][0])' -- a DFA moves one way per " +
                                          "event, or 'DFA=False'")
                }
                if (-not $lineOf.ContainsKey($k)) { $lineOf[$k] = @($target, $number) }
                $tripleList.Add(@($source, $event, $target))
                $source = $target
            }
        }
        if ($null -eq $first -and -not $declared.ContainsKey('initial')) { throw [FsmError]::new('the model names no state') }
        $start = if ($declared.ContainsKey('initial') -and $declared['initial'].Count -gt 0) { $declared['initial'][0] } else { $first }
        $states = [FsmMachine]::NewSet()
        $edges  = [System.Collections.Generic.List[object]]::new()
        foreach ($t in $tripleList) { if ($null -eq $t[1]) { [void]$states.Add($t[0]) } else { $edges.Add($t) } }
        $forbidden = if ($declared.ContainsKey('forbidden')) { $declared['forbidden'] } else { @() }
        $finalList = if ($declared.ContainsKey('final'))     { $declared['final'] }     else { @() }
        return [FsmMachine]::new($edges.ToArray(), $start, @{
            forbidden = $forbidden; final = $finalList; DFA = $dfa
            name      = if ($option.ContainsKey('name')) { $option['name'] } else { 'fsm' }
            write     = if ($option.ContainsKey('write')) { $option['write'] } else { $null }
            states    = $states
        })
    }

    <# RETURN: object[], every transition of the model as @(source, event, target), sorted. #>
    hidden [object[]] AllEdges() {
        $all = [System.Collections.Generic.List[object]]::new()
        foreach ($e in $this._edge_db.Values) { foreach ($t in $e.targets) { $all.Add([string[]]@($e.source, $e.event, $t)) } }
        return [FsmMachine]::SortedTuples($all)
    }

    <#
    RETURN: string, the model in the text 'FromString' reads, one transition
            per line, sorted (Python's 'to_string').
    #>
    [string] ToString() {
        $lineList = [System.Collections.Generic.List[string]]::new()
        $lineList.Add("initial: $($this.initial)")
        if ($this.model_forbidden.Count -gt 0) { $lineList.Add("forbidden: $(([FsmMachine]::Sorted($this.model_forbidden)) -join ', ')") }
        if ($this.final.Count -gt 0)           { $lineList.Add("final: $(([FsmMachine]::Sorted($this.final)) -join ', ')") }
        $named = [FsmMachine]::NewSet()
        [void]$named.Add($this.initial)
        foreach ($t in $this.AllEdges()) {
            $lineList.Add("$($t[0]) ---( $($t[1]) )---> $($t[2])")
            [void]$named.Add($t[0]); [void]$named.Add($t[2])
        }
        foreach ($s in $this.state_tuple) {
            if (-not $named.Contains($s) -and -not $this.model_forbidden.Contains($s)) { $lineList.Add("state $s") }
        }
        return $lineList -join "`n"
    }

    # ------------------------------------------------------------- running
    <#
    RETURN: nothing. The machine stands in its initial state again, under
            the model as written: what was seen is forgotten, and so is every
            mask and every state forbidden or permitted since.
    #>
    [void] Reset() {
        $this._mask_db   = [System.Collections.Generic.Dictionary[string, object]]::new([System.StringComparer]::Ordinal)
        $this._forbid_db = [System.Collections.Generic.Dictionary[string, object]]::new([System.StringComparer]::Ordinal)
        foreach ($s in $this.model_forbidden) { $this._forbid_db[$s] = $null }
        $this._permit_db = [System.Collections.Generic.Dictionary[string, object]]::new([System.StringComparer]::Ordinal)
        $this._current   = [FsmMachine]::NewSet()
        [void]$this._current.Add($this.initial)
        $this._visit_db  = [System.Collections.Generic.Dictionary[string, int]]::new([System.StringComparer]::Ordinal)
        $this._visit_db[$this.initial] = 1
        $this._taken_db  = [System.Collections.Generic.Dictionary[string, int]]::new([System.StringComparer]::Ordinal)
        $this._trace_list = [System.Collections.Generic.List[object]]::new()
        $this.breach_n   = 0
    }

    <# RETURN: nothing; 'line' handed to the machine's writer. #>
    hidden [void] Say([string]$line) { & $this.write $line }

    <# RETURN: bool, as 'Fire(event, where)' with no place named. #>
    [bool] Fire([string]$event) { return $this.Fire($event, $null) }

    <#
    RETURN: bool, $true where 'event' moved the machine and entered no
            forbidden state; $false where it was not allowed where the
            machine stands -- a BREACH line is written and the machine stays
            -- or it entered a forbidden state, which is written too.

    'where' is the place the breach line names: an integer is a line number
    ('line 3'), a text stands as written.
    #>
    [bool] Fire([string]$event, [object]$where) {
        $moved  = [FsmMachine]::NewSet()
        $masked = [System.Collections.Generic.List[string]]::new()
        foreach ($state in [FsmMachine]::Sorted($this._current)) {
            $k    = [FsmMachine]::Key(@($state, $event))
            $edge = if ($this._edge_db.ContainsKey($k)) { $this._edge_db[$k] } else { $null }
            if ($this.MaskedF($state, $event)) {
                if ($null -ne $edge) { $masked.Add($state) }
                continue
            }
            if ($null -eq $edge) { continue }
            foreach ($target in [FsmMachine]::Sorted($edge.targets)) {
                [void]$moved.Add($target)
                $tk = [FsmMachine]::Key(@($state, $event, $target))
                if ($this._taken_db.ContainsKey($tk)) { $this._taken_db[$tk]++ } else { $this._taken_db[$tk] = 1 }
                $this._trace_list.Add(@($where, $state, $event, $target))
            }
        }
        if ($moved.Count -eq 0) {
            $this.breach_n++
            $allowedNow = $this.Allowed()
            $hint = if ($allowedNow.Count -gt 0) { "allowed: $($allowedNow -join ', ')" } else { 'no event leaves it' }
            if ($this.event_tuple -cnotcontains $event) {
                $hint = 'an event the model never names'
            } elseif ($masked.Count -gt 0) {
                $one = [FsmMachine]::Key(@($masked[0], $event))
                $any = [FsmMachine]::Key(@($null, $event))
                $since = if ($this._mask_db.ContainsKey($one)) { $this._mask_db[$one].since }
                         elseif ($this._mask_db.ContainsKey($any)) { $this._mask_db[$any].since } else { $null }
                $hint = 'disallowed' + [FsmMachine]::SinceText($since)
            }
            $this.Say("BREACH$([FsmMachine]::WhereText($where)): '$event' in $($this.Here()) -- $hint")
            return $false
        }
        $this._current = $moved
        foreach ($s in $moved) { if ($this._visit_db.ContainsKey($s)) { $this._visit_db[$s]++ } else { $this._visit_db[$s] = 1 } }
        $entered = [FsmMachine]::Sorted(@(foreach ($s in $moved) { if ($this._forbid_db.ContainsKey($s)) { $s } }))
        foreach ($s in $entered) {
            $this.breach_n++
            $since = $this._forbid_db[$s]
            $what  = if ($this.model_forbidden.Contains($s) -and $null -eq $since) { 'a forbidden state' } else { 'forbidden' + [FsmMachine]::SinceText($since) }
            $this.Say("BREACH$([FsmMachine]::WhereText($where)): '$s' entered by '$event' -- $what")
        }
        return $entered.Count -eq 0
    }

    # --------------------------------------------------- the law, changing
    <#
    RETURN: HashSet[string], the states forbidden NOW -- the model's, less
            those permitted, with those forbidden since (Python's 'forbidden').
    #>
    [System.Collections.Generic.HashSet[string]] Forbidden() {
        $s = [FsmMachine]::NewSet()
        foreach ($k in $this._forbid_db.Keys) { [void]$s.Add($k) }
        return $s
    }

    <# RETURN: bool, $true if 'event' is disallowed in 'state' now -- in every state, or in that one. #>
    hidden [bool] MaskedF([string]$state, [string]$event) {
        return $this._mask_db.ContainsKey([FsmMachine]::Key(@($null, $event))) -or $this._mask_db.ContainsKey([FsmMachine]::Key(@($state, $event)))
    }

    <#
    RETURN: nothing, if 'event' and 'state' are named by the model (or
            $null); throws FsmError naming what is not, else.
    #>
    hidden [void] Known([object]$event, [object]$state) {
        if ($null -ne $event -and $this.event_tuple -cnotcontains $event) {
            throw [FsmError]::new("'$event': an event the model never names -- events: $($this.event_tuple -join ', ')")
        }
        if ($null -ne $state -and $this.state_tuple -cnotcontains $state) {
            throw [FsmError]::new("'$state': a state the model never names -- states: $($this.state_tuple -join ', ')")
        }
    }

    <# RETURN: nothing; 'Disallow(event, $null, $null)'. #>
    [void] Disallow([string]$event) { $this.Disallow($event, $null, $null) }
    <# RETURN: nothing; 'Disallow(event, state, $null)'. #>
    [void] Disallow([string]$event, [object]$state) { $this.Disallow($event, $state, $null) }

    <#
    RETURN: nothing. From now on 'event' is a breach -- in 'state' alone, or
            in every state where $null -- until 'Allow' lifts it; the breach
            line says 'disallowed since <where>'. Throws FsmError where the
            model names no such event or state.
    #>
    [void] Disallow([string]$event, [object]$state, [object]$where) {
        $this.Known($event, $state)
        $k = [FsmMachine]::Key(@($state, $event))
        if (-not $this._mask_db.ContainsKey($k)) { $this._mask_db[$k] = @{ state = $state; event = $event; since = $where } }
    }

    <# RETURN: nothing; 'Allow(event, $null, $null)'. #>
    [void] Allow([string]$event) { $this.Allow($event, $null, $null) }
    <# RETURN: nothing; 'Allow(event, state, $null)'. #>
    [void] Allow([string]$event, [object]$state) { $this.Allow($event, $state, $null) }

    <#
    RETURN: nothing. The mask 'Disallow(event, state)' set is lifted; a mask
            set for another scope stays. Throws FsmError where the model
            names no such event or state.
    #>
    [void] Allow([string]$event, [object]$state, [object]$where) {
        $this.Known($event, $state)
        [void]$this._mask_db.Remove([FsmMachine]::Key(@($state, $event)))
    }

    <# RETURN: nothing; 'Forbid(state, $null)'. #>
    [void] Forbid([string]$state) { $this.Forbid($state, $null) }

    <#
    RETURN: nothing. From now on entering 'state' is a breach, until
            'Permit'. Where the machine STANDS in it, one BREACH line is
            written at once. Throws FsmError where the model names no such
            state.
    #>
    [void] Forbid([string]$state, [object]$where) {
        $this.Known($null, $state)
        if ($this._forbid_db.ContainsKey($state)) { return }
        $this._forbid_db[$state] = $where
        [void]$this._permit_db.Remove($state)
        if ($this._current.Contains($state)) {
            $this.breach_n++
            $this.Say("BREACH$([FsmMachine]::WhereText($where)): stands in '$state' -- forbidden$([FsmMachine]::SinceText($where))")
        }
    }

    <# RETURN: nothing; 'Permit(state, $null)'. #>
    [void] Permit([string]$state) { $this.Permit($state, $null) }

    <#
    RETURN: nothing. 'state' is no longer forbidden -- a state of the model's
            own 'forbidden:' too, until 'Forbid' again. Throws FsmError where
            the model names no such state.
    #>
    [void] Permit([string]$state, [object]$where) {
        $this.Known($null, $state)
        if ($this._forbid_db.Remove($state) -and $this.model_forbidden.Contains($state)) { $this._permit_db[$state] = $where }
    }

    <#
    RETURN: FsmPhase: 'event' disallowed (see 'Disallow') while its
            'Run(block)' runs, allowed again on leaving it -- whatever way.
    #>
    [FsmPhase] Disallowed([string]$event, [object]$state, [object]$where) {
        $m = $this
        return [FsmPhase]::new({ $m.Disallow($event, $state, $where) }.GetNewClosure(),
                               { $m.Allow($event, $state) }.GetNewClosure())
    }

    <#
    RETURN: FsmPhase: 'state' forbidden (see 'Forbid') while its 'Run(block)'
            runs, permitted again on leaving it -- whatever way.
    #>
    [FsmPhase] Forbidding([string]$state, [object]$where) {
        $m = $this
        return [FsmPhase]::new({ $m.Forbid($state, $where) }.GetNewClosure(),
                               { $m.Permit($state) }.GetNewClosure())
    }

    <# RETURN: string, where the machine stands: "'idle'", or "{'a', 'b'}". #>
    hidden [string] Here() {
        if ($this._current.Count -eq 1) { return "'$(@($this._current)[0])'" }
        return '{' + ((@(foreach ($s in [FsmMachine]::Sorted($this._current)) { "'$s'" })) -join ', ') + '}'
    }

    # ------------------------------------------------------------ questions
    <#
    RETURN: string, the one state the machine stands in, if success; throws
            FsmError, else -- a set of states stands (DFA=False).
    #>
    [string] State() {
        if ($this._current.Count -ne 1) { throw [FsmError]::new("the machine stands in $($this.Here()): ask 'current()'") }
        return @($this._current)[0]
    }

    <# RETURN: HashSet[string], every state the machine stands in (a copy). #>
    [System.Collections.Generic.HashSet[string]] Current() {
        $s = [FsmMachine]::NewSet()
        $s.UnionWith($this._current)
        return $s
    }

    <# RETURN: bool, $true if the machine stands in 'state'. #>
    [bool] InState([string]$state) { return $this._current.Contains($state) }

    <# RETURN: bool, $true if 'event' would move the machine now. #>
    [bool] Can([string]$event) {
        foreach ($s in $this._current) {
            if ($this._edge_db.ContainsKey([FsmMachine]::Key(@($s, $event))) -and -not $this.MaskedF($s, $event)) { return $true }
        }
        return $false
    }

    <# RETURN: string[], the events that would move the machine now, sorted, each once. #>
    [string[]] Allowed() {
        $found = [FsmMachine]::NewSet()
        foreach ($e in $this._edge_db.Values) {
            if ($this._current.Contains($e.source) -and -not $this.MaskedF($e.source, $e.event)) { [void]$found.Add($e.event) }
        }
        return [FsmMachine]::Sorted($found)
    }

    <# RETURN: object[], every transition fired, in order, each @(where, state, event, state). #>
    [object[]] Trace() { return $this._trace_list.ToArray() }

    # ------------------------------------------------------ the model alone
    <#
    RETURN: Dictionary, state -> sorted list of @(event, state) leaving it --
            under the masks where 'masked', as written else.
    #>
    hidden [System.Collections.Generic.Dictionary[string, object]] SuccessorDb([bool]$masked) {
        $found = [System.Collections.Generic.Dictionary[string, object]]::new([System.StringComparer]::Ordinal)
        foreach ($e in $this._edge_db.Values) {
            if ($masked -and $this.MaskedF($e.source, $e.event)) { continue }
            foreach ($t in $e.targets) {
                if (-not $found.ContainsKey($e.source)) { $found[$e.source] = [System.Collections.Generic.List[object]]::new() }
                $found[$e.source].Add([string[]]@($e.event, $t))
            }
        }
        foreach ($k in @($found.Keys)) { $found[$k] = [FsmMachine]::SortedTuples($found[$k]) }
        return $found
    }

    <# RETURN: string[] or $null, 'PathTo(state, $null, $true)'. #>
    [object] PathTo([string]$state) { return $this.PathTo($state, $null, $true) }
    <# RETURN: string[] or $null, 'PathTo(state, start, $true)'. #>
    [object] PathTo([string]$state, [object]$start) { return $this.PathTo($state, $start, $true) }

    <#
    RETURN: string[], the shortest sequence of events from 'start' -- the
            initial state where $null, 'now' for where the machine stands --
            into 'state', if one exists (empty where 'start' is 'state');
            among equally short ones the first in event order; $null, else:
            'state' cannot be reached from there. Under the masks standing
            now; 'masked' $false asks the model as written.
    #>
    [object] PathTo([string]$state, [object]$start, [bool]$masked) {
        $startSet = [FsmMachine]::NewSet()
        if ($start -ceq 'now')     { $startSet.UnionWith($this._current) }
        elseif ($null -eq $start)  { [void]$startSet.Add($this.initial) }
        else                       { [void]$startSet.Add([string]$start) }
        if ($startSet.Contains($state)) { return [string[]]@() }
        $successorDb = $this.SuccessorDb($masked)
        $queue = [System.Collections.Generic.Queue[object]]::new()
        foreach ($s in [FsmMachine]::Sorted($startSet)) { $queue.Enqueue(@($s, [string[]]@())) }
        $seen = [FsmMachine]::NewSet()
        $seen.UnionWith($startSet)
        while ($queue.Count -gt 0) {
            $item = $queue.Dequeue()
            $here = $item[0]; $path = [string[]]$item[1]
            if (-not $successorDb.ContainsKey($here)) { continue }
            foreach ($pair in $successorDb[$here]) {
                $target = $pair[1]
                if ($seen.Contains($target)) { continue }
                $longer = [string[]]($path + @($pair[0]))
                if ($target -ceq $state) { return $longer }
                [void]$seen.Add($target)
                $queue.Enqueue(@($target, $longer))
            }
        }
        return $null
    }

    <# RETURN: bool, 'StateReachable(state, $null, $true)'. #>
    [bool] StateReachable([string]$state) { return $this.StateReachable($state, $null, $true) }
    <# RETURN: bool, 'StateReachable(state, start, $true)'. #>
    [bool] StateReachable([string]$state, [object]$start) { return $this.StateReachable($state, $start, $true) }
    <# RETURN: bool, $true if 'state' can be reached from 'start' (see 'PathTo'). #>
    [bool] StateReachable([string]$state, [object]$start, [bool]$masked) { return $null -ne $this.PathTo($state, $start, $masked) }

    <# RETURN: HashSet[string], the states forbidden now where 'masked', the model's own else. #>
    hidden [System.Collections.Generic.HashSet[string]] ForbiddenOf([bool]$masked) {
        if ($masked) { return $this.Forbidden() }
        return $this.model_forbidden
    }

    <# RETURN: string[], 'Unreachable($true)'. #>
    [string[]] Unreachable() { return $this.Unreachable($true) }

    <#
    RETURN: string[], the states no path from the initial state reaches,
            forbidden ones left out -- sorted; under the masks unless
            'masked' is $false.
    #>
    [string[]] Unreachable([bool]$masked) {
        $forbidden = $this.ForbiddenOf($masked)
        return [string[]]@(foreach ($s in $this.state_tuple) { if (-not $forbidden.Contains($s) -and -not $this.StateReachable($s, $null, $masked)) { $s } })
    }

    <# RETURN: string[], 'DeadEnds($true)'. #>
    [string[]] DeadEnds() { return $this.DeadEnds($true) }

    <#
    RETURN: string[], the states no event leaves that are neither final nor
            forbidden -- sorted; under the masks unless 'masked' is $false.
    #>
    [string[]] DeadEnds([bool]$masked) {
        $successorDb = $this.SuccessorDb($masked)
        $forbidden   = $this.ForbiddenOf($masked)
        return [string[]]@(foreach ($s in $this.state_tuple) { if (-not $successorDb.ContainsKey($s) -and -not $this.final.Contains($s) -and -not $forbidden.Contains($s)) { $s } })
    }

    <# RETURN: string[], 'ForbiddenReachable($true)'. #>
    [string[]] ForbiddenReachable() { return $this.ForbiddenReachable($true) }

    <#
    RETURN: string[], the forbidden states the model lets the system reach
            from the initial state -- sorted; under the masks and the states
            forbidden now unless 'masked' is $false.
    #>
    [string[]] ForbiddenReachable([bool]$masked) {
        return [string[]]@(foreach ($s in [FsmMachine]::Sorted($this.ForbiddenOf($masked))) { if ($this.StateReachable($s, $null, $masked)) { $s } })
    }

    <# RETURN: int, 'Check($true)'. #>
    [int] Check() { return $this.Check($true) }

    <#
    RETURN: int, how many findings the MODEL has, each written as one line
            'MODEL: ...'; 0 where it has none -- unreachable states, dead
            ends, reachable forbidden states with the shortest way there;
            under the masks unless 'masked' is $false.
    #>
    [int] Check([bool]$masked) {
        $lineList = [System.Collections.Generic.List[string]]::new()
        foreach ($s in $this.Unreachable($masked)) { $lineList.Add("MODEL: '$s' cannot be reached") }
        foreach ($s in $this.DeadEnds($masked))    { $lineList.Add("MODEL: '$s' is a dead end -- no event leaves it") }
        foreach ($s in $this.ForbiddenReachable($masked)) {
            $lineList.Add("MODEL: forbidden '$s' is reachable: $(($this.PathTo($s, $null, $masked)) -join ' ')")
        }
        foreach ($line in $lineList) { $this.Say($line) }
        return $lineList.Count
    }

    # -------------------------------------------------------------- the end
    <#
    RETURN: int, the breaches seen, counting a non-final end; written before
            it, sorted, what the events covered of the model -- states
            counted without the forbidden ones -- every transition taken or
            not, states never in, where it ended, the masks still standing;
            a BREACH line for an end outside the final states.
    #>
    [int] Report() {
        $allEdge = $this.AllEdges()
        $breachN = $this.breach_n
        $endF    = $this.final.Count -eq 0
        foreach ($s in $this._current) { if ($this.final.Contains($s)) { $endF = $true } }
        if (-not $endF) { $breachN++ }
        $goal    = @(foreach ($s in $this.state_tuple) { if (-not $this.model_forbidden.Contains($s)) { $s } })
        $visited = @(foreach ($s in $goal) { if ($this._visit_db.ContainsKey($s)) { $s } })
        $plural  = if ($breachN -eq 1) { '' } else { 'es' }
        $this.Say("$($this.name): $($visited.Count) of $($goal.Count) states visited, " +
                  "$($this._taken_db.Count) of $($allEdge.Count) transitions taken, " +
                  "$breachN breach$plural")
        foreach ($t in $allEdge) {
            $k = [FsmMachine]::Key(@($t[0], $t[1], $t[2]))
            $n = if ($this._taken_db.ContainsKey($k)) { $this._taken_db[$k] } else { 0 }
            $label = if ($n -gt 0) { 'taken    ' } else { 'not taken' }
            $times = if ($n -gt 1) { "   x$n" } else { '' }
            $this.Say("  $label  $($t[0]) ---( $($t[1]) )---> $($t[2])$times")
        }
        foreach ($s in $this.state_tuple) {
            if (-not $this._visit_db.ContainsKey($s) -and -not $this.model_forbidden.Contains($s)) { $this.Say("  never in   '$s'") }
        }
        $this.Say("  ended in   $($this.Here())")
        $maskList = [System.Collections.Generic.List[object]]::new()
        foreach ($mk in $this._mask_db.Values) { $maskList.Add($mk) }
        $maskList.Sort([System.Comparison[object]] {
            param($a, $b)
            [FsmMachine]::CompareTuple([string[]]@($a.event, [string]$a.state), [string[]]@($b.event, [string]$b.state))
        })
        foreach ($mk in $maskList) {
            $scope = if ($null -eq $mk.state) { 'in every state' } else { "in '$($mk.state)'" }
            $this.Say("  disallowed '$($mk.event)' $scope$([FsmMachine]::SinceText($mk.since))")
        }
        foreach ($s in [FsmMachine]::Sorted(@(foreach ($k in $this._forbid_db.Keys) { if (-not $this.model_forbidden.Contains($k)) { $k } }))) {
            $this.Say("  forbidden  '$s'$([FsmMachine]::SinceText($this._forbid_db[$s]))")
        }
        foreach ($s in [FsmMachine]::Sorted($this._permit_db.Keys)) {
            $this.Say("  permitted  '$s'$([FsmMachine]::SinceText($this._permit_db[$s]))")
        }
        if (-not $endF) { $this.Say("BREACH: ended in $($this.Here()) -- final: $(([FsmMachine]::Sorted($this.final)) -join ', ')") }
        return $breachN
    }
}
