from enum import IntEnum

class detectionMode(IntEnum):
    different = 1
    same      = 2
    change    = 3
    fast      = 4
    idle      = 5
    GOLD      = 69
    undefined = 0