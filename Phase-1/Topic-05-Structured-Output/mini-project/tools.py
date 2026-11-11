import os, json, requests
from schema import (
    OrderSchema,
    WeatherSchema,
    DateDiffSchema,
    CurrentDateSchema
)
from datetime import datetime, date
import calendar


# ------------------------------------------
#               Helper
# ------------------------------------------
_WEATHER_CODES = {
    0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast",
    45: "fog", 48: "fog", 51: "light drizzle", 53: "drizzle", 55: "heavy drizzle",
    61: "light rain", 63: "rain", 65: "heavy rain", 80: "rain showers",
    95: "thunderstorm",
}

def _add_months(d: date, months: int) -> date:
    """Move a date forward by N months, clamping the day (31 Jan + 1 month = 28/29 Feb)."""
    total = d.year * 12 + (d.month - 1) + months
    year, month = divmod(total, 12)
    month += 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)
# ------------------------------------------



# ------------------------------------------
#               Tools
# ------------------------------------------
def get_order_status(order_id : str) -> OrderSchema:
    fake_db = {'A1042' : 'Shipped', 'B2200' : 'Processing', 'C4801' : 'Cancelled'}
    status = fake_db.get(order_id, default = None)

    if status is None:
        return OrderSchema(ok = False, order_id = order_id, order_status = None, error = f"Order of {order_id} not found.")
    return OrderSchema(order_id = True, order_status = status)

def get_weather(city : str) -> WeatherSchema:
    if not city or not str(city).strip():
        return WeatherSchema(ok = False, city = city, error = "city name must be a non-empty string")

    query = str(city).strip()

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
        wind_kph  = current.get("wind_speed_10m"),
        condition = _WEATHER_CODES.get(code, f"code {code}"),
    )


def get_current_date() -> CurrentDateSchema:
    return CurrentDateSchema(current_date = date.today().strftime("%d-%m-%Y"))


def calculate_date_difference(start_date: str, end_date: str) -> DateDiffSchema:
    date_format = "%d-%m-%Y"

    try:
        start = datetime.strptime(start_date, date_format).date()
        end   = datetime.strptime(end_date, date_format).date()
    except (ValueError, TypeError):
        return DateDiffSchema(
            ok=False,
            error="Invalid date. Use the format dd-MM-yyyy, e.g. 02-05-2004."
        )

    if start > end:
        return DateDiffSchema(ok=False, error="Start date cannot be later than end date.")

    # whole months between the two dates, then step back if we overshot
    months = (end.year - start.year) * 12 + (end.month - start.month)
    anchor = _add_months(start, months)
    if anchor > end:
        months -= 1
        anchor = _add_months(start, months)

    years, months = divmod(months, 12)
    days = (end - anchor).days

    return DateDiffSchema(ok=True, difference_in_year=years, difference_in_month=months, difference_in_days=days)