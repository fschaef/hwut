
@typechecked
def do(subject:        str, 
       nominal:        str, 
       pattern_finder: PatternFinder) -> tuple[bool, list[tuple[str,str]]]:
    """RETURNS: [0] True, if 'self' and 'nominal' are equivalent.
                    False, else.
                [1] AnalogyDb required for the equivalents of [0] to hold.
    """
    def _trivial_analogy_list(subject, nominal):
        if not pattern_finder.analogy_enabled_f:         
            return []
        else:
            # if both lines are equal => trivial analogies: s -> n with s == n
            analogy_str_list = pattern_finder.find_analogy_strings(subject)
            return [(s,s) for s in analogy_str_list]

    verdict = None
    if subject == nominal:
        return True, _trivial_analogy_list(subject, nominal)

    # Make sure that backslashes -> '/' if required and n-space -> single space
    subject_u = pattern_finder.uniform(subject_line)
    nominal_u = pattern_finder.uniform(nominal_line)
    if subject_u == nominal_u: 
        return True, _trivial_analogy_list(subject_u, nominal_u)

    subject_le_list = pattern_finder.do(subject_u)
    nominal_le_list = pattern_finder.do(nominal_u)

    if len(subject_le_list) != len(nominal_le_list): 
        return False, []

    analogy_list = []
    for subject_le, nominal_le in zip(subject, nominal):
        verdict, analogy = subject_le.compare(nominal_le)
        if verdict != E_Verdict.EQUIVALENT:
            return False, []
        elif analogy:
            analogy_list.append(analogy)

    return True, analogy_list

