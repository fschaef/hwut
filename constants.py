from quex_enum  import QuexEnum
from enum import auto

class E_Build(QuexEnum):
    SCRIPT = auto()
    MAKE = auto()

class E_Verdict(QuexEnum):
    BUILD_APP_NOT_EXIST = auto()
    BUILD_FAILURE = auto()
    BUILD_STORAGE_LIMIT = auto()
    BUILD_SUCCESS = auto()
    BUILD_SUCCESS = auto()
    BUILD_SUCCESS = auto()
    BUILD_TIMEOUT = auto()
    SUCCESS = auto()
    FAILURE = auto()
    VOID = auto()

