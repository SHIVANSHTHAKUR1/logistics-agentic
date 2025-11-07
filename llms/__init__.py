# Import models conditionally to avoid import errors
from langchain_google_genai import ChatGoogleGenerativeAI


try:
    from .groq_models import groq_models
except ImportError:
    groq_models = {}

try:
    from .openai_models import openai_models
except ImportError:
    openai_models = {}

try:
    from .gemini_models import gemini_models
except ImportError:
    gemini_models = {
        
    }

try:
    from .ollama_models import ollama_models
except ImportError:
    ollama_models = {}

# Try to find a working model in order of preference
DEFAULT_MODEL = None

# First try Gemini models (prioritized due to token availability)
if DEFAULT_MODEL is None and gemini_models:
    for model_key in ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-2.5-pro", "gemini-flash-latest", "gemini-pro-latest"]:
        if model_key in gemini_models and gemini_models[model_key] is not None:
            try:
                # Test if Gemini actually works
                DEFAULT_MODEL = gemini_models[model_key]
                print(f"Using Gemini model: {model_key}")
                break
            except Exception as e:
                print(f"Warning: Gemini model {model_key} failed: {e}")
                DEFAULT_MODEL = None

# Try Groq models as fallback (tokens may be exhausted)
if DEFAULT_MODEL is None and groq_models:
    for model_key in ["llama-3.1-8b-instant", "llama-3.1-70b-versatile", "mixtral-8x7b-32768"]:
        if model_key in groq_models and groq_models[model_key] is not None:
            DEFAULT_MODEL = groq_models[model_key]
            print(f"Using Groq model (fallback): {model_key}")
            break

# Finally try OpenAI models
if DEFAULT_MODEL is None and openai_models:
    for model_key in ["gpt-4", "gpt-3.5-turbo", "gpt-4-turbo"]:
        if model_key in openai_models and openai_models[model_key] is not None:
            DEFAULT_MODEL = openai_models[model_key]
            print(f"Using OpenAI model (fallback): {model_key}")
            break

# Warning if no models available
if DEFAULT_MODEL is None:
    print("Warning: No LLM models available. Please check your API keys in .env file")
