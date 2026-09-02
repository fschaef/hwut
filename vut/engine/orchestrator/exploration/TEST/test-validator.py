#! /usr/bin/env python3
#
# @hwut {
#     title      = "Validator: plain tree, or refusal by name"
#     choices    = ["choiceless", "conf", "exclusivity", "header",
#                   "list_form", "off", "root_only", "types",
#                   "vocabulary"]
#     interactive = true
# }
#
"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: The validator -- the annotated tree becomes the plain tree, or a
         refusal by name with a position.

CHOICES: header, list_form, choiceless, vocabulary, types, off,
         root_only, conf, exclusivity;

DESCRIPTION:

header      a full header: root defaults, per-choice parameters, every
            parameter kind once; the record shows what was CHOSEN and
            nothing else.

list_form   'choices = [\"one\", \"two\"]' means the map with empty bodies.

choiceless  no 'choices': the single entry 'None' -- absence is data.

vocabulary  an unknown key, a misspelt key, a missing 'title' -- each
            refused by name, at its position; validation completes.

types       'numeric' beyond [0..1], a cap that is no number, a cap
            that is not positive, an
            unknown cap, a boolean where a string belongs, an 'analogy'
            of three markers, and a key bound to nothing.

off         absence is never off: 'build' named alone, and 'analogy',
            'comment' and 'constraints' switched off through '[]',
            'false', 'no' and an empty value; a marker pair set to
            'true' says nothing and is refused. 'comment' is a pair
            like 'analogy' -- the opening and the closing marker of an
            ignored line.

root_only   'same' and 'interactive' stand at the root and reach every
            choice through the resolution; inside a choice each is
            refused by name, saying why it cannot stand there.

conf        a full 'hwut.conf': directory keys, 'collision' and
            'dependency' written in targets, 'language-setup', and
            'apps' entries carrying the header vocabulary unchanged.

exclusivity a test parameter at the root of 'hwut.conf' -- refused with
            the sentence that says where it belongs.
