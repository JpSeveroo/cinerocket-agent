"""Serviço de controle de cota diária de requisições."""

import json
import os
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from src.config import CACHE_DIR, LIMITE_COTA_DIARIA

LIMITE_DIARIO_PADRAO: int = LIMITE_COTA_DIARIA
NOME_ARQUIVO_COTA: str = "cota.json"

_trava_cota = threading.Lock()


@dataclass
class StatusCota:
    disponivel: bool
    usadas: int
    limite: int
    restantes: int
    data_utc: str
    mensagem_interface: str


def _obter_data_utc_atual() -> str:
    """Retorna a data atual no fuso UTC no formato AAAA-MM-DD."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")  # noqa: UP017


class GerenciadorCota:
    """Controla o limite diário de requisições HTTP e persistência do contador."""

    def __init__(self, diretorio_cache: Path = CACHE_DIR, limite_diario: int = LIMITE_DIARIO_PADRAO):
        self.diretorio_cache = Path(diretorio_cache)
        self.caminho_arquivo = self.diretorio_cache / NOME_ARQUIVO_COTA
        self.limite_diario = limite_diario

    def _carregar_estado(self) -> tuple[str, int]:
        """Lê os dados do arquivo de cota ou reinicializa se virar o dia UTC."""
        hoje_utc = _obter_data_utc_atual()

        if not self.caminho_arquivo.exists():
            return hoje_utc, 0

        try:
            with open(self.caminho_arquivo, "r", encoding="utf-8") as f:
                dados = json.load(f)
                data_registrada = dados.get("data_utc", hoje_utc)
                usadas = int(dados.get("requisicoes_usadas", 0))

                if data_registrada != hoje_utc:
                    return hoje_utc, 0

                return data_registrada, max(0, usadas)
        except (json.JSONDecodeError, ValueError, OSError):
            return hoje_utc, 0

    def _salvar_estado_atomico(self, data_utc: str, usadas: int) -> None:
        """Cria o diretório se não existir e persiste de forma atômica."""
        self.diretorio_cache.mkdir(parents=True, exist_ok=True)
        caminho_tmp = self.caminho_arquivo.with_suffix(".tmp")

        conteudo = {
            "data_utc": data_utc,
            "requisicoes_usadas": usadas,
        }

        with open(caminho_tmp, "w", encoding="utf-8") as f:
            json.dump(conteudo, f, ensure_ascii=False, indent=2)

        os.replace(caminho_tmp, self.caminho_arquivo)

    def _montar_status(self, data_utc: str, usadas: int) -> StatusCota:
        """Monta o objeto StatusCota formatado com mensagens em português."""
        restantes = max(0, self.limite_diario - usadas)
        disponivel = usadas < self.limite_diario

        if disponivel:
            mensagem = (
                f"Cota diária: {usadas}/{self.limite_diario}. "
                f"Reinicia hoje às 21:00 (Horário de Brasília)."
            )
        else:
            mensagem = (
                f"Limite diário de {self.limite_diario} consultas gratuitas atingido. "
                f"A cota reinicia hoje às 21:00 (Horário de Brasília)."
            )

        return StatusCota(
            disponivel=disponivel,
            usadas=usadas,
            limite=self.limite_diario,
            restantes=restantes,
            data_utc=data_utc,
            mensagem_interface=mensagem,
        )

    def consultar_status(self) -> StatusCota:
        """Inspeciona o saldo diário sem debitar requisições."""
        with _trava_cota:
            data_utc, usadas = self._carregar_estado()

        return self._montar_status(data_utc, usadas)

    def verificar_cota_disponivel(self) -> bool:
        """Retorna True se ainda houver cota para o dia atual."""
        return self.consultar_status().disponivel

    def registrar_requisicao(self, quantidade: int = 1) -> StatusCota:
        """Registra a quantidade real de requisições HTTP efetuadas no turno."""
        qtd = max(1, int(quantidade))
        with _trava_cota:
            data_utc, usadas = self._carregar_estado()
            novas_usadas = usadas + qtd
            self._salvar_estado_atomico(data_utc, novas_usadas)
            return self._montar_status(data_utc, novas_usadas)

    def incrementar(self) -> StatusCota:
        """Incrementa em 1 o contador de requisições usadas."""
        return self.registrar_requisicao(1)

    def forcar_esgotamento(self) -> StatusCota:
        """Trava o contador de cota diária no limite máximo após detecção de HTTP 429."""
        with _trava_cota:
            data_utc, _ = self._carregar_estado()
            self._salvar_estado_atomico(data_utc, self.limite_diario)
            return self._montar_status(data_utc, self.limite_diario)

    def resetar(self) -> None:
        """Zera o contador manualmente para testes."""
        with _trava_cota:
            hoje_utc = _obter_data_utc_atual()
            self._salvar_estado_atomico(hoje_utc, 0)


_gerenciador_cota = GerenciadorCota()


def verificar_cota_disponivel() -> bool:
    """Interface direta para checagem rápida de disponibilidade de cota."""
    return _gerenciador_cota.verificar_cota_disponivel()


def consultar_status_cota() -> StatusCota:
    """Interface para exibir status na barra lateral do frontend."""
    return _gerenciador_cota.consultar_status()


def incrementar_cota() -> StatusCota:
    """Interface para debitar uma requisição."""
    return _gerenciador_cota.incrementar()


def registrar_requisicao_cota(quantidade: int = 1) -> StatusCota:
    """Interface para registrar quantidade específica de requisições."""
    return _gerenciador_cota.registrar_requisicao(quantidade)


def forcar_esgotamento_cota() -> StatusCota:
    """Interface para forçar esgotamento imediato da cota após erro 429."""
    return _gerenciador_cota.forcar_esgotamento()