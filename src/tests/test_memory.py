"""Testes unitários para o gerenciador de memória de sessão (src/services/memory.py).

Garante a retenção correta dos turnos de conversa, o comportamento da janela deslizante,
a síntese determinística de resumos curtos e a capacidade de reinicialização da memória.
"""

import pytest

from src.agent.models import TurnoMemoria
from src.services.memory import GerenciadorMemoria, gerar_resumo_curto


def test_adicionar_turno_armazena_corretamente() -> None:
    """Valida que pergunta, SQL e resumo são armazenados corretamente na memória."""
    memoria = GerenciadorMemoria(max_turnos=3)

    pergunta = "Qual a maior bilheteria de todos os tempos?"
    sql = "SELECT title, revenue FROM dim_movies ORDER BY revenue DESC LIMIT 1"
    resposta = "O filme com maior bilheteria de todos os tempos é Avatar, com US$ 2,9 bilhões arrecadados mundialmente."

    memoria.adicionar_turno(pergunta=pergunta, sql=sql, texto_resposta=resposta)

    historico = memoria.obter_historico()
    assert len(historico) == 1

    turno = historico[0]
    assert isinstance(turno, TurnoMemoria)
    assert turno.pergunta == pergunta
    assert turno.sql == sql
    assert "Avatar" in turno.resumo
    assert len(turno.resumo) <= 155


def test_janela_deslizante_descarta_turnos_antigos() -> None:
    """Valida que a memória mantém estritamente os últimos N turnos configurados."""
    memoria = GerenciadorMemoria(max_turnos=2)

    memoria.adicionar_turno("Pergunta 1", "SQL 1", "Resposta 1")
    memoria.adicionar_turno("Pergunta 2", "SQL 2", "Resposta 2")
    assert len(memoria.obter_historico()) == 2

    # Terceiro turno deve descartar o Turno 1
    memoria.adicionar_turno("Pergunta 3", "SQL 3", "Resposta 3")
    historico = memoria.obter_historico()

    assert len(historico) == 2
    assert historico[0].pergunta == "Pergunta 2"
    assert historico[1].pergunta == "Pergunta 3"


def test_resumo_curto_truncamento() -> None:
    """Garante que textos longos são truncados respeitando limites e adicionando reticências."""
    texto_longo = (
        "Este é um texto analítico extremamente detalhado sobre todas as bilheterias "
        "mundiais registradas no catálogo de cinema internacional ao longo de mais de "
        "um século de produções cinematográficas consagradas por crítica e público."
    )

    resumo = gerar_resumo_curto(texto_longo, max_chars=80)

    assert len(resumo) <= 85
    assert resumo.endswith("...")
    assert "Este é um texto" in resumo


def test_resumo_curto_preserva_texto_pequeno_e_vazio() -> None:
    """Valida que textos pequenos não recebem reticências e textos vazios retornam string vazia."""
    assert gerar_resumo_curto("") == ""
    assert gerar_resumo_curto("   ") == ""

    texto_curto = "Avatar faturou US$ 2,9 bi."
    resumo = gerar_resumo_curto(texto_curto, max_chars=100)
    assert resumo == texto_curto
    assert not resumo.endswith("...")


def test_limpar_memoria() -> None:
    """Valida que o método limpar() reseta totalmente o histórico de turnos."""
    memoria = GerenciadorMemoria(max_turnos=3)
    memoria.adicionar_turno("Pergunta 1", "SQL 1", "Resposta 1")
    memoria.adicionar_turno("Pergunta 2", "SQL 2", "Resposta 2")

    assert len(memoria.obter_historico()) == 2

    memoria.limpar()

    assert len(memoria.obter_historico()) == 0


def test_obter_historico_retorna_copia_defensiva() -> None:
    """Garante que mutações na lista obtida não afetam o estado interno da memória."""
    memoria = GerenciadorMemoria(max_turnos=3)
    memoria.adicionar_turno("P1", "S1", "R1")

    historico = memoria.obter_historico()
    historico.clear()

    assert len(memoria.obter_historico()) == 1


def test_adicionar_turno_com_sql_none() -> None:
    """Valida que turnos originados de recusas (sem SQL) são suportados."""
    memoria = GerenciadorMemoria(max_turnos=3)
    memoria.adicionar_turno(
        pergunta="Receita de bolo",
        sql=None,
        texto_resposta="Desculpe, meu escopo é restrito a cinema.",
    )

    historico = memoria.obter_historico()
    assert len(historico) == 1
    assert historico[0].sql is None
    assert "escopo é restrito" in historico[0].resumo
