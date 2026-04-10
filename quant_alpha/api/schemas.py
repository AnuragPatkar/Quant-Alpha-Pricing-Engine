from pydantic import BaseModel

class PriceRequest(BaseModel):
    spot: float
    strike: float
    maturity: float
    rate: float
    vol: float
    option_type: str
