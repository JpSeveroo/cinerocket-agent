import sqlite3

import pytest

from src.config import DATABASE_PATH
from src.database.schema import extract_schema_text, get_database_schema


@pytest.fixture
def banco_temporario(tmp_path):
    """Cria um banco SQLite temporário com tabelas, pontes e tabela técnica de migração."""
    caminho_db = tmp_path / "teste_cinema.db"
    conn = sqlite3.connect(caminho_db)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE alembic_version (
            version_num VARCHAR(32) PRIMARY KEY
        );
    """)
    cursor.execute("""
        CREATE TABLE dim_movies (
            sk_movie_id TEXT PRIMARY KEY,
            titulo TEXT NOT NULL,
            ano_lancamento INTEGER,
            sinopse TEXT,
            url_poster TEXT
        );
    """)
    cursor.execute("""
        CREATE TABLE dim_genres (
            sk_genre_id TEXT PRIMARY KEY,
            nome_genero TEXT NOT NULL
        );
    """)
    cursor.execute("""
        CREATE TABLE bridge_movie_genre (
            sk_movie_id TEXT,
            sk_genre_id TEXT,
            PRIMARY KEY (sk_movie_id, sk_genre_id),
            FOREIGN KEY (sk_movie_id) REFERENCES dim_movies(sk_movie_id),
            FOREIGN KEY (sk_genre_id) REFERENCES dim_genres(sk_genre_id)
        );
    """)
    conn.commit()
    conn.close()
    return caminho_db


def test_extract_schema_text_estrutura_correta(banco_temporario):
    """Garante que a extração DDL omite alembic_version, colunas pesadas e formata PK composta."""
    conn = sqlite3.connect(f"file:{banco_temporario.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        schema = extract_schema_text(conn)
        # Tabelas presentes
        assert "CREATE TABLE dim_movies" in schema
        assert "CREATE TABLE dim_genres" in schema
        assert "CREATE TABLE bridge_movie_genre" in schema

        # alembic_version deve ser ignorada
        assert "alembic_version" not in schema

        # Colunas pesadas de dim_movies devem ser omitidas
        assert "sinopse" not in schema
        assert "url_poster" not in schema

        # PK composta formatada adequadamente em linha única
        assert "PRIMARY KEY (sk_movie_id, sk_genre_id)" in schema
        assert "FOREIGN KEY (sk_movie_id) REFERENCES dim_movies(sk_movie_id)" in schema
    finally:
        conn.close()


def test_cache_schema_apenas_para_banco_padrao(banco_temporario, monkeypatch, tmp_path):
    """Garante que bancos temporários NÃO gravam cache, e que o banco padrão usa cache."""
    cache_mock = tmp_path / ".cache"
    monkeypatch.setattr("src.database.schema.CACHE_DIR", cache_mock)

    # 1. Banco temporário (diferente de DATABASE_PATH) não deve criar nem usar cache
    _ = get_database_schema(db_path=banco_temporario)
    assert not (cache_mock / "db_schema.txt").exists()


    # 2. Quando o caminho coincide com DATABASE_PATH, o cache deve ser criado e reutilizado
    monkeypatch.setattr("src.database.schema.DATABASE_PATH", banco_temporario)
    schema_1 = get_database_schema(db_path=banco_temporario)
    arquivo_cache = cache_mock / "db_schema.txt"
    assert arquivo_cache.exists()
    assert arquivo_cache.read_text(encoding="utf-8") == schema_1

    # Segunda chamada: deve ser idêntica
    schema_2 = get_database_schema(db_path=banco_temporario)
    assert schema_1 == schema_2


def test_inspecao_banco_real_cinerocket():
    """Valida que o banco oficial cinerocket.db é lido com os filtros corretos."""
    if not DATABASE_PATH.exists():
        pytest.skip("cinerocket.db não localizado para teste de integração.")

    schema = get_database_schema(db_path=DATABASE_PATH, force_reload=True)
    assert len(schema) > 0
    assert "CREATE TABLE" in schema
    assert "alembic_version" not in schema
    assert "url_poster" not in schema
    assert "sinopse" not in schema
    assert "PRIMARY KEY (sk_movie_id, sk_person_id)" in schema

    