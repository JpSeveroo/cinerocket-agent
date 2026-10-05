"""Testes de integração ponta a ponta para o Pipeline CineData (src/pipeline.py).

Garante a perfeita orquestração dos 6 nós:
Nó 1: Input Guard
Nó 2: Cache de Consultas
Nó 3: Gerenciamento de Cota
Nó 4: Agente Text-to-SQL (via TestModel determinístico)
Nó 5: Visualização de Dados (Plotly)
Nó 6: Pós-processamento e Persistência
"""

from pathlib import Path
from typing import Any

import plotly.graph_objects as go
import pytest
from pydantic_ai.models.test import TestModel

from src.config import DATABASE_PATH
from src.pipeline import PipelineCineData, ResultadoPipeline
from src.services.cache import CacheConsultas
from src.services.memory import GerenciadorMemoria
from src.services.quota import GerenciadorCota


class SqlTestModel(TestModel):
    """TestModel que simula chamada de ferramenta com consulta SQL controlada."""

    def __init__(self, sql_to_run: str = "SELECT 1", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.sql_to_run = sql_to_run

    def gen_tool_args(self, tool_def: Any) -> Any:
        if getattr(tool_def, "name", "") == "executar_sql":
            return {"sql": self.sql_to_run}
        return super().gen_tool_args(tool_def)


@pytest.fixture
def ambiente_pipeline(tmp_path: Path) -> PipelineCineData:
    """Fixture que isola cache e controle de cota em diretório temporário."""
    cache = CacheConsultas(caminho_arquivo=tmp_path / "cache_teste.json")
    memoria = GerenciadorMemoria(max_turnos=3)
    gerenciador_cota = GerenciadorCota(diretorio_cache=tmp_path, limite_diario=10)

    return PipelineCineData(
        cache=cache,
        memoria=memoria,
        gerenciador_cota=gerenciador_cota,
        caminho_banco=DATABASE_PATH,
    )


# ==============================================================================
# TESTES DE FLUXO E INTEGRAÇÃO DO PIPELINE
# ==============================================================================


@pytest.mark.anyio
async def test_pipeline_rejeita_entrada_invalida_no_no_1(
    ambiente_pipeline: PipelineCineData,
) -> None:
    """Verifica que entradas maliciosas ou vazias são barradas no Nó 1 com erro=True."""
    # 1. Entrada vazia
    res_vazia = await ambiente_pipeline.executar("")
    assert res_vazia.erro is True
    assert res_vazia.do_cache is False
    assert res_vazia.sql is None
    assert res_vazia.grafico is None
    assert "vazia" in res_vazia.texto

    # 2. Comando malicioso de injeção
    res_injecao = await ambiente_pipeline.executar("drop table dim_movies")
    assert res_injecao.erro is True
    assert res_injecao.do_cache is False
    assert res_injecao.sql is None
    assert "não permitidos" in res_injecao.texto

    # A cota não deve ter sido consumida
    assert ambiente_pipeline.gerenciador_cota.consultar_status().usadas == 0


@pytest.mark.anyio
async def test_pipeline_executa_com_sucesso_ponta_a_ponta(
    ambiente_pipeline: PipelineCineData,
) -> None:
    """Valida o fluxo completo de 1 a 6 gerando texto, SQL, gráfico e persistindo cache/memória."""
    sql_filmes = "SELECT id_filme, titulo, ano_lancamento FROM dim_movies LIMIT 4"
    ambiente_pipeline.modelo = SqlTestModel(
        sql_to_run=sql_filmes,
        custom_output_text="Aqui estão 4 filmes do catálogo.",
    )

    pergunta = "Quais são os primeiros 4 filmes cadastrados?"
    resultado = await ambiente_pipeline.executar(pergunta)

    # Verificação da estrutura do resultado
    assert isinstance(resultado, ResultadoPipeline)
    assert resultado.erro is False
    assert resultado.do_cache is False
    assert resultado.texto == "Aqui estão 4 filmes do catálogo."
    assert resultado.sql == sql_filmes

    # Nó 5: Deve ter gerado gráfico de barras
    assert isinstance(resultado.grafico, go.Figure)

    # Nó 3: Deve ter consumido as requisições reais da cota (2 requests: tool call + síntese)
    assert ambiente_pipeline.gerenciador_cota.consultar_status().usadas == 2

    # Nó 6: Memória e cache devem estar povoados
    historico = ambiente_pipeline.memoria.obter_historico()
    assert len(historico) == 1
    assert historico[0].sql == sql_filmes

    cache_item = ambiente_pipeline.cache.obter(pergunta)
    assert cache_item is not None
    assert cache_item["sql"] == sql_filmes


@pytest.mark.anyio
async def test_pipeline_cache_hit_evita_consumo_de_cota_e_agente(
    ambiente_pipeline: PipelineCineData,
) -> None:
    """Valida que uma pergunta idêntica dá cache hit (Nó 2), com do_cache=True e cota intocada."""
    sql = "SELECT id_filme, titulo FROM dim_movies LIMIT 3"
    ambiente_pipeline.modelo = SqlTestModel(
        sql_to_run=sql,
        custom_output_text="Primeira resposta gerada.",
    )

    pergunta = "Mostre 3 filmes"

    # Primeira execução: miss no cache, consulta executada
    res1 = await ambiente_pipeline.executar(pergunta)
    assert res1.do_cache is False
    assert ambiente_pipeline.gerenciador_cota.consultar_status().usadas == 2

    # Segunda execução (com variações de caixa e espaços): hit no cache!
    pergunta_variacao = "  mostre 3 filmes?!  "
    res2 = await ambiente_pipeline.executar(pergunta_variacao)

    assert res2.do_cache is True
    assert res2.erro is False
    assert res2.texto == res1.texto
    assert res2.sql == sql
    # A cota permanece em 2 (não consumiu tokens nem requisição de cota)
    assert ambiente_pipeline.gerenciador_cota.consultar_status().usadas == 2

    # Memória da sessão deve registrar os dois turnos
    assert len(ambiente_pipeline.memoria.obter_historico()) == 2


@pytest.mark.anyio
async def test_pipeline_bloqueio_quando_cota_esgotada(
    ambiente_pipeline: PipelineCineData,
) -> None:
    """Verifica que quando o saldo diário atinge zero, o Nó 3 bloqueia a execução."""
    # Simula cota esgotada (0 restantes)
    ambiente_pipeline.gerenciador_cota.limite_diario = 0

    pergunta = "Qual o melhor filme de ficção científica?"
    resultado = await ambiente_pipeline.executar(pergunta)

    assert resultado.erro is True
    assert resultado.do_cache is False
    assert resultado.sql is None
    assert resultado.grafico is None
    assert "atingido" in resultado.texto


@pytest.mark.anyio
async def test_pipeline_recusa_de_escopo_sem_sql_e_sem_grafico(
    ambiente_pipeline: PipelineCineData,
) -> None:
    """Valida que recusas educadas de domínio fora de cinema fluem sem SQL nem gráfico."""
    ambiente_pipeline.modelo = TestModel(
        call_tools=[],
        custom_output_text="Desculpe, meu escopo é restrito a dados do catálogo CineRocket.",
    )

    pergunta = "Qual a previsão do tempo para amanhã?"
    resultado = await ambiente_pipeline.executar(pergunta)

    assert resultado.erro is False
    assert resultado.do_cache is False
    assert resultado.sql is None
    assert resultado.grafico is None
    assert "escopo é restrito" in resultado.texto

    # Bateu no modelo, logo gastou cota
    assert ambiente_pipeline.gerenciador_cota.consultar_status().usadas == 1


@pytest.mark.anyio
async def test_pipeline_consulta_sem_registros_retorna_template_estatico(
    ambiente_pipeline: PipelineCineData,
) -> None:
    """Valida que consultas que não trazem dados adotam o template estático sem gráfico."""
    sql_vazio = "SELECT id_filme FROM dim_movies WHERE ano_lancamento = 1800"
    ambiente_pipeline.modelo = SqlTestModel(
        sql_to_run=sql_vazio,
        custom_output_text="Texto arbitrário do modelo que deve ser ignorado.",
    )

    pergunta = "Filmes do ano 1800"
    resultado = await ambiente_pipeline.executar(pergunta)

    assert resultado.erro is False
    assert resultado.do_cache is False
    assert (
        resultado.texto
        == "Não foram encontrados registros no catálogo CineRocket para os critérios informados."
    )
    assert resultado.sql == sql_vazio
    assert resultado.grafico is None


@pytest.mark.anyio
async def test_pipeline_erro_generico_no_no_4_retorna_mensagem_amigavel(
    ambiente_pipeline: PipelineCineData,
) -> None:
    """Garante que falhas genéricas do agente retornem mensagem amigável sem expor stacktraces."""
    from unittest.mock import patch

    with patch("src.pipeline.responder_pergunta", side_effect=RuntimeError("Connection timeout 500")):
        resultado = await ambiente_pipeline.executar("Qualquer pergunta válida")

    assert resultado.erro is True
    assert "Não foi possível concluir a análise devido a uma instabilidade temporária" in resultado.texto
    assert "Connection timeout" not in resultado.texto


@pytest.mark.anyio
async def test_pipeline_erro_429_forca_esgotamento_de_cota(
    ambiente_pipeline: PipelineCineData,
) -> None:
    """Garante que erro HTTP 429 force o esgotamento da cota e retorne mensagem específica."""
    from unittest.mock import patch

    with patch("src.pipeline.responder_pergunta", side_effect=RuntimeError("HTTP 429: Rate limit exceeded")):
        resultado = await ambiente_pipeline.executar("Top 10 filmes mais lucrativos")

    assert resultado.erro is True
    assert "esgotado no provedor OpenRouter" in resultado.texto
    status = ambiente_pipeline.gerenciador_cota.consultar_status()
    assert status.usadas == ambiente_pipeline.gerenciador_cota.limite_diario
    assert status.disponivel is False


@pytest.mark.anyio
async def test_pipeline_registra_quantidade_real_de_requests(
    ambiente_pipeline: PipelineCineData,
) -> None:
    """Valida que múltiplas requisições HTTP retornadas pelo agente são debitadas da cota."""
    from unittest.mock import patch
    from src.agent.models import RespostaAgente

    resposta_mock = RespostaAgente(
        texto="Resposta com 3 requests internos",
        sql="SELECT 1",
        qtd_requests=3,
    )

    with patch("src.pipeline.responder_pergunta", return_value=resposta_mock):
        resultado = await ambiente_pipeline.executar("Pergunta qualquer")

    assert resultado.erro is False
    assert ambiente_pipeline.gerenciador_cota.consultar_status().usadas == 3
