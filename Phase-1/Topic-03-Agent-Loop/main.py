import os, json, requests
from openai import OpenAI
from dotenv import load_dotenv


load_dotenv()


#   ----------------------------------------------------------
#                             Tools
#   ----------------------------------------------------------

def get_order_status(order_id : str) -> dict:
    fake_db = {"A1042": "shipped", "B2200": "processing"}
    return {'order_id' : order_id, 'status' : fake_db.get(order_id , "Not found")}

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

HISTORY = [
    {
        "role"    : "system",
        "content" : "You're a helpful assistant."
    }
]

client = OpenAI(
    base_url  = "https://openrouter.ai/api/v1",
    api_key   = os.environ.get("OPENROUTER_API_KEY")
)



#   ----------------------------------------------------------
#                          Display
#   ----------------------------------------------------------

WIDTH = 64
USD_TO_INR_FALLBACK = 94.5


def _rule(char="-", width=WIDTH):
    print(char * width)


def _heading(title):
    _rule("=")
    print(f"  {title}")
    _rule("=")


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


def _print_answer(title, text):
    print()
    print(f"  {title}")
    body = (text or "").strip() or "(empty)"
    for line in body.splitlines():
        print(f"    {line}")


def _print_totals(total_prompt_tokens, total_completion_tokens, total_input_cost, total_output_cost):
    total_usd = total_input_cost + total_output_cost
    inr_rate = usd_to_inr_rate()
    print()
    _heading("Totals")
    print(f"  Tokens   {total_prompt_tokens:>6} in   {total_completion_tokens:>6} out   "
          f"{total_prompt_tokens + total_completion_tokens:>6} total")
    print(f"  Cost     {_money(total_input_cost):>12} in   {_money(total_output_cost):>12} out   "
          f"{_money(total_usd):>12} all")
    print(f"  INR      {_inr(total_usd * inr_rate)}   (1 USD = ₹{inr_rate:.2f})")
    _rule("=")


#   ----------------------------------------------------------
#                             Agent
#   ----------------------------------------------------------

def Agent(user_prompt : str, max_iterations : int = 5):
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_input_cost = 0.0
    total_output_cost = 0.0

    HISTORY.append({
        "role"    : "user",
        "content" : user_prompt
    })

    _heading("Agent run")
    print(f"  Model    {MODEL}")
    print(f"  User     {user_prompt}")

    result = {"status": "max_iterations", "message": "Stopped: reached max iterations without a final answer."}

    for i in range(max_iterations):
        print()
        _rule()
        print(f"  Step {i + 1} of {max_iterations}")
        _rule()

        # --------< Get Response >--------
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
        msg = response.choices[0].message

        print(f"  Status   {finish}")
        _print_usage(prompt_tokens, completion_tokens, input_cost, output_cost)

        HISTORY.append(
            msg.model_dump(exclude_none = True)
        )

        # --------< Termination conditions & Tool Call >--------
        if finish == "stop":
            _print_answer("Answer", msg.content)
            result = {"status": "OK", "message": msg.content}
            break

        if finish == "length":
            _print_answer("Answer (truncated)", msg.content)
            result = {"status": "truncated", "message": msg.content}
            break

        if finish == "content_filter":
            blocked = "Your prompt may contains unauthentic message..!"
            _print_answer("Blocked", blocked)
            result = {"status": "blocked", "message": blocked}
            break

        if finish == "tool_calls":
            print()
            print("  Tools")
            for n, tool_object in enumerate(msg.tool_calls, start=1):
                try:
                    args = json.loads(tool_object.function.arguments)
                    tool_result = TOOL_KIT[tool_object.function.name](**args)
                except Exception as e:
                    args = {}
                    tool_result = {"ok": False, "error": str(e)}

                print(f"    [{n}] {tool_object.function.name}")
                _print_kv("args", json.dumps(args, ensure_ascii=False), indent=8)
                _print_kv("result", json.dumps(tool_result, ensure_ascii=False), indent=8)

                HISTORY.append({
                    'role'         : "tool",
                    'tool_call_id' : tool_object.id,
                    'content'      : json.dumps(tool_result)
                })
            continue

        unknown = f"Unknown response type : {finish}"
        _print_answer("Unknown finish", unknown)
        result = {"status": "unknown_finish", "message": unknown}
        break
    else:
        _print_answer("Stopped", result["message"])

    _print_totals(total_prompt_tokens, total_completion_tokens, total_input_cost, total_output_cost)
    return result


if __name__ == "__main__":
    Agent("What is the current weather condition in all cities in Goa.")