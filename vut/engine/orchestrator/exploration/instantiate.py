"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
______________________________________________________________________________

PURPOSE: INSTANTIATION -- build the consumer configurations from a test
         case's record. What the author stated fills the member; what he
         left unstated stands at the value the owning component declares.

There is one mechanism and no per-component code: 'relation.RELATION' says
which member carries which parameter, and 'configuration_of' writes them.
A component joins by declaring its configuration; adding a parameter is one
line in the table.

The record is kept BESIDE what is built here: the record says what the
author CHOSE -- 'None' where he chose nothing -- and the configuration says
what will happen. The store records the record.
______________________________________________________________________________
"""
from .relation import configuration_of, value_db_of


def configurations_of(parameters):
    """
    YIELD: [0] type    the configuration class
           [1] object  its instance, COMPLETE: stated values written,
                       everything else at the owner's declared default

    One pair per class the relation table names. A consumer takes the
    instance of its own class and reads nothing else.
    """
    from .relation import RELATION
    value_db = value_db_of(parameters)
    seen     = []
    for entry in RELATION.values():
        cls = entry[0]
        if cls in seen: continue
        seen.append(cls)
        yield cls, configuration_of(cls, value_db)


def configuration_for(cls, parameters):
    """
    RETURN: an instance of 'cls' carrying every parameter the relation
            table relates to it -- the case's values, the owner's
            declared defaults for the rest.
    """
    return configuration_of(cls, value_db_of(parameters))
