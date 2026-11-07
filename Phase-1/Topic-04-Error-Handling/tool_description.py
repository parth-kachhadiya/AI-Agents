from tool_schema import (
    OrderArgs, WeatherArgs
)
from tools import (
    get_order_status, get_weather
)



def _schema(model):
    s = model.model_json_schema()
    s.pop("title", None)                       # drop the token-wasting titles
    for prop in s.get("properties", {}).values():
        prop.pop("title", None)
    return s


TOOL_KIT = {
    "get_order_status"  : (OrderArgs, get_order_status, "Return the status of order of given Order ID."),
    "get_weather"       : (WeatherArgs, get_weather, "Get the current weather condition of given city.")
}

TOOLS = [
    {
        "type"     : "function",
        "function" : {"name" : name, "description" : description, "parameters" : _schema(args_model)}
    } for name, (args_model, _, description) in TOOL_KIT.items()
]