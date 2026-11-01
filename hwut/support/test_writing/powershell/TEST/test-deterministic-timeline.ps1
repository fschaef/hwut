# @hwut {
#     title      = "TriggerDispatcher: schedule, priority, and the end of time"
#     choices {
#         abstract    { features = ["ps-timeline"] }
#         cancel      { features = ["ps-timeline"] }
#         edges       { features = ["ps-timeline"] }
#         priority    { features = ["ps-timeline"] }
#         schedule    { features = ["ps-timeline"] }
#         stable      { features = ["ps-timeline"] }
#         stop        { features = ["ps-timeline"] }
#         termination { features = ["ps-timeline"] }
#         yielding    { features = ["ps-timeline"] }
#     }
#     caps        { file_size_mb = 2097152 }
#     interactive = true
# }
#
# SPDX-License: MIT; Project HWUT; (C) Frank-Rene Schaefer
#_____________________________________________________________________________
#
# PURPOSE: The PowerShell port of 'python/TEST/test-deterministic-timeline.py',
#          choice for choice, held against its GOOD files by '.link'. Where
#          Python awaits, a task is stepped (deterministic_timeline.psm1).
#_____________________________________________________________________________
using module ../hwut_runner.psm1
using module ../deterministic_timeline.psm1

<# RETURN: nothing; a section heading on [Console]::Out. #>
function banner([string]$label) { Out-Py ''; Out-Py "--- $label ---" }

#  A trigger that says what it is asked to do, and when.
class SpeakingTrigger : Trigger {
    [bool] $silent_termination_f

    <# RETURN: SpeakingTrigger 'name' on 'timeline'; says so. #>
    SpeakingTrigger([string]$name, [string]$timeline) : base($timeline, $name) { $this.Setup($false) }

    <# RETURN: SpeakingTrigger 'name' on 'timeline', silent at the end where 'silent'; says so. #>
    SpeakingTrigger([string]$name, [string]$timeline, [bool]$silent) : base($timeline, $name) { $this.Setup($silent) }

    <# RETURN: nothing; the SETUP line printed. #>
    hidden [void] Setup([bool]$silent) {
        $this.silent_termination_f = $silent
        Out-Py ('SETUP: {0,-7} |{1}|' -f $this.name, $this.timeline)
    }

    <# RETURN: nothing. Says that this trigger fired, and at which tick. #>
    [void] Fire([int]$pseudo_time) { Out-Py ('  [t:{0}] {1} fires' -f $pseudo_time, $this.name) }

    <# RETURN: nothing. Says that the timeline has passed, and where. #>
    [void] OnTermination([int]$end_tick) {
        if ($this.silent_termination_f) { return }
        Out-Py ('  [end:{0}] {1} notified' -f $end_tick, $this.name)
    }
}

#  A trigger that fires and does NOT override 'OnTermination' -- the base's
#  silence is what this one demonstrates.
class MuteTrigger : Trigger {
    <# RETURN: MuteTrigger 'name' on 'timeline'; says so. #>
    MuteTrigger([string]$name, [string]$timeline) : base($timeline, $name) {
        Out-Py ('SETUP: {0,-7} |{1}|  (no on_termination override)' -f $name, $timeline)
    }

    <# RETURN: nothing. Says that this trigger fired, and at which tick. #>
    [void] Fire([int]$pseudo_time) { Out-Py ('  [t:{0}] {1} fires' -f $pseudo_time, $this.name) }
}

#  Prepares one item per tick for a consumer (choice 'yielding').
class ProducingTrigger : Trigger {
    [object] $item
    [bool]   $finished

    <# RETURN: ProducingTrigger 'name' on 'timeline', no item yet; says so. #>
    ProducingTrigger([string]$name, [string]$timeline) : base($timeline, $name) {
        $this.item = $null; $this.finished = $false
        Out-Py ('SETUP: {0,-7} |{1}|' -f $name, $timeline)
    }

