"""Guardrail de segurança para consultas SQL.

Garante que apenas consultas SELECT ou UNION puras e seguras sejam executadas
no SQLite, prevenindo comandos de mutação, administrativos ou múltiplos statements.
"""

import sqlglot
from sqlglot import exp

NOS_PROIBIDOS = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Drop,
    exp.Alter,
    exp.Create,
    exp.Pragma,
    exp.Command,
)


def validar_query_segura(sql: str) -> None:
    """Valida se a consulta SQL é estritamente segura para execução somente leitura.

    Args:
        sql: String com a consulta SQL a ser inspecionada.

    Raises:
        ValueError: Se a consulta for vazia, contiver erros de sintaxe, múltiplas
            instruções ou comandos de mutação/administração.
    """
    if not sql or not sql.strip():
        raise ValueError("A consulta SQL não pode ser vazia.")

    try:
        parsed = sqlglot.parse(sql, read="sqlite")
    except Exception as e:
        raise ValueError(f"Erro de sintaxe SQL ao analisar a consulta: {e}") from e

    expressoes = [e for e in parsed if e is not None]
    if not expressoes:
        raise ValueError("Nenhuma instrução SQL válida foi identificada.")

    if len(expressoes) > 1:
        raise ValueError(
            "Múltiplas instruções SQL não são permitidas. Envie apenas uma consulta SELECT."
        )

    instrucao = expressoes[0]
    if not isinstance(instrucao, (exp.Select, exp.Union)):
        tipo_cmd = type(instrucao).__name__
        raise ValueError(
            f"Comando SQL não permitido ({tipo_cmd}). Apenas consultas SELECT são permitidas."
        )

    if instrucao.find(NOS_PROIBIDOS):
        raise ValueError(
            "Comando de modificação ou instrução administrativa identificada na consulta."
        )

    if instrucao.find(exp.Into):
        raise ValueError("Cláusula INTO não é permitida em consultas somente leitura.")
