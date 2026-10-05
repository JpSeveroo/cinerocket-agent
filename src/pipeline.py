"""Orquestrador do Pipeline CineData (Nós 1 a 6).

Conecta de ponta a ponta todos os componentes do sistema:
1. Input Guard (Sanitização e Validação de Entrada)
2. Cache de Consultas (Verificação em Disco com Hit/Miss)
3. Controle de Cota Diária (Limite de 50 requisições/dia)
4. Agente Text-to-SQL (PydanticAI + Modelos Gratuitos + SQLite Read-Only)
5. Visualização de Dados (Geração Determinística de Gráficos Plotly)
6. Pós-processamento e Persistência (Memória de Sessão + Atualização do Cache)
"""

from pathlib import Path
import traceback
from typing import Any

from pydantic import BaseModel

from src.agent.models import ContextoAgente
from src.agent.text_to_sql import responder_pergunta
from src.config import DATABASE_PATH
from src.guardrails.input_guard import validate_user_input
from src.services.cache import CacheConsultas
from src.services.memory import GerenciadorMemoria
from src.services.quota import GerenciadorCota, _gerenciador_cota
from src.services.viz import gerar_grafico


class ResultadoPipeline(BaseModel):
    """Contrato de saída final estruturado para consumo pela interface (Streamlit)."""

    texto: str
    sql: str | None = None
    grafico: Any | None = None  # go.Figure do Plotly ou None
    do_cache: bool = False
    erro: bool = False


