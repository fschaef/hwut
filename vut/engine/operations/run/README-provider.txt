==============================================================================
provision -- THE PROVIDER ARCHITECTURE: STAGES, PROXIES, MULTIS
==============================================================================

Companion of provision/core.py and provision/provider.py. The subject
side of a test run: how two comparable streams COME TO EXIST.


1  THE STAGES, AND THE ONE ANSWER SHAPE
______________________________________________________________________________

A Provision holds one slot per role. Exactly one of execute/load is
filled: a provision either RUNS or LOADS.

      RUN                                        REPLAY
      acquire ...... dependencies exist          load .... the store's
      build ........ the application exists               candidates,
      execute ...... raw behavior exists                  already
      canonicalise . the subject exists                   canonical
                     (pype rewrites raw)

Every provider answers in ONE shape:

      Supply(product, report, record_list)
             |        |       '-- attribution: ProcsitterResults etc.,
             |        |           kept even in failure
             |        '-- an E_TestRunResult token; speaks when the
             |            product is None
             '-- the role's product; None ends provision with the token

The sequence of a PLAIN provision ('Provision._provide'):

      Provision        acquire      build        execute      canonicalise
         |  supply() -->  |            .            .            .
         |<--Supply-------|            .            .            .
         |  supply() ----------------->|            .            .
         |<--Supply--------------------|            .            .
         |  supply() ------------------------------>|            .
         |<--Supply(raw_db, timing_db)--------------|            .
         |  supply(raw_db) -------------------------------------->|
         |<--Supply(readers)-------------------------------------|
         |
         '--> Subjects(readers, record, raw_db?, timing_db?)

Any stage answering product None stops the walk; the Subjects then
carry the token and every record gathered so far. The cadence
('timing_db') rides IN the execute delivery: a dict where measured,
None where the provider cannot measure -- absent, never empty.


2  THE PROVIDER FAMILY
______________________________________________________________________________

      I_Provider                       the root: the Supply law above
         |
         +-- I_AcquireProvider         supply(stop_event=None)
         +-- I_BuildProvider           supply(stop_event=None)
         +-- I_ExecuteProvider         supply(stop_event=None)
         +-- I_CanonicaliseProvider    supply(raw_db, stop_event=None)
         +-- I_LoadProvider            supply(stop_event=None)
         |
         +-- I_ProxyProvider           handed out by a multi; parks,
                                       triggers when told; names its
                                       multi ('.multi')

      I_MultiProvider                  NOT a provider: the holder of
          start() / close() / .record  ONE shared means; its PROXIES
          provider(*key) -> proxy      fill the slots

The role is the TYPE: Provision refuses a provider in the wrong slot at
construction, by name. Behind the interfaces, a local stage and a proxy
are indistinguishable -- nothing downstream asks.

Concrete pairs, one per amortisation partner:

      multi                shared means             proxy, in role
      -------------------  -----------------------  -------------------
      MultiExecute         ONE app call,            ChoiceExecute
      (multi_execute.py)   '--interactive'          (execute)
      MultiBuild           ONE tool invocation      TargetBuild
      (multi_build.py)     per WAVE                 (build)


3  SEQUENCE: THE INTERACTIVE SESSION (MultiExecute)
______________________________________________________________________________

Capability: the configuration registers 'interactive'. The wire is the
hwut_runner protocol; sinks are the transport, RELATIVE, under
'TMP/session/'.

  Orchestrator   MultiExecute      app --interactive        ChoiceExecute
      |             |                    |                     (per choice)
      | ctor        |                    |                        |
      | provider(c)-|------------------------------------------->(hand-out)
      |             |                    |                        |
      |  ...queued ceremony calls proxy.supply() ................ |
      |             |<---- start(), once, lazily ----------------|
      |             |--launch, procsittered->|                    |
      |             |<--submit(c): ticket----------------------- |
      |             |--"run c <s.out> <s.err>">|                  |
      |             |                    |  fd1/fd2 -> sinks      |
      |             |                    |  run choice c          |
      |             |                    |  flush, close sinks    |
      |             |<--"done c <status>"-|                       |
      |             |--resolve ticket--------------------------->|
      |             |                    |   read sinks, delete   |
      |             |                    |<========= Supply({stdout,
      |             |                    |            stderr}, None)
      | run(choices)|--"quit" after the LAST choice------------->|
      |             |<--"bye", exit------|                        |
      |<-.record: the session's ONE ProcsitterResult              |
      |  ...THEN the ceremonies read: every delivery carries that  |
      |     record -- the process that produced a result is part   |
      |     of it. The sinks outlive the quit and leave with the   |
      |     visit ('discard()').                                   |

Status: 0 and positive DELIVER, report OK (an exit is behavior);
negative delivers with 'test-app-contained'; 'fail' delivers nothing,
'test-app-launch-failed'; a session ending first answers
'test-app-contained' with the session record beside it. A session
serves CHANNEL subjects only ('OUT/' is shared across its choices).


4  SEQUENCE: THE WAVE BUILD (MultiBuild)
______________________________________________________________________________

Knowledge per build system, behind I_BuildSystem:

      waves(targets) -> ((t1, t2), (t3,), ...)   parallel WITHIN a
                                                 wave, ORDER between
      argv(wave)     -> the ONE invocation building that wave

Targets are given at construction: a partition needs the whole set.
The partition law -- every target in exactly one wave -- is refused at
the door when violated.

  Orchestrator   MultiBuild         tool (per wave)         TargetBuild
      |             |                    |                   (per target)
      | ctor(system, targets, dir, caps) |                        |
      | provider(t)-|------------------------------------------->(hand-out)
      |  ...queued ceremony calls proxy.supply() ................ |
      |             |<---- start(), once, lazily-----------------|
      |             |--invoke argv(wave1), procsittered-->|       |
      |             |<--record: OK_COMPLETED, exit 0------|       |
      |             |--resolve every ticket of wave1------------>|
      |             |                    |<========= Supply(target,
      |             |                    |            OK, (record,))
      |             |--invoke argv(wave2)-->|  sees wave1's artifacts
      |             |        ...              standing            |
      | close()---->|-- awaits the building's end                 |
      |<-.record: one ProcsitterResult per invocation             |

A wave ending otherwise than OK_COMPLETED fails ITS targets with
'build-failed', the record beside them -- and every LATER wave answers
'target-not-built' with NO record and NO invocation.


5  THE ORCHESTRATOR'S DECISION
______________________________________________________________________________

(vut/engine/orchestrator/ -- one directory, held ONCE on its
non-recursive mutex; ceremonies entered through 'run_test_held'.)

      queue <-- plain provider            OR      multi.provider(k1)
                (StageExecute, StageBuild,        multi.provider(k2)
                 planned by provision_of)         multi.provider(k3)

The queue consumes I_Provider uniformly and never learns which it got.
For execute, MULTI when every request agrees: 'interactive' registered,
two or more requests, no replay, channel subjects only -- one dissenter
forces plain. The build decision (which waves, from which system) is
orchestrator work on the same seam.
