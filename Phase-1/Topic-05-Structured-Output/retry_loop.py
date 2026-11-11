import json
from pydantic import ValidationError
from shared_setup import (
    Person, client, MODEL
)

DEFAULT_SYSTEM_PROMPT = (
    "Extract name, age and city from the user message."
    "Reply with ONLY a JSON object with exactly these keys : name, age, city."
    "Use only informations written in the user message."
    "If value is not written there, use null. never make any guess or invent any value."
)

def is_grounded(source : str, value : str) -> bool:
    """
    Does value text exist in source text or not?
    """
    return str(value).lower() in source.lower()

def validator(prompt : str, model_class, max_retries : int = 3) -> dict:
    
    schema_hint = json.dumps(model_class.model_json_schema())

    HISTORY = [
        {
            'role'    : 'system',
            'content' : DEFAULT_SYSTEM_PROMPT
        },
        {
            'role'    : 'user',
            'content' : prompt
        }
    ]

    value, missing = None, list(Person.model_fields)

    for attempt in range(max_retries):
        response = client.chat.completions.create(
            model           = MODEL,
            messages        = HISTORY,
            max_tokens      = 300,
            response_format = {'type' : 'json_object'}
        )

        choice      = response.choices[0]
        raw_content = choice.message.content or ""

        print(f"Attempt {attempt + 1} : finish_reason = {choice.finish_reason} , token_in = {response.usage.prompt_tokens}")

        # >-----------< 1. Cut Off ? : Retrying with the same length would cut off again..!! >-----------<
        if choice.finish_reason == "length":
            return {'status' : 'Truncated', 'data' : None, 'error' : 'Output hit max_tokens limit.!'}

        try:
            person = Person.model_validate_json(raw_content)
        except ValidationError as ve:
            # Format problems : bad JSON, wrong type, empty string, extra keys
            problems = "; ".join(
                f"{'.'.join(str(p) for p in err['loc']) or 'JSON'}: {err['msg']}" for err in ve.errors()
            )
            feedback = (
                f"Your reply wasn't valid : {problems}"
                "Reply with ONLY a JSON object with keys name , age and city."
            )
        else:
            value = person.model_dump()

            # <>----< 1. Identify those values which are invented by LLM and were not present in user prompt >----<>
            invented = [k for k, v in value.items() if v is not None and not is_grounded(prompt, v)]

            # <>----< 2. Make those invented values None >----<>
            for k in invented:
                value[k] = None

            # <>----< 3. Identify missing values >----<>
            missing = [k for k, v in value.items() if v is None]

            if not missing:
                return {'status' : 'ok', 'data' : value, 'missing' : []}

            feedback = ""
            
            # <>----< 4. If there is any invented value, add feedback for LLM >----<>
            if invented:
                feedback += f"The values for {invented} do not appear in the user message, so they were rejected. "
            
            feedback += (f"Fields still empty: {missing}. Read the user message again. "
                         f"If a value is written there, copy it exactly as written. "
                         f"If it is not written there, keep it null. Never guess.")

        HISTORY.append({'role' : 'assistant', 'content' : raw_content})
        HISTORY.append({'role' : 'user'     , 'content' : feedback})    
            
    if value is None:
        return {'status' : 'invalid', 'data' : None, 'missing' : missing}

    return {'status' : 'incomplete', 'data' : value, 'missing' : missing}

if __name__ == "__main__":
    test_cases = [
        "Parth lives in surat. his age is 25 years old.",
        "Parth is 25 years old.",
        "That person lives in Surat."
    ]

    for test_prompt in test_cases:
        print("\n\n<>" + "-" * 50 + "<>")
        print(f"[USER] : {test_prompt}")
        print(validator(test_prompt, Person))