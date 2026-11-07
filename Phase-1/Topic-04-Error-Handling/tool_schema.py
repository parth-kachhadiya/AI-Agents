from pydantic import BaseModel, Field, ConfigDict   
from typing import Literal



# ---------- arguments: what the MODEL sends ----------
class OrderArgs(BaseModel):
    model_config   = ConfigDict(extra = "forbid")
    order_id : str = Field(min_length = 1, description = "Order ID , e.g. A0232")

class WeatherArgs(BaseModel):
    model_config   = ConfigDict(extra = "forbid")
    city : str     = Field(min_length = 1, description = "City , e.g. Surat") 


# ---------- results: what the TOOL returns ----------
class OrderSchema(BaseModel):
    ok           : bool = True
    order_id     : str
    order_status : Literal["Shipped", "Processing"] | None = None
    error        : str | None = None

class WeatherSchema(BaseModel):
    ok        : bool = True
    city      : str | None = None
    country   : str | None = None
    temp_c    : float | None = None
    wind_kmh  : float | None = None
    condition : str | None = None
    error     : str | None = None
