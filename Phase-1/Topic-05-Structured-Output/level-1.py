"""
Level - 1 : Ask in the prompt
• “Reply only with JSON like {...}”. The model usually complies, but sometimes adds Sure! Here's your JSON: or markdown fences, and then json.loads fails. Fragile.
""" 

from shared_setup import (
    client, MODEL, Person, HISTORY
)

try:
    response = client.chat.completions.create(
        model       = MODEL,
        messages    = HISTORY,
        max_tokens  = 800
   )

    raw_content = response.choices[0].message.content

    print("-" * 20 + "< CONTENT >" + "-" * 20)
    print(f"\nRaw Content            : {raw_content}")

    try:
        person = Person.model_validate_json(raw_content)
        print(f"Person pydantic schema : {person}")
    except Exception as e:
        print(f"[JSON-VALIDATION-ERROR] : {str(e)}")

except Exception as e:
    print(f"[MODEL-ERROR] : {str(e)}")
