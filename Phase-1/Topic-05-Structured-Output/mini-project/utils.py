import json, requests
from pydantic import ValidationError
from tool_description import (
    TOOL_KIT
)

# ----------------------------------------------------------------
#                        Helper Functions
# ----------------------------------------------------------------

def _err(msg : str) -> str:
    return json.dumps({"ok" : False, "error" : msg})


def execute_tool(call) -> str:
    
    tool_name = call.function.name

    # --------------< Identify Unknown Tool >--------------
    if tool_name not in TOOL_KIT:
        return _err(f"Unknown tool '{tool_name}' identified. Accessable tools are : {', '.join(TOOL_KIT)}")

    args_model, tool = TOOL_KIT[tool_name]
    
    
    # --------------< Valid JSON Schema >--------------
    try:
        raw_response = json.loads(call.function.arguments or "{}")
    except json.JSONDecodeError as jde:
        return _err("Arguments were not in valid JSON format. Send complete JSON matching tool schema.")
    if not isinstance(raw_response, dict):
        return _err("Arguments must be JSON object.")


    # --------------< Validation Agains Schema >--------------
    try:
        arguments = args_model(**raw_response)
    except ValidationError as ve:
        problems = "; ".join(
            f"{'.'.join(str(p) for p in err['loc']) or 'arguments'} : {err['msg']}" for err in ve.errors()
        )
        return _err(f"Invalid arguments : {problems}")


    # --------------< Tool Execution >--------------
    try:
        tool_call_result = tool(**arguments.model_dump())
    except Exception as e:
        print(f"[TOOL-BUG] : {tool_name} , {e!r}")
        return _err(f"Tool '{tool_name}' failed internally, don't guess result; tell the user.")

    return tool_call_result.model_dump_json(exclude_none = True)



#   ----------------------------------------------------------
#                       Display Functions
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
 

