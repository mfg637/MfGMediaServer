import enum


class LoadAcceleration(enum.Enum):
    NONE = 0
    LAZY_LOAD = 1
    PAGINATION = 2
    BOTH = 3
