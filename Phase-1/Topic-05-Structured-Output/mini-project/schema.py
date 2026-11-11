from tkinter import N
from pydantic import BaseModel, Field, ConfigDict
from typing import Literal


# ---------------------------------------
#            Model Arguments
# ---------------------------------------
class OrderArgs(BaseModel):
    model_config   = ConfigDict(extra = 'forbid')
    order_id : str = Field(min_length = 1, description = 'Order ID, e.g. A0232')

class WeatherArgs(BaseModel):
    model_config  = ConfigDict(extra = 'forbid')
    city : str    = Field(min_length = 1, description = 'City, e.g. Surat')

class DateDiffArgs(BaseModel):
    model_config  = ConfigDict(extra = 'forbid')
    start_date : str = Field(min_length=8, description = 'Start date. Formate : `dd-MM-yyyy`, e.g. `02-05-2004`')
    end_date   : str = Field(min_length=8, description = 'End date. Formate : `dd-MM-yyyy`, e.g. `02-05-2004`')

class CurrentDateArgs(BaseModel):
    model_config  = ConfigDict(extra = 'forbid')


# ---------------------------------------
#            Model Result
# ---------------------------------------
class OrderSchema(BaseModel):
    ok           : bool = True
    order_id     : str
    order_status : Literal['Shipped', 'Processing', 'Cancelled'] | None = None 
    error        : str | None = None

class WeatherSchema(BaseModel):
    ok        : bool = True
    city      : str | None = None
    country   : str | None = None
    temp_c    : float | None = None
    wind_kph  : float | None = None
    condition : str | None = None
    error     : str | None = None 

class DateDiffSchema(BaseModel):
    ok                  : bool = True
    difference_in_year  : int | None = Field(default=None, description = 'Difference in year, e.g. `12`')
    difference_in_month : int | None = Field(default=None, description = 'Difference in months, e.g. `11`')
    difference_in_days  : int | None = Field(default=None, description = 'Difference in days, e.g. `32`')
    error               : str | None = None

class CurrentDateSchema(BaseModel):
    ok           : bool = True
    current_date : str | None = Field(min_length = 8, description = "Current date. format = `dd-MM-yyyy`")