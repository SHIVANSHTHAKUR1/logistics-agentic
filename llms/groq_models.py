from langchain_groq import ChatGroq
import os
from itertools import cycle

from utils import _set_if_undefined

_set_if_undefined("GROQ_API_KEY")
_set_if_undefined("GROQ_API_KEY1")

# Get API keys from environment
api_keys = [
    os.getenv("GROQ_API_KEY"),
    os.getenv("GROQ_API_KEY1")
]

# Filter out None values and create a cycle
valid_keys = [key for key in api_keys if key is not None]
if not valid_keys:
    raise ValueError("No valid GROQ API keys found in environment variables")

key_cycle = cycle(valid_keys)

groq_models = {
    "openai/gpt-oss-20b": ChatGroq(model="openai/gpt-oss-20b", api_key=next(key_cycle)),
    "openai/gpt-oss-120b": ChatGroq(model="openai/gpt-oss-120b", api_key=next(key_cycle)),
    "llama-3.1-8b-instant": ChatGroq(model="llama-3.1-8b-instant", api_key=next(key_cycle)),
    "meta-llama/llama-4-scout-17b-16e-instruct": ChatGroq(model="meta-llama/llama-4-scout-17b-16e-instruct", api_key=next(key_cycle)),  
}