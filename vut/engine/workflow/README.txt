WORKFLOW MANAGEMENT:

MOTIVATION

  This component provides general workflow management. The original motivation
  was to be able automatically coordinate and trace the generation and
  execution of HWUT unit tests. The goal was to make the complete process part
  of the test, thus errors in the contruction and code generation are part of
  the failure. The result is a unit test framework that is stable under
  unstable test applications.

SYNOPSIS

  The user orders an 'Artifact', i.e. an description of a state of the world he
  wants to be real. This can be a confirmation that a file exists, that a test
  has been executed and its verdict, it may be a network connection being opened
  or any other testimony about something that might be useful (or not).

  The worflow manager breaks down the overall task to bring about the artifact
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
                     '--- ArtifactDb      
                     '--- TaskManager     

USER:

    The user, simply calls the '.order(target, dict: description)' function
    which tells the 'factory' what he wants. 

                FACTORY
                .-----------
      User: --->| .order_<name>(dict: description)
                |
            <---| report queue yields (event id, dict: description)
                '-------------

    Immediately, as a return value the user receives a 'handle' that contains
    a 'termination_signal' that he can set in order to cancel the order. Also,
    the handle contains a 'report_queue' by means of which he receives
    information about the progress and the termination of the order.

FACTORY:

    The following diagram shows the internal workings of the factory. 

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
         | .-----------------.           .------------. |
         | | DependencyGraph |           | ArtifactDb | |
         | '-----------------'           '------------' |
         |         |:|                         |:|      |
         | .------------------------------------------. |
         | |               TaskManager                |<========> Running Tasks
         | '------------------------------------------' |  
         |                                              |
         '----------------------------------------------'       
                               |   
                            report 
                     progress & termination

Artifact:
---------

    E_Artifact: type
    dict:       description
    int:        artifact_id
    dict:       environment

    An artifact may appear in the role of a 'resource' of a task that is required
    for operation. It may appear in the role of a 'product' that is produced by
    a task. And, it may appear as a 'terminal product' that is required by order
    of the user.

    Artifacts are used internally. The user is not aware of this construct.
    Instead it communicated with the factory via 'order' functions and receives
    updates about the processing and the final status.

    Note:  artifact_id   <---> (type, environment, description) 

    That is, file names etc. must be specified in a globally consistent 
    manner. This consistency needs to be accomplished by the 'TaskGenerator'.

    An Artifact is the workflow's record of a milestone, never the milestone
    itself. The real thing - file, socket, event - lives outside the manager;
    the Artifact only tracks it.

    The '.environment' helps in defining the meaning of the description. 
    (may be this is dropped later). It may help to find globally unique
    representations.

task_generator(function)
------------------------

The user's order is handled immediately by the 'task_generator' function. That
function interacts with the 'RecipeDb' in order to produce a set of tasks and
their depedencies to accomplish the required order.

     workload = RecipeDb.lookup(target, circumstances)
     user_com = UserComHandle(user_report_queue, termination_signal)
     workload.bind_user(user_com)
     workflow_manager.register(workload)
     return user_com

Note, that the workflow manager initiates a 'task launch decision making'
directly after setting a workload. In case that a terminal artifact, i.e. the
thing the user wants, is already available, the report queue may immediately
respond with 'DONE'.

The 'workflow_manager.register(workload)' sets up the internal components:

    -- add artifacts to the internal ArtifactDb
    -- add task descriptions to the DependencyGraph
    -- initial dependency graph evaluation

RecipeDb
--------

Supports the generation of 'workloads' which are required to produce an
artifact of some type. The 'lookup' function finds a 'knower' that can provide
a set of tasks together with their dependencies which are required to achieve
the requested target.

   map: artifact type --> recipe knower of how to build it
   .lookup(target, dict: circumstances)
       get knower <-- by target artifact.type
       recipe = knower(target, circumstances)
       return recipe # containing TaskDescriptions, resources, and products
   .register(artifact type, knower)
       register knower for artifact type

RecipeKnower
------------

A recipe knower determines a set of tasks given a dictionary of
'circumstances'. That is, the knower expresses a procedure to produce a
'target' in terms of operations (tasks) that rely on
resources/dependencies/inputs and produce products/targets/outputs.

   .get_tasks(target, dict: circumstances) --> list of list of TaskDescription
   .documentation()
      return string that tells what is done with 'dict circumstances'
   .check(dict: circumstances)

The '.get_tasks()' may report multiple alternative approaches to generate the
target. Each list in the 'list of lists of TaskDescription' is on of those
solutions.

Workload(dataclass)
-------------------

