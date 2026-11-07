import requests
from tool_schema import (
    OrderSchema, WeatherSchema
)

def get_order_status(order_id : str) -> OrderSchema:
    fake_db = {"A1042": "Shipped", "B2200": "Processing"}
    status = fake_db.get(order_id)

    if status is None:
        return OrderSchema(ok = False, order_id = order_id, error = f"Order '{order_id}' not found. Valid IDs look like 'A1042'.")
    return OrderSchema(order_id = order_id, order_status = status)


_WEATHER_CODES = {
    0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast",
    45: "fog", 48: "fog", 51: "light drizzle", 53: "drizzle", 55: "heavy drizzle",
    61: "light rain", 63: "rain", 65: "heavy rain", 80: "rain showers",
    95: "thunderstorm",
}


def get_weather(city: str) -> WeatherSchema:
    if not city or not str(city).strip():
        return WeatherSchema(ok = False, city = city, error = "city name must be a non-empty string")

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
        return WeatherSchema(ok = False, city = query, error = f"geocoding request failed: {e}")

    results = geo.json().get("results")
    if not results:
        return WeatherSchema(ok = False, city = query, error = f"City '{query}' not found")

    place = results[0]
    lat = place.get("latitude")
    lon = place.get("longitude")
    if lat is None or lon is None:
        return WeatherSchema(ok = False, city = query, error=f"incomplete geocoding data for '{query}'")

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
        return WeatherSchema(ok = False, city = query, error=f"weather request failed: {e}")

    current = w.json().get("current")
    if not current:
        return WeatherSchema(ok = False, city = query, error=f"no current weather data returned for '{query}'")

    code = current.get("weather_code")

    return WeatherSchema(
        city      = place.get("name", query),
        country   = place.get("country"),
        temp_c    = current.get("temperature_2m"),
        wind_kmh  = current.get("wind_speed_10m"),
        condition = _WEATHER_CODES.get(code, f"code {code}"),
    )
