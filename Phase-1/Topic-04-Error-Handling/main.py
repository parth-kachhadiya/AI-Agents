import os, json
from openai import OpenAI
from dotenv import load_dotenv
from tool_description import TOOLS
from utils import (
    execute_tool, 
    _rule, 
    _heading, 
    _print_kv, 
    _print_usage, 
    _print_answer, 
    _print_totals, 
    _shorten
)

load_dotenv()

# ----------------------------------------------------------------


MODEL = "gpt-4o-mini"

INPUT_PRICE_PER_M  = 0.15
OUTPUT_PRICE_PER_M = 0.60


HISTORY = [
    {
        "role"     : "system",
        "content"  : "You're a helful assistant."
    }
]

Client = OpenAI(
    base_url  = "https://openrouter.ai/api/v1",
    api_key   = os.environ.get("OPENROUTER_API_KEY")
)



#   ----------------------------------------------------------
#                             Agent
#   ----------------------------------------------------------

def Agent(user_prompt : str, max_iterations : int = 7):


    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_input_cost = 0.0
    total_output_cost = 0.0


    HISTORY.append({
        'role'     : "user",
        'content'  : user_prompt
    })

    _heading("Agent run")
    print(f"  Model    {MODEL}")
    print(f"  User     {user_prompt}")

    for i in range(max_iterations):

        print()
        _rule()
        print(f"  Iteration {i + 1} of {max_iterations}")
        _rule()

        # <>--------------< Get Response >--------------<>
        response = Client.chat.completions.create(
            model      = MODEL,
            messages   = HISTORY,
            tools      = TOOLS,
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

        msg = response.choices[0].message

        print(f"  Status   {response.choices[0].finish_reason}")
        _print_usage(prompt_tokens, completion_tokens, input_cost, output_cost)

        HISTORY.append(
            msg.model_dump(exclude_none = True)
        )


        # <>--------------< Loop Termination Conditions & Tool Call >--------------<>
        reason_of_termination = response.choices[0].finish_reason
 
        if reason_of_termination == "stop":
            _print_answer("Answer", msg.content)
            result = {"status" : "OK", "message" : msg.content}
            break
 
        if reason_of_termination == "length":
            _print_answer("Answer (truncated)", msg.content)
            result = {"status" : "Truncated", "message" : msg.content}
            break
 
        if reason_of_termination == "content_filter":
            blocked = "The response is blocked by provider's safty filters."
            _print_answer("Blocked", blocked)
            result = {"status" : "Blocked", "message" : blocked}
            break
 
        if reason_of_termination == "tool_calls":
 
            print()
            print("  Tools")
            for n, tool_object in enumerate(msg.tool_calls, start=1):
 
                tool_result = execute_tool(tool_object)
 
                print(f"    [{n}] {tool_object.function.name}")
                _print_kv("args", _shorten(tool_object.function.arguments or "{}"), indent=8)
                _print_kv("result", _shorten(tool_result), indent=8)
 
                HISTORY.append({
                    'role'         : "tool",
                    'tool_call_id' : tool_object.id,
                    'content'      : tool_result
                })
 
            continue

    else:
        result = {"status" : "max_iterations", "message" : f"Stopped after {max_iterations} steps without a final answer."}
        _print_answer("Stopped", result["message"])
 
    _print_totals(total_prompt_tokens, total_completion_tokens, total_input_cost, total_output_cost)
    return result

    
if __name__ == "__main__":
    prompt = """
        Follow the order:
        1. Check the current weather condition of Surat city.
        2. Check my current order status, A1042
        3. What is the value of pi in maths.
        4. Check the weather condition of pink city in rajasthan.
    """
    Agent(prompt , max_iterations = 2)