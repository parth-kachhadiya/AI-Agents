import os, json, requests
from openai import OpenAI
from dotenv import load_dotenv
from tools import (
    CODING_TOOLS, CODING_TOOL_KIT
)

load_dotenv()

MODEL = "gpt-4o-mini"
INPUT_PRICE_PER_M  = 0.15
OUTPUT_PRICE_PER_M = 0.60

HISTORY = [
    {
        "role"    : "system",
        "content" : "You're a intelligent coding assistant."
    }
]

client = OpenAI(
    base_url = "https://openrouter.ai/api/v1",
    api_key  = os.environ.get("OPENROUTER_API_KEY")
)


#   ----------------------------------------------------------
#                          Display
#   ----------------------------------------------------------

WIDTH = 64
USD_TO_INR_FALLBACK = 94.5
DISPLAY_LIMIT = 400     # display only: long tool results are cut on screen, not in HISTORY


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


def _shorten(text, limit=DISPLAY_LIMIT):
    text = str(text)
    if len(text) <= limit:
        return text
    return text[:limit] + f"... [+{len(text) - limit} chars hidden on screen]"


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
#                             Coder
#   ----------------------------------------------------------

def Coder(user_prompt : str, max_iterations : int = 5):

    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_input_cost = 0.0
    total_output_cost = 0.0

    HISTORY.append({
        'role'    : "user",
        'content' : user_prompt
    })

    _heading("Coder run")
    print(f"  Model    {MODEL}")
    print(f"  User     {user_prompt}")

    for i in range(max_iterations):

        print()
        _rule()
        print(f"  Step {i + 1} of {max_iterations}")
        _rule()

        response = client.chat.completions.create(
            model    = MODEL,
            messages = HISTORY,
            tools    = CODING_TOOLS,
            max_tokens = 1000
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

        # >------------------< Loop Break Condition & Tool Calling >------------------<
        if finish == "stop":
            _print_answer("Answer", msg.content)
            result = {"status" : "ok", "message" : msg.content}
            break

        elif finish == "length":
            _print_answer("Answer (truncated)", msg.content)
            result = {"status" : "truncated", "message" : msg.content}
            break

        elif finish == "content_filter":
            blocked = "Your prompt may contains unauthentic message..!"
            _print_answer("Blocked", blocked)
            result = {"status" : "blocked", "message" : blocked}
            break

        elif finish == "tool_calls":

            print()
            print("  Tools")
            for n, tool_object in enumerate(msg.tool_calls, start=1):
                try:
                    args = json.loads(tool_object.function.arguments)
                    tool_result = CODING_TOOL_KIT[tool_object.function.name](**args)
                except Exception as e:
                    args = {}
                    tool_result = {"ok" : False, "error" : str(e)}

                print(f"    [{n}] {tool_object.function.name}")
                _print_kv("args", _shorten(json.dumps(args, ensure_ascii=False)), indent=8)
                _print_kv("result", _shorten(json.dumps(tool_result, ensure_ascii=False)), indent=8)

                HISTORY.append({
                    'role'         : "tool",
                    'tool_call_id' : tool_object.id,
                    'content'      : json.dumps(tool_result)
                })

        else:
            unknown = f"Unknown response type : {finish}"
            _print_answer("Unknown finish", unknown)
            result = {"status" : "unknown_finish", "message" : unknown}
            break
    else:
        result = {"status": "max_iterations",
              "message": f"Stopped after {max_iterations} steps without a final answer."}
              
    _print_totals(total_prompt_tokens, total_completion_tokens, total_input_cost, total_output_cost)
    return result


if __name__ == "__main__":
    while True:
        user_message = input("\n[USER] : ")
        answer = Coder(user_message)
        print(f"[CODER] : ", end="")
        _print_answer('Answer', answer['message'])