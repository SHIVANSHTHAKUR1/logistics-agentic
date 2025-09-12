# Import models conditionally to avoid import errors
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
    gemini_models = {}

try:
    from .ollama_models import ollama_models
except ImportError:
    ollama_models = {}

# DEFAULT_MODEL = groq_models["meta-llama/llama-4-scout-17b-16e-instruct"]
# DEFAULT_MODEL = ollama_models["gpt-oss:20b"]
DEFAULT_MODEL = openai_models.get("gpt-4o-mini")

__all__ = ["groq_models", "openai_models", "gemini_models", "ollama_models", "DEFAULT_MODEL"]