"""Serviço de gerenciamento de memória da sessão (Janela deslizante de turnos).

Mantém em memória os últimos N turnos da conversa para contexto do agente.
"""

from src.agent.models import TurnoMemoria

MAX_TURNOS_PADRAO = 3
MAX_CHARS_RESUMO = 150


def gerar_resumo_curto(texto: str, max_chars: int = MAX_CHARS_RESUMO) -> str:
    """Extrai um resumo determinístico e compacto do texto de resposta.

    Args:
        texto: Texto completo da resposta a ser resumida.
        max_chars: Limite máximo de caracteres antes do truncamento.

    Returns:
        String contendo o resumo conciso.
    """
    if not texto or not texto.strip():
        return ""

    texto_limpo = " ".join(texto.split()).strip()
    if len(texto_limpo) <= max_chars:
        return texto_limpo

    for pontuacao in (". ", "! ", "? "):
        pos = texto_limpo.find(pontuacao)
        if 20 <= pos <= max_chars:
            return texto_limpo[: pos + 1].strip()

    trecho = texto_limpo[:max_chars]
    if " " in trecho:
        trecho = trecho.rsplit(" ", 1)[0]

    return f"{trecho.rstrip()}..."


class GerenciadorMemoria:
    """Gerencia a janela deslizante de memória da sessão do usuário."""

    def __init__(self, max_turnos: int = MAX_TURNOS_PADRAO) -> None:
        """Inicializa o gerenciador com a capacidade máxima de turnos.

        Args:
            max_turnos: Quantidade de turnos recentes preservados na memória.
        """
        self.max_turnos = max_turnos
        self.turnos: list[TurnoMemoria] = []

    def adicionar_turno(
        self, pergunta: str, sql: str | None, texto_resposta: str
    ) -> None:
        """Adiciona um novo turno de conversa e aplica a janela deslizante.

        Args:
            pergunta: Pergunta enviada pelo usuário.
            sql: Consulta SQL executada (ou None se não houve consulta).
            texto_resposta: Resposta final retornada ao usuário.
        """
        resumo = gerar_resumo_curto(texto_resposta)
        turno = TurnoMemoria(
            pergunta=pergunta.strip(),
            sql=sql,
            resumo=resumo,
        )
        self.turnos.append(turno)

        if len(self.turnos) > self.max_turnos:
            self.turnos = self.turnos[-self.max_turnos :]

    def obter_historico(self) -> list[TurnoMemoria]:
        """Retorna uma cópia da lista de turnos atualmente armazenados.

        Returns:
            Lista de objetos TurnoMemoria para injeção no ContextoAgente.
        """
        return list(self.turnos)

    def limpar(self) -> None:
        """Esvazia todo o histórico de turnos da memória da sessão."""
        self.turnos.clear()
