import sqlite3
from pathlib import Path
from src.config import DATABASE_PATH, CACHE_DIR
from src.database.connection import get_readonly_connection

def extract_schema_text(conn: sqlite3.Connection) -> str:
    """
    Inspeciona o banco SQLite e compila a estrutura das tabelas em DDL simplificado.
    Captura nomes de tabelas, colunas, tipos, PKs e chaves estrangeiras.
    """
    cursor = conn.cursor()
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name;"
    )
    tabelas = [row["name"] for row in cursor.fetchall()]
    
    if not tabelas:
        return ""
    
    definicoes = []
    
    for tabela in tabelas:
        cursor.execute(f"PRAGMA table_info('{tabela}');")
        colunas = cursor.fetchall()
        
        cursor.execute(f"PRAGMA foreign_key_list('{tabela}');")
        fks = cursor.fetchall()
        
        linhas_colunas = []
        for col in colunas:
            nome = col["name"]
            tipo = col["type"] or "TEXT"
            pk = " PRIMARY KEY" if col["pk"] else ""
            linhas_colunas.append(f"  {nome} {tipo}{pk}")
            
        for fk in fks:
            col_origem = fk["from"]
            tab_destino = fk["table"]
            col_destino = fk["to"]
            linhas_colunas.append(
                f"  FOREIGN KEY ({col_origem}) REFERENCES {tab_destino}({col_destino})"
            )
            
        ddl_tabela = f"CREATE TABLE {tabela} (\n" + ",\n".join(linhas_colunas) + "\n);"
        definicoes.append(ddl_tabela)
        
    return "\n\n".join(definicoes)

def get_database_schema(db_path: Path = DATABASE_PATH, force_reload: bool = False) -> str:
    """
    Recupera a descrição do esquema do banco.
    Lê do cache em .cache/db_schema.txt se disponível, caso contrário inspeciona
    o banco e gera o arquivo de cache para as próximas chamadas.
    """
    cache_file = CACHE_DIR / "db_schema.txt"
    
    if not force_reload and cache_file.exists():
        return cache_file.read_text(encoding="utf-8")
        
    conn = get_readonly_connection(db_path)
    try:
        schema_text = extract_schema_text(conn)
    finally:
        conn.close()
        
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(schema_text, encoding="utf-8")
    
    return schema_text