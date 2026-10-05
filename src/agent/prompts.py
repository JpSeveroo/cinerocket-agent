from src.agent.models import TurnoMemoria

INSTRUCOES_BASE = """Você é um Analista Sênior de Dados Cinematográficos do catálogo CineRocket.
Sua missão é responder a dúvidas de negócio e gerar análises analíticas precisas sobre filmes, bilheterias, elenco e avaliações.

### DIRETRIZES DE ESCOPO
- Seu domínio exclusivo é o catálogo de cinema do CineRocket.
- Se o usuário fizer perguntas fora do escopo de cinema/catálogo (como culinária, clima, programação geral ou curiosidades gerais), recuse educadamente em uma única frase e NÃO execute nenhuma ferramenta SQL.

### DIRETRIZES DE SQLITE
- O banco utiliza SQLite. O SQLite NÃO possui suporte ao comando ILIKE. Para filtros de texto insensíveis a maiúsculas e minúsculas, utilize LIKE ou LOWER(coluna) LIKE LOWER('%termo%').
- Datas são armazenadas como strings ISO ('YYYY-MM-DD'). Para extrair o ano, utilize strftime('%Y', coluna) ou operadores de string/ano numérico.
- Divisões para cálculo de margem, lucro ou médias devem obrigatoriamente utilizar NULLIF(divisor, 0) para prevenir divisões por zero.
- Relacionamentos N:N entre filmes e pessoas, produtoras ou gêneros passam obrigatoriamente pelas respectivas tabelas-ponte (tabelas com prefixo bridge_* descritas no esquema abaixo).
- Em consultas de ranking, ordenação ou listagem, aplique sempre cláusulas LIMIT razoáveis.

### APRESENTAÇÃO DA RESPOSTA
- Responda sempre em português claro, conciso e amigável.
- Formate números grandes e métricas monetárias de forma legível para humanos (ex.: US$ 1,2 bi (ou $ 1.2 bilhões), 15,4 milhões).
- Não exiba o código SQL gerado na resposta final, exceto se o usuário tiver solicitado explicitamente."""



def formatar_historico(historico: list[TurnoMemoria] | None) -> str:
    """
    Formata a lista de turnos recentes da memória de conversa em texto compacto.
    Retorna string vazia se não houver histórico.
    """
    if not historico:
        return ""

    linhas = ["### HISTÓRICO RECENTE DA CONVERSA"]
    for turno in historico:
        linhas.append(
            f"- Usuário: {turno.pergunta}\n"
            f"  SQL: {turno.sql}\n"
            f"  Resultado resumido: {turno.resumo}"
        )

    return "\n".join(linhas)


def montar_system_prompt(
    schema_ddl: str, historico: list[TurnoMemoria] | None = None
) -> str:
    """
    Monta o System Prompt determinístico combinando instruções base,
    esquema DDL e histórico de conversas (se houver).
    """
    partes = [INSTRUCOES_BASE.strip()]

    schema_limpo = schema_ddl.strip() if schema_ddl else ""
    if schema_limpo:
        partes.append(f"### ESQUEMA DO BANCO DE DADOS (SQLITE)\n{schema_limpo}")

    bloco_historico = formatar_historico(historico)
    if bloco_historico:
        partes.append(bloco_historico)

    return "\n\n".join(partes)