______________________________________________________________________________
"""
import sys
from config import HwutRunner                                # noqa: F401

from vut.engine.orchestrator.exploration.unwrapper        import plain_lines
from vut.test_writing_support.python.hwut_hocon import parse
from vut.engine.orchestrator.exploration                  import validator


def banner(label):
    """RETURN: None. Section heading."""
    print()
    print("--- %s ---" % label)


def show_parameters(parameters, indent="    "):
    """RETURN: None. Prints the STATED fields only -- 'None' is absence
    and absence prints nothing."""
    stated = [(name, getattr(parameters, name))
              for name in parameters.__dataclass_fields__
              if getattr(parameters, name) is not None]
    if not stated:
        print("%s(nothing stated)" % indent)
    for name, value in stated:
        print("%s%s = %r" % (indent, name, value))


def show_spec(spec):
    """RETURN: None. Prints one TestAppSpec."""
    print("title    '%s'  language %s  origin %s  at %s"
          % (spec.title, spec.language, spec.origin.name, spec.position))
    print("root:")
    show_parameters(spec.root_parameters)
    for name in sorted(spec.choice_db, key=lambda n: (n is None, n or "")):
        print("choice %s:" % ("-" if name is None else "'%s'" % name))
        show_parameters(spec.choice_db[name])


def header(label, text):
    """RETURN: None. Parses and validates 'text' as a header."""
    banner(label)
    document, fault_list = parse(plain_lines(text), "f.py")
    node = validator.document_hwut_node(document, "f.py", fault_list)
    spec = None
    if node is not None:
        spec, more = validator.validate_header(node, "f.py")
        fault_list.extend(more)
    if spec is not None: show_spec(spec)
    else:                print("no specification")
    for fault in fault_list:
        print("FAULT %s" % fault)


def conf(label, text):
    """RETURN: None. Parses and validates 'text' as hwut.conf."""
    banner(label)
    document, fault_list = parse(plain_lines(text), "hwut.conf")
    node = validator.document_hwut_node(document, "hwut.conf", fault_list)
    if node is not None:
        spec, app_db, more = validator.validate_conf(node, "hwut.conf")
        fault_list.extend(more)
        if spec is not None:
            print("on_entry %r  on_exit %r  ignore %r"
                  % (spec.on_entry, spec.on_exit, spec.ignore))
            print("collision %s"
                  % [str(x) for x in spec.collision])
            for target in sorted(spec.dependency or {}, key=str):
                print("dependency %-16s <- %s"
                      % (str(target),
                         [str(x) for x in spec.dependency[target]]))
            for name in sorted(spec.language_setup):
                setup = spec.language_setup[name]
                print("language '%s': interpreter %r coverage %r "
                      "profiler %r"
                      % (name, setup.interpreter, setup.coverage,
                         setup.profiler))
            for name in sorted(app_db):
                print("app '%s':" % name)
                show_spec(app_db[name])
    for fault in fault_list:
        print("FAULT %s" % fault)


def test_header():
    """RETURN: None. Every parameter kind once."""
    header("a full header",
           '@hwut {\n'
           '    title      = "Parser corner cases"\n'
           '    language   = "heartfun"\n'
           '    build {\n'
           '        framework  = "make"\n'
           '        executable = "special.exe"\n'
           '        caps { timeout_sec = 300 }\n'
           '    }\n'
           '    caps {\n'
           '        timeout_sec          = 30\n'
           '        cpu_sec              = 20\n'
           '        memory_mb            = 512\n'
           '        file_size_mb         = 64\n'
           '        child_process_max_n  = 4\n'
           '        file_handle_max_n    = 64\n'
           '        network              = false\n'
           '        write_directory_list = ["tmp", "out"]\n'
           '    }\n'
           '    pype        = \"strip.pype\"\n'
           '    tolerance { numeric_ratio = 0.01  slash = yes }\n'
           '    eq-pattern  = ["bonjour|hello"]\n'
           '    nothing     = "_"\n'
           '    analogy     = ["((", "))"]\n'
           '    constraints = ["x < y + 2", "abs(sin(z) - x) < eps"]\n'
           '    comment     = ["##", "##"]\n'
           '    same        = yes\n'
           '    interactive = yes\n'
           '    choices {\n'
           '        one { }\n'
           '        two { numeric = 0.05  caps { timeout_sec = 5 } }\n'
           '    }\n'
           '}\n')


def test_list_form():
    """RETURN: None. The list form of 'choices'."""
    header("choices as a list of names",
           '@hwut {\n'
           '    title   = "T"\n'
           '    choices = [\"one\", \"two\", \"three\"]\n'
           '}\n')


def test_choiceless():
    """RETURN: None. No 'choices': the single 'None' entry."""
    header("choice-less: root parameters are the one call's",
           '@hwut {\n'
           '    title   = "T"\n'
           '    tolerance { numeric_ratio = 0.5 }\n'
           '}\n')


def test_vocabulary():
    """RETURN: None. Unknown, misspelt, and missing keys."""
    header("unknown and misspelt keys, by name and position",
           '@hwut {\n'
           '    title   = "T"\n'
           '    numerc  = 0.5\n'
           '    choices {\n'
           '        one { pyep = \"x.pype\" }\n'
           '    }\n'
           '}\n')
    header("a key bound to nothing, where something is required",
           '@hwut {\n'
           '    title   = "T"\n'
           '    tolerance { numeric_ratio =  }\n'
           '    comment = null\n'
           '}\n')
    header("'title' absent",
           '@hwut {\n'
           '    tolerance { numeric_ratio = 0.5 }\n'
           '}\n')


def test_types():
    """RETURN: None. Values of the wrong shape."""
    header("wrong shapes, each named",
           '@hwut {\n'
           '    title   = "T"\n'
           '    tolerance { numeric_ratio = 1.5  slash = "maybe" }\n'
           '    build   = yes\n'
           '    caps    { timeout_sec = \"fast\"  memory_mb = -1\n'
           '              bandwidth   = 10 }\n'
           '    analogy = ["((", "))", "extra"]\n'
           '    choices = [\"one\", { a = 1 }]\n'
           '}\n')


def test_off():
    """RETURN: None. Absence takes the default; off is written, in any
    of its spellings."""
    header("build named alone; analogy and constraints switched off",
           '@hwut {\n'
           '    title       = "T"\n'
           '    build       = "make"\n'
           '    analogy     = []\n'
           '    constraints = false\n'
           '}\n')
    header("the other spellings of off, and absence beside them",
           '@hwut {\n'
           '    title       = "T"\n'
           '    analogy     = no\n'
           '    constraints =\n'
           '}\n')
    header("'analogy = true' says nothing and is refused",
           '@hwut {\n'
           '    title   = "T"\n'
           '    analogy = true\n'
           '}\n')
    header("'comment' is a marker pair, and reads alike",
           '@hwut {\n'
           '    title   = "T"\n'
           '    comment = ["/*", "*/"]\n'
           '}\n')
    header("'comment' switched off, and one of three markers",
           '@hwut {\n'
           '    title   = "T"\n'
           '    comment = []\n'
           '    choices { one { comment = ["#", "#", "#"] } }\n'
           '}\n')


def test_root_only():
    """RETURN: None. The two root-only parameters, well and badly
    placed."""
    header("at the root: they reach every choice",
           '@hwut {\n'
           '    title       = "T"\n'
           '    same        = yes\n'
           '    interactive = yes\n'
           '    choices { one { } two { tolerance { numeric_ratio = 0.05 } } }\n'
           '}\n')
    header("inside a choice: refused, by name",
           '@hwut {\n'
           '    title   = "T"\n'
           '    choices {\n'
           '        one { same        = yes }\n'
           '        two { interactive = yes }\n'
           '    }\n'
           '}\n')


def test_conf():
    """RETURN: None. A full hwut.conf."""
    conf("a full hwut.conf",
         '@hwut {\n'
         '    on_entry  = "setup.sh"\n'
         '    on_exit   = "teardown.sh"\n'
         '    ignore    = ["*.gen.c", "tmp-*"]\n'
         '    collision = ["test-a.py", "test-b.py two"]\n'
         '    dependency {\n'
         '        "test-b.py"     = ["test-a.py"]\n'
         '        "test-c.py two" = ["test-a.py", "test-b.py one"]\n'
         '    }\n'
         '\n'
         '    language-setup {\n'
         '        python   { interpreter = "python3.12 -u"\n'
         '                   coverage    = "coverage run" }\n'
         '        heartfun { interpreter = \"heartfun\" }\n'
         '    }\n'
         '\n'
         '    apps {\n'
         '        test-gen.c {\n'
         '            title   = "generated parser"\n'
         '            build   = "make"\n'
         '            choices = [\"one\", \"two\"]\n'
         '        }\n'
         '    }\n'
         '}\n')


def test_exclusivity():
    """RETURN: None. A test parameter at the conf root."""
    conf("test parameters do not stand at the conf root",
         '@hwut {\n'
         '    tolerance { numeric_ratio = 0.01 }\n'
         '    title    = "T"\n'
         '    on_entry = "setup.sh"\n'
         '}\n')
    conf("a target of three words",
         '@hwut {\n'
         '    collision = ["test-a.py one two"]\n'
         '}\n')


if __name__ == "__main__":
    HwutRunner(sys.argv,
               "Validator: plain tree, or refusal by name;", {
        "header":      test_header,
        "list_form":   test_list_form,
        "choiceless":  test_choiceless,
        "vocabulary":  test_vocabulary,
        "types":       test_types,
        "off":         test_off,
        "root_only":   test_root_only,
        "conf":        test_conf,
        "exclusivity": test_exclusivity,
    }).run()
