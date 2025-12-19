from langchain_google_genai import ChatGoogleGenerativeAI
from utils import _set_if_undefined
import os
import itertools
import logging

# Set up all available Google API keys (checking both naming patterns)
api_keys = [
    os.getenv("GOOGLE_API_KEY"),      # Primary key
    os.getenv("GOOGLE_API_KEY_1"),   # Alternative primary
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

def create_gemini_model(model_name="gemini-pro", max_retries=3):
    """Create a Gemini model with API key rotation on failure and optimized parameters."""
    if not api_keys:
        raise ValueError("No Google API keys available")
        
    for attempt in range(max_retries):
        try:
            api_key = get_next_api_key()
            model = ChatGoogleGenerativeAI(
                model=model_name, 
                google_api_key=api_key,
                temperature=0.1,  # Low temperature for consistent parsing
                max_output_tokens=4096,  # Increased for tool calls
                top_p=0.8,  # Focused responses
                top_k=40,   # Balanced creativity
                # Remove convert_system_message_to_human for newer models
            )
            return model
        except Exception as e:
            logging.warning(f"Gemini model {model_name} failed on attempt {attempt + 1}: {e}")
            if attempt == max_retries - 1:
                raise Exception(f"Gemini model {model_name} failed after {max_retries} attempts: {e}")

# Create gemini models with error handling
def safe_create_model(model_key, model_name):
    """Safely create a Gemini model, returning None if it fails."""
    try:
        return create_gemini_model(model_name)
    except Exception as e:
        logging.warning(f"Failed to create Gemini model {model_key} ({model_name}): {e}")
        return None

# Create models dictionary (some may fail and be None)
gemini_models = {}

# List of models to try in order of preference (using current Google model names)
models_to_try = [
    ("gemini-3.0-flash", "gemini-3.0-flash"),
    ("gemini-3.0-pro", "gemini-3.0-pro"),
    ("gemini-3.0-flash-latest", "gemini-3.0-flash-latest"),
    ("gemini-3.0-pro-latest", "gemini-3.0-pro-latest"),
    ("gemini-3.0", "gemini-3.0"),
]

for model_key, model_name in models_to_try:
    model = safe_create_model(model_key, model_name)
    if model is not None:
        gemini_models[model_key] = model
