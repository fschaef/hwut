WORKFLOW MANAGEMENT
================================================================================

SYNOPSIS

  The user orders an 'artifact': the record of a state of the world to be
  brought about — a file existing, a test executed with verdict, a network
  connection open. The factory decomposes the order into tasks. A task
  requires artifacts (role: resource) and produces artifacts (role:
  product). The factory runs tasks whose resources are present until the
  ordered artifact — the terminal product — is present or proven
  impossible. The user observes and cancels through a single EventTerminal.

STRUCTURE

            Factory
               '--- task_generator (function)
               |--- RecipeDb
               '--- WorkflowManager
                      '--- ArtifactManager
                      '--- DependencyGraph
                      '--- TaskSelector      # decides what runs
                      '--- TaskSupervisor    # runs and watches
                      '--- EventRouter       # user-facing fan-out

SIBLING COMPONENTS

  event    -- Event; EventTerminal (one end of a communication channel,
              carries a '.dispatcher'); EventDispatcher (per-terminal
              subscription: subscribe_on_event / subscribe_on_category /
              subscribe_on_predicate); EventRouter (fan-out hub: source
              terminals in, destination terminals out, per-entry predicate
              selects which destination receives which event; entries
              whose peer goes down are removed automatically);
              EventChannelParameter (ECP) — factories for_async,
              for_thread, for_process, for_remote each produce a pair of
              channel ends; one EventTerminal is built per end. The
              factory choice determines the transport.

  spawner  -- CallableThing; spawn_async / spawn_thread / spawn_process —
              turns a task reference into a running child plus the
              EventTerminal to it.

FACTORY DATA FLOW

                     artifact to be produced
                               |
        .----------.   .----------------.
        | RecipeDb |<->| task_generator |
        '----------'   '----------------'
                               |
                            Workload
                               |
      .--------------------------------------------------.
      |                 WorkflowManager                   |
      |  .-----------------.       .-----------------.    |
      |  | ArtifactManager |       | DependencyGraph |    |
      |  '-----------------'       '-----------------'    |
      |           |                        |              |
      |  .----------------.       .----------------.      |
      |  |  TaskSelector  | ----> | TaskSupervisor | <======> running tasks
      |  '----------------'       '----------------'      |  (one EventTerminal
      |                                    |              |   pair per task)
      |  .---------------------------------------------.  |
      |  |                 EventRouter                 |  |
      |  '---------------------------------------------'  |
      '----------------------------|----------------------'
                                   |
                       EventTerminal (one per order)
                                   |
                                  User


Artifact (frozen dataclass)
--------------------------------------------------------------------------------

    E_Artifact:  type
    dict:        normalized_description    # canonical, by construction
    int:         artifact_id               # assigned by ArtifactManager

  An Artifact is the workflow's record of a milestone, never the milestone
  itself. The real thing — file, socket, event — lives outside the
  manager; the Artifact only tracks it. Identity is the artifact_id;
  "same artifact?" is answered by comparing ids.

  Roles an Artifact takes: resource (required by a task), product
  (produced by a task), terminal product (ordered by the user). Internal
  construct; the user never sees Artifacts, only order functions and
  Events.

  Lifecycle states, tracked per artifact:

            .------------------<-----------------------.
            |                                           |
         (ABSENT) --> (IN_PRODUCTION) --> (PRESENT) ----'
            |               |
            '--------> (IMPOSSIBLE)


ArtifactHandling (per E_Artifact value)
--------------------------------------------------------------------------------

  Translates between three representations of the same artifact:

    raw description --canonicalise--> normalized description --resolve--> local handle
    (recipe input)                    (workflow-internal id)              (task input)

    .canonicalise(description, conventions) -> normalized_description
        Strips locally-varying surface detail. Two descriptions of the
        same artifact yield the same dict under the same conventions.
        'conventions' carries workflow-wide context (test_root, ...).
        Description values must be hashable; nested mutables are
        normalised here, before the dict reaches the ArtifactManager.

    .resolve(normalized_description, local_context) -> local handle
        Joins the canonical form with execution-host context
        (host_root, user, machine_id, ...). Returns the type the task
        consumes: pathlib path, connected socket, process handle.

  The two operations are duals: 

  -- canonicalise() at workload construction, on the recipe side; 
     => distinct description indepedent of locality

  -- resolve() at execution time, on the launcher side.
     => concrete description meaningful in local context.

  Handlers are registered per E_Artifact in an ArtifactHandlingRegistry.
  The WorkflowManager owns one registry ('.artifact_handling_registry');
  all tasks of one artifact type share one handler.

  Worked example: FILEPATH. Canonical form is the path relative to
  conventions['test_root']; resolve joins it onto
  local_context['host_root'].


