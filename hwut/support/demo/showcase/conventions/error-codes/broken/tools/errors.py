# tools/errors.py -- error codes of the host tools: range 3000..3999
import enum

class ToolError(enum.IntEnum):
    USAGE        = 3001
    NO_DEVICE    = 3002
    IMAGE_FORMAT = 3005
    DISK_FULL    = 3003