    <# RETURN: nothing. Prepares one item, stamped with its tick. #>
    [void] Fire([int]$pseudo_time) {
        $this.item = "item@$pseudo_time"
        Out-Py ('  [t:{0}] {1} prepared {2}' -f $pseudo_time, $this.name, $this.item)
    }

    <# RETURN: nothing. Announces end-of-stream to the consumer. #>
    [void] OnTermination([int]$end_tick) {
        $this.finished = $true
        Out-Py ('  [end:{0}] {1} announced end-of-stream' -f $end_tick, $this.name)
    }
}

#  Fires once, then asks the run to leave (choice 'stop').
class StoppingTrigger : SpeakingTrigger {
    [object] $dispatcher

    <# RETURN: StoppingTrigger 'name' on 'timeline', no dispatcher yet. #>
    StoppingTrigger([string]$name, [string]$timeline) : base($name, $timeline) { $this.dispatcher = $null }

    <# RETURN: nothing. Fires, then asks the dispatcher to stop. #>
    [void] Fire([int]$pseudo_time) {
        ([SpeakingTrigger]$this).Fire($pseudo_time)
        Out-Py '  ... asks the dispatcher to stop'
        $this.dispatcher.Stop()
    }
}

#  Overrides nothing (choice 'abstract').
class BareTrigger : Trigger {
    <# RETURN: BareTrigger 'name' on 'timeline'. #>
    BareTrigger([string]$timeline, [string]$name) : base($timeline, $name) { }
}

<# RETURN: nothing. A dispatcher over 'trigger_list', run to completion. #>
function dispatch([object[]]$trigger_list) { [TriggerDispatcher]::new($trigger_list).Run() }

$schedule = {
    banner 'staggered: A at 0, B at 2, C at 4'
    dispatch @([SpeakingTrigger]::new('A', '1    '),
               [SpeakingTrigger]::new('B', '  1  '),
               [SpeakingTrigger]::new('C', '    1'))

    banner "a SHORT timeline stops contributing; the long one goes on"
    dispatch @([SpeakingTrigger]::new('SHORT', '11'),
               [SpeakingTrigger]::new('LONG',  '111111'))

    banner "the SCHEDULE as built -- '[tick] (priority)name'"
    Out-Py ([TriggerDispatcher]::new(@([SpeakingTrigger]::new('A', '12'),
                                       [SpeakingTrigger]::new('B', '21'))).ToString())
}

$priority = {
    banner 'digits swap between ticks: B leads at 0, A leads at 1'
    dispatch @([SpeakingTrigger]::new('A', '21'),
               [SpeakingTrigger]::new('B', '12'))

    banner '0 is the strongest digit, 9 the weakest'
    dispatch @([SpeakingTrigger]::new('WEAK',   '9'),
               [SpeakingTrigger]::new('STRONG', '0'))
}

$stable = {
    banner 'three triggers, all digit 1 at tick 0'
    dispatch @([SpeakingTrigger]::new('first',  '1'),
               [SpeakingTrigger]::new('second', '1'),
               [SpeakingTrigger]::new('third',  '1'))

    banner 'registered BACKWARDS -- the order follows registration, not the name'
    dispatch @([SpeakingTrigger]::new('third',  '1'),
               [SpeakingTrigger]::new('second', '1'),
               [SpeakingTrigger]::new('first',  '1'))
}

$termination = {
    banner 'end_tick is the LENGTH -- 5 characters, last firing at tick 0'
    dispatch @([SpeakingTrigger]::new('EARLY', '1    '))

    banner 'a trigger that NEVER fires is notified all the same'
    dispatch @([SpeakingTrigger]::new('FIRES',  '1  '),
               [SpeakingTrigger]::new('SILENT', '   '))

    banner 'the LONGEST timeline sets end_tick for everybody'
    dispatch @([SpeakingTrigger]::new('SHORT', '1'),
               [SpeakingTrigger]::new('LONG',  '1      '))

    banner 'a trigger that does not override is simply silent at the end'
    dispatch @([SpeakingTrigger]::new('SPEAKS', '1 '),
               [MuteTrigger]::new('MUTE',       '1 '))
}

