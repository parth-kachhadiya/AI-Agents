import requests


def get_order_status(order_id : str) -> dict:
    fake_db = {"A1042": "shipped", "B2200": "processing"}
    return {'order_id' : order_id, 'status' : fake_db.get(order_id , "No found")}

_WEATHER_CODES = {
    0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast",
    45: "fog", 48: "fog", 51: "light drizzle", 53: "drizzle", 55: "heavy drizzle",
    61: "light rain", 63: "rain", 65: "heavy rain", 80: "rain showers",
    95: "thunderstorm",
}

def _weather_result(city, country=None, temp_c=None, wind_kmh=None, condition=None, error=None):
    return {
        "ok": error is None,
        "city": city,
        "country": country,
        "temp_c": temp_c,
        "wind_kmh": wind_kmh,
        "condition": condition,
        "error": error,
    }


def get_weather(city: str) -> dict:
    if not city or not str(city).strip():
        return _weather_result(city, error="city name must be a non-empty string")

    query = str(city).strip()

    # 1. Geocoding
    try:
        geo = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": query, "count": 1},
            timeout=10,
        )
        geo.raise_for_status()
    except requests.RequestException as e:
        return _weather_result(query, error=f"geocoding request failed: {e}")

    results = geo.json().get("results")
    if not results:
        return _weather_result(query, error=f"city '{query}' not found")

    place = results[0]
    lat = place.get("latitude")
    lon = place.get("longitude")
    if lat is None or lon is None:
        return _weather_result(query, error=f"incomplete geocoding data for '{query}'")

    # 2. Weather
    try:
        w = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,weather_code,wind_speed_10m",
            },
            timeout=10,
        )
        w.raise_for_status()
    except requests.RequestException as e:
        return _weather_result(query, error=f"weather request failed: {e}")

    current = w.json().get("current")
    if not current:
        return _weather_result(query, error=f"no current weather data returned for '{query}'")

    code = current.get("weather_code")
    return _weather_result(
        city=place.get("name", query),
        country=place.get("country"),
        temp_c=current.get("temperature_2m"),
        wind_kmh=current.get("wind_speed_10m"),
        condition=_WEATHER_CODES.get(code, f"code {code}"),
    )



TOOLS = [
    {
        "type"     : "function",
        "function" : {
            "name"        : "get_order_status",
            "description" : "Return the customer order status based on given Order ID.",
            "parameters"  : {
                "type"       : "object",
                "properties" : {
                    "order_id" : {"type" : "string", "description" : "e.g. A01323"}
                },
                "required"   : ["order_id"]
            }
        } 
    },

    {
        "type"     : "function",
        "function" : {
            "name"        : "get_weather",
            "description" : "Get weather data of given city.",
            "parameters"  : {
                "type"       : "object",
                "properties" : {
                    "city" : {"type" : "string", "description" : "e.g. Surat"}
                },
                "required" : ["city"]
            }
        }
    }
]

TOOL_KIT = {
    "get_order_status" : get_order_status,
    "get_weather"      : get_weather
}