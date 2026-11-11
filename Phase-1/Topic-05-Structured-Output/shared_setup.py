import os
from typing import Required
from openai import OpenAI
from pydantic import BaseModel, ConfigDict, Field
from dotenv import load_dotenv


load_dotenv()


client = OpenAI(
    base_url = "https://openrouter.ai/api/v1",
    api_key  = os.environ.get("OPENROUTER_API_KEY")
)

MODEL = "gpt-4o-mini"
PROMPT = "My friend ravi is 25 years old and lives in Surat."

HISTORY = [
    {
        'role'    : "user",
        'content' : f'Extract `name`, `age` and `city`. Reply with ONLY JSON formate like : {{"name" : "...", "age" : 0, "city" : "..."}} , user message : {PROMPT}'
    }
]

class Person(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1)   # min_length blocks ""
    age:  int | None = Field(default=None, ge=0, le=130)
    city: str | None = Field(default=None, min_length=1)