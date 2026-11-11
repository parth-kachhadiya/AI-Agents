import os
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


# ---------------------------------------------------------------
load_dotenv()

MODEL = "gpt-4o-mini"
INPUT_PRICE_PER_M  = 0.15
OUTPUT_PRICE_PER_M = 0.60

Client = OpenAI(
    base_url   = "https://openrouter.ai/api/v1",
    api_key    = os.environ.get("OPENROUTER_API_KEY")
)



# ---------------------------------------------------------------
#                           Agent
# ---------------------------------------------------------------

def Agent(user_prompt : str, max_iterations : int = 5):

    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_input_cost = 0.0
    total_output_cost = 0.0


    HISTORY = [
        {
            'role'    : 'user',
            'content' : user_prompt
        }
    ]

    _heading("Agent run")
    print(f"  Model    {MODEL}")
    print(f"  User     {user_prompt}")

    for i in range(max_iterations):

        print()
        _rule()
        print(f"  Iteration {i + 1} of {max_iterations}")
        _rule()


        # <>-------------------< Response >-------------------<>
        response = Client.chat.completions.create(
            model      = MODEL,
            messages   = HISTORY,
            tools      = TOOLS,
            max_tokens = 1000,
            extra_body = {"reasoning" : {'effort' : 'low'}}
        )

        thinking = getattr(response.choices[0].message, 'reasoning', None)
        if thinking:
            _print_answer("Thinking", thinking)

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

        HISTORY.append(msg.model_dump(exclude_none = True))


        # <>-------------------< Loop Termination Condition & Tool Call >-------------------<>
        finish_reason = response.choices[0].finish_reason

        if finish_reason == "stop":
            _print_answer("Answer", msg.content)
            result = {'status' : 'ok', 'message' : msg.content}
            break

        if finish_reason == "length":
            _print_answer("Answer (truncated)", msg.content)
            result = {'status' : 'truncated', 'message' : msg.content}
            break

        if finish_reason == "content_filter":
            blocking_reason = "Your prompt contains content that violates our privacy policy."
            _print_answer("Blocked", blocking_reason)
            result = {'status' : 'blocked', 'message' : blocking_reason}
            break

        if finish_reason == "tool_calls":

            print()
            print("  Tools")

            for n, tool_object in enumerate(msg.tool_calls, start=1):
                
                tool_call_result = execute_tool(tool_object)

                print(f"    [{n}] {tool_object.function.name}")
                _print_kv("args", _shorten(tool_object.function.arguments or "{}"), indent=8)
                _print_kv("result", _shorten(tool_call_result), indent=8)

                HISTORY.append({
                    'role'         : 'tool',
                    'tool_call_id' : tool_object.id,
                    'content'      : tool_call_result
                })

            continue
    
    else:
        result = {'status' : 'max_iterations', 'message' : f'Stopped after `{max_iterations}` iterations.'}
        _print_answer('stopped', result['message'])

    
    _print_totals(total_prompt_tokens, total_completion_tokens, total_input_cost, total_output_cost)
    return result


if __name__ == "__main__":
    prompt = """
        Weather in delhi today.
    """
    Agent(prompt)
