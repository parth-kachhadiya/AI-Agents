import os, json, requests
from dotenv import load_dotenv
from openai import OpenAI


# >---------------------------------< Setup >---------------------------------<
load_dotenv()

client = OpenAI(
    base_url = "https://openrouter.ai/api/v1",
    api_key  = os.environ["OPENROUTER_API_KEY"]
)

MODEL              = "openrouter/free"   
HAYSTACK_STORE     = "json_files\\context-rot.json"
SYSTEM_PROMPT      = {
    'role'    : 'system',
    'content' : (
        "Answer the question using only the provided context. "
        "Return only the answer, without explanation. "
        "If the answer cannot be determined, return UNKNOWN."
    )
}

HISTORY = [SYSTEM_PROMPT.copy()]



# >---------------------------------< Check Token Balance >---------------------------------<

response = requests.get(
    "https://openrouter.ai/api/v1/key",
    headers={"Authorization": f"Bearer {os.environ.get('OPENROUTER_API_KEY')}"}
)

data = response.json()['data']

print("Credits remaining ($):", data.get("limit_remaining"))  # None if no key cap is set
print("Total usage ($):", data.get("usage"))
print("Free tier status:", data.get("is_free_tier"))



# >---------------------------------< Test Cases >---------------------------------<

TEST_CASES = [
    {
        "type": "DIRECT",
        "question": "Which programming language does Parth love the most?",
        "needle": (
            "Parth loves the Python programming language "
            "more than any other programming language."
        ),
        "expected_answer": "Python"
    },
    {
        "type": "INDIRECT",
        "question": "Which programming language does Parth love the most?",
        "needle": (
            "Parth's favourite programming language is the one "
            "whose official package installer is called pip "
            "and which is widely used in Machine Learning "
            "and Data Science."
        ),
        "expected_answer": "Python"
    }
]


# >---------------------------------< Configurations >---------------------------------<
QUESTION = "Which programming language does Parth love the most?"
  
EXPECTED_ANSWER = "Python"
  
TEST_TYPES = ["direct", "indirect"]
  
with open(HAYSTACK_STORE, "r", encoding="utf-8") as file:
    CONTEXTS = json.load(file)


# >---------------------------------< LLM Call >---------------------------------<

def run_test(context : str) -> dict:

    his = HISTORY.copy()

    his.append({
        'role'   : 'user',
        'content': (
            f"<context>\n{context}\n</context>\n\n"
            f"Question: {QUESTION}"
        )
    })

    response = client.chat.completions.create(
        model       = MODEL,
        messages    = his,
        temperature = 0,
        max_tokens  = 2000,
        extra_body  = {
            "reasoning" : {
                "enabled" : False
            }
        }
    )

    print(f"  Actual Model  : {response.model}")
    print(f"  Finish Reason : {response.choices[0].finish_reason}")
    print(f"  Raw Answer    : {response.choices[0].message.content!r}")
    
    answer = (response.choices[0].message.content or "").strip()

    is_correct = (
        answer.lower().strip(" .\"'") == EXPECTED_ANSWER.lower()
    )

    return {
        "answer": answer,
        "expected": EXPECTED_ANSWER,
        "is_correct": is_correct,
        "input_tokens": response.usage.prompt_tokens,
        "output_tokens": response.usage.completion_tokens
    }



# >---------------------------------< Experiment >---------------------------------<

def main():

    results = []

    print("=" * 65)
    print("                 CONTEXT ROT EXPERIMENT")
    print("=" * 65)

    print(f"Model       : {MODEL}")
    print(f"Contexts    : {len(CONTEXTS)}")
    print(f"Total Tests : {len(CONTEXTS) * len(TEST_TYPES)}")

    for context in CONTEXTS:

        print("\n" + "=" * 65)
        print(f"CONTEXT {context['id']}")
        print(f"Words : {context['background_words']:,}")
        print("=" * 65)

        for test_type in TEST_TYPES:

            print(f"\n  Test Type : {test_type.upper()}")
            print("  " + "-" * 45)

            try:

                result = run_test(context[test_type])

                result["context_id"] = context["id"]
                result["test_type"] = test_type
                result["context_words"] = len(
                    context[test_type].split()
                )

                results.append(result)

                print(f"  Input Tokens  : {result['input_tokens']:,}")
                print(f"  Output Tokens : {result['output_tokens']:,}")
                print(f"  Expected      : {result['expected']}")
                print(f"  Actual        : {result['answer']}")

            except Exception as error:

                print(f"  Error : {error}")

                results.append({
                    "context_id": context["id"],
                    "test_type": test_type,
                    "error": str(error)
                })


    # >----------------------< Summary >----------------------<

    print("\n" + "=" * 85)
    print("                          FINAL SUMMARY")
    print("=" * 85)

    print(f"{'Words':<12}{'Direct Answer':<35}{'Indirect Answer':<35}")
    print("-" * 85)

    for context in CONTEXTS:

        answers = {}

        for result in results:

            if result["context_id"] != context["id"]:
                continue

            answer = result.get("answer", "API ERROR")

            answers[result["test_type"]] = answer or "[EMPTY RESPONSE]"

        print(
            f"{context['background_words']:<12,}"
            f"{answers.get('direct', 'N/A'):<35}"
            f"{answers.get('indirect', 'N/A'):<35}"
        )

    print("=" * 85)

    # Save experimental results

    with open("results.json", "w", encoding="utf-8") as file:
        json.dump(results, file, indent=4)

    print("\nResults saved to results.json")


if __name__ == "__main__":
    main()