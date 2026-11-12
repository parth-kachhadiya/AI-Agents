import os
from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()

Client = OpenAI(
    base_url   = "https://openrouter.ai/api/v1",
    api_key    = os.environ.get("OPENROUTER_API_KEY")
)

MODEL = "gpt-4o-mini"
CALLS = 0


def Ask(prompt : str, system_prompt : str = "You're a helpful assistant.", temperature : float = 0.7, response_as_json : bool = False):
    global CALLS
    CALLS += 1
    
    extra = {"response_format" : {"type" : "json_object"}} if response_as_json else {}

    response = Client.chat.completions.create(
        model       = MODEL,
        max_tokens  = 400,
        temperature = temperature,
        messages    = [
            {
                'role'    :  'system',
                'content' : system_prompt  
            },
            {
                'role'    : 'user',
                'content' : prompt 
            }
        ],
        **extra 
    )

    return response.choices[0].message.content or ""