#! /usr/bin/env python3
# @hwut {
#     title    = "CrowdStrike (2024): a template type of 21 fields, 20 inputs supplied, and a criterion on field 21"
#     choices {
#         july-2024      { features = ["instance-matrix", "validator-verdict", "crash-named"]
#                          tolerance { constraints = ["crashes > 0"] } }
#         validated      { features = ["instance-matrix", "validator-verdict", "no-crash"]
#                          tolerance { constraints = ["crashes == 0", "refused > 0"] } }
#         bounds-checked { features = ["instance-matrix", "validator-verdict", "no-crash"]
#                          tolerance { constraints = ["crashes == 0", "refused == 0"] } }
#     }
# }
"""
______________________________________________________________________________
SUBJECT  per template instance of one template type: which fields it puts
         a criterion on, what the content validator says, and what the
         content interpreter does with the inputs the sensor supplies
HISTORY  On 19 July 2024 CrowdStrike delivered new template instances for
the Falcon sensor in Channel File 291. Windows machines running the
sensor crashed at once and on every reboot (Microsoft counted about 8.5
million). The company's root cause analysis of 6 August 2024: the template
type behind Channel File 291 declared 21 input fields, but the sensor code
that called the content interpreter supplied only 20 input values. The
instances delivered before had a wildcard in field 21, which is not read;
the new instances were the first to put a criterion there. The content
validator checked them against the 21 declared fields and passed them;
the interpreter read input 21 of 20 -- an out-of-bounds read in the
kernel.

REQUIREMENT  No template instance that the validator accepts makes the
             interpreter read an input the sensor does not supply.

THE UNIT  '../content.py': validate(instance, release), interpret(instance,
inputs, release) -- a template type of 21 declared fields, 20 supplied
inputs. 'july-2024' as delivered; 'validated', the validator checks
against the supplied inputs; 'bounds-checked', the interpreter checks the
index.

WHAT THE TEST PRINTS
  ONE ROW PER INSTANCE: its 21 fields ('*' wildcard, 'c' a criterion), the
  validator's word, and what the interpreter did on the sensor's 20
  inputs: 'match', 'no match', or 'CRASH' with the read that faulted.
  Then the counts.

CHOICES
    july-2024       the new instance passes the validator and crashes the
                    interpreter.
    validated       the validator refuses it; nothing crashes.
    bounds-checked  the validator passes it, the interpreter reads no
                    field it was not given: 'no match', nothing crashes.

HOW TO READ THE GOOD  Field 21 is the last column of the matrix; the
instances above the new one all hold '*' there. The matrix stands in
'##! verbatim'. Bindings: '((crashes: N))' instances that faulted the
interpreter -- law '> 0' for july-2024, '== 0' else; '((refused: N))'
instances the validator refused -- law '> 0' for validated (it is the
fix), '== 0' for bounds-checked (it refuses nothing).
______________________________________________________________________________
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from content import (validate, interpret, Inputs, OutOfBounds,        # noqa: E402
                     DECLARED_N, SUPPLIED_N, WILDCARD)

RELEASE_TUPLE = ("july-2024", "validated", "bounds-checked")

#  The sensor's inputs for one IPC event: 20 values.
INPUT_LIST = ["in%02d" % (k + 1) for k in range(SUPPLIED_N)]


def instance(criterion_db):
    """
    RETURN: list of str, a template instance of DECLARED_N fields: the
            criterion of 'criterion_db' (field number -> value) where it
            names one, the wildcard elsewhere.
    """
    return [criterion_db.get(k + 1, WILDCARD) for k in range(DECLARED_N)]


#  The instances, in the order of their delivery. The criteria name the
#  inputs they compare against; the last one names field 21.
INSTANCE_LIST = [
    ("earlier #1", instance({1: "in01", 4: "in04"})),
    ("earlier #2", instance({2: "in02", 7: "xx07"})),
    ("earlier #3", instance({1: "in01", 12: "in12", 20: "in20"})),
    ("earlier #4", instance({3: "in03", 15: "in15"})),
    ("new",        instance({1: "in01", 21: "in21"})),
]


def main(release):
    """RETURN: int, 0 once the matrix and the counts are printed."""
    inputs = Inputs(INPUT_LIST)
    crashes = refused = 0
    print("release %s: template type of %d fields, %d inputs supplied" % (release, DECLARED_N, SUPPLIED_N))
    print()
    print("##! verbatim")
    print("   %-10s  %-*s   %-10s  %s" % ("instance", DECLARED_N, "fields 1 .. %d" % DECLARED_N,
                                          "validator", "interpreter"))
    for name, fields in INSTANCE_LIST:
        strip = "".join("*" if criterion == WILDCARD else "c" for criterion in fields)
        why = validate(fields, release)
        if why is not None:
            refused += 1
            print("   %-10s  %s   %-10s  -- (%s)" % (name, strip, "REFUSED", why))
            continue
        try:
            outcome = interpret(fields, inputs, release)
        except OutOfBounds as fault:
            crashes += 1
            outcome = "CRASH: %s" % fault
        print("   %-10s  %s   %-10s  %s" % (name, strip, "accepted", outcome))
    print("####")
    print("   ('*' wildcard, not read   'c' a criterion, compared with its input)")
    if release == "july-2024":
        print("   instances that crash the interpreter ((crashes: %d))   law > 0   the failure, reproduced" % crashes)
    else:
        print("   instances that crash the interpreter ((crashes: %d))   law == 0   %s"
              % (crashes, "kept" if crashes == 0 else "BROKEN"))
    print("   instances the validator refuses ((refused: %d))" % refused)
    return 0


if __name__ == "__main__":
    release = sys.argv[1] if len(sys.argv) > 1 else ""
    if release not in RELEASE_TUPLE:
        print("choices: %s" % ", ".join(RELEASE_TUPLE))
        sys.exit(1)
    status = main(release)
    print("<hwut-end>")
    sys.exit(status)
