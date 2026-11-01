# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#_____________________________________________________________________________
#
# PURPOSE: A DETERMINISTIC EVENT DISPATCHER -- the port of
#          'python/deterministic_timeline.py'. Triggers fire at the ticks their
#          timeline strings mark with a digit; within one tick the LOWER digit
#          fires first, equal digits in registration order:
#
#              Trigger A: "1  12 1"
#              Trigger B: " 1  1 2"
#
#          When the last tick has passed, every trigger is told
#          'OnTermination(end_tick)', 'end_tick' being the LONGEST timeline's
#          length. 'Stop' leaves early and still announces; a CANCELLED task
#          announces nothing.
#
# USAGE:
#
#     using module ../deterministic_timeline.psm1
#     class MyTrigger : Trigger {
#         MyTrigger([string]$timeline, [string]$name) : base($timeline, $name) { }
#         [void] Fire([int]$pseudo_time) { Out-Py "[$pseudo_time] $($this.name) fired" }
#     }
#     [TriggerDispatcher]::new(@([MyTrigger]::new('1 1 3', 'SUB'))).Run()
#
# THE YIELD WITHOUT COROUTINES. PowerShell has no 'async'; as in the C port a
# task is a STEP FUNCTION -- a script block that runs up to its next yield and
# returns $true ('await asyncio.sleep(0)': more to come) or $false (done).
# 'Fire' is a plain method: a firing runs whole, as an asyncio coroutine that
# does not await runs whole. Python's asyncio, and how it reads here:
#
#     asyncio.run(d.run())                $d.Run()
#     task = asyncio.create_task(d.run()) $task = $d.Task()
#     await asyncio.sleep(0)  (in main)   [void]$task.Step()   # it runs one turn
#     task.cancel(); await task           $task.Cancel(); $task.Await()
#     await asyncio.gather(d.run(), c())  [AsyncTask]::Gather(@($d.Task(), [AsyncTask]::new({ ... })))
#
# 'Gather' steps the tasks in turn, in the order given -- the order asyncio's
# ready queue gives them -- until each is done; so the drawn interleaving is
# the one that happens, line for line. A CANCELLED task is told at its next
# step: it does not run again, and 'Await' throws CancelledError.
#
# EXCEPTIONS are classes named as Python's: NotImplementedError (the base
# 'Fire'), CancelledError (asyncio's).
#_____________________________________________________________________________
Set-StrictMode -Version 3.0

class NotImplementedError : System.Exception {
    <# RETURN: NotImplementedError, named as Python's exception, without a message. #>
    NotImplementedError() : base('') { }
    <# RETURN: NotImplementedError with 'message'. #>
    NotImplementedError([string]$message) : base($message) { }
}

class CancelledError : System.Exception {
    <# RETURN: CancelledError, named as asyncio's exception, without a message. #>
    CancelledError() : base('') { }
}

class AsyncTask {
    [bool] $done_f
    [bool] $cancelled_f
    hidden [scriptblock] $_step
    hidden [bool]        $_cancel_requested_f
    hidden [object]      $_error                 # what the step threw, once done

    <#
    RETURN: AsyncTask over the step function 'step' -- a script block that
            runs up to its next yield and returns $true (yielded, more to
            come) or $false (done); not yet started.
    #>
    AsyncTask([scriptblock]$step) { $this._step = $step }

    <#
    RETURN: bool, $true where the task yielded and has more to run; $false
            where it is done -- now or before: its step returned $false or
            threw (kept for 'Await'), or it was cancelled (it is not run
            again; CancelledError kept).
    #>
    [bool] Step() {
        if ($this.done_f) { return $false }
        if ($this._cancel_requested_f) {
            $this.cancelled_f = $true
            $this.done_f      = $true
            $this._error      = [CancelledError]::new()
            return $false
        }
        try {
            $more = [bool](& $this._step)
        } catch {
            $x = $_.Exception
            #  A method's throw reaches a script block wrapped: unwrap it.
            while ($x -is [System.Management.Automation.MethodInvocationException] -and $null -ne $x.InnerException) { $x = $x.InnerException }
            $this._error = $x
            $this.done_f = $true
            return $false
        }
        if (-not $more) { $this.done_f = $true }
        return $more
    }

    <#
    RETURN: bool, $true where the task was not done and is now to be
            cancelled (told at its next step); $false where it was done.
    #>
    [bool] Cancel() {
        if ($this.done_f) { return $false }
        $this._cancel_requested_f = $true
        return $true
    }

    <#
    RETURN: nothing, once the task has ended by returning -- stepped until
            then; throws what it threw, CancelledError where it was cancelled.
    #>
    [void] Await() {
        while ($this.Step()) { }
        if ($null -ne $this._error) { throw $this._error }
    }

    <#
    RETURN: nothing, once every task of 'task_list' is done -- stepped in
            turn, in the order given, one step each per round, as asyncio's
            'gather' runs them; throws the first error a task threw (by the
            order of the list).
    #>
    static [void] Gather([AsyncTask[]]$task_list) {
        $any = $true
        while ($any) {
            $any = $false
            foreach ($t in $task_list) { if ($t.Step()) { $any = $true } }
        }
        foreach ($t in $task_list) { if ($null -ne $t._error) { throw $t._error } }
    }
}

