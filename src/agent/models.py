"""Modelos de dados e contratos do agente Text-to-SQL."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from src.config import DATABASE_PATH, MAX_LINHAS_RESULTADO


class RespostaAgente(BaseModel):
    """Contrato de saída final estruturado para o pipeline."""

    texto: str
    sql: str | None = None
    qtd_requests: int = 1


@dataclass
class TurnoMemoria:
    """Registro de um turno na janela deslizante de histórico de conversa."""

    pergunta: str
    sql: str | None = None
    resumo: str = ""


@dataclass
class ContextoAgente:
    """Contexto de execução e dependências para processamento de uma pergunta."""

    caminho_banco: Path = DATABASE_PATH
    historico: list[TurnoMemoria] = field(default_factory=list)
    limite_linhas: int = MAX_LINHAS_RESULTADO

    ultimo_sql_executado: str | None = None
    colunas_resultado: list[str] | None = None
    linhas_resultado: list[list[Any]] | None = None
    erro_execucao: str | None = None

    @property
    def tem_resultado(self) -> bool:
        """Indica se a última consulta foi executada com sucesso."""
        return self.ultimo_sql_executado is not None and self.erro_execucao is None

    def registrar_sucesso(
        self, sql: str, colunas: list[str], linhas: list[Any]
    ) -> None:
        """Registra os resultados da consulta SQL executada com sucesso.

        Args:
            sql: Consulta SQL executada.
            colunas: Nomes das colunas retornadas.
            linhas: Registros retornados pela consulta.
        """
        self.ultimo_sql_executado = sql
        self.colunas_resultado = list(colunas)
        self.linhas_resultado = [list(linha) for linha in linhas]
        self.erro_execucao = None

    def registrar_falha(self, erro: str) -> None:
        """Registra falha de execução e limpa resultados anteriores.

        Args:
            erro: Mensagem descritiva da falha.
        """
        self.ultimo_sql_executado = None
        self.colunas_resultado = None
        self.linhas_resultado = None
        self.erro_execucao = erro