class PipelineCineData:
    """Orquestra a execução sequencial e determinística do fluxo CineData."""

    def __init__(
        self,
        cache: CacheConsultas | None = None,
        memoria: GerenciadorMemoria | None = None,
        gerenciador_cota: GerenciadorCota | None = None,
        caminho_banco: Path = DATABASE_PATH,
        modelo: Any = None,
    ) -> None:
        """Inicializa o pipeline com seus respectivos serviços e dependências.

        Args:
            cache: Serviço de persistência de cache em disco.
            memoria: Serviço de janela deslizante de memória da sessão.
            gerenciador_cota: Serviço de controle de cota diária.
            caminho_banco: Caminho para o banco de dados SQLite cinerocket.db.
            modelo: Modelo opcional do PydanticAI (usado para testes determinísticos).
        """
        self.cache = cache if cache is not None else CacheConsultas()
        self.memoria = memoria if memoria is not None else GerenciadorMemoria()
        self.gerenciador_cota = (
            gerenciador_cota if gerenciador_cota is not None else _gerenciador_cota
        )
        self.caminho_banco = caminho_banco
        self.modelo = modelo

    async def executar(self, pergunta: str) -> ResultadoPipeline:
        """Processa uma pergunta do usuário através dos 6 nós do pipeline.

        Args:
            pergunta: Pergunta enviada pelo usuário em linguagem natural.

        Returns:
            Instância de ResultadoPipeline contendo resposta, SQL, gráfico e metadados.
        """
        # ======================================================================
        # NÓ 1: Validação de Entrada e Higienização (Input Guard)
        # ======================================================================
        guard_result = validate_user_input(pergunta)
        if not guard_result.is_valid:
            mensagem_erro = (
                guard_result.error_message
                or "A pergunta informada não atende aos critérios de validação."
            )
            return ResultadoPipeline(
                texto=mensagem_erro,
                sql=None,
                grafico=None,
                do_cache=False,
                erro=True,
            )

        pergunta_limpa = guard_result.sanitized_prompt

        # ======================================================================
        # NÓ 2: Verificação de Cache em Disco
        # ======================================================================
        cache_hit = self.cache.obter(pergunta_limpa)
        if cache_hit is not None:
            texto_cache = cache_hit["texto"]
            sql_cache = cache_hit.get("sql")
            colunas_cache = cache_hit.get("colunas")
            linhas_cache = cache_hit.get("linhas")

            # Reconstrói gráfico se houver dados tabulares cacheados
            grafico_cache = None
            if colunas_cache and linhas_cache:
                grafico_cache = gerar_grafico(colunas_cache, linhas_cache)

            # Registra o turno na memória da sessão atual
            self.memoria.adicionar_turno(
                pergunta=pergunta_limpa,
                sql=sql_cache,
                texto_resposta=texto_cache,
            )

            return ResultadoPipeline(
                texto=texto_cache,
                sql=sql_cache,
                grafico=grafico_cache,
                do_cache=True,
                erro=False,
            )

        # ======================================================================
        # NÓ 3: Verificação de Cota Diária
        # ======================================================================
        if not self.gerenciador_cota.verificar_cota_disponivel():
            status_cota = self.gerenciador_cota.consultar_status()
            return ResultadoPipeline(
                texto=status_cota.mensagem_interface,
                sql=None,
                grafico=None,
                do_cache=False,
                erro=True,
            )

        # ======================================================================
        # NÓ 4: Execução do Agente Text-to-SQL (PydanticAI)
        # ======================================================================
        contexto = ContextoAgente(
            caminho_banco=self.caminho_banco,
            historico=self.memoria.obter_historico(),
        )

        try:
            resposta_agente = await responder_pergunta(
                pergunta=pergunta_limpa,
                contexto=contexto,
                modelo=self.modelo,
            )
            # Debita a quantidade real de requisições HTTP da cota diária
            qtd_requests = getattr(resposta_agente, "qtd_requests", 1)
            if hasattr(resposta_agente, "usage"):
                u = resposta_agente.usage() if callable(resposta_agente.usage) else resposta_agente.usage
                qtd_requests = getattr(u, "requests", qtd_requests) or qtd_requests
            self.gerenciador_cota.registrar_requisicao(quantidade=qtd_requests)
        except Exception as e:
            print("\n" + "=" * 60)
            print(f"[ERRO NO PIPELINE]: {type(e).__name__} - {e}")
            traceback.print_exc()
            print("=" * 60 + "\n")

            # Identificação de erro 429 / Rate Limit
            erro_str = str(e).lower()
            eh_429 = "429" in erro_str or "rate limit" in erro_str
            if not eh_429 and hasattr(e, "exceptions"):
                for sub_e in getattr(e, "exceptions", []):
                    sub_str = str(sub_e).lower()
                    if "429" in sub_str or "rate limit" in sub_str:
                        eh_429 = True
                        break

            if eh_429:
                self.gerenciador_cota.forcar_esgotamento()  # trava o contador local no limite máximo
                return ResultadoPipeline(
                    texto=(
                        "O limite diário de requisições gratuitas da API (50 chamadas HTTP) foi "
                        "esgotado no provedor OpenRouter. Aguarde a renovação diária da cota "
                        "ou atualize a chave OPENROUTER_API_KEY no arquivo .env para continuar."
                    ),
                    sql=None,
                    grafico=None,
                    do_cache=False,
                    erro=True,
                )

            return ResultadoPipeline(
                texto=(
                    "Não foi possível concluir a análise devido a uma instabilidade temporária "
                    "no serviço de inteligência. Por favor, tente novamente em alguns instantes."
                ),
                sql=contexto.ultimo_sql_executado,
                grafico=None,
                do_cache=False,
                erro=True,
            )

        # ======================================================================
        # NÓ 5: Visualização de Dados (Plotly)
        # ======================================================================
        grafico = None
        if contexto.tem_resultado and contexto.colunas_resultado and contexto.linhas_resultado:
            grafico = gerar_grafico(
                colunas=contexto.colunas_resultado,
                linhas=contexto.linhas_resultado,
            )

        # ======================================================================
        # NÓ 6: Pós-processamento e Persistência (Memória e Cache)
        # ======================================================================
        self.memoria.adicionar_turno(
            pergunta=pergunta_limpa,
            sql=resposta_agente.sql,
            texto_resposta=resposta_agente.texto,
        )

        # Salva no cache apenas se não houve erro de execução na consulta
        if contexto.erro_execucao is None:
            self.cache.salvar(
                pergunta=pergunta_limpa,
                texto=resposta_agente.texto,
                sql=resposta_agente.sql,
                colunas=contexto.colunas_resultado,
                linhas=contexto.linhas_resultado,
            )

        return ResultadoPipeline(
            texto=resposta_agente.texto,
            sql=resposta_agente.sql,
            grafico=grafico,
            do_cache=False,
            erro=False,
        )
