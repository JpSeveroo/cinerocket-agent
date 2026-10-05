"""Testes unitários para a interface Streamlit (app.py).

Valida conformidade estrita com as diretrizes:
- Ausência total de emojis
- Funcionamento do helper de execução assíncrona
- Presença de todos os fluxos e textos da especificação
"""

import asyncio
import re
from pathlib import Path

import pytest

from app import executar_async


def test_executar_async_sucesso():
    """Valida que executar_async executa corrotinas e retorna o resultado."""
    async def corrotina_exemplo():
        await asyncio.sleep(0.01)
        return "sucesso_async"

    resultado = executar_async(corrotina_exemplo())
    assert resultado == "sucesso_async"


def test_ausencia_total_de_emojis_em_app_py():
    """Garante a diretriz estrita de design: nenhum caractere emoji no arquivo app.py."""
    caminho_app = Path("app.py")
    assert caminho_app.exists(), "O arquivo app.py deve existir na raiz do projeto."

    conteudo = caminho_app.read_text(encoding="utf-8")

    # Regex para detecção de emojis Unicode comuns e símbolos de apresentação gráfica
    regex_emojis = re.compile(
        "[\U00010000-\U0010ffff"
        "\u2600-\u26ff"
        "\u2700-\u27bf"
        "\u2300-\u23ff"
        "\u2b50-\u2b55"
        "\u200d"
        "\ufe0f]"
    )

    emojis_encontrados = regex_emojis.findall(conteudo)
    assert not emojis_encontrados, f"Emojis proibidos encontrados em app.py: {emojis_encontrados}"


def test_elementos_obrigatorios_presentes_em_app_py():
    """Verifica a presença dos textos e elementos estipulados na especificação do CineData."""
    conteudo = Path("app.py").read_text(encoding="utf-8")

    textos_obrigatorios = [
        'page_title="CineData"',
        'layout="wide"',
        "CineData",
        "Text-to-SQL Analytics",
        "Nova Conversa",
        "Limpar Cache",
        "Cache limpo com sucesso.",
        "Cota diária:",
        "CineData Analytics",
        "Consulte métricas e dados do catálogo CineRocket.",
        "Top 10 filmes mais lucrativos",
        "Faturamento total por ano",
        "Atores com mais participações",
        "Média de avaliação por gênero",
        "Resposta recuperada do cache local (custo zero)",
        "Ver consulta SQL",
        "Pergunte sobre o catálogo CineRocket...",
        "Analisando dados e gerando consulta...",
        "PipelineCineData",
    ]

    for texto in textos_obrigatorios:
        assert texto in conteudo, f"Texto obrigatório '{texto}' ausente em app.py."
