"""Serviço de Cache de Consultas e Respostas em Disco.

Armazena resultados normalizados em arquivo JSON com persistência atômica.
"""

import hashlib
import json
from pathlib import Path
from typing import Any

from src.config import CACHE_DIR

ARQUIVO_CACHE_PADRAO = CACHE_DIR / "cache_perguntas.json"


def normalizar_pergunta(pergunta: str) -> str:
    """Normaliza uma pergunta para geração de chave de cache determinística.

    Args:
        pergunta: Pergunta original enviada pelo usuário.

    Returns:
        String normalizada em minúsculas e sem pontuações periféricas.
    """
    if not pergunta:
        return ""

    texto = " ".join(pergunta.split()).strip().lower()
    return texto.strip("?!.,;:-\"'`~ ")


def gerar_chave_cache(pergunta: str) -> str:
    """Gera um hash SHA-256 a partir da pergunta normalizada.

    Args:
        pergunta: Pergunta em linguagem natural.

    Returns:
        Hexadecimal de 64 caracteres do hash SHA-256.
    """
    normalizada = normalizar_pergunta(pergunta)
    return hashlib.sha256(normalizada.encode("utf-8")).hexdigest()


class CacheConsultas:
    """Mecanismo de persistência de consultas e respostas em arquivo JSON."""

    def __init__(self, caminho_arquivo: Path | str | None = None) -> None:
        """Inicializa o cache apontando para o arquivo de persistência.

        Args:
            caminho_arquivo: Caminho personalizado para o arquivo JSON de cache.
        """
        self.caminho_arquivo = (
            Path(caminho_arquivo) if caminho_arquivo is not None else ARQUIVO_CACHE_PADRAO
        )
        self.caminho_arquivo.parent.mkdir(parents=True, exist_ok=True)

    def _carregar_dados(self) -> dict[str, Any]:
        """Carrega os registros persistidos do disco."""
        if not self.caminho_arquivo.exists():
            return {}

        try:
            conteudo = self.caminho_arquivo.read_text(encoding="utf-8")
            if not conteudo.strip():
                return {}
            dados = json.loads(conteudo)
            return dados if isinstance(dados, dict) else {}
        except (json.JSONDecodeError, OSError):
            return {}

    def _salvar_dados(self, dados: dict[str, Any]) -> None:
        """Grava os dados em disco atomicamente através de arquivo temporário."""
        self.caminho_arquivo.parent.mkdir(parents=True, exist_ok=True)
        temp_file = self.caminho_arquivo.with_suffix(".tmp")
        conteudo = json.dumps(dados, ensure_ascii=False, indent=2)
        temp_file.write_text(conteudo, encoding="utf-8")
        temp_file.replace(self.caminho_arquivo)

    def obter(self, pergunta: str) -> dict[str, Any] | None:
        """Busca uma consulta no cache pela pergunta normalizada.

        Args:
            pergunta: Pergunta em linguagem natural.

        Returns:
            Dicionário com texto, sql, colunas e linhas se houver hit, ou None se miss.
        """
        chave = gerar_chave_cache(pergunta)
        dados = self._carregar_dados()
        registro = dados.get(chave)

        if registro and isinstance(registro, dict):
            return {
                "texto": registro.get("texto", ""),
                "sql": registro.get("sql"),
                "colunas": registro.get("colunas"),
                "linhas": registro.get("linhas"),
            }

        return None

    def salvar(
        self,
        pergunta: str,
        texto: str,
        sql: str | None,
        colunas: list[str] | None = None,
        linhas: list[list[Any]] | None = None,
    ) -> None:
        """Armazena o resultado de uma consulta no cache em disco.

        Args:
            pergunta: Pergunta em linguagem natural.
            texto: Texto de resposta final retornado pelo agente.
            sql: Consulta SQL executada (se houver).
            colunas: Lista com o nome das colunas do resultado.
            linhas: Registros tabulares retornados pela consulta.
        """
        chave = gerar_chave_cache(pergunta)
        dados = self._carregar_dados()

        dados[chave] = {
            "pergunta_normalizada": normalizar_pergunta(pergunta),
            "texto": texto,
            "sql": sql,
            "colunas": colunas,
            "linhas": linhas,
        }

        self._salvar_dados(dados)

    def limpar(self) -> None:
        """Esvazia todo o cache e remove o arquivo de persistência em disco."""
        if self.caminho_arquivo.exists():
            try:
                self.caminho_arquivo.unlink()
            except OSError:
                self._salvar_dados({})
