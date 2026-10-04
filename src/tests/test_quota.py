import json
import pytest
from pathlib import Path
from unittest.mock import patch
from src.services.quota import GerenciadorCota, NOME_ARQUIVO_COTA


@pytest.fixture
def gerenciador_temporario(tmp_path):
    """Cria uma instância isolada do GerenciadorCota apontando para diretório temporário."""
    return GerenciadorCota(diretorio_cache=tmp_path, limite_diario=3)


def test_inicio_com_pasta_e_arquivo_inexistentes(gerenciador_temporario):
    status = gerenciador_temporario.consultar_status()
    assert status.disponivel is True
    assert status.usadas == 0
    assert status.restantes == 3
    assert "Reinicia hoje às 21:00" in status.mensagem_interface


def test_incremento_de_cota_cria_diretorio_e_arquivo(gerenciador_temporario, tmp_path):
    # Incrementa 1 vez
    status = gerenciador_temporario.incrementar()
    assert status.usadas == 1
    assert status.restantes == 2
    assert status.disponivel is True

    # Verifica gravação no JSON dentro da pasta
    caminho_arquivo = tmp_path / NOME_ARQUIVO_COTA
    assert caminho_arquivo.exists()

    with open(caminho_arquivo, "r", encoding="utf-8") as f:
        dados = json.load(f)
        assert dados["requisicoes_usadas"] == 1


def test_bloqueio_quando_atinge_o_limite(gerenciador_temporario):
    # Consome as 3 requisições
    gerenciador_temporario.incrementar()
    gerenciador_temporario.incrementar()
    status_final = gerenciador_temporario.incrementar()

    assert status_final.usadas == 3
    assert status_final.restantes == 0
    assert status_final.disponivel is False
    assert gerenciador_temporario.verificar_cota_disponivel() is False
    assert "Limite diário de 3 consultas gratuitas atingido" in status_final.mensagem_interface


def test_reset_automatico_virada_de_dia_utc(gerenciador_temporario, tmp_path):
    # Simula consumo de requisições no dia anterior
    caminho_arquivo = tmp_path / NOME_ARQUIVO_COTA
    with open(caminho_arquivo, "w", encoding="utf-8") as f:
        json.dump({"data_utc": "2026-10-03", "requisicoes_usadas": 3}, f)

    # Ao checar no dia atual (2026-10-04), reseta automaticamente
    with patch("src.services.quota._obter_data_utc_atual", return_value="2026-10-04"):
        status = gerenciador_temporario.consultar_status()
        assert status.disponivel is True
        assert status.usadas == 0
        assert status.restantes == 3


def test_recuperacao_graciosa_arquivo_corrompido(gerenciador_temporario, tmp_path):
    # Escreve JSON quebrado no disco
    caminho_arquivo = tmp_path / NOME_ARQUIVO_COTA
    with open(caminho_arquivo, "w", encoding="utf-8") as f:
        f.write("{ json_invalido: 123, ")

    # Não quebra o sistema; reinicia zerado
    status = gerenciador_temporario.consultar_status()
    assert status.disponivel is True
    assert status.usadas == 0