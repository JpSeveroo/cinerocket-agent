import sqlite3
from pathlib import Path

from src.config import CACHE_DIR, DATABASE_PATH
from src.database.connection import get_readonly_connection

TABELAS_IGNORADAS = {"alembic_version"}
COLUNAS_IGNORADAS = {
    "dim_movies": {"sinopse", "url_poster", "url_backdrop"},
    "movie_reviews": {"text"},
}


def extract_schema_text(conn: sqlite3.Connection) -> str:
    """Inspeciona o banco SQLite e compila a estrutura das tabelas em DDL simplificado.

    Args:
        conn: Conexão ativa com o banco SQLite.

    Returns:
        String formatada em DDL contendo tabelas, colunas, tipos e relacionamentos.
    """
    cursor = conn.cursor()
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name;"
    )
    tabelas = [row["name"] for row in cursor.fetchall() if row["name"] not in TABELAS_IGNORADAS]

    if not tabelas:
        return ""

    definicoes = []

    for tabela in tabelas:
        cursor.execute(f"PRAGMA table_info('{tabela}');")
        todas_colunas = cursor.fetchall()

        cursor.execute(f"PRAGMA foreign_key_list('{tabela}');")
        fks = cursor.fetchall()

        colunas_ignoradas_tabela = COLUNAS_IGNORADAS.get(tabela, set())
        colunas = [c for c in todas_colunas if c["name"] not in colunas_ignoradas_tabela]

        pks = [c["name"] for c in sorted(colunas, key=lambda x: x["pk"]) if c["pk"] > 0]
        pk_composta = len(pks) > 1

        linhas_tabela = []
        for col in colunas:
            nome = col["name"]
            tipo = col["type"] or "TEXT"
            pk_str = " PRIMARY KEY" if (len(pks) == 1 and col["pk"] > 0) else ""
            linhas_tabela.append(f"  {nome} {tipo}{pk_str}")

        if pk_composta:
            linhas_tabela.append(f"  PRIMARY KEY ({', '.join(pks)})")

        for fk in fks:
            col_origem = fk["from"]
            tab_destino = fk["table"]
            col_destino = fk["to"]
            linhas_tabela.append(
                f"  FOREIGN KEY ({col_origem}) REFERENCES {tab_destino}({col_destino})"
            )

        ddl_tabela = f"CREATE TABLE {tabela} (\n" + ",\n".join(linhas_tabela) + "\n);"
        definicoes.append(ddl_tabela)

    return "\n\n".join(definicoes)


def get_database_schema(db_path: Path = DATABASE_PATH, force_reload: bool = False) -> str:
    """Recupera a descrição do esquema do banco com suporte a cache local.

    Args:
        db_path: Caminho para o arquivo do banco de dados SQLite.
        force_reload: Se True, ignora o cache em disco e força a extração do schema.

    Returns:
        String com a representação em DDL do esquema do banco de dados.
    """
    caminho_banco = Path(db_path).resolve()
    caminho_padrao = Path(DATABASE_PATH).resolve()
    usar_cache = caminho_banco == caminho_padrao
    cache_file = CACHE_DIR / "db_schema.txt"

    if usar_cache and not force_reload and cache_file.exists():
        return cache_file.read_text(encoding="utf-8")

    conn = get_readonly_connection(db_path)
    try:
        schema_text = extract_schema_text(conn)
    finally:
        conn.close()

    if usar_cache:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(schema_text, encoding="utf-8")

    return schema_text