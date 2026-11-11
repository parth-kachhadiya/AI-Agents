"""
Level - 4 : Force a tool call
• No loop and no tool execution here. The “tool” is only a container for the answer shape, and you never run save_person. Notice the finish_reason is now tool_calls, not stop, even though nothing will be executed.
"""

from shared_setup import (
    client,
    PROMPT,
    Person,
    MODEL
)
import json


TOOLS = [
    {
        "type"     : "function",
        "function" : {
            "name"        : "save_person",
            "description" : "Save the extracted person details.",
            "parameters"  : Person.model_json_schema()
        }
    }
]

try:
    response = client.chat.completions.create(
        model       = MODEL,
        max_tokens  = 200,
        messages    = [
            {
                'role'    : 'user',
                'content' : f'Extract the person details. \nText : {PROMPT}' 
            }
        ],
        tools       = TOOLS,
        tool_choice = {
            "type"     : "function",
            "function" : { 'name' : 'save_person' }
        }
    )

    tool_calls = response.choices[0].message.tool_calls

    print("-" * 20 + "< CONTENT >" + "-" * 20)
    print(f"\nRaw Content            : {tool_calls[0].model_dump()}")
    print(f"\nRaw Content            : {tool_calls[0].function.arguments}")

    try:
        person = Person.model_validate_json(tool_calls[0].function.arguments)
        print(f"Person pydantic schema : {person}")
    except Exception as e:
        print(f"[JSON-VALIDATION-ERROR] : {str(e)}")


except Exception as e:
    print(f"[LLM-ERROR] : {str(e)}")