ArtifactManager
--------------------------------------------------------------------------------

  Single point of artifact identity. Every Artifact instance is minted
  here; every artifact_id originates here. All queries about current
  artifact information go here.

    artifact_id --> Artifact:                 db
    artifact_id --> E_ArtifactState:          state_db
    artifact_id --> (time, E_ArtifactState):  history_db

    .generate(type, normalized_description) -> Artifact
        Expects a normalized_description. Mints the placeholder record,
        not the thing itself. Repeated calls with the same
        (type, normalized_description) return the same instance.

  State changes enter through the WorkflowManager's artifact-update path
  (below). The goal state: every terminal product PRESENT.


Dependency expression
--------------------------------------------------------------------------------

  A boolean expression over artifact availability. Each leaf tests one
  artifact. Evaluation uses Kleene's strong three-valued logic with
  UNKNOWN: 'true and unknown = unknown', 'false and unknown = false'.
  An artifact-state change updates the leaves it touches; a leaf whose
  value changes informs its parent node, upward until the root. The root
  value tells: condition met, not met, or never satisfiable.


TaskDescription (dataclass)
--------------------------------------------------------------------------------

  Describes and parameterises a task; it is not the running task.

    int             .task_id
    str             .task_type_name            # 'C-Compiler', etc.
    dict            .parameters                # passed to the launcher
    dependency_expr .resource_dependency_expr  # resources required to run
    list(Artifact)  .product_list              # products of a run


Workload (dataclass)
--------------------------------------------------------------------------------

  The interpretation of one user order in factory terms.

    int:                    workload_id
    Artifact:               final_product   # the terminal product
    list(TaskDescription):  tasks
    EventTerminal:          wfm_terminal    # WFM end of the user channel

  The Artifact describes the product; whether the associated reality is
  present is read from the ArtifactManager. 'tasks' holds the task
  descriptions of all alternative solutions flattened; the alternative
  structure is carried by shared products in the DependencyGraph.
  'bind_user(wfm_terminal)' records the WFM-side channel end on the
  workload.


RecipeKnower
--------------------------------------------------------------------------------

  One knower per target artifact type; the type is implied by the
  registration key and not passed as an argument.

    .get_tasks(dict: target_description) -> list of list of TaskDescription
        Each inner list is one alternative solution that produces the
        target.
    .canonicalise_description(dict: target_description) -> dict
        Delegates to the registered ArtifactHandling.canonicalise() of
        the target type; recipe-specific normalisation may be layered on
        top. Output is the identity basis handed to
        ArtifactManager.generate().
    .check(dict: target_description) -> verdict
        Validates description completeness before task generation;
        verdict handling is the caller's.
    .documentation() -> str
        States what is done with a target_description.


RecipeDb
--------------------------------------------------------------------------------

  map: E_Artifact --> RecipeKnower

    .register(artifact_type, knower)
    .lookup(target_type, dict: target_description) -> recipe
        knower = map[target_type]
        return knower.get_tasks(target_description)
        # recipe: TaskDescriptions with their resources and products


DependencyGraph
--------------------------------------------------------------------------------

  Maintains the launchability of all tasks from the dependency
  expressions and the products at hand.

    artifact_id --> set(DependencyExprLeaf):  dependency_leaf_db
    artifact_id --> set(TaskDescription):     tasks_by_product_db
    task_id     --> set(artifact_id):         product_by_task_db
    task_id     --> E_Runnability:            runnability_db

  Several tasks may produce the same artifact (tasks_by_product_db);
  any one of them producing it satisfies the dependents — this carries
  the recipe alternatives.

    .register(workload)
        Integrates the workload's tasks; merges tasks already known;
        records alternatives via shared products.
    .evaluate() -> runnable tasks, impossible tasks

  Runnability states:

    E_Runnability.NOT_YET  -- dependencies not yet met
    E_Runnability.NOW      -- dependencies met, task may run
    E_Runnability.NEVER    -- dependencies unsatisfiable with the tasks
                              at hand

  From the NEVER set the graph also derives the artifacts that have
  become impossible.


TaskSelector (base class)
--------------------------------------------------------------------------------

  Decides; runs nothing.

    .pick(runnable_tasks: set) -> list[task_id]

  Constructed with access to all WorkflowManager components. The derived
  class implements the strategy: FIFO, most-blocking-first, fail-fast,
  CRM. Picked task ids are handed to the TaskSupervisor.


