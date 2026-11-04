============================================================================
ENGINE/PLATFORMS -- WHERE A BUBBLE RUNS
============================================================================

Status:  P-1, P-2, P-5 of adm/WORK/plan/42-platforms: the helper,
         'local' and 'container'; the conf's reader asks 'kind_tuple'
         and 'check'; the orchestrator's hand-over asks 'start', 'run',
         'stop'. How a tree says a platform is written here with P-9.
Layer:   ENGINE, beside the orchestrator. Imports only the engine and the
         standard library (TEST: choice 'imports').

    __init__.py     is_available, start, run, stop, keys, check,
                    kind_tuple --
                    each dispatched on the platform's kind; the reserved
                    name 'local' needs none
    local.py        'local': always available, never handed a bubble
    container.py    'container': podman or docker, the image built from
                    its recipe where it does not stand, the bubble run
                    with the tree mounted at its own path; also 'engine'
                    and 'root_of', which 'hwut.dev.podman.*' take from here

SPEC:  adm/WORK/spec/42-platforms.txt, section 4 (the services) and 5
       (the stream). WHY: adm/WORK/intend/42-platforms.txt, rulings 14-22.
