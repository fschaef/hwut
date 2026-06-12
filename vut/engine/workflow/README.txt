WORKFLOW MANAGEMENT:

MOTIVATION

  This component provides general workflow management. The original motivation
  was to be able automatically coordinate and trace the generation and
  execution of HWUT unit tests. The goal was to make the complete process part
  of the test, thus errors in the construction and code generation are part of
  the failure. The result is a unit test framework that is stable under
  unstable test applications.

SYNOPSIS

  The user orders an 'Artifact', i.e. an description of a state of the world he
  wants to be real. This can be a confirmation that a file exists, that a test
  has been executed and its verdict, it may be a network connection being opened
  or any other testimony about something that might be useful (or not).

  The workflow manager breaks down the overall task to bring about the artifact
  into sub tasks and their intermediate dependencies, called 'resources'. Based
  on the knowledge of required resources of tasks and the products that they 
  produce, it may streamline the tasks that are necessary to accomplished the
  ordered artifact.

STRUCTURE:

    Factory
       '--- task_generator(function)
       |--- RecipeDb
       '--- WorkflowManager
             '--- DependencyGraph 
             '--- ArtifactManager      
             '--- TaskSelector          # decides what to run
             '--- TaskSupervisor        # supervises running tasks
             '--- EventRouter           # user-facing fan-out

Sibling Components: 

     event     - EventTerminal, EventDispatcher, EventRouter,
                 EventChannelParameter (user- and task-facing
                 communication).

     spawner   - CallableThing, spawn_async / spawn_thread /
                 spawn_process (turns a task reference into a running
                 child with an EventTerminal to it).

USER:

    The user, simply calls the '.order(target, dict: description)' function
    which tells the 'factory' what he wants. 

                FACTORY
                .-----------
      User: --->| .order_<name>(dict: description)
                |
            <---| EventTerminal delivers Event-s
                '-------------

    Immediately, as a return value the user receives a plain 'EventTerminal'.
    It is the single object through which the user observes and controls the
    order:

       -- it delivers Event-s about progress and termination. The user
          subscribes handlers on its '.dispatcher' (subscribe_on_event,
          subscribe_on_category, subscribe_on_predicate).

       -- it cancels the order. Calling '.stop()' tears the terminal down;
          the workflow manager sees the peer go down and unsubscribes the
          user from the order's tasks (see "Cancellation" below).

    There is no separate report queue and no separate termination signal.
    The terminal is the report channel and the control handle in one.

