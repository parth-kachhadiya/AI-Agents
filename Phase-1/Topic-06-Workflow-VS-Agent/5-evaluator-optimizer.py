from shared_setup import Ask
from pydantic import BaseModel


class Verdict(BaseModel):
    passed     : bool
    feedback   : str 


def EvalOpt(topic : str, max_iterations : int = 3):

    draft = Ask(f"Write a 2 sentence description of given topic : {topic}.")

    for _ in range(max_iterations):

        print("\n" + "-" * 30 + f"< Iteration - {_ + 1} >" + "-" * 30)

        raw = Ask(f'''
            Critique this topic description : "{draft}".
            Rules : Under 30 words, and it names one concrete benefit.
            Reply as JSON : {{"passed" : true, "feedback" : "..."}} , no extra text or special-characters etc..
        ''')

        print(f"\t• [Step - 1 : LLM Response] : {raw}")

        verdict = Verdict.model_validate_json(raw)

        print(f"\t• [Step - 2 : Schema Validation] : Schema Validation passed ✅ `{verdict}`")

        if verdict.passed:
            return draft

        print("\t• [Step - 3 : Verdict Failed] : Trying again..")

        draft = Ask(f'''
            Rewrite the text using this feedback : {verdict.feedback}.
            Text : {draft}.
            Reply with only the new text.
        ''')



    
    return draft



print(EvalOpt("AGI"))