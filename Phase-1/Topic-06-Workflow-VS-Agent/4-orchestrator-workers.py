from concurrent.futures import ThreadPoolExecutor
from pydantic import BaseModel
from shared_setup import Ask


class Plan(BaseModel):
    subtasks : list[str]


def Orchestrator(goal : str):
    raw = Ask(
        prompt           = f'Split this goal into 3 short subtasks. Reply as JSON : {{"subtasks" : ["...", "..."]}}\n Goal : {goal}',
        temperature      = 0,
        response_as_json = True    
    )

    print(f"• [Step - 1 : LLM Response] : {raw}")

    plan = Plan.model_validate_json(raw)
    tasks = plan.subtasks

    with ThreadPoolExecutor() as pool:
        results = list(pool.map(lambda t : Ask(f"Do this one subtask (Out of 3) into 2-3 sentences : {t}"), tasks))

    return Ask(f"Combine these into one short answer : \n{results}")


print(f'• [Step - 2 : Final Answer] : {Orchestrator("Make a cup of tea.")}')
