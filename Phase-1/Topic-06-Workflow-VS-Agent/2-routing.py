from pydantic import BaseModel, ValidationError
from typing import Literal
from shared_setup import Ask



class Route(BaseModel):
    kind   : Literal["math", "travel", "other"]

HANDLERS = {
    "math"   : "You're a math tutor. Show short steps.",
    "travel" : "You're a travel guide. Give 3 short tips.",
    "other"  : "You're a helpful assistant. Be brief."
}


def Routing(question : str):
    raw = Ask(f'Classift the asked question as `math` or `travel` or `other`. Reply as JSON : {{"kind" : "..."}} . Question : {question}')
    print(f"[Step-1] : Got answer from LLM : {raw}")
    try:
         kind = Route.model_validate_json(raw).kind
         print("• Schema Validation passed ✅")
    except ValidationError:
        kind = "other"
        print("• Schema Validation failed ❌")

    print("[Step-2] : Final answer on screen.")
    return Ask(question, system_prompt = HANDLERS[kind])

question_bank = [
    "What is the actual value of PI.",
    "Listdown all famous tourist places in goa.",
    "What is the full form of AGI."
]

print(Routing(question_bank[2]))