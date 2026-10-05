"""Testes unitários para o módulo Text-to-SQL (src/agent/text_to_sql.py e src/guardrails/sql_guard.py).

Utiliza o TestModel nativo do PydanticAI para validação determinística sem consumir
cota do OpenRouter nem realizar requisições externas de rede.
"""

import json
from typing import Any
from unittest.mock import MagicMock

import pytest
from pydantic_ai import ModelRetry, RunContext
from pydantic_ai.models.fallback import FallbackModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.models.test import TestModel

from src.agent.models import ContextoAgente, RespostaAgente, TurnoMemoria
from src.agent.text_to_sql import (
    LIMITE_AMOSTRA_LLM,
    agente,
    executar_sql,
    injetar_system_prompt,
    obter_modelo_openrouter,
    responder_pergunta,
)
from src.config import DATABASE_PATH
from src.guardrails.sql_guard import validar_query_segura


class SqlTestModel(TestModel):
    """TestModel nativo que simula chamada de ferramenta com uma consulta SQL controlada."""

    def __init__(self, sql_to_run: str = "SELECT 1", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.sql_to_run = sql_to_run

    def gen_tool_args(self, tool_def: Any) -> Any:
        if getattr(tool_def, "name", "") == "executar_sql":
            return {"sql": self.sql_to_run}
        return super().gen_tool_args(tool_def)


def _criar_mock_run_context(contexto: ContextoAgente) -> RunContext[ContextoAgente]:
    """Cria um RunContext sintético para teste direto das ferramentas."""
    mock_ctx = MagicMock(spec=RunContext)
    mock_ctx.deps = contexto
    return mock_ctx


# ==============================================================================
# TESTES DE VALIDAÇÃO DE SEGURANÇA (SQL_GUARD)
# ==============================================================================


def test_sql_guard_permite_select_e_union() -> None:
    """Verifica que consultas SELECT válidas, com CTE e UNION são aprovadas."""
    validar_query_segura("SELECT movie_id, title FROM dim_movies LIMIT 10")
    validar_query_segura("SELECT 1 UNION ALL SELECT 2")
    validar_query_segura("WITH cte AS (SELECT 1 AS val) SELECT val FROM cte")


@pytest.mark.parametrize(
    "sql_inseguro",
    [
        "DROP TABLE dim_movies",
        "DELETE FROM dim_genres WHERE 1=1",
        "UPDATE dim_movies SET title = 'hacked'",
        "INSERT INTO dim_movies (title) VALUES ('novo')",
        "ALTER TABLE dim_movies ADD COLUMN malicioso TEXT",
        "PRAGMA table_info('dim_movies')",
        "SELECT 1; DROP TABLE dim_movies;",
        "",
        "   ",
    ],
)
def test_sql_guard_bloqueia_mutacoes_e_comandos_perigosos(sql_inseguro: str) -> None:
    """Verifica que qualquer comando de mutação ou multi-statement é rejeitado."""
    with pytest.raises(ValueError):
        validar_query_segura(sql_inseguro)


# ==============================================================================
# TESTES DA FERRAMENTA EXECUTAR_SQL
# ==============================================================================


def test_executar_sql_sucesso_popula_contexto() -> None:
    """Verifica que a ferramenta executa no SQLite real e popula os dados no contexto."""
    contexto = ContextoAgente(caminho_banco=DATABASE_PATH, limite_linhas=5)
    mock_ctx = _criar_mock_run_context(contexto)

    sql = "SELECT id_filme, titulo, ano_lancamento FROM dim_movies LIMIT 3"
    resposta_json = executar_sql(mock_ctx, sql)

    # Contexto deve estar populado
    assert contexto.tem_resultado is True
    assert contexto.ultimo_sql_executado == sql
    assert contexto.colunas_resultado == ["id_filme", "titulo", "ano_lancamento"]
    assert contexto.linhas_resultado is not None
    assert len(contexto.linhas_resultado) == 3
    assert contexto.erro_execucao is None

    # Resposta deve ser JSON com amostra
    dados = json.loads(resposta_json)
    assert dados["status"] == "sucesso"
    assert dados["total_linhas"] == 3
    assert dados["colunas"] == ["id_filme", "titulo", "ano_lancamento"]
    assert len(dados["linhas"]) == 3


def test_executar_sql_query_invalida_dispara_model_retry_e_registra_falha() -> None:
    """Verifica que erro de sintaxe SQL no SQLite dispara ModelRetry e registra a falha."""
    contexto = ContextoAgente(caminho_banco=DATABASE_PATH)
    mock_ctx = _criar_mock_run_context(contexto)

    sql_invalido = "SELECT coluna_que_nao_existe_xyz FROM dim_movies"

    with pytest.raises(ModelRetry) as exc_info:
        executar_sql(mock_ctx, sql_invalido)

    assert "Erro ao executar SQL" in str(exc_info.value)
    assert contexto.tem_resultado is False
    assert contexto.ultimo_sql_executado is None
    assert contexto.erro_execucao is not None
    assert "no such column" in contexto.erro_execucao


def test_executar_sql_comando_proibido_dispara_model_retry() -> None:
    """Verifica que tentativa de mutação (ex: DROP) dispara ModelRetry via sql_guard."""
    contexto = ContextoAgente(caminho_banco=DATABASE_PATH)
    mock_ctx = _criar_mock_run_context(contexto)

    sql_mutacao = "DROP TABLE dim_movies"

    with pytest.raises(ModelRetry) as exc_info:
        executar_sql(mock_ctx, sql_mutacao)

    assert "Consulta SQL não permitida" in str(exc_info.value)
    assert contexto.tem_resultado is False
    assert contexto.ultimo_sql_executado is None
    assert contexto.erro_execucao is not None


def test_executar_sql_retorna_amostra_truncada_para_muitas_linhas() -> None:
    """Verifica que uma consulta com mais linhas que LIMITE_AMOSTRA_LLM retorna aviso de amostra."""
    contexto = ContextoAgente(caminho_banco=DATABASE_PATH, limite_linhas=30)
    mock_ctx = _criar_mock_run_context(contexto)

    sql = "SELECT id_filme FROM dim_movies LIMIT 20"
    resposta_json = executar_sql(mock_ctx, sql)

    dados = json.loads(resposta_json)
    assert dados["total_linhas"] == 20
    assert len(dados["linhas"]) == LIMITE_AMOSTRA_LLM
    assert "aviso" in dados
    # Porém no contexto completo, todas as 20 linhas devem estar salvas
    assert contexto.linhas_resultado is not None
    assert len(contexto.linhas_resultado) == 20


# ==============================================================================
# TESTES DE INJEÇÃO DO SYSTEM PROMPT
# ==============================================================================


def test_injetar_system_prompt_contem_schema_e_diretrizes() -> None:
    """Verifica se a injeção dinâmica de system prompt traz as diretrizes e esquema."""
    contexto = ContextoAgente(
        caminho_banco=DATABASE_PATH,
        historico=[TurnoMemoria(pergunta="P1", sql="S1", resumo="R1")],
    )
    mock_ctx = _criar_mock_run_context(contexto)

    prompt = injetar_system_prompt(mock_ctx)
    assert "Analista Sênior de Dados Cinematográficos" in prompt
    assert "### ESQUEMA DO BANCO DE DADOS (SQLITE)" in prompt
    assert "dim_movies" in prompt
    assert "### HISTÓRICO RECENTE DA CONVERSA" in prompt
    assert "P1" in prompt


# ==============================================================================
# TESTES DO PONTO DE ENTRADA RESPONDER_PERGUNTA (ASSÍNCRONO COM TESTMODEL)
# ==============================================================================


@pytest.mark.anyio
async def test_responder_pergunta_com_sucesso_ponta_a_ponta() -> None:
    """Testa chamada completa de responder_pergunta com TestModel executando tool e gerando resposta."""
    contexto = ContextoAgente(caminho_banco=DATABASE_PATH)
    modelo = SqlTestModel(
        sql_to_run="SELECT count(*) AS total FROM dim_movies",
        custom_output_text="O catálogo CineRocket conta com mais de 95 mil filmes cadastrados.",
    )

    resposta = await responder_pergunta(
        pergunta="Quantos filmes temos no catálogo?",
        contexto=contexto,
        modelo=modelo,
    )

    assert isinstance(resposta, RespostaAgente)
    assert "95 mil filmes" in resposta.texto
    assert resposta.sql == "SELECT count(*) AS total FROM dim_movies"
    assert contexto.tem_resultado is True
    assert contexto.ultimo_sql_executado == "SELECT count(*) AS total FROM dim_movies"
    assert contexto.colunas_resultado == ["total"]
    assert contexto.linhas_resultado is not None
    assert contexto.linhas_resultado[0][0] > 0


@pytest.mark.anyio
async def test_responder_pergunta_sem_execucao_de_ferramenta() -> None:
    """Testa chamada quando o modelo decide responder diretamente (ex: recusa de escopo)."""
    contexto = ContextoAgente(caminho_banco=DATABASE_PATH)
    modelo = TestModel(
        call_tools=[],
        custom_output_text="Desculpe, meu domínio é restrito ao catálogo de cinema CineRocket.",
    )

    resposta = await responder_pergunta(
        pergunta="Como fazer um bolo de chocolate?",
        contexto=contexto,
        modelo=modelo,
    )

    assert isinstance(resposta, RespostaAgente)
    assert "domínio é restrito" in resposta.texto
    assert resposta.sql is None
    assert contexto.tem_resultado is False
    assert contexto.ultimo_sql_executado is None


@pytest.mark.anyio
async def test_responder_pergunta_consulta_sem_registros_retorna_template_estatico() -> None:
    """Valida que consultas que não retornam linhas adotam o template estático e registram o SQL."""
    contexto = ContextoAgente(caminho_banco=DATABASE_PATH)
    sql_sem_linhas = "SELECT id_filme FROM dim_movies WHERE ano_lancamento = 1800"
    modelo = SqlTestModel(
        sql_to_run=sql_sem_linhas,
        custom_output_text="Texto arbitrário do modelo que deve ser sobrescrito pelo template.",
    )

    resposta = await responder_pergunta(
        pergunta="Quais filmes foram lançados no ano 1800?",
        contexto=contexto,
        modelo=modelo,
    )

    assert isinstance(resposta, RespostaAgente)
    assert (
        resposta.texto
        == "Não foram encontrados registros no catálogo CineRocket para os critérios informados."
    )
    assert resposta.sql == sql_sem_linhas
    assert contexto.tem_resultado is True
    assert contexto.linhas_resultado == []


# ==============================================================================
# TESTES DE CONFIGURAÇÃO DE MODELOS OPENROUTER
# ==============================================================================


def test_obter_modelo_openrouter_cria_fallback_model() -> None:
    """Verifica que a função de obtenção de modelos monta FallbackModel com múltiplos modelos."""
    modelo = obter_modelo_openrouter(
        modelos=["qwen/qwen3.8-27b:free", "cohere/north-mini-code:free"],
        api_key="sk-teste",
    )
    assert isinstance(modelo, FallbackModel)

    # Se apenas um modelo for informado, retorna o modelo direto
    modelo_unico = obter_modelo_openrouter(
        modelos=["qwen/qwen3.8-27b:free"],
        api_key="sk-teste",
    )
    assert isinstance(modelo_unico, OpenAIChatModel)


def test_obter_modelo_openrouter_lista_vazia_lanca_erro() -> None:
    """Verifica que lista vazia de modelos lança ValueError."""
    with pytest.raises(ValueError):
        obter_modelo_openrouter(modelos=[])
