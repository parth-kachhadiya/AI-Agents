import os, json, requests
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

#   ----------------------------------------------------------
#                             Tools
#   ----------------------------------------------------------

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


# ----------------------------------------------------------


MODEL = "gpt-4o-mini"
# Official gpt-4o-mini prices are quoted per 1M tokens (output is more expensive).
INPUT_PRICE_PER_M  = 0.15
OUTPUT_PRICE_PER_M = 0.60
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

client = OpenAI(
    base_url = "https://openrouter.ai/api/v1",
    api_key  = os.environ.get("OPENROUTER_API_KEY")
)



WIDTH = 64


def _rule(char="-", width=WIDTH):
    print(char * width)


def _heading(title):
    _rule("=")
    print(f"  {title}")
    _rule("=")


USD_TO_INR_FALLBACK = 94.5


def _money(value):
    return f"${value:.8f}"


def _inr(value):
    return f"₹{value:.4f}"


def usd_to_inr_rate():
    try:
        r = requests.get("https://open.er-api.com/v6/latest/USD", timeout=5)
        r.raise_for_status()
        return float(r.json()["rates"]["INR"])
    except Exception:
        return USD_TO_INR_FALLBACK


def _print_usage(prompt_tokens, completion_tokens, input_cost, output_cost):
    print(f"  Tokens   {prompt_tokens:>6} in   {completion_tokens:>6} out   "
          f"{prompt_tokens + completion_tokens:>6} total")
    print(f"  Cost     {_money(input_cost):>12} in   {_money(output_cost):>12} out   "
          f"{_money(input_cost + output_cost):>12} step")


def _print_kv(label, value, indent=4):
    print(f"{' ' * indent}{label:<10} {value}")


def run_loop(user_input : str, iterations = 2):
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_input_cost = 0.0
    total_output_cost = 0.0

    HISTORY = [
        {
            "role" : "system", "content" : "You're an helpful assistant"
        },
        {
            "role" : "user", "content" : user_input
        }
    ]

    final_message = None

    _heading("Agent run")
    print(f"  Model    {MODEL}")
    print(f"  User     {user_input}")

    for i in range(iterations):
        print()
        _rule()
        print(f"  Step {i + 1} of {iterations}")
        _rule()

        response = client.chat.completions.create(
            model    = MODEL,
            messages = HISTORY,
            tools    = TOOLS
        )

        usage = response.usage
        prompt_tokens = usage.prompt_tokens or 0
        completion_tokens = usage.completion_tokens or 0
        input_cost  = (prompt_tokens / 1_000_000) * INPUT_PRICE_PER_M
        output_cost = (completion_tokens / 1_000_000) * OUTPUT_PRICE_PER_M

        total_prompt_tokens += prompt_tokens
        total_completion_tokens += completion_tokens
        total_input_cost += input_cost
        total_output_cost += output_cost

        finish = response.choices[0].finish_reason
        print(f"  Status   {finish}")
        _print_usage(prompt_tokens, completion_tokens, input_cost, output_cost)

        msg = response.choices[0].message
        HISTORY.append(msg.model_dump(exclude_none = True)) # Remove those properties which has value `None`

        if finish != "tool_calls":
            print()
            print("  Answer")
            answer = (msg.content or "").strip() or "(empty)"
            for line in answer.splitlines():
                print(f"    {line}")
            final_message = msg
            break

        print()
        print("  Tools")
        for n, tool_object in enumerate(response.choices[0].message.tool_calls, start=1):
            arguments = json.loads(tool_object.function.arguments)
            print(f"    [{n}] {tool_object.function.name}")
            _print_kv("args", json.dumps(arguments, ensure_ascii=False), indent=8)

            try:
                result = TOOL_KIT[tool_object.function.name](**arguments)
            except Exception as e:
                result = {"ok": False, "error": str(e)}

            _print_kv("result", json.dumps(result, ensure_ascii=False), indent=8)
            HISTORY.append(
                {
                    'role' : 'tool',
                    'tool_call_id' : tool_object.id,
                    'content' : json.dumps(result)
                }
            )

    print()
    _heading("Totals")
    total_usd = total_input_cost + total_output_cost
    inr_rate = usd_to_inr_rate()
    print(f"  Tokens   {total_prompt_tokens:>6} in   {total_completion_tokens:>6} out   "
          f"{total_prompt_tokens + total_completion_tokens:>6} total")
    print(f"  Cost     {_money(total_input_cost):>12} in   {_money(total_output_cost):>12} out   "
          f"{_money(total_usd):>12} all")
    print(f"  INR      {_inr(total_usd * inr_rate)}   (1 USD = ₹{inr_rate:.2f})")
    _rule("=")

    return final_message


USER_PROMPT = "What is the weather condition at 1. pink city, 2. Capital of gujarat, 3. Capital of maharashtra, 4. ABC City"
run_loop(USER_PROMPT, 5)