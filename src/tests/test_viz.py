"""Testes unitários para o serviço de visualização determinístico (src/services/viz.py).

Garante que o gerador de gráficos identifique corretamente os tipos de dados e
produza figuras interativas do Plotly apropriadas (barras, linhas ou dispersão),
além de descartar de forma segura resultados escalares, vazios ou sem atributos numéricos.
"""

import plotly.graph_objects as go
import pytest

from src.services.viz import gerar_grafico


def test_resultado_vazio_retorna_none() -> None:
    """Verifica que matriz de dados vazia descarta a criação de gráfico e retorna None."""
    assert gerar_grafico([], []) is None
    assert gerar_grafico(["filme", "bilheteria"], []) is None


def test_resultado_escalar_retorna_none() -> None:
    """Verifica que resultado com apenas uma linha (ex: COUNT(*)) retorna None."""
    assert gerar_grafico(["total_filmes"], [[95645]]) is None
    # Mesmo com 2 colunas, se tiver apenas 1 registro não é representativo graficamente
    assert gerar_grafico(["categoria", "total"], [["Geral", 100]]) is None


def test_gerar_grafico_barras() -> None:
    """Verifica que dados categóricos acompanhados de métrica numérica geram gráfico de barras."""
    colunas = ["titulo", "bilheteria"]
    linhas = [
        ["Avatar", 2923706026],
        ["Vingadores: Ultimato", 2799439100],
        ["Titanic", 2264743305],
    ]

    fig = gerar_grafico(colunas, linhas)

    assert isinstance(fig, go.Figure)
    assert len(fig.data) > 0
    assert fig.data[0].type == "bar"


def test_gerar_grafico_linhas_temporal() -> None:
    """Verifica que dados temporais acompanhados de métrica numérica geram gráfico de linhas."""
    colunas = ["ano_lancamento", "faturamento_total"]
    linhas = [
        [2020, 15000000],
        [2021, 23000000],
        [2022, 31000000],
        [2023, 28000000],
    ]

    fig = gerar_grafico(colunas, linhas)

    assert isinstance(fig, go.Figure)
    assert len(fig.data) > 0
    assert fig.data[0].type == "scatter"
    assert fig.data[0].mode == "lines+markers"


def test_sem_colunas_numericas_retorna_none() -> None:
    """Verifica que consultas que retornam apenas texto (sem métricas) retornam None."""
    colunas = ["titulo", "diretor", "genero"]
    linhas = [
        ["Inception", "Christopher Nolan", "Ficção Científica"],
        ["Pulp Fiction", "Quentin Tarantino", "Crime"],
    ]

    assert gerar_grafico(colunas, linhas) is None


def test_gerar_grafico_dispersao_com_duas_colunas_numericas() -> None:
    """Verifica que dados com duas variáveis numéricas geram gráfico de dispersão (scatter)."""
    colunas = ["orcamento", "receita"]
    linhas = [
        [100000000, 300000000],
        [150000000, 450000000],
        [200000000, 800000000],
    ]

    fig = gerar_grafico(colunas, linhas)

    assert isinstance(fig, go.Figure)
    assert len(fig.data) > 0
    assert fig.data[0].type == "scatter"
    assert fig.data[0].mode != "lines+markers"


def test_grafico_barras_mais_de_15_itens_limita_top_15_horizontal() -> None:
    """Verifica que consultas com mais de 15 barras limitam aos top 15 na horizontal."""
    colunas = ["genero", "qtd_filmes"]
    linhas = [[f"Gênero {i}", i * 10] for i in range(1, 25)]

    fig = gerar_grafico(colunas, linhas)

    assert isinstance(fig, go.Figure)
    assert len(fig.data) > 0
    assert fig.data[0].type == "bar"
    assert fig.data[0].orientation == "h"
    # Deve conter no máximo 15 registros
    assert len(fig.data[0].x) == 15


def test_resiliencia_dados_anomalos_retorna_none_sem_quebrar() -> None:
    """Verifica que dados corrompidos ou inconsistentes retornam None graciosamente."""
    assert gerar_grafico(["col1", "col2"], [None, None]) is None  # type: ignore[arg-type]
    assert gerar_grafico(None, None) is None  # type: ignore[arg-type]


def test_prioridade_categorica_sobre_temporal_gera_barras() -> None:
    """Verifica que quando há colunas categóricas e temporais juntas, prioriza gráfico de barras."""
    colunas = ["title", "release_year", "revenue"]
    linhas = [
        ["Avatar", 2009, 2923706026],
        ["Vingadores: Ultimato", 2019, 2799439100],
        ["Titanic", 1997, 2264743305],
    ]

    fig = gerar_grafico(colunas, linhas)

    assert isinstance(fig, go.Figure)
    assert len(fig.data) > 0
    assert fig.data[0].type == "bar"
    # O eixo X ou Y deve corresponder ao título dos filmes
    assert list(fig.data[0].x) == ["Avatar", "Vingadores: Ultimato", "Titanic"]


def test_grafico_linhas_agrega_datas_repetidas() -> None:
    """Verifica que datas/anos repetidos são agregados para evitar ziguezague no gráfico de linhas."""
    colunas = ["ano", "faturamento"]
    linhas = [
        [2020, 100],
        [2020, 200],
        [2021, 300],
        [2021, 400],
    ]

    fig = gerar_grafico(colunas, linhas)

    assert isinstance(fig, go.Figure)
    assert len(fig.data) > 0
    assert fig.data[0].type == "scatter"
    assert fig.data[0].mode == "lines+markers"
    # Após agregação (mean), deve haver exatamente 2 pontos (2020 e 2021)
    assert len(fig.data[0].x) == 2
    assert list(fig.data[0].x) == [2020, 2021]
    assert list(fig.data[0].y) == [150.0, 350.0]

