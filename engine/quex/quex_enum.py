# Project Quex (http://quex.sourceforge.net); License: MIT;
# Copied original code from Quex (2021y01m23d)
# (C) 2005-2020 Frank-Rene Schaefer; 
#_______________________________________________________________________________
# (C) Frank-Rene Schaefer
# License MIT
from enum import Enum, EnumMeta

class QuexMetaEnum(EnumMeta):
    def __contains__(cls, other):
        return other in cls.__members__.values()

class QuexEnum(Enum, metaclass=QuexMetaEnum):
    def _generate_next_value_(name, start, count, last_values):
        return count
        
    def __repr__(self):
        return self.name

    def __str__(self):
        return self.name

    def __lt__(self, Other):
        return QuexEnum.general_cmp(self, Other) == -1

    @staticmethod
    def general_cmp(X, Y):
        def cmp(A, B):  # Cannot use 'quex.engine.misc.tools.cmp' to avoid circular inclusion
            return (A>B)-(A<B)
        x_enum_f = isinstance(X, Enum)
        y_enum_f = isinstance(Y, Enum)
        if x_enum_f:
            if y_enum_f: return cmp(X.value, Y.value) # cmp(Enum, Enum) 
            else:        return 1                     # cmp(Enum, other)  -> Enum is bigger (other sorts first)
        else:
            if y_enum_f: return -1                    # cmp(other, Enum)  -> other is lesser (other sorts first)
            else:        return cmp(X, Y)             # cmp(other, other)

    @staticmethod
    def general_key(X):
        if isinstance(X, Enum): return (1, X.value)   # Enum is bigger
        else:                   return (0, X)         # Other sorts first
