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

DEFAULT_MODEL = groq_models.get("meta-llama/llama-4-scout-17b-16e-instruct")
if DEFAULT_MODEL is None:
    DEFAULT_MODEL = gemini_models.get("gemini-1.5-flash")
# DEFAULT_MODEL = ollama_models["gpt-oss:20b"]
# DEFAULT_MODEL = openai_models.get("gpt-4o-mini")

__all__ = ["groq_models", "openai_models", "gemini_models", "ollama_models", "DEFAULT_MODEL"]