import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    base_url = "https://openrouter.ai/api/v1",
    api_key = os.environ.get("OPENROUTER_API_KEY")
)

response = client.chat.completions.create(
    model = "gpt-4o-mini",
    max_tokens = 200,
    messages = [
        {
            "role"    : "system",
            "content" : "You're a terse assistant." 
        },
        {
            "role"    : "user",
            "content" : "Explain, what an AI Agent is like you're explainint to your best friend. in non-technical words."
        }
    ]
)

# Pretty-print the full response as nested JSON
print(json.dumps(response.model_dump(), indent=2, default=str))

print("\n--- Assistant message ---")
print(response.choices[0].message.content)
