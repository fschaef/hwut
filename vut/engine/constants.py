"""SPDX-License: MIT; Project VUT; (C) Frank-Rene Schaefer
________________________________________________________________________________

PURPOSE:
"""
from enum import Enum, auto

class E_Side(Enum):
    SUBJECT = auto()
    NOMINAL = auto()

    def contrary(self):
        if self == E_Side.SUBJECT: return E_Side.NOMINAL
        else:                      return E_Side.SUBJECT

class E_Build(Enum):
    SCRIPT = auto()
    MAKE = auto()

class E_Verdict(Enum):
    BUILD_APP_NOT_EXIST = auto()
    BUILD_FAILURE = auto()
    BUILD_STORAGE_LIMIT = auto()
    BUILD_SUCCESS = auto()
    BUILD_TIMEOUT = auto()
    SUCCESS = auto()
    FAILURE = auto()
    VOID = auto()