class Trigger {
    static hidden [int] $counter = 0
    [string] $timeline
    [string] $name

    <#
    RETURN: Trigger with 'timeline' and 'name' -- a name chosen by the
            machine ('trigger-<n>') where 'name' is empty.
    #>
    Trigger([string]$timeline, [string]$name) {
        $this.timeline = $timeline
        if ($name) { $this.name = $name }
        else       { [Trigger]::counter++; $this.name = "trigger-$([Trigger]::counter)" }
    }

    <# RETURN: Trigger with 'timeline' and a name chosen by the machine. #>
    Trigger([string]$timeline) { $this.timeline = $timeline; [Trigger]::counter++; $this.name = "trigger-$([Trigger]::counter)" }

    <#
    RETURN: never; ABSTRACT -- a trigger that does nothing when its tick comes
            has no reason to stand in the timeline: throws NotImplementedError.
    #>
    [void] Fire([int]$pseudo_time) { throw [NotImplementedError]::new() }

    <#
    RETURN: nothing. Optional: a trigger with nothing to wind down says
            nothing. Not a step: the run is over, nobody is left to yield to.
    #>
    [void] OnTermination([int]$end_tick) { }
}

class TriggerDispatcher {
    hidden [bool]     $_running_f
    hidden [object[]] $_triggers
    hidden [object[]] $_trigger_time_db      # per tick: list of @(priority, trigger)
    hidden [int]      $_end_tick

    <#
    RETURN: TriggerDispatcher over 'triggers', its schedule built: one entry
            per tick (as many as the LONGEST timeline has characters), the
            (priority, trigger) pairs due there, lower digit first,
            registration order between equal digits (a stable sort).
    #>
    TriggerDispatcher([object[]]$triggers) {
        $this._running_f = $true
        $this._triggers  = if ($null -eq $triggers) { @() } else { @($triggers) }
        $end = 0
        foreach ($t in $this._triggers) { if ($t.timeline.Length -gt $end) { $end = $t.timeline.Length } }
        $this._trigger_time_db = [object[]]::new($end)
        for ($tick = 0; $tick -lt $end; $tick++) { $this._trigger_time_db[$tick] = [System.Collections.Generic.List[object]]::new() }
        foreach ($trigger in $this._triggers) {
            for ($tick = 0; $tick -lt $trigger.timeline.Length; $tick++) {
                $c = $trigger.timeline[$tick]
                if ($c -ge [char]'0' -and $c -le [char]'9') { $this._trigger_time_db[$tick].Add(@(([int]$c - 48), $trigger)) }
            }
        }
        for ($tick = 0; $tick -lt $end; $tick++) {
            #  Sort-Object -Stable keeps registration order between equal digits.
            $sorted = [object[]]@($this._trigger_time_db[$tick] | Sort-Object -Stable -Property { $_[0] })
            $list = [System.Collections.Generic.List[object]]::new()
            foreach ($pair in $sorted) { $list.Add($pair) }
            $this._trigger_time_db[$tick] = $list
        }
        $this._end_tick = $end
    }

    <#
    RETURN: nothing. Asks the run to leave the timeline at the next firing;
            the run still announces termination.
    #>
    [void] Stop() { $this._running_f = $false }

    <#
    RETURN: nothing, once the timeline has passed -- every trigger due fired
            tick by tick in priority order -- and every trigger was told
            'OnTermination(end_tick)' (also after 'Stop()'); throws what a
            'Fire' threw. Python's 'asyncio.run(dispatcher.run())'.
    #>
    [void] Run() { $this.Task().Await() }

    <#
    RETURN: AsyncTask, the run as a task: each step fires the next trigger
            due and yields (Python's 'await fire(t); await sleep(0)'); the
            step that finds the timeline passed, or 'Stop()' asked, tells
            every trigger 'OnTermination(end_tick)' and ends the task. A
            cancelled task announces nothing.
    #>
    [AsyncTask] Task() {
        $at = @{ tick = 0; i = 0; dispatcher = $this }
        $step = {
            $d  = $at.dispatcher
            $db = $d._trigger_time_db
            while ($at.tick -lt $db.Count -and $at.i -ge $db[$at.tick].Count) { $at.tick++; $at.i = 0 }
            if ($d._running_f -and $at.tick -lt $db.Count) {
                $pair = $db[$at.tick][$at.i]
                $at.i++
                $pair[1].Fire($at.tick)
                return $true
            }
            foreach ($trigger in $d._triggers) { $trigger.OnTermination($d._end_tick) }
            return $false
        }.GetNewClosure()
        return [AsyncTask]::new($step)
    }

    <#
    RETURN: string, the schedule as built -- 'TriggerDispatcher', then one
            line per firing, '[tick] (priority)name', in the order of the
            run (Python's '__repr__').
    #>
    [string] ToString() {
        $line = [System.Collections.Generic.List[string]]::new()
        $line.Add('TriggerDispatcher')
        for ($tick = 0; $tick -lt $this._trigger_time_db.Count; $tick++) {
            foreach ($pair in $this._trigger_time_db[$tick]) { $line.Add("[$tick] ($($pair[0]))$($pair[1].name)") }
        }
        return $line -join "`n"
    }
}
