"""
Level - 2 : JSON Mode
• response_format={"type": "json_object"}. The output is guaranteed to be valid JSON, but not to match your schema. Fields can be missing, renamed, or the wrong type.
"""

from shared_setup import (
    client,
    MODEL,
    Person,
    HISTORY
)

try:
    response = client.chat.completions.create(
        model           = MODEL,
        messages        = HISTORY,
        max_tokens      = 50,
        response_format = {"type" : "json_object"}
    )

    print(response.choices[0])
    raw_response = response.choices[0].message.content

    print("-" * 20 + "< CONTENT >" + "-" * 20)
    print(f"\nRaw Content            : {raw_response}")

    try:
        person = Person.model_validate_json(raw_response)
        print(f"Person pydantic schema : {person}")
    except Exception as e:
        print(f"[JSON-VALIDATION-ERROR] : {str(e)}")

except Exception as e:
    print(f"[LLM-ERROR] : {str(e)}")