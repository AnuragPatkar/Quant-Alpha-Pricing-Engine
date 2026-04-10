from dataclasses import dataclass, field
from typing import List
from quant_alpha.enums import OptionType, ExerciseType

@dataclass(frozen=True)
class Dividend:
    t: float
    amount: float

@dataclass(frozen=True)
class VanillaOption:
    spot: float
    strike: float
    maturity: float
    rate: float
    vol: float
    option_type: OptionType
    exercise: ExerciseType = ExerciseType.EUROPEAN
    dividends: List[Dividend] = field(default_factory=list)

    def validate(self) -> None:
        if self.spot <= 0 or self.strike <= 0:
            raise ValueError("spot and strike must be > 0")
        if self.maturity <= 0:
            raise ValueError("maturity must be > 0")
        if self.vol < 0:
            raise ValueError("vol must be >= 0")
        if self.rate < -0.5 or self.rate > 0.5:
            raise ValueError("rate must be between -50% and 50%")
        for d in self.dividends:
            if d.t > self.maturity:
                raise ValueError(f"dividend at {d.t} exceeds maturity {self.maturity}")
            if d.amount < 0 or d.amount > self.spot:
                raise ValueError(f"dividend {d.amount} invalid for spot {self.spot}")
