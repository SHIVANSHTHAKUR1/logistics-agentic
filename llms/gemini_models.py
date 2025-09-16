from langchain_google_genai import ChatGoogleGenerativeAI
from utils import _set_if_undefined
import os
import itertools
import logging

# Set up all 5 Google API keys
api_keys = [
    os.getenv("GOOGLE_API_KEY_1"),
    os.getenv("GOOGLE_API_KEY_2"), 
    os.getenv("GOOGLE_API_KEY_3"),
    os.getenv("GOOGLE_API_KEY_4"),
    os.getenv("GOOGLE_API_KEY_5")
]

# Filter out None values
api_keys = [key for key in api_keys if key]

if not api_keys:
    raise ValueError("No Google API keys found in environment variables")

# Create a rotating iterator
key_rotation = itertools.cycle(api_keys)

def get_next_api_key():
    """Get the next API key in rotation"""
    return next(key_rotation)

def create_gemini_model(model_name, max_retries=5):
    """Create a Gemini model with API key rotation on failure and optimized parameters."""
    for attempt in range(max_retries):
        try:
            api_key = get_next_api_key()
            return ChatGoogleGenerativeAI(
                model=model_name, 
                google_api_key=api_key,
                temperature=0.1,  # Low temperature for consistent parsing
                max_output_tokens=2048,  # Reasonable limit for JSON responses
                top_p=0.8,  # Focused responses
                top_k=40,   # Balanced creativity
            )
        except Exception as e:
            logging.warning(f"API key failed on attempt {attempt + 1}: {e}")
            if attempt == max_retries - 1:
                raise Exception("All API keys failed")
    

gemini_models = {
    #  models
    "gemini-1.5-flash": create_gemini_model("gemini-1.5-flash"),
    "gemini-1.5-pro": create_gemini_model("gemini-1.5-pro"),

    # Gemini 2.5 Models
    "gemini-2.5-pro": create_gemini_model("gemini-2.5-pro"),
    "gemini-2.5-flash": create_gemini_model("gemini-2.5-flash"),
    "gemini-2.5-flash-lite": create_gemini_model("gemini-2.5-flash-lite"),
    "gemini-2.5-pro-deep-think": create_gemini_model("gemini-2.5-pro-deep-think"),
}
