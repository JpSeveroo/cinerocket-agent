"""Módulo do agente Text-to-SQL baseado em PydanticAI."""

import json
import sqlite3
from typing import Any

from pydantic_ai import Agent, ModelRetry, RunContext
from pydantic_ai.exceptions import UsageLimitExceeded
from pydantic_ai.models.fallback import FallbackModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openrouter import OpenRouterProvider
from pydantic_ai.usage import UsageLimits

from src.agent.models import ContextoAgente, RespostaAgente
from src.agent.prompts import montar_system_prompt
from src.config import (
    MAX_REQUESTS_POR_PERGUNTA,
    MAX_RETRIES_SQL,
    MODELOS_OPENROUTER,
    OPENROUTER_API_KEY,
)
from src.database.connection import get_readonly_connection
from src.database.schema import get_database_schema
from src.guardrails.sql_guard import validar_query_segura

LIMITE_AMOSTRA_LLM = 15


def obter_modelo_openrouter(
    modelos: list[str] | None = None,
    api_key: str | None = None,
) -> FallbackModel | OpenAIChatModel:
    """Configura provedor e modelos OpenRouter com suporte a fallback.

    Args:
        modelos: Lista de identificadores de modelos.
        api_key: Chave da API OpenRouter.

    Returns:
        Instância de modelo OpenAI ou FallbackModel para o PydanticAI.
    """
    lista = modelos if modelos is not None else MODELOS_OPENROUTER
    if not lista:
        raise ValueError("Nenhum modelo OpenRouter configurado.")

    chave = api_key or OPENROUTER_API_KEY or "sk-dummy"
    provedor = OpenRouterProvider(api_key=chave)
    modelos_chat = [OpenAIChatModel(m, provider=provedor) for m in lista]

    if len(modelos_chat) == 1:
        return modelos_chat[0]

    return FallbackModel(modelos_chat[0], *modelos_chat[1:])


agente: Agent[ContextoAgente, str] = Agent(
    model=obter_modelo_openrouter(),
    deps_type=ContextoAgente,
    output_type=str,
    retries=MAX_RETRIES_SQL,
    model_settings={"temperature": 0.0},
)


@agente.system_prompt
def injetar_system_prompt(ctx: RunContext[ContextoAgente]) -> str:
    """Injeta dinamicamente o System Prompt com instruções, schema e histórico recente."""
    schema_ddl = get_database_schema(ctx.deps.caminho_banco)
    return montar_system_prompt(schema_ddl, ctx.deps.historico)


@agente.tool(retries=MAX_RETRIES_SQL)
def executar_sql(ctx: RunContext[ContextoAgente], sql: str) -> str:
    """Executa uma consulta SQL somente leitura (SELECT) no banco de dados SQLite do CineRocket.

    Args:
        ctx: Contexto da execução com dependências do agente e armazenamento de resultados.
        sql: Comando SQL SELECT a ser executado no SQLite.

    Returns:
        String em formato JSON com colunas, total de linhas e amostra dos registros.
    """
    try:
        validar_query_segura(sql)
    except ValueError as erro_guard:
        msg = str(erro_guard)
        ctx.deps.registrar_falha(msg)
        raise ModelRetry(
            f"Consulta SQL não permitida: {msg}. Gere exclusivamente consultas SELECT válidas."
        ) from erro_guard

    conn = get_readonly_connection(ctx.deps.caminho_banco)
    try:
        cursor = conn.cursor()
        cursor.execute(sql)
        colunas = [desc[0] for desc in cursor.description] if cursor.description else []
        linhas_raw = cursor.fetchmany(ctx.deps.limite_linhas)

        linhas: list[list[Any]] = []
        for r in linhas_raw:
            linhas.append([
                v.decode("utf-8", errors="replace") if isinstance(v, (bytes, bytearray)) else v
                for v in r
            ])

        ctx.deps.registrar_sucesso(sql=sql, colunas=colunas, linhas=linhas)

    except sqlite3.Error as erro_sql:
        msg_sql = str(erro_sql)
        ctx.deps.registrar_falha(msg_sql)
        raise ModelRetry(
            f"Erro ao executar SQL no SQLite: {msg_sql}. "
            "Corrija a consulta garantindo conformidade com o esquema e dialeto SQLite."
        ) from erro_sql
    finally:
        conn.close()

    total_linhas = len(linhas)
    amostra = linhas[:LIMITE_AMOSTRA_LLM]

    amostra_info: dict[str, Any] = {
        "status": "sucesso",
        "total_linhas": total_linhas,
        "colunas": colunas,
        "linhas": amostra,
    }
    if total_linhas > LIMITE_AMOSTRA_LLM:
        amostra_info["aviso"] = (
            f"Amostra exibindo as primeiras {LIMITE_AMOSTRA_LLM} linhas de {total_linhas} encontradas. "
            "Os dados completos foram salvos no contexto para gráficos."
        )
    elif total_linhas == 0:
        amostra_info["mensagem"] = "Consulta executada com sucesso, mas nenhuma linha foi retornada."

    return json.dumps(amostra_info, ensure_ascii=False)


async def responder_pergunta(
    pergunta: str,
    contexto: ContextoAgente,
    modelo: Any = None,
) -> RespostaAgente:
    """Executa o agente para responder perguntas em linguagem natural.

    Args:
        pergunta: Pergunta do usuário em linguagem natural.
        contexto: ContextoAgente configurado para o turno de conversa.
        modelo: Modelo alternativo opcional para execução.

    Returns:
        Instância de RespostaAgente com texto e consulta SQL executada.
    """
    limites = UsageLimits(request_limit=MAX_REQUESTS_POR_PERGUNTA)

    try:
        if modelo is not None:
            resultado = await agente.run(
                pergunta,
                deps=contexto,
                usage_limits=limites,
                model=modelo,
            )
        else:
            resultado = await agente.run(
                pergunta,
                deps=contexto,
                usage_limits=limites,
            )
    except UsageLimitExceeded:
        return RespostaAgente(
            texto=(
                "A complexidade desta análise ultrapassou o limite máximo de etapas "
                "permitidas por consulta (8 passos). Para obter os dados, tente fazer "
                "uma pergunta mais direta ou especificar filtros mais pontuais."
            ),
            sql=contexto.ultimo_sql_executado,
            qtd_requests=MAX_REQUESTS_POR_PERGUNTA,
        )

    if contexto.tem_resultado and len(contexto.linhas_resultado or []) == 0:
        texto = "Não foram encontrados registros no catálogo CineRocket para os critérios informados."
        sql = contexto.ultimo_sql_executado
    else:
        texto = resultado.output
        sql = contexto.ultimo_sql_executado

    qtd_requests = 1
    if hasattr(resultado, "usage"):
        u = resultado.usage() if callable(resultado.usage) else resultado.usage
        qtd_requests = getattr(u, "requests", 1) or 1

    return RespostaAgente(texto=texto, sql=sql, qtd_requests=qtd_requests)