$yielding = {
    banner 'producer fires at every tick; consumer waits between them'
    $producer = [ProducingTrigger]::new('PROD', '111')
    #  The consumer as a task: each step takes what is there, then yields
    #  -- Python's 'await asyncio.sleep(0)' -- or ends on end-of-stream.
    $state    = @{ taken = 0 }
    $consume  = {
        while ($true) {
            if ($null -ne $producer.item) {
                $state.taken++
                Out-Py "        consumer took $($producer.item)"
                $producer.item = $null
                continue
            }
            if ($producer.finished) {
                Out-Py "  consumer saw end-of-stream after $($state.taken) item(s)"
                return $false
            }
            return $true
        }
    }.GetNewClosure()
    [AsyncTask]::Gather(@([TriggerDispatcher]::new(@($producer)).Task(), [AsyncTask]::new($consume)))
    Out-Py ''
    Out-Py 'Each item was taken BEFORE the next tick prepared one: the run yields.'
}

$stop = {
    banner 'stop() after the first tick -- ticks 1.. are not walked, the announcement still comes'
    $stopper    = [StoppingTrigger]::new('STOPPER', '1111')
    $bystander  = [SpeakingTrigger]::new('OTHER',   '1111')
    $dispatcher = [TriggerDispatcher]::new(@($stopper, $bystander))
    $stopper.dispatcher = $dispatcher
    $dispatcher.Run()

    Out-Py ''
    Out-Py "end_tick is still the timeline's length, not the tick the run stopped at."
}

$cancel = {
    banner 'cancel() the task carrying run() -- no announcement follows'
    $dispatcher = [TriggerDispatcher]::new(@([SpeakingTrigger]::new('A', '1111111111')))
    $task       = $dispatcher.Task()
    [void]$task.Step()                      # 'await asyncio.sleep(0)': it runs one turn
    [void]$task.Cancel()
    try {
        $task.Await()
    } catch [CancelledError] {
        Out-Py '  run() was cancelled'
    }
    Out-Py ''
    Out-Py "No '[end:..]' line above: the triggers were abandoned, not ended."
}

$edges = {
    banner 'an EMPTY timeline -- end_tick 0'
    dispatch @([SpeakingTrigger]::new('EMPTY', ''))

    banner 'a timeline of BLANKS -- no digit, so nothing fires'
    dispatch @([SpeakingTrigger]::new('BLANK', '    '))

    banner 'NO TRIGGERS at all -- nothing to announce, and no failure'
    dispatch @()
    Out-Py '  (dispatcher ran; nothing was scheduled)'

    banner 'a timeline of blanks beside one that fires'
    dispatch @([SpeakingTrigger]::new('BLANK', '   '),
               [SpeakingTrigger]::new('FIRES', ' 1 '))
}

$abstract = {
    banner "the BASE 'fire' is abstract -- it refuses"
    try {
        dispatch @([BareTrigger]::new('1', 'BARE'))
    } catch [NotImplementedError] {
        Out-Py '  NotImplementedError -- as owed: a trigger must say what it does'
    }

    banner "the BASE 'on_termination' is optional -- it is silent"
    $bare = [BareTrigger]::new('', 'BARE')
    $bare.OnTermination(0)
    Out-Py '  returned quietly; nothing raised, nothing printed'

    banner 'a NAME given is the name kept'
    Out-Py "  name: $([Trigger]::new('1', 'GIVEN').name)"
}

[HwutRunner]::new(@{
    argv       = @($PSCommandPath) + $args
    title      = 'TriggerDispatcher: schedule, priority, and the end of time'
    choice_map = @{
        schedule    = $schedule
        priority    = $priority
        stable      = $stable
        termination = $termination
        yielding    = $yielding
        stop        = $stop
        cancel      = $cancel
        edges       = $edges
        abstract    = $abstract
    }
}).Run()
