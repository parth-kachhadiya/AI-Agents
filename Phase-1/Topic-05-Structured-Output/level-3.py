"""
Level - 3 : JSON Schema mode (Strict)
• The schema is passed to the API.
• With strict: True, the output is constrained while it’s generated, so it follows the schema. The model can’t emit a field that isn’t allowed. This is the strongest option when it’s supported.
• Notice the prompt says nothing about format. The schema does all the work, and the output is constrained while it is generated. require_parameters stops OpenRouter from quietly routing you to a provider that ignores response_format. If your chosen provider doesn’t support it, you’ll get an error instead, which is better than silent failure.
"""

from shared_setup import (
    client,
    MODEL,
    PROMPT,
    Person
)

try:
    response = client.chat.completions.create(
        model           = MODEL,
        max_tokens      = 100,
        response_format = {
            "type"        : "json_schema",
            "json_schema" : {
                "name"   : "person",
                "strict" : True,
                "schema" : Person.model_json_schema()  # Our pydantic model is the schema
            }
        },
        extra_body      = {
            "provider" : {"require_parameters" : True}  # OpenRouter : only use providers that supports this
        },
        messages        = [
            {
                'role'    : 'user',
                'content' : f'Extract the person details. \nText : {PROMPT}' 
            }
        ]
    )

    raw_response = response.choices[0].message.content

    print("-" * 20 + "< CONTENT >" + "-" * 20)
    print(f"\nRaw Content            : {raw_response}")
    print(f"Provider               : {response.provider}")

    try:
        person = Person.model_validate_json(raw_response)
        print(f"Person pydantic schema : {person}")
    except Exception as e:
        print(f"[JSON-VALIDATION-ERROR] : {str(e)}")


except Exception as e:
    print(f"[LLM-ERROR] : {str(e)}")