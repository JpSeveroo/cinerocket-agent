"""Interface Streamlit Minimalista do CineData (app.py).

Conecta visualmente o usuário ao orquestrador PipelineCineData seguindo
diretrizes estritas de design minimalista, alta tipografia e zero emojis.
"""

import asyncio
import threading
from typing import Any

import streamlit as st

from src.pipeline import PipelineCineData


class AsyncRunner:
    """Mantém um event loop persistente em thread dedicada para o Streamlit."""

    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def run(self, coro: Any) -> Any:
        fut = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return fut.result()


st.set_page_config(page_title="CineData", layout="wide")

st.markdown(
    """
    <style>
        .block-container {
            padding-top: 2rem;
            padding-bottom: 5rem;
            max-width: 900px;
        }

        h1, h2, h3, h4 {
            font-weight: 600;
            letter-spacing: -0.02em;
        }

        .stButton > button {
            border-radius: 8px;
            padding: 0.75rem 1rem;
            font-weight: 500;
            border: 1px solid rgba(128, 128, 128, 0.2);
            transition: all 0.2s ease-in-out;
        }

        .stButton > button:hover {
            border-color: rgba(128, 128, 128, 0.4);
            transform: translateY(-1px);
        }
    </style>
    """,
    unsafe_allow_html=True,
)

if "_async_runner" not in st.session_state:
    st.session_state._async_runner = AsyncRunner()

runner: AsyncRunner = st.session_state._async_runner


def executar_async(coroutine: Any) -> Any:
    return runner.run(coroutine)


if "pipeline" not in st.session_state:
    st.session_state.pipeline = PipelineCineData()

if "mensagens" not in st.session_state:
    st.session_state.mensagens = []

if "prompt_sugerido" not in st.session_state:
    st.session_state.prompt_sugerido = None

if "pergunta_pendente" not in st.session_state:
    st.session_state.pergunta_pendente = None

pipeline: PipelineCineData = st.session_state.pipeline

with st.sidebar:
    st.markdown("### CineData")
    st.caption("Text-to-SQL Analytics")
    st.divider()

    st.markdown("#### Ações")
    if st.button("Nova Conversa", width="stretch"):
        pipeline.memoria.limpar()
        st.session_state.mensagens = []
        st.session_state.prompt_sugerido = None
        st.session_state.pergunta_pendente = None
        st.rerun()

    if st.button("Limpar Cache", width="stretch"):
        pipeline.cache.limpar()
        st.toast("Cache limpo com sucesso.")

    st.divider()

    status_cota = pipeline.gerenciador_cota.consultar_status()
    st.caption(f"Cota diária: {status_cota.usadas} / {status_cota.limite} requisições")

sugestao_clicada: str | None = None

if len(st.session_state.mensagens) == 0:
    st.markdown(
        """
        <div style="text-align: center; margin-top: 3.5rem; margin-bottom: 2.5rem;">
            <h1 style="font-size: 2.2rem; font-weight: 600; letter-spacing: -0.02em; margin-bottom: 0.5rem;">CineData Analytics</h1>
            <p style="color: #888888; font-size: 1.05rem;">Consulte métricas e dados do catálogo CineRocket.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Top 10 filmes mais lucrativos", width="stretch"):
            sugestao_clicada = "Top 10 filmes mais lucrativos"
        if st.button("Atores com mais participações", width="stretch"):
            sugestao_clicada = "Atores com mais participações"
    with col2:
        if st.button("Faturamento total por ano", width="stretch"):
            sugestao_clicada = "Faturamento total por ano"
        if st.button("Média de avaliação por gênero", width="stretch"):
            sugestao_clicada = "Média de avaliação por gênero"

else:
    for idx, msg in enumerate(st.session_state.mensagens):
        if msg["role"] == "user":
            st.chat_message("user").markdown(msg["conteudo"])
        elif msg["role"] == "assistant":
            with st.chat_message("assistant"):
                if msg.get("erro"):
                    st.error(msg["conteudo"])
                else:
                    st.markdown(msg["conteudo"])

                if msg.get("grafico") is not None:
                    with st.expander("Visualizar gráfico analítico", expanded=False):
                        st.plotly_chart(
                            msg["grafico"],
                            key=f"grafico_{idx}",
                            use_container_width=True,
                        )

                if msg.get("do_cache"):
                    st.caption("Resposta recuperada do cache local (custo zero)")

                if msg.get("sql"):
                    with st.expander("Ver consulta SQL", expanded=False):
                        st.code(msg["sql"], language="sql")

esta_ocupado = st.session_state.pergunta_pendente is not None

prompt_input = st.chat_input(
    "Pergunte sobre o catálogo CineRocket...",
    disabled=esta_ocupado,
)

pergunta_recebida = (
    prompt_input
    or sugestao_clicada
    or st.session_state.prompt_sugerido
)
st.session_state.prompt_sugerido = None

if pergunta_recebida and not esta_ocupado:
    st.session_state.pergunta_pendente = pergunta_recebida
    st.session_state.mensagens.append(
        {
            "role": "user",
            "conteudo": pergunta_recebida,
            "sql": None,
            "grafico": None,
            "do_cache": False,
            "erro": False,
        }
    )
    st.rerun()

if st.session_state.pergunta_pendente:
    pergunta_atual = st.session_state.pergunta_pendente
    try:
        with st.chat_message("assistant"):
            with st.spinner("Analisando dados e gerando consulta..."):
                resultado = executar_async(pipeline.executar(pergunta_atual))

        st.session_state.mensagens.append(
            {
                "role": "assistant",
                "conteudo": resultado.texto,
                "sql": resultado.sql,
                "grafico": resultado.grafico,
                "do_cache": resultado.do_cache,
                "erro": resultado.erro,
            }
        )
    except Exception as e:
        st.session_state.mensagens.append(
            {
                "role": "assistant",
                "conteudo": f"Ocorreu um erro inesperado: {e}",
                "sql": None,
                "grafico": None,
                "do_cache": False,
                "erro": True,
            }
        )
    finally:
        st.session_state.pergunta_pendente = None
        st.rerun()