A workload is the interpretation of the user's order in terms of what the
factory has to do. It informs about the final product, that the user ordered,
the set of tasks that need to operate, and how the users communicates with
the workflow manager.

     Artifact:                final_product 
     list(TaskDescription):   tasks
     UserComHandle:           user_com

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

The Workload is then passed to the WorkflowManager, who fills the ArtifactDb
and the DependencyGraph.

     DependencyGraph <-- Task Descriptions (resources, products)

ArtifactDb
----------

Maintains the state and relations of artifacts. Anything to be asked about
current information on artifacts is to be asked from here.

     artifact_id --> Artifact:                db
     artifact id --> E_ArtifactState:         state_db
     artifact id --> set(Workload):           workload_concerned_db
     artifact id --> (time, E_ArtifactState): history_db

Artifact states: ABSENT, IN_PRODUCTION, PRESENT, IMPOSSIBLE

            .---------------<----------------------.
            |                                      |
          ABSENT --> IN_PRODUCTION --> PRESENT ----'
            |             |
            '------> IMPOSSIBLE

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
     task id --> E_Runnability:                 runability_db

     .register(workload)
         integrates tasks of workload into dependency, possibly merges
         and defines alternatives.
     .evaluate()
         => runable tasks, impossible tasks

A task description is associated with one of three states:

 E_Runnability.NOT_YET -- dependencies not yet met 
 E_Runnability.NOW     -- dependencies met, task may run
 E_Runnability.NEVER   -- dependencies can never be met by tasks at
                          hand, task may never operate

When a status of an artifact changes, the leafs of booleand condition
expressions where those play a role are informed. If the correspondent boolean
expression changes, it informs the parent node, etc. This way a change of
conditions mitigates throught the condition expression until it the root where
it determines whether the condition is met, not met, or can never be met.

The condition expression work on a Kleene's strong three-valued logic, that
includes 'unknown'. E.g. 'true and unknown = unknown', 'false and unknown =
false'.

TaskManager
-----------

The TaskManager runs and terminates tasks. It maintains internally a scheduler
that decides what tasks to be run from the list of runable tasks. It is the
only component that crosses the sync/async boundary: it accepts synchronous
orders from the WorkflowManager and converts them into asyncio.Task lifecycles.

State per registered task:

   task_id         -> TaskDescription
   task_id         -> asyncio.Task         # the awaitable, "the running task"
   task_id         -> asyncio.Event        # termination signal
   task_id         -> E_TaskState
   task_id         -> set(user_queue)      # subscribers
   task_id         -> set(workload_id)     # interested workloads
   task_type_name  -> launcher             # factory map

Task lifecycle:

   PENDING -> RUNNING -- terminates by itself --> DONE
                 '------ fails to operate ------> FAILED
                 '------ cancellation ----------> ZOMBIE --.
                 .-----------------------------------------'
                 '------ terminates by itself --> CANCELLED   

Operations:

   .register_launcher(task_type_name, launcher)
   .register_task(task_description, subscribers)
   .subscribe(task_id, user_queue)
   .unsubscribe(task_id, user_queue)
       if subscribers becomes empty and task is RUNNING -> abort_task

   .launch(task_id)
       evt = asyncio.Event()
       awaitable = launcher_for(td.task_type_name)(
                       td.parameters, evt, self.report_queue)
       atask = asyncio.create_task(awaitable)
       store evt, atask, set state RUNNING

   .abort_task(task_id)
       term_event[task_id].set()
       state -> ZOMBIE
       # confirmation arrives via the report loop noticing the
       # asyncio.Task has completed

Launcher contract:

   The TaskManager is agnostic of execution context that the launched 
   task applied internally (sync, in-thread, subprocess, remote). However,
   it must:

     - honor 'termination request signal': 
       The task must initiate anything that terminates the the processing
       of the task and return to the 'await'-ing TaskManager (function return).

     - reports via report queue about events related to its operation 
       (success, failure, termination). 

Reporting:

The WorkFlow manager receives reports from tasks and may decide if and how
it informs the concerned user about the evolvement of the task.

Artifact Update
---------------

The report queue delivers information about the artifact production from the
task to the WorkflowManager. An update of an artifact state is directly
fed into the DependencyGraph. 

   Artifact Update ---> DependencyGraph ---> Runable, Unrunable Tasks

The based on its knowledge of unrable tasks, the DependencyGraph may also
determine the set of impossible artifacts. Then, the artifact db can be 
updated

   Artifact Update + Impossible Artifacts ---> ArtifactDb

Depending on the changes to the ArtifactDb the user may be also informed.
