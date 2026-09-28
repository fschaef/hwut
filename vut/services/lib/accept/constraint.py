# SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
"""
______________________________________________________________________________
PURPOSE: WHAT THE CONSTRAINTS SAY ABOUT A TEXT, for the faces that show or
         accept one (services E-124): 'hwut.accept', 'hwut.accept.
         interactive' (its commit), 'hwut.sanitize'.

    finding_text_list(setup, subject, nominal)
                        the findings of compare (C-20) holding OUTPUT
                        against GOOD, each one sentence naming its side
    own_finding_text_list(setup, text)
                        the findings of a text held against ITSELF -- what
                        it would say were it the GOOD: a text that breaks
                        its constraints, or never binds a variable they
                        name, is never accepted
______________________________________________________________________________
"""
import asyncio
import io


def finding_list_of(setup, subject_text, nominal_text):
    """
    RETURN: list, the findings of the constraints (compare C-20) holding
            'subject_text' against 'nominal_text' -- 'ConstraintFinding's;
            a constraint that does not compile, its message as a str.
            Empty where nothing was found, or no constraint stands.
    """
    from vut.engine.compare.api import (Configuration, ConstraintSpecError,
                                        RegionSyntaxError, is_equivalent)
    setup        = setup if setup is not None else Configuration()
    if not setup.constraint_db: return []
    finding_list = []
    try:
        asyncio.run(is_equivalent(setup, io.StringIO(subject_text),
                                  io.StringIO(nominal_text), finding_list))
    except ConstraintSpecError as error:
        return ["constraint: %s" % error]
    except RegionSyntaxError:
        return []                  # said by the face that reads regions
    return finding_list


def finding_text_list(setup, subject_text, nominal_text):
    """
    RETURN: list[str], one sentence per finding of 'finding_list_of' --
            'OUTPUT: constraint "...": ...' or 'GOOD: constraint ...'.
    """
    return [f if isinstance(f, str) else f.text()
            for f in finding_list_of(setup, subject_text, nominal_text)]


def own_finding_list(setup, text):
    """
    RETURN: list, what the constraints find in 'text' held against itself
            -- each finding once, whichever side found it (the text is
            both): 'ConstraintFinding's, or a str for a constraint that
            does not compile.
    """
    result, seen = [], set()
    for finding in finding_list_of(setup, text, text):
        mark = finding if isinstance(finding, str) else \
               (finding.kind, finding.expression, finding.variable,
                finding.line_n)
        if mark in seen: continue
        seen.add(mark)
        result.append(finding)
    return result


def own_text(finding):
    """RETURN: str, a finding of 'own_finding_list' as one sentence, its
               side dropped."""
    if isinstance(finding, str): return finding
    return finding.text().partition(": ")[2]


def own_finding_text_list(setup, text):
    """
    RETURN: list[str], what the constraints find in 'text' held against
            itself, each sentence once, its side dropped. Empty where it
            keeps every constraint and binds every variable they name.
    """
    return [own_text(f) for f in own_finding_list(setup, text)]
