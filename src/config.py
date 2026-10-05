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
CACHE_VERSION = "v1"
LIMITE_COTA_DIARIA = 50
MAX_RETRIES_SQL = 1
MAX_REQUESTS_POR_PERGUNTA = 4   # Teto de segurança do agent

MAX_LINHAS_RESULTADO = 100  # Limite padrão de retorno das queries

MSG_SEM_MODELOS = (
    "Nenhum modelo gratuito respondeu agora. Rode notebooks/escolher_modelos.ipynb, "
    "cole a linha MODELOS_OPENROUTER no arquivo .env e reinicie a aplicação."
)


def exigir_chave() -> str:
    """Retorna a chave da API OpenRouter ou levanta erro se não configurada."""
    chave = os.getenv("OPENROUTER_API_KEY", "") or OPENROUTER_API_KEY
    if not chave or not chave.strip():
        raise RuntimeError(
            "Chave OPENROUTER_API_KEY não configurada. "
            "Copie o arquivo .env.example para .env e preencha sua chave da OpenRouter."
        )
    return chave.strip()