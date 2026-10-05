import re
from dataclasses import dataclass
from enum import Enum


class RejectionReason(str, Enum):
    EMPTY = "EMPTY"
    TOO_SHORT = "TOO_SHORT"
    TOO_LONG = "TOO_LONG"
    INJECTION_DETECTED = "INJECTION_DETECTED"


PADROES_BLOQUEIO = [
    r"ignore\s+(all\s+)?(previous\s+|the\s+)?(instructions|rules)",
    r"ignore\s+(todas\s+as|as)?\s*(regras|instruções|instrucoes)",
    r"esque(ça|ce)\s+(as|todas\s+as)?\s*(instruções|instrucoes|regras)",
    r"\b(system\s*prompt|developer\s*mode|dan\s*mode)\b",
    r"voc[eê]\s+agora\s+[eé]\s+(o|um)?\s*terminal",
    r"terminal\s+bash",
    r"^\s*(drop\s+table|delete\s+from|truncate\s+table|insert\s+into|update\s+\w+\s+set)\b",
    r";\s*(drop\s+table|delete\s+from|truncate\s+table|insert\s+into|alter\s+table)\b",
]

REGEX_BLOQUEIOS = [
    re.compile(p, re.IGNORECASE) for p in PADROES_BLOQUEIO
]


@dataclass
class InputGuardResult:
    is_valid: bool
    sanitized_prompt: str
    rejection_reason: RejectionReason | None = None
    error_message: str | None = None


def sanitize_text(text: str) -> str:
    """Remove caracteres de controle ASCII e normaliza espaçamentos redundantes.

    Args:
        text: Texto bruto de entrada.

    Returns:
        String sanitizada sem caracteres de controle.
    """
    texto_limpo = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", text)
    texto_limpo = re.sub(r"\s+", " ", texto_limpo)
    return texto_limpo.strip()


def validate_user_input(
    raw_prompt: str, min_chars: int = 3, max_chars: int = 500
) -> InputGuardResult:
    """Valida comprimento e padrões de segurança na entrada do usuário.

    Args:
        raw_prompt: Entrada fornecida pelo usuário.
        min_chars: Comprimento mínimo aceitável.
        max_chars: Comprimento máximo aceitável.

    Returns:
        Instância de InputGuardResult com validação e eventuais motivos de recusa.
    """
    if not raw_prompt or not isinstance(raw_prompt, str):
        return InputGuardResult(
            is_valid=False,
            sanitized_prompt="",
            rejection_reason=RejectionReason.EMPTY,
            error_message="A pergunta não pode estar vazia.",
        )

    prompt_limpo = sanitize_text(raw_prompt)

    if len(prompt_limpo) < min_chars:
        return InputGuardResult(
            is_valid=False,
            sanitized_prompt=prompt_limpo,
            rejection_reason=RejectionReason.TOO_SHORT,
            error_message=f"Pergunta muito curta. Forneça pelo menos {min_chars} caracteres.",
        )

    if len(prompt_limpo) > max_chars:
        return InputGuardResult(
            is_valid=False,
            sanitized_prompt=prompt_limpo,
            rejection_reason=RejectionReason.TOO_LONG,
            error_message=f"A pergunta excede o limite máximo de {max_chars} caracteres.",
        )

    for regex in REGEX_BLOQUEIOS:
        if regex.search(prompt_limpo):
            return InputGuardResult(
                is_valid=False,
                sanitized_prompt=prompt_limpo,
                rejection_reason=RejectionReason.INJECTION_DETECTED,
                error_message="A mensagem contém padrões ou comandos não permitidos.",
            )

    return InputGuardResult(
        is_valid=True,
        sanitized_prompt=prompt_limpo,
        rejection_reason=None,
        error_message=None,
    )