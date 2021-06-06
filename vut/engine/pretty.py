"""SPDX-Linces: MIT; Project UT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: Pretty printing of object content.

The function '.do(object)' shall transform the given object into a string which
is easy to reflect by humans. It relies on the object implementing the member
function:

        def __pretty__(self):
            ...

This function must return two objects:

        [0] name:    describing the type/class/category of the object.
        [1] content: i.e. a list describing the content of the object.

The 'content' can be:

    (i)    'None'
           => prints 'None'

    (ii)   an object providing '.__pretty__()'
           => recursive call to transform the object.

    (iii)  a 'list' or a 'tuple' of contents.
           => a sequence of contents is printed.

    (iv)   a plain python object.
           => the string representation function is called.

EXAMPLES: The unit tests 'test-pretty.py' for the main APIs. All objects
          communicated through main APIs shall provide the pretty print
          functionality.
______________________________________________________________________________
"""


def do(obj):
    return "".join(_indent(obj))

def _indent(obj):
    indent    = 0
    newline_f = True
    for txt in _class(obj):
        if   txt == 1:  indent += 1; continue
        elif txt == -1: indent -= 1; continue

        if newline_f: yield ".   " * indent
        yield txt
        if not txt.endswith(":"): yield "\n"; newline_f = True
        else:                     yield " ";  newline_f = False

def _iterable(element):
    if   element is None:                yield "None"
    elif hasattr(element, "__pretty__"): yield from _class(element)
    elif type(element) == list:          yield from _list(element)
    elif type(element) == tuple:         yield from _list(element, "tuple")
    else:                                yield "%s" % element

def _class(obj):
    class_name, member_list = obj.__pretty__()
    assert type(member_list) == list
    if not member_list: return [class_name]
    return _member_sequence(member_list, class_name)

def _member_sequence(member_list, class_name):
    txt = ["[%s]" % class_name, +1]
    for name, content in member_list:
        txt.append(".%s:" % name)
        txt.extend(_iterable(content))
    txt.extend([-1])
    return txt

def _list(obj_list, list_name="list"):
    txt = ["<%s>" % list_name, +1]
    for obj in obj_list:
        txt.extend(_iterable(obj))
    txt.extend([-1])
    return txt

        
