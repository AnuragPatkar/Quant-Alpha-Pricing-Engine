from enum import Enum

class OptionType(str, Enum):
    CALL = "call"
    PUT = "put"

class ExerciseType(str, Enum):
    EUROPEAN = "european"
    AMERICAN = "american"
