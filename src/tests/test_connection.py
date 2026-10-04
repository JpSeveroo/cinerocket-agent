import sqlite3
import pytest
from pathlib import Path
from src.database.connection import get_readonly_connection

def test_conexao_leitura_sucesso():
    """Garante que a conexão abre e permite consultas SELECT."""
    conn = get_readonly_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 AS resultado")
        linha = cursor.fetchone()
        assert linha["resultado"] == 1
    finally:
        conn.close()

def test_bloqueio_de_escrita_mode_ro():
    """Garante que comandos de escrita disparam erro de read-only no SQLite."""
    conn = get_readonly_connection()
    try:
        cursor = conn.cursor()
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            cursor.execute("CREATE TABLE tabela_proibida (id INT)")
    finally:
        conn.close()

def test_row_factory_permite_acesso_por_chave():
    """Garante que sqlite3.Row permite acessar colunas pelo nome e por índice."""
    conn = get_readonly_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT 'teste' AS nome, 42 AS valor")
        linha = cursor.fetchone()
        
        # Acesso por nome da coluna
        assert linha["nome"] == "teste"
        assert linha["valor"] == 42
        
        # Acesso por índice posicional
        assert linha[0] == "teste"
        assert linha[1] == 42
    finally:
        conn.close()

def test_arquivo_inexistente_lanca_erro(tmp_path):
    """Garante que FileNotFoundError é lançado se o caminho do banco for inválido."""
    caminho_falso = tmp_path / "banco_que_nao_existe.db"
    
    with pytest.raises(FileNotFoundError):
        get_readonly_connection(db_path=caminho_falso)