FACTORY:

    The following diagram shows the internal workings of the factory.
    User- and task-facing communication is built entirely on the event
    component (EventTerminal, EventDispatcher, EventRouter); running
    children are produced by the spawner component. 

                   artifact to be produced
                               |
   .----------.        .----------------.
   | RecipeDb |<------>|  TaskGenerator |
   '----------'        '----------------'
                               |
                           Workload
                               |
         .----------------------------------------------.
         |               WorkflowManager                |
         | .-----------------.      .-----------------. |
         | | DependencyGraph |      | ArtifactManager | |
         | '-----------------'      '-----------------' |
         |         |:|                    |:|           |
         | .--------------------.  .-----------------.  |
         | |   TaskSelector     |->|  TaskSupervisor |<====> Running Tasks
         | | (decides what runs)|  | (runs/supervises|  |  (one EventTerminal
         | '--------------------'  '-----------------'  |   pair per task,
         |                      |                       |   via the spawner)
         | .------------------------------------------. |
         | |               EventRouter                | |
         | '------------------------------------------' |
         '---------------------|------------------------'
                               |
                       EventTerminal (one per order)
                               |
                              User

    The EventRouter is the single fan-out hub. Task-side Terminals (peer of a
    running Task) are its event SOURCES; user-side EventTerminal-s are its
    DESTINATIONS. A router entry's predicate selects which user receives which
    event - typically by workload id or task id. 

Artifact(frozen dataclass)
--------------------------

    E_Artifact: type
    dict:       normalized_description  # canonical, by construction
    int:        artifact_id             # assigned by ArtifactManager

    An artifact may appear in the role of a 'resource' of a task that is required
    for operation. It may appear in the role of a 'product' that is produced by
    a task. And, it may appear as a 'terminal product' that is required by order
    of the user.

    Artifacts are used internally. The user is not aware of this construct.
    Instead it communicated with the factory via 'order' functions and receives
    updates about the processing and the final status.

    An Artifact is the workflow's record of a milestone, never the milestone
    itself. The real thing - file, socket, event - lives outside the manager;
    the Artifact only tracks it.

    Based on the 'normalized_description', an artifact id is assigned by
    the container of artifacts: the ArtifactManager.

ArtifactHandling (per artifact type)
------------------------------------

An ArtifactHandling class translates descriptions of artifacts into
normalized (globally distinct) descriptions. On the other hand it
translates normalized descriptions back into descriptions which are
meaningful for the local task execution.

   .canonicalise(artifact_description, conventions) -> normalized_description

   .resolve(normalized_description, local_context) -> local_handle
       Used by Task launchers at execution time. Reads the canonical
       form, applies the local execution context, returns a real
       handle (pathlib.Path, socket, etc.).

ArtifactHandling classes need to be registered in the WorkflowManager by
artifact id. This way, they become available to the RecipeKnower and the Task
launcher.

RecipeKnower: takes the user's artifact description and translates it into a
   normalized_description that helps to identify artifacts in the 'global' scope
   of the workflow manager. For that it uses the 'canonicalise(...)' function.

Task: translates the 'normalized_description' into a description
   that is meaningful for the local executor task.

Example: 'file path' being relative, absolute, etc.

The 'normalized_description' is later passed to the ArtifactManager, which is
then able to associate it with a unique artifact id.

task_generator(function)
------------------------

The user's order is handled immediately by the 'task_generator' function. That
function interacts with the 'RecipeDb' in order to produce a set of tasks and
their dependencies to accomplish the required order.

     workload = RecipeDb.lookup(E_Artifact: target_type, 
                                dict:       target_description)

     # One EventTerminal pair: the user end and the WFM (router) end.
     user_ecp, wfm_ecp = EventChannelParameter.for_async()
     user_terminal = WorkflowEventTerminal(user_ecp)
     wfm_terminal  = EventTerminal(wfm_ecp)

     workload.bind_user(wfm_terminal)
     workflow_manager.register(workload)
     return user_terminal

The 'wfm_terminal' is added as an entry to the WorkflowManager's EventRouter,
under a predicate that matches the events of this workload's tasks. The
'user_terminal' (a WorkflowEventTerminal) is what the user receives.

Note, that the workflow manager initiates a 'task launch decision making'
directly after setting a workload. In case that a terminal artifact, i.e. the
thing the user wants, is already available, the user_terminal may immediately
receive an 'EventTargetAvailable'.

WorkflowManager
---------------

    .register(workload)
    .cancel(workload_id)            # invoked when a user terminal stops
    .handle_artifact_update(event)  # the central report loop body
    .artifact_handling_db
    .router                         # the EventRouter (user-facing fan-out)

The 'workflow_manager.register(workload)' sets up the internal components:

    -- add artifacts to the internal ArtifactManager
    -- add task descriptions to the DependencyGraph
    -- add the workload's 'wfm_terminal' as an entry on the EventRouter,
       under a predicate matching this workload's events
    -- initial dependency graph evaluation

The artifact_handling_db provides ArtifactHandling classes for artifacts
to synchronize the 'normalized_description' of artifacts and their localized
descriptions.

RecipeDb
--------

Supports the generation of 'workloads' which are required to produce an
artifact of some type. The 'lookup' function finds a 'knower' that can provide
a set of tasks together with their dependencies which are required to achieve
the requested target.

   map: artifact type --> recipe knower of how to build it
   .lookup(target_type, dict: target_description)
       get knower <-- by target artifact.type
       recipe = knower(target_type, target_description)
       return recipe # containing TaskDescriptions, resources, and products
   .register(artifact type, knower)
       register knower for artifact type

RecipeKnower
------------

A recipe knower determines a set of tasks given a dictionary of
'target_description'. That is, the knower expresses a procedure to produce a
'target' in terms of operations (tasks) that rely on
resources/dependencies/inputs and produce products/targets/outputs. Notably,
the 'RecipeKnower' is identified by the 'target_type', so it does not receive
the type as an argument.

   .get_tasks(dict: target_description) 
    --> list of list of TaskDescription
   .documentation()
      return string that tells what is done with 'target_description'
   .check(dict: target_description)
   .canonicalize_description(dict: target_description)

The '.get_tasks()' may report multiple alternative approaches to generate the
target. Each list in the 'list of lists of TaskDescription' is one of those
solutions.

The '.canonicalize_description()' takes the 'loose' description that the user
provides and canonicalizes it. That is, it ensures that two artifacts which are
the same with respect to the recipe have the same 'normalized_description'. It
is the bases for identity detection. A simple example is the generation of a
file that is accessible from different machines. 


Workload(dataclass)
-------------------

A workload is the interpretation of the user's order in terms of what the
factory has to do. It informs about the final product, that the user ordered,
the set of tasks that need to operate, and how the users communicates with
the workflow manager.

     Artifact:                final_product 
     list(TaskDescription):   tasks
     EventTerminal:           wfm_terminal   # WFM end of the user channel

Notably, the 'Artifact' only describes the product. The fact that the
associated 'reality' is present is accessible via the ArtifactManager.

The 'wfm_terminal' is the workflow-manager end of the EventTerminal pair whose
other end - a plain EventTerminal - was returned to the user. It is registered
on the WorkflowManager's EventRouter; 'bind_user(wfm_terminal)' records it on
the workload.

The User Terminal
-----------------

The object the user receives in return for an order is a plain EventTerminal.
There is no workflow-specific terminal subclass and no separate UserComHandle.
The earlier design had a handle carrying a report queue plus a termination
signal; the bare terminal subsumes both:

   -- report channel  -> the terminal delivers Event-s; the user
                          subscribes handlers on '.dispatcher'
                          (subscribe_on_event / _category / _predicate).

   -- cancellation     -> '.stop()'. It tears the user terminal down.
                          See "Cancellation" - the WorkflowManager reacts
                          to the peer going down; the user side needs no
                          extra method, hence no subclass.

TaskDescription(dataclass)
--------------------------

A task description is not equal to the running class. It only describes and
parameterizes a task. That is, it describes what dependencies the task has in
order to operate. This is expressed in a boolean 'dependency expression' that
checks on availability of artifacts. It also maintains a list of
targets/products that the task-to-be-run is supposed to produce.

     int            .task_id
     str            .task_type_name           # 'C-Compiler', etc.
     dict           .parameters               # additional info to be passed ot Task constructor
     bool_expr      .resource_dependency_expr # Artifact-s that must be present for operation
     list(Artifact) .product_list             # Artifact-s that are produced by task

The Workload is then passed to the WorkflowManager, who fills the ArtifactManager
and the DependencyGraph.

     DependencyGraph <-- Task Descriptions (resources, products)

ArtifactManager
---------------

Mints, registers, and tracks the state of all artifacts in the workflow. It is
the single point of artifact identity: every Artifact instance is created here,
and every artifact_id originates here. Anything to be asked about current
information on artifacts is to be asked from here.

     artifact_id --> Artifact:                db
     artifact id --> E_ArtifactState:         state_db
     artifact id --> (time, E_ArtifactState): history_db

     .make(type, normalized_description) -> Artifact
        excepts a 'normalized_description' and produces Artifact,
        which is a new one, if Artifact did not exist before.

Artifact states: ABSENT, IN_PRODUCTION, PRESENT, IMPOSSIBLE

            .------------------<-----------------------.
            |                                          |
         (ABSENT) --> (IN_PRODUCTION) --> (PRESENT) ---'
            |               |
            '--------> (IMPOSSIBLE)

     The goal is to have the Artifacts requested by user orders in
     state 'PRESENT'. Only, those tasks can start working where all
     resources (resource_dependency_expr()) are valid.

DependencyGraph
---------------

Maintains the launchability status of all tasks. It allows to determine
what tasks are ready to run and what tasks are impossible. For this
it reflects on the dependency condition expressions of the tasks at
hand and the products that they may produce.

     artifact id --> set(DependencyExprLeaf):  dependency_leaf_db
     artifact id --> set(TaskDescription):     tasks_by_product_db
     task id --> set(artifact id):             product_by_task_db
     task id --> E_Runnability:                runnability_db

     .register(workload)
         integrates tasks of workload into dependency, possibly merges
         and defines alternatives.
     .evaluate()
         => runnable tasks, impossible tasks

A task description is associated with one of three states:

 E_Runnability.NOT_YET -- dependencies not yet met 
 E_Runnability.NOW     -- dependencies met, task may run
 E_Runnability.NEVER   -- dependencies can never be met by tasks at
                          hand, task may never operate

When a status of an artifact changes, the leafs of boolean condition
expressions where those play a role are informed. If the correspondent boolean
expression changes, it informs the parent node, etc. This way a change of
conditions propagates through the condition expression until it reaches the
root where it determines whether the condition is met, not met, or can never be
met.

The condition expression work on a Kleene's strong three-valued logic, that
includes 'unknown'. E.g. 'true and unknown = unknown', 'false and unknown =
false'.

Task Handling: TaskSelector and TaskSupervisor
----------------------------------------------

Running tasks is split into two responsibilities, deliberately kept in
separate components:

   TaskSelector   - DECIDES. Given the set of runnable tasks (from the
                    DependencyGraph), it picks which ones to run.
   TaskSupervisor - SUPERVISES. It runs the picked tasks, holds a
                    'TaskState' per running task, owns the task-side
                    EventTerminal peers, relays their events, and
                    aborts tasks on request.

The TaskSelector decides; it does not run anything. The TaskSupervisor
runs and watches; it does not decide what to run. The Selector hands
picked task ids to the Supervisor.

TaskSelector(base class)
------------------------

Takes the set of runnable tasks and determines which of them is to be
launched.

   .pick(runnable_tasks: set) -> list[task_id]

Upon construction, the TaskSelector receives access to all components of
the workflow manager in order to make informed decisions. The derived
class implements a selection strategy such as FIFO, most-blocking first,
fail-fast, or CRM.

TaskSupervisor
--------------

The TaskSupervisor is the interface between the synchronous workflow
management and the asynchronous Task execution. It maintains a 'TaskState'
object for each running task.

Each running task communicates with the TaskSupervisor over an
EventTerminal pair: the task holds one end, the TaskSupervisor the peer.
Task progress and result Event-s arrive on the peer terminal's
'.dispatcher'. The TaskSupervisor obtains a running task plus its peer
terminal from the spawner component - one of 'spawn_async',
'spawn_thread', 'spawn_process' - so the transport flavour is the
spawner's concern, not the Supervisor's. There is no task report queue.

TaskState
----------

   E_TaskRunningState   running_state
   TaskDescription      description
   asyncio.Task         task
   asyncio.Event        termination_signal
   EventTerminal        task_terminal         (TaskManager-side peer)
   set(workload_id)     workloads_concerned   (-> user terminals)

The 'termination_signal' is the task-abort mechanism and is distinct from
EventTerminal lifecycle: '.stop()' on a terminal tears down a communication
channel, whereas 'termination_signal.set()' asks a running task to cease
work. A task is aborted via the signal; its terminal is closed afterwards
when the TaskState is retired.

E_TaskRunningState:

       (PENDING) 
          | 
       launched
          |
       (RUNNING) -- terminates by itself --> (DONE)
          '------ fails to operate --------> (FAILED)
          '------ cancellation ------------> (ZOMBIE)
                                                |
                                       terminates by itself 
                                                |
                                           (CANCELLED)

Operations:

   .register_launcher(task_type_name, launcher)
   .register_task(task_description, subscribers: set[workload_id])
   .subscribe(task_id, workload_id)
   .unsubscribe(task_id, workload_id)
       if subscribers becomes empty and task is RUNNING -> abort_task

   .launch(task_id)
       evt = asyncio.Event()
       # one EventTerminal pair: task end and TaskManager end
       task_ecp, mgr_ecp = EventChannelParameter.for_async()
       awaitable = launcher_for(td.task_type_name)(
                       td.parameters, evt, task_ecp)
       atask = asyncio.create_task(awaitable)
       mgr_terminal = EventTerminal(mgr_ecp)
       # mgr_terminal feeds the WorkflowManager's report loop
       store evt, atask, mgr_terminal, set state RUNNING

   .abort_task(task_id)
       termination_signal[task_id].set()
       state -> ZOMBIE
       # confirmation arrives via the report loop noticing the
       # asyncio.Task has completed

Launcher contract:

The task launcher is identified by the task_type as given in the task
description. The TaskManager is agnostic of execution context that the launched
task applies internally (sync, in-thread, subprocess, remote). However, it
must:

     - honor the 'termination_signal' (asyncio.Event):
       The task must initiate anything that terminates the processing
       of the task and return to the 'await'-ing TaskManager (function return).

     - report via its EventTerminal about events related to its operation.
       The launcher builds an EventTerminal from the EventChannelParameter
       handed to it and sends Event-s of category WORKFLOW - typically
       EventTaskProgress, EventTaskDone, EventTaskFailed - over it.

The choice of EventChannelParameter factory (for_async, for_thread,
for_process, for_remote) is what makes a launcher in-thread, subprocess, or
remote. The TaskManager and the WorkflowManager see only EventTerminal-s and
Event-s; the transport is invisible above the launcher.

User Interaction Handling
-------------------------

Report path

The WorkflowManager receives Event-s from running tasks on the
TaskSupervisor-side EventTerminal-s, and decides if and how to inform the
concerned users. Informing a user means routing an Event to that user's
WorkflowEventTerminal through the EventRouter: a router entry's predicate
matches the events of the workloads the user subscribed to.

   task ev. --> TaskSupervisor terminal --> EventRouter --> user terminal(s)

The WorkflowManager itself also originates Event-s about the order as a
whole - EventTargetAvailable, EventTargetImpossible, EventTargetCancelled -
and publishes them through the same EventRouter.

Cancellation

The user cancels an order by calling '.stop()' on the user EventTerminal.
There is no separate termination signal at the user boundary. The
WorkflowManager registered a peer-down callback on the WFM-side terminal
when the workload was registered; '.stop()' makes that callback fire, and
the WorkflowManager then:

   remove the workload's user terminal from (
       subscribers of each task in workload.tasks
   )
   abort_task(
       each task in workload.tasks where subscribers = empty
   )

The EventRouter removes the now-dead entry automatically (its own peer-down
auto-removal). Because the user terminal is already gone, no closing Event
is sent to it; '.stop()' was the user's own action and needs no echo.

Note - 'termination_signal' on TaskState is a different mechanism: it aborts
one running task. User cancellation may, via the empty-subscriber rule
above, lead to 'termination_signal.set()' on some tasks, but the two are not
the same signal.

Artifact Update
---------------

Task Event-s carry information about artifact production. An EventTaskDone /
EventTaskFailed delivered to the WorkflowManager's report loop is turned
into an artifact-state update and fed directly into the DependencyGraph.

   Artifact Update ---> DependencyGraph ---> Runnable, Unrunnable Tasks

Based on its knowledge of unrunnable tasks, the DependencyGraph may also
determine the set of impossible artifacts. Then, the artifact db is
updated

   Artifact Update + Impossible Artifacts ---> ArtifactManager

Depending on the changes to the ArtifactManager the user may be also
informed - by publishing the corresponding WORKFLOW Event through the
EventRouter.