TaskSupervisor
--------------------------------------------------------------------------------

  Runs and watches; decides nothing. The boundary between synchronous
  workflow management and asynchronous task execution. Per running task
  it holds a TaskState:

    E_TaskRunningState   running_state
    TaskDescription      description
    asyncio.Task         task
    asyncio.Event        termination_signal
    EventTerminal        task_terminal          # supervisor-side peer
    set(workload_id)     workloads_concerned    # -> user terminals

  Two distinct mechanisms on a TaskState:
    termination_signal.set()  asks the running task to cease work.
    task_terminal '.stop()'   tears down the communication channel; done
                              when the TaskState is retired, after the
                              task has returned.

    (PENDING)
       |
    launched
       |
    (RUNNING) --- returns ------------------> (DONE)
       '------- fails to operate -----------> (FAILED)
       '------- abort requested ------------> (ZOMBIE)
                                                 |
                                              returns
                                                 |
                                             (CANCELLED)

  Operations:

    .register_launcher(task_type_name, launcher)
    .register_task(task_description, subscribers: set[workload_id])
    .subscribe(task_id, workload_id)
    .unsubscribe(task_id, workload_id)
        subscriber set empty and task RUNNING -> .abort_task(task_id)

    .launch(task_id)
        evt                = asyncio.Event()
        task_ecp, sup_ecp  = EventChannelParameter.for_async()
        awaitable          = launcher_for(td.task_type_name)(
                                 td.parameters, evt, task_ecp)
        atask              = asyncio.create_task(awaitable)
        task_terminal      = EventTerminal(sup_ecp)
        # store evt, atask, task_terminal; state -> RUNNING
        # task_terminal feeds the WorkflowManager's artifact-update path

    .abort_task(task_id)
        termination_signal[task_id].set()
        state -> ZOMBIE
        # completion of the asyncio.Task confirms; observed on the
        # artifact-update path

  Launcher contract — the launcher is identified by task_type_name and
  receives (parameters, termination_signal, task_ecp). It must:

    -- honour the termination_signal: initiate whatever ends the task's
       processing and return to the awaiting TaskSupervisor;

    -- report over the EventTerminal built from task_ecp: Events of
       category WORKFLOW — EventTaskProgress, EventTaskDone,
       EventTaskFailed.

  The ECP factory chosen inside the launcher (for_async, for_thread,
  for_process, for_remote) sets the transport; launchers employ the
  spawner component to start the child. Above the launcher, only
  EventTerminals and Events are visible.


WorkflowManager
--------------------------------------------------------------------------------

    .register(workload)
    .cancel(workload_id)
    .handle_artifact_update(event)
    .artifact_handling_registry
    .router                         # the EventRouter

  .register(workload):

    -- workload artifacts          --> ArtifactManager
    -- workload task descriptions  --> DependencyGraph
    -- workload.wfm_terminal       --> EventRouter entry, predicate
                                       matching this workload's events
    -- initial DependencyGraph.evaluate(); launch decision follows
       immediately. A terminal product already PRESENT sends
       EventTargetAvailable to the user at once.

  .handle_artifact_update(event) — the body of the artifact-update path;
  driven by Events arriving on the supervisor-side task terminals:

    EventTaskDone / EventTaskFailed
        --> artifact state update --> DependencyGraph.evaluate()
        --> runnable tasks --> TaskSelector.pick() --> TaskSupervisor
        --> impossible artifacts --> ArtifactManager
        --> order-level Events through the EventRouter:
            EventTargetAvailable / EventTargetImpossible /
            EventTargetCancelled


Order flow (task_generator)
--------------------------------------------------------------------------------

  The user calls '.order(target_type, dict: description)' on the factory.

    recipe   = RecipeDb.lookup(target_type, description)
    workload = <assemble Workload from recipe>

    # one ECP pair: user end and WFM end
    user_ecp, wfm_ecp = EventChannelParameter.for_async()
    user_terminal     = EventTerminal(user_ecp)
    wfm_terminal      = EventTerminal(wfm_ecp)

    workload.bind_user(wfm_terminal)
    workflow_manager.register(workload)
    return user_terminal

  The returned user_terminal is a plain EventTerminal — the single
  object through which the user observes and controls the order:

    -- reports: the terminal delivers Events; the user subscribes
       handlers on '.dispatcher' (subscribe_on_event /
       subscribe_on_category / subscribe_on_predicate);

    -- cancellation: '.stop()' tears the terminal down; the
       WorkflowManager reacts to the peer going down (below).


Report path
--------------------------------------------------------------------------------

  task event --> supervisor task_terminal --> handle_artifact_update
             --> EventRouter --> user terminal(s)

  Order-level Events originated by the WorkflowManager itself travel the
  same EventRouter.


Cancellation
--------------------------------------------------------------------------------

  user '.stop()' --> peer-down callback on wfm_terminal
                 --> WorkflowManager:

    for task in workload.tasks:
        TaskSupervisor.unsubscribe(task.task_id, workload_id)
        # empty subscriber set aborts the task (see TaskSupervisor)

  The EventRouter removes the dead entry through its peer-down
  auto-removal. No closing Event is sent: the destination terminal no
  longer exists.

  'termination_signal' on a TaskState aborts one running task; user
  cancellation reaches it only through the empty-subscriber rule. The
  two are separate mechanisms.
