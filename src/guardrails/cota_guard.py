"""Módulo de proteção e controle de cota (Nó 3 do Pipeline CineData).

Reexporta GerenciadorCota e utilitários de src/services/quota.py.
"""

from src.services.quota import (
    GerenciadorCota,
    StatusCota,
    _gerenciador_cota,
    consultar_status_cota,
    forcar_esgotamento_cota,
    incrementar_cota,
    registrar_requisicao_cota,
    verificar_cota_disponivel,
)

__all__ = [
    "GerenciadorCota",
    "StatusCota",
    "_gerenciador_cota",
    "consultar_status_cota",
    "forcar_esgotamento_cota",
    "incrementar_cota",
    "registrar_requisicao_cota",
    "verificar_cota_disponivel",
]
