# Project Quex (http://quex.sourceforge.net); License: MIT;
# (C) 2005-2020 Frank-Rene Schaefer; 
#_______________________________________________________________________________

class TypeTuple:
    def __init__(self, *args):
        self.list = list(args)

def typed(**_parameters_):
    """parameter=Type                   --> isinstance(parameter, Type)
                                            Type == None --> no requirements.
       parameter=(Type0, Type1, ...)    --> isinstance(parameter, (Type0, Type1, ...))
                                            TypeX == None means that parameter can be None
       parameter=[Type]                 --> (1) isinstance(parameter, list)
                                            (2) all_isinstance(parameter, Type)
       parameter=[(Type0, Type1, ...)]  --> (1) isinstance(parameter, list)
                                            (2) all_isinstance(parameter, (Type0, Type1, ...))
       parameter={Type0: Type1}         --> (1) isinstance(parameter, dict)
                                            (2) all_isinstance(parameter.keys(),   Type0)
                                            (3) all_isinstance(parameter.values(), Type1)
                                        (Here, Type0 or Type1 may be a tuple (TypeA, TypeB, ...)
                                         indicating alternative types.)
    """
    def name_type(TypeD):
        if isinstance(TypeD, tuple):
            return "[%s]" % "".join("%s, " % name_type(x) for x in TypeD)
        elif hasattr(TypeD, __name__):
            return "'%s'" % TypeD.__name__
        else:
            return str(TypeD)

    def error(Name, Value, TypeD):
        return "Parameter '%s' is a '%s'. Expected '%s'." \
               % (Name, Value.__class__.__name__, name_type(TypeD))

    def check_types(_func_, _parameters_ = _parameters_):
        def modified(*arg_values, **kw):
            arg_names = _func_.__code__.co_varnames
            kw.update(list(zip(arg_names, arg_values)))
            for name, type_d in _parameters_.items():
                if name not in kw:  # Default arguments may possibly not appear
                    continue
                value = kw[name]
                if type_d is None:  # No requirements on type_d
                    continue

                elif value is None:
                    assert type_d is None or (type(type_d) == tuple and None in type_d), \
                           error(name, value, type_d)

                elif type(type_d) == tuple:
                    if None in type_d: 
                        # 'None' is accepted as alternative. But, if value was 'None' it
                        # would have triggered the previous case. So, here filter it out.
                        type_d = tuple(set(x for x in type_d if x is not None))
                    assert isinstance(value, type_d), error(name, value, type_d)

                elif type(type_d) == list:
                    assert len(type_d) == 1
                    assert isinstance(value, list), error(name, value, type_d)
                    value_type = type_d[0]
                    assert all(isinstance(x, value_type) for x in value), error(name, value, type_d)

                elif type(type_d) == dict:
                    assert len(type_d) == 1
                    assert isinstance(value, dict), error(name, value, type_d)
                    key_type, value_type = next(iter(type_d.items()))
                    assert all(isinstance(x, key_type) for x in iter(value.keys())), \
                           "Dictionary '%s' contains key not of of '%s'" % (name, name_type(key_type))
                    assert all(isinstance(x, value_type) for x in iter(value.values())), \
                           "Dictionary '%s' contains value not of of '%s'" % (name, name_type(value_type))

                elif type_d.__class__ == TypeTuple:
                    assert isinstance(value, list), error(name, value, type_d)
                    value_type = type_d[0]
                    assert all(isinstance(x, value_type) for x in value), error(name, value, type_d)
                    
                else:
                    assert isinstance(value, type_d), \
                           error(name, value, type_d)
            return _func_(**kw)
        return modified

    return check_types

