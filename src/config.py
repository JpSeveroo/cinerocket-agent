import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DATABASE_PATH = BASE_DIR / "cinerocket.db"
CACHE_DIR = BASE_DIR / ".cache"

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Modelos padrão gratuitos (:free) validados com Tool Calling
MODELOS_PADRAO = [
    "qwen/qwen3.8-27b:free",
    "cohere/north-mini-code:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "nvidia/nemotron-3.5-lightning:free",
]

# Lê do .env se houver customização; caso contrário, adota a lista padrão testada
_modelos_env = [
    m.strip() for m in os.getenv("MODELOS_OPENROUTER", "").split(",") if m.strip()
]
MODELOS_OPENROUTER = _modelos_env if _modelos_env else MODELOS_PADRAO

# Constantes do fluxo
LIMITE_COTA_DIARIA = 50
MAX_RETRIES_SQL = 1
MAX_REQUESTS_POR_PERGUNTA = 4   # Teto de segurança do agent