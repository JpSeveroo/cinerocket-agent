import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DATABASE_PATH = BASE_DIR / "cinerocket.db"
CACHE_DIR = BASE_DIR / ".cache"

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

MODELOS_OPENROUTER = [
    "qwen/qwen3.8-27b:free",
    "cohere/north-mini-code:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "nvidia/nemotron-3.5-lightning:free",
]

CACHE_VERSION = "v1"
LIMITE_COTA_DIARIA = 50
MAX_RETRIES_SQL = 1
MAX_REQUESTS_POR_PERGUNTA = 8
MAX_LINHAS_RESULTADO = 100

MSG_SEM_MODELOS = (
    "Nenhum modelo gratuito respondeu no momento. "
    "Aguarde alguns instantes ou atualize a lista MODELOS_OPENROUTER em src/config.py."
)


def exigir_chave() -> str:
    """Retorna a chave da API OpenRouter ou levanta erro se não configurada."""
    chave = OPENROUTER_API_KEY.strip()
    if not chave:
        raise RuntimeError(
            "Chave OPENROUTER_API_KEY não configurada. "
            "Copie o arquivo .env.example para .env e preencha sua chave da OpenRouter."
        )
    return chave