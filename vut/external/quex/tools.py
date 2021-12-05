# Project Quex (http://quex.sourceforge.net); License: MIT;
# (C) 2005-2020 Frank-Rene Schaefer; 
#_______________________________________________________________________________
from   itertools   import islice, combinations
import functools
from   operator    import iconcat
from   collections import deque
import sys
import os
from   enum import auto

def r_enumerate(x):
    """Reverse enumeration."""
    return zip(reversed(range(len(x))), reversed(x))

def delete_if(the_list, condition):
    """Delete element from the list if and only if 'condition(element)' 
    returns True.
    """
    for i in range(len(the_list)-1, -1, -1):
        if condition(the_list[i]): del the_list[i]

def do_and_delete_if(the_list, do, result):
    """'do()' operates on each element of the list and the 'result'. If
    it returns 'True' the element is deleted from 'the_list'.
    """
    for i in range(len(the_list)-1, -1, -1):
        if do(the_list[i], result): del the_list[i]

def print_callstack(BaseNameF=False):
    try:
        i = 1
        name_list = []
        while 1 + 1 == 2:
            f = sys._getframe(i)
            x = f.f_code

            # Do not consider the frame coming from the @typed decorator,
            # (See 'def typed(**parameters)' below)
            if x.co_name != "modified": 
                name_list.append([x.co_filename, f.f_lineno, x.co_name])
            i += 1
    except:
        pass

    prev_file_name = ""
    i = - 1
    for x in reversed(name_list):
        if BaseNameF: 
            name = os.path.basename(x[0])
            i += 1
        else:         
            file_name = x[0]
            if file_name != prev_file_name:
                name = file_name
                i += 1
            else:
                # base_name = os.path.basename(x[0])
                base_name = " " * len(os.path.basename(x[0]))
                name = " " * (len(file_name) - len(base_name)) + base_name
            prev_file_name = file_name
            
        print("%s%s:%s:%s(...)" % (" " * (i*4), name, x[1], x[2])) 

def pair_combinations(iterable):
    other = tuple(iterable)
    for i, x in enumerate(other):
        for y in islice(other, i+1, None):
            yield x, y

def flatten(ListOfListsIterable):
    """The very fastest way to flatten a list of lists of objects into a list
    of objects.

    EXAMPLE: input:   [1, 2], [3, 4], [5, 6]
             output:  [1, 2, 3, 4, 5, 6]

    RETURNS: List of objects.
    """
    # The fastest method ever! 
    # Before changing this, please benchmark propperly!
    return functools.reduce(iconcat, ListOfListsIterable, [])

def _check_all(Iterable, Condition):
    assert not isinstance(Iterable, (int, str))

    last_things = deque()
    if isinstance(Iterable, (tuple, list)): iterable = iter(Iterable)
    else:                                   iterable = Iterable
    i = -1
    while 1 + 1 == 2:
        i     += 1
        try:   thing = next(iterable)
        except StopIteration: break

        if len(last_things) > 10: last_things.popleft()
        last_things.append(thing)
        if Condition(thing): continue
        _report_failed_assertion(i, thing, last_things, iterable)
        return False
    return True

def _get_value_check_function(Type):
    """Tries possible operations on 'Type' and returns the operation which
    works without exception.
    """
    try:     
        if isinstance(4711, Type): pass
        return lambda value: isinstance(value, Type)
    except: 
        if not isinstance(Type, tuple):
            try: 
                if 4711 in Type: pass
                return lambda value: value in Type
            except:
                pass
        else:
            condition_array = tuple( 
                _get_value_check_function(alternative_type) 
                for alternative_type in Type
            )
            def is_ok(element):
                for condition in condition_array:
                    if condition(element): return True
                return False
            return is_ok
    return None

def all_isinstance(List, Type):
    if Type is None: return True
    is_ok = _get_value_check_function(Type) # 'Type' is coded in 'is_ok'
    assert is_ok is not None
    return _check_all(List, is_ok)

def none_isinstance(List, Type):
    if Type is None: return True
    is_ok = _get_value_check_function(Type) # 'Type' is coded in 'is_ok'
    assert is_ok is not None
    return _check_all(List, lambda element: not is_ok(element))

def none_is_None(Iterable):
    return not any(x is None for x in Iterable)

class TypedSet(set):
    def __init__(self, Cls):
        self.__element_class = Cls

    def add(self, X):
        assert isinstance(X, self.__element_class)
        set.add(self, X)

    def update(self, Iterable):
        for x in Iterable:
            assert isinstance(x, self.__element_class)
        set.update(self, Iterable)

class TypedDict(dict):
    def __init__(self, ClsKey=None, ClsValue=None):
        self.__key_class   = ClsKey
        self.__value_class = ClsValue

    def get(self, Key):
        assert self.__key_class is None or isinstance(Key, self.__key_class), \
               self._error_key(Key)
        return dict.get(self, Key)

    def __getitem__(self, Key):
        assert self.__key_class is None or isinstance(Key, self.__key_class), \
               self._error_key(Key)
        return dict.__getitem__(self, Key)

    def __setitem__(self, Key, Value):
        assert self.__key_class   is None or isinstance(Key, self.__key_class), \
               self._error_key(Key)
        assert self.__value_class is None or isinstance(Value, self.__value_class), \
               self._error_value(Value)
        return dict.__setitem__(self, Key, Value)

    def update(self, Iterable):
        # Need to iterate twice: 'list()' may be faster here then 'tee()'.
        if isinstance(Iterable, dict): iterable2 = iter(Iterable.items())
        else:                          Iterable = list(Iterable); iterable2 = iter(Iterable)

        for x in iterable2:
            assert isinstance(x, tuple)
            assert self.__key_class   is None or isinstance(x[0], self.__key_class), \
                   self._error_key(x[0])
            assert self.__value_class is None or isinstance(x[1], self.__value_class), \
                   self._error_value(x[1])

        dict.update(self, Iterable)

    def _error(self, ExpectedClass):
        return "TypedDict(%s, %s) expects %s" % \
                (self.__key_class.__name__, self.__value_class.__name__, \
                 ExpectedClass.__name__)

    def _error_key(self, Key):
        return "%s as a key. Found type='%s; value='%s';" % \
                (self._error(self.__key_class), Key.__class__.__name__, Key)

    def _error_value(self, Value):
        return "%s as value. Found '%s'" % \
                (self._error(self.__value_class), Value.__class__.__name__)

