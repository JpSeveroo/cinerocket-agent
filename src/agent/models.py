"""Modelos e contratos do agente: memória, contexto de execução e saída.

O contexto (ContextoAgente) é a dependência injetada no PydanticAI. A ferramenta
`executar_sql` guarda nele o resultado COMPLETO da consulta, para que o pipeline use
esses dados no gráfico e no cache sem que eles passem pelo modelo.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from src.config import DATABASE_PATH, MAX_LINHAS_RESULTADO


class RespostaAgente(BaseModel):
    """Contrato de saída final estruturado para o pipeline."""

    texto: str
    sql: str | None = None


@dataclass
class TurnoMemoria:
    """Um turno da janela deslizante de memória (o histórico guarda os últimos N)."""

    pergunta: str
    sql: str | None = None
    resumo: str = ""


@dataclass
class ContextoAgente:
    """Dependências do PydanticAI para UMA pergunta.

    Crie um objeto novo a cada pergunta. O histórico vem da memória da sessão
    (services/memory.py), mas os campos de captura começam sempre vazios. Reusar o
    objeto faria o resultado da pergunta anterior vazar para o cache e para o gráfico.
    """

    caminho_banco: Path = DATABASE_PATH
    historico: list[TurnoMemoria] = field(default_factory=list)
    limite_linhas: int = MAX_LINHAS_RESULTADO

    # Captura da ferramenta executar_sql. Sempre reflete a ÚLTIMA chamada:
    # sucesso preenche os três primeiros campos; falha limpa tudo e preenche o erro.
    ultimo_sql_executado: str | None = None
    colunas_resultado: list[str] | None = None
    linhas_resultado: list[list[Any]] | None = None
    erro_execucao: str | None = None

    @property
    def tem_resultado(self) -> bool:
        """True se a última consulta rodou com sucesso (mesmo com zero linhas)."""
        return self.ultimo_sql_executado is not None and self.erro_execucao is None

    def registrar_sucesso(
        self, sql: str, colunas: list[str], linhas: list[Any]
    ) -> None:
        """Guarda o resultado completo da consulta. As linhas viram listas (iguais ao
        que o JSON do cache devolve), para o gráfico ter um único formato de entrada."""
        self.ultimo_sql_executado = sql
        self.colunas_resultado = list(colunas)
        self.linhas_resultado = [list(linha) for linha in linhas]
        self.erro_execucao = None

    def registrar_falha(self, erro: str) -> None:
        """Registra o erro e descarta qualquer resultado anterior."""
        self.ultimo_sql_executado = None
        self.colunas_resultado = None
        self.linhas_resultado = None
        self.erro_execucao = erro