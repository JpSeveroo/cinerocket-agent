from src.agent.models import TurnoMemoria
from src.agent.prompts import formatar_historico, montar_system_prompt


def test_montar_system_prompt_sem_historico():
    """Garante inclusão de instruções e schema, e ausência de histórico quando não fornecido."""
    schema_mock = "CREATE TABLE dim_movies (sk_movie_id TEXT PRIMARY KEY, titulo TEXT);"
    prompt = montar_system_prompt(schema_ddl=schema_mock)

    assert "Analista Sênior de Dados Cinematográficos" in prompt
    assert "### ESQUEMA DO BANCO DE DADOS (SQLITE)" in prompt
    assert schema_mock in prompt
    assert "### HISTÓRICO RECENTE DA CONVERSA" not in prompt


def test_montar_system_prompt_com_historico():
    """Valida se instâncias de TurnoMemoria são formatadas e anexadas adequadamente."""
    schema_mock = "CREATE TABLE dim_movies (sk_movie_id TEXT PRIMARY KEY);"
    historico = [
        TurnoMemoria(
            pergunta="Quais os top 5 filmes?",
            sql="SELECT titulo FROM dim_movies LIMIT 5;",
            resumo="Retornou 5 filmes populares.",
        ),
        TurnoMemoria(
            pergunta="E o faturamento deles?",
            sql="SELECT f.receita_brl FROM fact_movies_performance f;",
            resumo="Faturamento detalhado em reais.",
        ),
    ]

    prompt = montar_system_prompt(schema_ddl=schema_mock, historico=historico)

    assert "### HISTÓRICO RECENTE DA CONVERSA" in prompt
    assert "- Usuário: Quais os top 5 filmes?" in prompt
    assert "SQL: SELECT titulo FROM dim_movies LIMIT 5;" in prompt
    assert "Resultado resumido: Retornou 5 filmes populares." in prompt
    assert "- Usuário: E o faturamento deles?" in prompt


def test_formatar_historico_vazio_ou_nulo():
    """Garante que histórico vazio ou None retorne string vazia."""
    assert formatar_historico(None) == ""
    assert formatar_historico([]) == ""


def test_diretrizes_sqlite_presentes():
    """Assegura presença de instruções críticas do dialeto SQLite."""
    prompt = montar_system_prompt(schema_ddl="CREATE TABLE teste (id INT);")

    assert "ILIKE" in prompt
    assert "LIKE" in prompt
    assert "strftime" in prompt
    assert "NULLIF" in prompt
    assert "bridge_" in prompt
    assert "LIMIT" in prompt


def test_regra_fora_de_escopo_presente():
    """Valida que a diretriz de recusa sem acionar ferramenta SQL está explícita."""
    prompt = montar_system_prompt(schema_ddl="")

    assert "fora do escopo" in prompt
    assert "NÃO execute nenhuma ferramenta SQL" in prompt
