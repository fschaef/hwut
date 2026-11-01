"""
______________________________________________________________________________
content.py -- a content validator and a content interpreter as CrowdStrike's
Falcon sensor used them for the template type behind Channel File 291 in
July 2024 (the company's root cause analysis of 6 August 2024).

    validate(instance, release)    -> None, accepted; str, why refused
    interpret(instance, inputs, release)
                                   -> 'match' | 'no match'; raises
                                      OutOfBounds where it reads past the
                                      inputs it was given

The TEMPLATE TYPE declares DECLARED_N = 21 input fields. The sensor code
that calls the interpreter supplies SUPPLIED_N = 20 input values. An
instance names, per field, a criterion or the wildcard '*'; a wildcard
field is not read.

    'july-2024'       the validator checks an instance against the 21
                      DECLARED fields; the interpreter reads every
                      non-wildcard field, unchecked.
    'validated'       the validator checks against the 20 SUPPLIED values:
                      an instance with a criterion beyond them is refused.
    'bounds-checked'  the interpreter checks the index: a field beyond the
                      inputs is no match, never a read.
______________________________________________________________________________
"""
DECLARED_N = 21
SUPPLIED_N = 20
WILDCARD   = "*"


class OutOfBounds(Exception):
    """A read past the inputs the interpreter was given: in the kernel, a
    page fault the driver did not catch -- the machine stops."""


class Inputs:
    """The input values the sensor hands the interpreter, and nothing past
    them: reading index n of SUPPLIED_N values raises OutOfBounds."""

    def __init__(self, value_list):
        """RETURN: None. Holds 'value_list'."""
        self.value_list = list(value_list)

    def read(self, index):
        """RETURN: str, the input at 'index' (0-based), if it was supplied;
        raises OutOfBounds, else."""
        if index >= len(self.value_list):
            raise OutOfBounds("read input %d of %d" % (index + 1, len(self.value_list)))
        return self.value_list[index]


def validate(instance, release):
    """
    RETURN: None, the instance is accepted for release;
            str, why it is refused, else.
    """
    if len(instance) != DECLARED_N:
        return "has %d fields, the type declares %d" % (len(instance), DECLARED_N)
    if release == "validated":
        beyond = [i + 1 for i, criterion in enumerate(instance)
                  if i >= SUPPLIED_N and criterion != WILDCARD]
        if beyond:
            return "criterion on field %s, only %d inputs supplied" % (beyond[0], SUPPLIED_N)
    return None


def interpret(instance, inputs, release):
    """
    RETURN: str, 'match' where every non-wildcard field's criterion equals
            its input, 'no match' else. Raises OutOfBounds where release
            reads a field the inputs do not hold.
    """
    for index, criterion in enumerate(instance):
        if criterion == WILDCARD:
            continue
        if release == "bounds-checked" and index >= len(inputs.value_list):
            return "no match"
        if inputs.read(index) != criterion:
            return "no match"
    return "match"
