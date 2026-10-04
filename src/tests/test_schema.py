import sqlite3
import pytest
from pathlib import Path
from src.database.schema import extract_schema_text, get_database_schema
from src.config import DATABASE_PATH

@pytest.fixture
def banco_temporario(tmp_path):
    """Cria um banco SQLite temporário com estrutura relacional para teste."""
    caminho_db = tmp_path / "teste_cinema.db"
    conn = sqlite3.connect(caminho_db)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE generos (
            id INTEGER PRIMARY KEY,
            nome TEXT NOT NULL
        );
    """)
    cursor.execute("""
        CREATE TABLE filmes (
            id INTEGER PRIMARY KEY,
            titulo TEXT NOT NULL,
            ano INTEGER,
            genero_id INTEGER,
            FOREIGN KEY (genero_id) REFERENCES generos(id)
        );
    """)
    conn.commit()
    conn.close()
    return caminho_db

def test_extract_schema_text_estrutura_correta(banco_temporario):
    """Garante que a extração DDL inclui tabelas, colunas, tipos e FKs."""
    conn = sqlite3.connect(f"file:{banco_temporario.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        schema = extract_schema_text(conn)
        assert "CREATE TABLE filmes" in schema
        assert "CREATE TABLE generos" in schema
        assert "titulo TEXT" in schema
        assert "ano INTEGER" in schema
        assert "FOREIGN KEY (genero_id) REFERENCES generos(id)" in schema
    finally:
        conn.close()

def test_cache_schema_leitura_e_persistencia(banco_temporario, monkeypatch, tmp_path):
    """Garante que o schema é salvo no cache e reutilizado."""
    cache_mock = tmp_path / ".cache"
    monkeypatch.setattr("src.database.schema.CACHE_DIR", cache_mock)
    
    # Primeira chamada: deve ler o banco e criar o arquivo de cache
    schema_1 = get_database_schema(db_path=banco_temporario)
    arquivo_cache = cache_mock / "db_schema.txt"
    assert arquivo_cache.exists()
    assert arquivo_cache.read_text(encoding="utf-8") == schema_1

    # Segunda chamada: deve carregar direto do cache
    schema_2 = get_database_schema(db_path=banco_temporario)
    assert schema_1 == schema_2

def test_inspecao_banco_real_cinerocket():
    """Valida que o banco oficial cinerocket.db pode ser lido e retorna tabelas válidas."""
    if not DATABASE_PATH.exists():
        pytest.skip("cinerocket.db não localizado para teste de integração.")
        
    schema = get_database_schema(db_path=DATABASE_PATH, force_reload=True)
    assert len(schema) > 0
    assert "CREATE TABLE" in schema
    