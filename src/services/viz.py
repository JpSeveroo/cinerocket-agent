"""Serviço de Visualização de Dados (Nó 5 do Pipeline CineData).

Analisa de forma puramente determinística (sem consumo de LLM) os dados tabulares
extraídos do banco de dados e gera gráficos interativos do Plotly (linhas temporais,
barras categóricas ou dispersão) adequados para renderização no frontend.
"""

import re
from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Padrão regex para identificar colunas de data/tempo isoladas por início, fim ou underscore
PADRAO_TEMPO = re.compile(
    r"(^|_)(ano|year|data|date|release_date|dt|month|mes|day|dia)($|_)",
    re.IGNORECASE,
)

LIMITE_BARRAS_TOP = 15


def gerar_grafico(
    colunas: list[str], linhas: list[list[Any]]
) -> go.Figure | None:
    """Gera uma figura do Plotly determinística a partir dos dados tabulares retornados.

    Args:
        colunas: Lista de nomes de colunas retornadas pela consulta SQL.
        linhas: Lista de registros (linhas com valores das colunas).

    Returns:
        Instância de plotly.graph_objects.Figure configurada, ou None caso os dados
        não preencham os critérios mínimos para visualização gráfica.
    """
    try:
        # 1. Critérios de descarte imediato
        if not colunas or len(colunas) < 2:
            return None
        if not linhas or len(linhas) < 2:
            return None

        df = pd.DataFrame(linhas, columns=colunas)
        if df.empty:
            return None

        colunas_temporais: list[str] = []
        colunas_numericas: list[str] = []
        colunas_categoricas: list[str] = []

        total_linhas = len(df)

        # 2. Identificação e coerção de tipos
        for col in colunas:
            col_str = str(col).strip()

            # Tenta coerção numérica
            num_series = pd.to_numeric(df[col], errors="coerce")
            valores_numericos_validos = num_series.notna().sum()
            eh_numerica = valores_numericos_validos >= max(2, int(total_linhas * 0.5))

            # Verifica semântica temporal delimitada
            eh_tempo = bool(PADRAO_TEMPO.search(col_str))

            if eh_tempo:
                colunas_temporais.append(col)
                if eh_numerica:
                    df[col] = num_series
                else:
                    df[col] = pd.to_datetime(df[col], errors="coerce").fillna(df[col])
            elif eh_numerica:
                colunas_numericas.append(col)
                df[col] = num_series
            else:
                colunas_categoricas.append(col)

        # Se nenhuma coluna numérica foi identificada, não é possível gerar gráfico analítico
        if not colunas_numericas:
            return None

        # 3. Seleção do Gráfico
        fig: go.Figure | None = None

        # Cenário A: Categórico + Numérico -> Gráfico de Barras (Prioritário quando há categorias)
        if colunas_categoricas:
            col_x = colunas_categoricas[0]
            col_y = colunas_numericas[0]
            df_plot = df.dropna(subset=[col_x, col_y])

            if len(df_plot) >= 2:
                labels = {
                    col_x: col_x.replace("_", " ").title(),
                    col_y: col_y.replace("_", " ").title(),
                }
                if len(df_plot) > LIMITE_BARRAS_TOP:
                    # Mais de 15 barras: seleciona os top 15 e exibe na horizontal para legibilidade
                    df_plot = df_plot.nlargest(LIMITE_BARRAS_TOP, col_y).sort_values(
                        by=col_y, ascending=True
                    )
                    fig = px.bar(
                        df_plot,
                        x=col_y,
                        y=col_x,
                        orientation="h",
                        template="plotly_dark",
                        labels=labels,
                    )
                else:
                    fig = px.bar(
                        df_plot,
                        x=col_x,
                        y=col_y,
                        template="plotly_dark",
                        labels=labels,
                    )

        # Cenário B: Temporal + Numérico -> Gráfico de Linhas (Série Temporal Pura sem Categóricas)
        elif colunas_temporais:
            col_x = colunas_temporais[0]
            col_y = colunas_numericas[0]
            df_plot = df.dropna(subset=[col_x, col_y]).sort_values(by=col_x)

            # Agrega registros com datas/anos duplicados para evitar traçados em ziguezague
            if df_plot[col_x].duplicated().any():
                df_plot = df_plot.groupby(col_x, as_index=False)[col_y].mean()

            if len(df_plot) >= 2:
                labels = {
                    col_x: col_x.replace("_", " ").title(),
                    col_y: col_y.replace("_", " ").title(),
                }
                fig = px.line(
                    df_plot,
                    x=col_x,
                    y=col_y,
                    markers=True,
                    template="plotly_dark",
                    labels=labels,
                )

        # Cenário C: Ao menos 2 Numéricos -> Gráfico de Dispersão (Correlação)
        elif len(colunas_numericas) >= 2:
            col_x = colunas_numericas[0]
            col_y = colunas_numericas[1]
            df_plot = df.dropna(subset=[col_x, col_y])

            if len(df_plot) >= 2:
                labels = {
                    col_x: col_x.replace("_", " ").title(),
                    col_y: col_y.replace("_", " ").title(),
                }
                fig = px.scatter(
                    df_plot,
                    x=col_x,
                    y=col_y,
                    template="plotly_dark",
                    labels=labels,
                )

        # 4. Estilização do Gráfico
        if fig is not None:
            fig.update_layout(
                template="plotly_dark",
                margin=dict(l=40, r=40, t=50, b=40),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                hovermode="closest",
            )

        return fig

    except Exception:
        # Resiliência total: qualquer inconsistência inesperada retorna None de forma segura
        return None
