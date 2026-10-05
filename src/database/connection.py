import sqlite3
from pathlib import Path

from src.config import DATABASE_PATH


def get_readonly_connection(db_path: Path = DATABASE_PATH) -> sqlite3.Connection:
    """Abre e configura uma conexão SQLite em modo estritamente somente leitura."""
    caminho = Path(db_path).resolve()

    if not caminho.exists():
        raise FileNotFoundError(f"Arquivo de banco de dados não encontrado em: {caminho}")

    uri = f"file:{caminho.as_posix()}?mode=ro"

    conn = sqlite3.connect(uri, uri=True, timeout=5.0, check_same_thread=False)
    conn.execute("PRAGMA query_only = ON;")
    conn.row_factory = sqlite3.Row
    return conn