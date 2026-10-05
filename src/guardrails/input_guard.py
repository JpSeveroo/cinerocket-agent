import re
from dataclasses import dataclass
from enum import Enum


class RejectionReason(str, Enum):
    EMPTY = "EMPTY"
    TOO_SHORT = "TOO_SHORT"
    TOO_LONG = "TOO_LONG"
    INJECTION_DETECTED = "INJECTION_DETECTED"


# Padrões estruturais de injeção e comandos diretos
# Não bloqueia termos isolados para permitir títulos legítimos (ex: "Drop Zone")
PADROES_BLOQUEIO = [
    # Subversão de instruções do modelo
    r"ignore\s+(all\s+)?(previous|the)\s+instructions",
    r"esque(ça|ce)\s+(as|todas\s+as)?\s*(instruções|regras)",
    r"\b(system\s*prompt|developer\s*mode|dan\s*mode)\b",
    # Comandos SQL isolados iniciando a entrada
    r"^\s*(drop\s+table|delete\s+from|truncate\s+table|insert\s+into|update\s+\w+\s+set)\b",
    # Encadeamento malicioso com ponto e vírgula
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
    """
    Remove caracteres de controle ASCII invisíveis e normaliza espaçamentos.
    """
    texto_limpo = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", text)
    texto_limpo = re.sub(r"\s+", " ", texto_limpo)
    return texto_limpo.strip()


def validate_user_input(
    raw_prompt: str, min_chars: int = 3, max_chars: int = 500
) -> InputGuardResult:
    """
    Executa a higienização e validação preliminar (custo zero de tokens).
    Retorna o status, motivo estruturado de recusa e mensagem explicativa.
    """
    if not raw_prompt or not isinstance(raw_prompt, str):
        return InputGuardResult(
            is_valid=False,
            sanitized_prompt="",
            rejection_reason=RejectionReason.EMPTY,
            error_message="A pergunta não pode estar vazia.",
        )

    prompt_limpo = sanitize_text(raw_prompt)

    # 1. Validação de tamanho mínimo
    if len(prompt_limpo) < min_chars:
        return InputGuardResult(
            is_valid=False,
            sanitized_prompt=prompt_limpo,
            rejection_reason=RejectionReason.TOO_SHORT,
            error_message=f"Pergunta muito curta. Forneça pelo menos {min_chars} caracteres.",
        )

    # 2. Validação de tamanho máximo
    if len(prompt_limpo) > max_chars:
        return InputGuardResult(
            is_valid=False,
            sanitized_prompt=prompt_limpo,
            rejection_reason=RejectionReason.TOO_LONG,
            error_message=f"A pergunta excede o limite máximo de {max_chars} caracteres.",
        )

    # 3. Verificação de padrões maliciosos e injeções
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