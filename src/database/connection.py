import sqlite3
from pathlib import Path
from src.config import DATABASE_PATH

def get_readonly_connection(db_path: Path = DATABASE_PATH) -> sqlite3.Connection:
    caminho = Path(db_path).resolve()
    
    if not caminho.exists():
        raise FileNotFoundError(f"Arquivo de banco de dados não encontrado em: {caminho}")
    
    # Monta a URI padrão exigida pelo SQLite para modo somente leitura
    uri = f"file:{caminho.as_posix()}?mode=ro"
    
    conn = sqlite3.connect(uri, uri=True, timeout=5.0)
    conn.row_factory = sqlite3.Row
    return conn