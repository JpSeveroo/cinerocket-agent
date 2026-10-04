from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
from pydantic import BaseModel, Field

try:
    from src.config import DATABASE_PATH
except ImportError:
    DATABASE_PATH = Path("cinerocket.db")


@dataclass
class TurnoMemoria:
    """Tríade estruturada para a janela deslizante de memória (N=3)."""
    pergunta: str
    sql: str
    resumo: str


@dataclass
class ContextoAgente:
    """
    Dependências injetadas no PydanticAI via RunContext.
    Alimenta o system prompt e captura o resultado da execução da tool.
    """
    caminho_banco: Path = DATABASE_PATH
    historico: list[TurnoMemoria] = field(default_factory=list)
    limite_linhas: int = 100

    # Estado capturado durante a chamada de ferramenta (executar_sql)
    ultimo_sql_executado: Optional[str] = None
    colunas_resultado: Optional[list[str]] = None
    linhas_resultado: Optional[list[list[Any]]] = None
    erro_execucao: Optional[str] = None


class RespostaSintetizada(BaseModel):
    """Contrato de saída estruturada para o Nó 4.4."""
    texto_resposta: str = Field(
        description="Resposta em linguagem natural, clara e formatada em Markdown."
    )
    pergunta_autonoma: bool = Field(
        description="True se a pergunta faz sentido sozinha sem depender do histórico; False se for follow-up."
    )
    sugestao_grafico: Optional[str] = Field(
        default=None,
        description="Tipo de gráfico recomendado se houver dados tabulares: 'barras', 'linhas', 'pizza' ou None."
    )