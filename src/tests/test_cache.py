"""Testes unitários para o serviço de cache em disco (src/services/cache.py).

Garante que a normalização de texto e geração de hash sejam determinísticas,
que o mecanismo de hit/miss funcione conforme esperado e que a persistência em disco
resista à reinicialização de instâncias e manipulação de arquivos.
"""

from pathlib import Path

import pytest

from src.services.cache import CacheConsultas, gerar_chave_cache, normalizar_pergunta


def test_normalizacao_e_chave() -> None:
    """Valida que variações de maiúsculas/minúsculas, espaços e pontuações geram a mesma chave."""
    p1 = "Qual o filme mais caro?"
    p2 = "qual  o filme mais caro"
    p3 = "  QUAL O FILME MAIS CARO?!  "
    p4 = "qual o filme mais caro."

    norm1 = normalizar_pergunta(p1)
    norm2 = normalizar_pergunta(p2)
    norm3 = normalizar_pergunta(p3)
    norm4 = normalizar_pergunta(p4)

    assert norm1 == "qual o filme mais caro"
    assert norm1 == norm2 == norm3 == norm4

    k1 = gerar_chave_cache(p1)
    k2 = gerar_chave_cache(p2)
    k3 = gerar_chave_cache(p3)
    k4 = gerar_chave_cache(p4)

    assert len(k1) == 64
    assert k1 == k2 == k3 == k4


def test_cache_hit_e_miss(tmp_path: Path) -> None:
    """Valida que uma pergunta inédita dá miss (None) e, após salva, dá hit com os dados."""
    arquivo_cache = tmp_path / "cache_teste.json"
    cache = CacheConsultas(caminho_arquivo=arquivo_cache)

    pergunta = "Qual o filme com maior bilheteria?"

    # Miss inicial
    assert cache.obter(pergunta) is None

    # Salva resultado
    texto = "O filme com maior bilheteria é Avatar."
    sql = "SELECT title FROM dim_movies ORDER BY revenue DESC LIMIT 1"
    colunas = ["title"]
    linhas = [["Avatar"]]

    cache.salvar(
        pergunta=pergunta,
        texto=texto,
        sql=sql,
        colunas=colunas,
        linhas=linhas,
    )

    # Hit com pergunta idêntica e com variação de pontuação/espaços
    resultado = cache.obter(pergunta)
    assert resultado is not None
    assert resultado["texto"] == texto
    assert resultado["sql"] == sql
    assert resultado["colunas"] == colunas
    assert resultado["linhas"] == linhas

    resultado_variacao = cache.obter("  qual   o filme com maior bilheteria?!  ")
    assert resultado_variacao is not None
    assert resultado_variacao["texto"] == texto


def test_persistencia_disco(tmp_path: Path) -> None:
    """Valida que uma nova instância de CacheConsultas consegue ler dados salvos por outra."""
    arquivo_cache = tmp_path / "cache_persistente.json"

    # Instância 1 salva o registro
    cache1 = CacheConsultas(caminho_arquivo=arquivo_cache)
    cache1.salvar(
        pergunta="Quantos filmes existem?",
        texto="Existem 95 mil filmes.",
        sql="SELECT count(*) FROM dim_movies",
        colunas=["total"],
        linhas=[[95645]],
    )

    assert arquivo_cache.exists()

    # Instância 2 lê do mesmo arquivo em disco
    cache2 = CacheConsultas(caminho_arquivo=arquivo_cache)
    resultado = cache2.obter("quantos filmes existem")

    assert resultado is not None
    assert resultado["texto"] == "Existem 95 mil filmes."
    assert resultado["sql"] == "SELECT count(*) FROM dim_movies"
    assert resultado["colunas"] == ["total"]
    assert resultado["linhas"] == [[95645]]


def test_limpar_cache(tmp_path: Path) -> None:
    """Valida que limpar() remove todas as entradas e o arquivo em disco."""
    arquivo_cache = tmp_path / "cache_limpeza.json"
    cache = CacheConsultas(caminho_arquivo=arquivo_cache)

    cache.salvar("P1", "T1", "S1")
    assert cache.obter("P1") is not None
    assert arquivo_cache.exists()

    cache.limpar()

    assert cache.obter("P1") is None
    assert not arquivo_cache.exists()


def test_recuperacao_graciosa_arquivo_corrompido(tmp_path: Path) -> None:
    """Valida que se o arquivo de cache contiver JSON corrompido, o sistema não quebra."""
    arquivo_cache = tmp_path / "cache_corrompido.json"
    arquivo_cache.write_text("{conteudo_invalido_de_json:::", encoding="utf-8")

    cache = CacheConsultas(caminho_arquivo=arquivo_cache)

    # Deve retornar None e permitir sobrescrita sem levantar exceção
    assert cache.obter("qualquer pergunta") is None

    cache.salvar("Pergunta Nova", "Texto Novo", "SQL Novo")
    assert cache.obter("Pergunta Nova") is not None
